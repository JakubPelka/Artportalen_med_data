# -*- coding: utf-8 -*-
"""Exportprofiler för kolumnurval i resultatfilerna.

Profilerna påverkar endast vilka kolumner som skrivs till *_with_data.xlsx
och *_bara_skyddade.xlsx. Själva berikningen och API-anropen påverkas inte.

Kolumnordningen i profilerna är fast. Kolumner som saknas i ett visst
indata-/resultatflöde hoppas över automatiskt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import pandas as pd


@dataclass(frozen=True)
class ExportPreset:
    preset_id: str
    label: str
    description: str
    include_all_columns: bool = False
    include_original_columns: bool = False
    original_column_candidates: tuple[str, ...] = ()
    enrichment_columns: tuple[str, ...] = ()


CORE_INPUT_COLUMNS = (
    "TaxonId",
    "taxonId",
    "taxon_id",
    "taxon_svensktNamn",
    "taxon_vetenskapligtNamn",
    "taxon_auktor",
    "taxon_kategori",
    "taxon_rödlistad",
    "taxon_rodlistad",
    "Startdatum",
    "Slutdatum",
    "startdatum",
    "slutdatum",
    "observationsdatum",
    "Lokalnamn",
    "lokalnamn",
    "Kommun",
    "kommun",
    "Län",
    "lan",
    "Landskap",
    "landskap",
    "X",
    "Y",
    "SWEREF99_TM_X",
    "SWEREF99_TM_Y",
    "DecimalLatitude",
    "DecimalLongitude",
)

IDENTIFICATION_COLUMNS = (
    "TaxonId",
    "ScientificName",
    "SwedishName",
    "DisplayName",
    "Category",
)

REDLIST_COLUMNS = (
    "RedListCategory",
    "RedListCriterion",
    "RedListPeriodName",
    "RedListCriterionText",
)

PROTECTION_SUMMARY_COLUMNS = (
    "ConservationStatus",
    "Fridlyst",
    "Frid_text",
    "CITES",
    "Bernkonventionen",
    "Bonnkonventionen",
    "FågeldirektivetBilaga1",
    "PrioriteradeFågelarterSkogsvårdslagen",
    "ProtectedByWorkProtectionConstitution",
    "ProtectedBirds",
    "DirectiveAppendix2",
    "DirectiveAppendix2Priority",
    "DirectiveAppendix4",
    "DirectiveAppendix5",
    "Artikel 17 - 2019",
    "TypicalSpecies",
    "ForestrySignal",
    "ForestrySignalSpecies",
    "ActionProgramName",
    "ActionProgramStatus",
    "ActionProgramStart",
    "ActionProgramEnd",
    "IAS_Union_EU",
)

NATURE_TEXT_COLUMNS = (
    "LandscapeType",
    "Biotopes",
    "Characteristic",
    "SpreadAndStatus",
    "Ecology",
    "Threat",
    "ConservationMeasures",
    "Other",
    "SwedishPresence",
    "ImmigrationHistory",
    "SubstrateInformation",
    "EcologicalGroups",
    "ConservationEcology",
    "ConservationNatureConservation",
    "ConservationTreeSpecies",
)

ALIEN_SPECIES_COLUMNS = (
    "AlienSpeciesRiskCategories",
    "AlienSpeciesEnvironments",
    "AlienSpeciesEcologyEffect",
    "AlienSpeciesTaxonLists",
    "AlienSpeciesInvationPotentials",
    "AlienSpeciesRegions",
    "IAS_Union_EU",
)

EXPORT_PRESETS = {
    "standard": ExportPreset(
        preset_id="standard",
        label="Standard — originalkolumner + viktigaste naturvårdsfält",
        description=(
            "Behåller originalkolumnerna från Artportalen och lägger till de viktigaste "
            "kolumnerna för rödlistning, skydd, direktiv, åtgärdsprogram och korta naturvårdsfält."
        ),
        include_original_columns=True,
        enrichment_columns=(
            *IDENTIFICATION_COLUMNS,
            *REDLIST_COLUMNS,
            *PROTECTION_SUMMARY_COLUMNS,
            "LandscapeType",
            "Biotopes",
            "Threat",
            "ConservationMeasures",
        ),
    ),
    "kort_skyddade": ExportPreset(
        preset_id="kort_skyddade",
        label="Kort — skyddade/prioriterade arter",
        description=(
            "Kort lista med artidentitet, rödlistning och centrala skydds-/prioriteringsfält. "
            "Bra som snabb översikt."
        ),
        include_original_columns=False,
        original_column_candidates=CORE_INPUT_COLUMNS,
        enrichment_columns=(
            *IDENTIFICATION_COLUMNS,
            *REDLIST_COLUMNS,
            *PROTECTION_SUMMARY_COLUMNS,
        ),
    ),
    "naturvard": ExportPreset(
        preset_id="naturvard",
        label="Naturvård — bredare bedömningsunderlag",
        description=(
            "Originalkolumner plus rödlistning, skydd, habitat/biotoper och centrala texter "
            "som kan vara relevanta vid naturvårdsbedömning."
        ),
        include_original_columns=True,
        enrichment_columns=(
            *IDENTIFICATION_COLUMNS,
            *REDLIST_COLUMNS,
            *PROTECTION_SUMMARY_COLUMNS,
            *NATURE_TEXT_COLUMNS,
        ),
    ),
    "ias": ExportPreset(
        preset_id="ias",
        label="IAS / främmande arter",
        description=(
            "Fokuserar på främmande arter, IAS_Union_EU och relaterade risk-/miljöfält. "
            "Observera att IAS inte ensamt styr filtret bara_skyddade."
        ),
        include_original_columns=True,
        enrichment_columns=(
            *IDENTIFICATION_COLUMNS,
            *REDLIST_COLUMNS,
            *ALIEN_SPECIES_COLUMNS,
        ),
    ),
    "all": ExportPreset(
        preset_id="all",
        label="Alla kolumner — nuvarande/maximal export",
        description="Skriver ut alla kolumner som finns i resultatet. Detta motsvarar bredast möjliga export.",
        include_all_columns=True,
    ),
}

DEFAULT_PRESET_ID = "all"


def get_default_preset_id() -> str:
    return DEFAULT_PRESET_ID


def get_preset(preset_id: str | None) -> ExportPreset:
    if not preset_id:
        return EXPORT_PRESETS[DEFAULT_PRESET_ID]
    return EXPORT_PRESETS.get(preset_id, EXPORT_PRESETS[DEFAULT_PRESET_ID])


def list_presets() -> list[ExportPreset]:
    return list(EXPORT_PRESETS.values())


def _append_unique(target: list[str], columns: Iterable[str], existing: set[str]) -> None:
    for col in columns:
        if col in existing and col not in target:
            target.append(col)


def apply_export_preset(df: pd.DataFrame, preset_id: str | None) -> pd.DataFrame:
    """Returnerar en kopia av df med kolumner enligt vald exportprofil."""
    preset = get_preset(preset_id)

    if preset.include_all_columns:
        return df.copy()

    existing = set(df.columns)
    selected: List[str] = []

    if preset.include_original_columns:
        # Originalkolumnerna ligger först i df. Alla kolumner som inte är kända
        # enrichment-kolumner får följa med, så att lokala Artportalenfält inte tappas.
        known_enrichment = set(
            IDENTIFICATION_COLUMNS
            + REDLIST_COLUMNS
            + PROTECTION_SUMMARY_COLUMNS
            + NATURE_TEXT_COLUMNS
            + ALIEN_SPECIES_COLUMNS
        )
        original_columns = [c for c in df.columns if c not in known_enrichment]
        _append_unique(selected, original_columns, existing)
    else:
        _append_unique(selected, preset.original_column_candidates, existing)

    _append_unique(selected, preset.enrichment_columns, existing)

    if not selected:
        return df.copy()

    return df.loc[:, selected].copy()
