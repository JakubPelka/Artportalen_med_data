# -*- coding: utf-8 -*-
"""Exportprofiler för kolumnurval och filter i resultatfilerna.

Profilerna styr främst vilka kolumner som skrivs till *_with_data.xlsx
och *_bara_skyddade.xlsx. De kan också styra filtret för *_bara_skyddade,
men påverkar inte själva API-anropen eller berikningen.

Externa profiler läses från:

    <dev eller prod>/export_presets/*.json

Det betyder att DEV och PROD kan ha egna presetmappar:

    dev/export_presets/
    prod/export_presets/

Om mappen saknas används de inbyggda profilerna.
"""

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import pandas as pd

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)
EXTERNAL_PRESETS_DIR = os.path.join(REPO_ROOT, "export_presets")


@dataclass(frozen=True)
class ExportPreset:
    preset_id: str
    label: str
    description: str
    include_all_columns: bool = False
    include_original_columns: bool = False
    original_column_candidates: Tuple[str, ...] = ()
    enrichment_columns: Tuple[str, ...] = ()

    # Filter för *_bara_skyddade.xlsx / prioriterade arter.
    include_current_protection_filter: bool = True
    include_redlist_filter: bool = True
    redlist_categories: Tuple[str, ...] = ("RE", "CR", "EN", "VU", "NT")
    include_ias_union_eu_filter: bool = False

    # Metadata för felsökning/preview.
    source: str = "built-in"
    source_path: str = ""


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
    "Author",
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
    "FågeldirektivetBilaga2",
    "PrioriteradeFågelarterSkogsvårdslagen",
    "SkogsstyrelsensNaturvardsarter",
    "minskande_faglar",
    "ProtectedByWorkProtectionConstitution",
    "ProtectedBirds",
    "DirectiveAppendix2",
    "DirectiveAppendix2Priority",
    "DirectiveAppendix4",
    "DirectiveAppendix5",
    "Habitatdirektivet2023",
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
    "SwedishOccurrence",
    "SwedishHistory",
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
    "FrammandeArter",
    "FrammandeArterISverige",
    "IAS_Union_EU",
    "RisklistaFrammandeArter",
    "Risklista_SE",
    "Risklista_HI",
    "Risklista_PH",
    "Risklista_LO",
    "Risklista_NK",
)

BUILTIN_PRESETS = {
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
            "Filtret kan även ta med IAS_Union_EU om include_ias_union_eu_filter är true."
        ),
        include_original_columns=True,
        enrichment_columns=(
            *IDENTIFICATION_COLUMNS,
            *REDLIST_COLUMNS,
            *ALIEN_SPECIES_COLUMNS,
        ),
        include_current_protection_filter=False,
        include_redlist_filter=False,
        redlist_categories=(),
        include_ias_union_eu_filter=True,
    ),
    "frammande_invasiva": ExportPreset(
        preset_id="frammande_invasiva",
        label="Främmande / invasiva arter",
        description=(
            "Exportprofil för separat produkt _frammande_invasiva: främmande arter, "
            "EU-förordning 1143/2014 och Risklista SE/HI/PH/LO/NK."
        ),
        include_original_columns=True,
        enrichment_columns=(
            *IDENTIFICATION_COLUMNS,
            *REDLIST_COLUMNS,
            *ALIEN_SPECIES_COLUMNS,
            "SpreadAndStatus",
            "Ecology",
            "Threat",
            "ConservationMeasures",
        ),
        include_current_protection_filter=False,
        include_redlist_filter=False,
        redlist_categories=(),
        include_ias_union_eu_filter=True,
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


def _as_tuple(value: Any) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(x) for x in value if str(x).strip())
    if isinstance(value, list):
        return tuple(str(x) for x in value if str(x).strip())
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    return ()


def _bool_value(data: Dict[str, Any], key: str, default: bool) -> bool:
    val = data.get(key, default)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in {"1", "true", "yes", "ja", "y"}
    return bool(val)


def _preset_from_dict(data: Dict[str, Any], *, source: str, source_path: str = "") -> ExportPreset:
    preset_id = str(data.get("preset_id") or data.get("id") or "").strip()
    label = str(data.get("label") or data.get("name") or preset_id).strip()
    description = str(data.get("description") or "").strip()

    if not preset_id:
        raise ValueError("Preset saknar 'preset_id' eller 'id'.")
    if not label:
        label = preset_id

    # Filter kan ligga antingen i top-level eller i en separat "filter"-sektion.
    filter_data = data.get("filter") if isinstance(data.get("filter"), dict) else {}

    def get_filter_bool(key: str, default: bool) -> bool:
        if key in filter_data:
            return _bool_value(filter_data, key, default)
        return _bool_value(data, key, default)

    redlist_categories = (
        filter_data.get("redlist_categories")
        if "redlist_categories" in filter_data
        else data.get("redlist_categories", ("RE", "CR", "EN", "VU", "NT"))
    )

    return ExportPreset(
        preset_id=preset_id,
        label=label,
        description=description,
        include_all_columns=_bool_value(data, "include_all_columns", False),
        include_original_columns=_bool_value(data, "include_original_columns", False),
        original_column_candidates=_as_tuple(data.get("original_column_candidates")),
        enrichment_columns=_as_tuple(data.get("enrichment_columns") or data.get("columns")),
        include_current_protection_filter=get_filter_bool("include_current_protection_filter", True),
        include_redlist_filter=get_filter_bool("include_redlist_filter", True),
        redlist_categories=tuple(str(x).strip().upper() for x in _as_tuple(redlist_categories)),
        include_ias_union_eu_filter=get_filter_bool("include_ias_union_eu_filter", False),
        source=source,
        source_path=source_path,
    )


def _load_external_presets() -> Dict[str, ExportPreset]:
    presets: Dict[str, ExportPreset] = {}
    candidate_dirs = [
        os.path.join(REPO_ROOT, "export_presets"),
        os.path.join(REPO_ROOT, "dev", "export_presets"),
        os.path.join(REPO_ROOT, "prod", "export_presets"),
    ]
    for pdir in candidate_dirs:
        if not os.path.isdir(pdir):
            continue
        for filename in sorted(os.listdir(pdir)):
            if not filename.lower().endswith(".json"):
                continue
            path = os.path.join(pdir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("Preset JSON måste vara ett objekt.")
                preset = _preset_from_dict(data, source="json", source_path=path)
                presets[preset.preset_id] = preset
            except Exception as e:
                print(f"VARNING: kunde inte läsa exportpreset {path}: {e}")
    return presets


def load_presets() -> Dict[str, ExportPreset]:
    """Returnerar inbyggda profiler plus externa JSON-profiler.

    Om en extern profil har samma preset_id som en inbyggd profil skriver den
    externa över den inbyggda. Det gör det möjligt att justera standardprofiler
    lokalt i dev/export_presets eller prod/export_presets.
    """
    presets = dict(BUILTIN_PRESETS)
    presets.update(_load_external_presets())
    return presets


def get_preset(preset_id: Optional[str]) -> ExportPreset:
    presets = load_presets()
    if not preset_id:
        return presets[DEFAULT_PRESET_ID]
    return presets.get(preset_id, presets[DEFAULT_PRESET_ID])


def list_presets() -> List[ExportPreset]:
    return list(load_presets().values())


def _append_unique(target: List[str], columns: Iterable[str], existing: Set[str]) -> None:
    for col in columns:
        if col in existing and col not in target:
            target.append(col)


def apply_export_preset(df: pd.DataFrame, preset_id: Optional[str]) -> pd.DataFrame:
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


def get_known_export_columns() -> List[str]:
    """Kolumner som kan väljas i preset-editorn. Ordningen är stabil och praktisk."""
    columns: List[str] = []
    for group in (
        CORE_INPUT_COLUMNS,
        IDENTIFICATION_COLUMNS,
        REDLIST_COLUMNS,
        PROTECTION_SUMMARY_COLUMNS,
        NATURE_TEXT_COLUMNS,
        ALIEN_SPECIES_COLUMNS,
    ):
        for col in group:
            if col not in columns:
                columns.append(col)
    return columns


def save_custom_preset(data: Dict[str, Any]) -> Tuple[str, str]:
    """Sparar en användarskapad preset som JSON i <dev/prod>/export_presets/."""
    label = str(data.get("label") or data.get("name") or "Egen preset").strip()
    preset_id = str(data.get("preset_id") or data.get("id") or _slugify(label)).strip()
    if not preset_id:
        preset_id = _slugify(label)

    os.makedirs(EXTERNAL_PRESETS_DIR, exist_ok=True)

    existing = load_presets()
    base_id = preset_id
    if preset_id in existing:
        suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        preset_id = f"{base_id}_{suffix}"

    data = dict(data)
    data["preset_id"] = preset_id
    data["label"] = label

    path = os.path.join(EXTERNAL_PRESETS_DIR, f"{preset_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return preset_id, path


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9åäöA-ZÅÄÖ_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "custom_preset"


def preset_to_dict(preset: ExportPreset, *, preset_id: Optional[str] = None, label: Optional[str] = None) -> Dict[str, Any]:
    data = asdict(preset)
    data.pop("source", None)
    data.pop("source_path", None)
    data["preset_id"] = preset_id or preset.preset_id
    data["label"] = label or preset.label

    # Skriv tuples som listor så JSON blir lätt att redigera.
    for key in ("original_column_candidates", "enrichment_columns", "redlist_categories"):
        if isinstance(data.get(key), tuple):
            data[key] = list(data[key])

    return data


def save_preset_copy(source_preset_id: Optional[str], new_label: str) -> Tuple[str, str]:
    """Sparar en kopia av vald profil som JSON i <dev/prod>/export_presets/.

    Returnerar (new_preset_id, path).
    """
    base_preset = get_preset(source_preset_id)
    label = new_label.strip() or f"Kopia av {base_preset.label}"
    base_id = _slugify(label)

    os.makedirs(EXTERNAL_PRESETS_DIR, exist_ok=True)

    existing = load_presets()
    preset_id = base_id
    if preset_id in existing:
        suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        preset_id = f"{base_id}_{suffix}"

    data = preset_to_dict(base_preset, preset_id=preset_id, label=label)
    data["description"] = data.get("description") or f"Egen exportprofil baserad på {base_preset.label}."

    path = os.path.join(EXTERNAL_PRESETS_DIR, f"{preset_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return preset_id, path


def preset_summary_text(preset_id: Optional[str]) -> str:
    preset = get_preset(preset_id)
    column_mode = []
    if preset.include_all_columns:
        column_mode.append("Alla kolumner i resultatet")
    if preset.include_original_columns:
        column_mode.append("Originalkolumner från Artportalen")
    if preset.original_column_candidates:
        column_mode.append(f"Utvalda originalkolumner: {len(preset.original_column_candidates)}")
    if preset.enrichment_columns:
        column_mode.append(f"Valda enrich-kolumner: {len(preset.enrichment_columns)}")
    if not column_mode:
        column_mode.append("Fallback: alla kolumner om urvalet blir tomt")

    lines = [
        f"Namn: {preset.label}",
        f"ID: {preset.preset_id}",
        f"Källa: {preset.source}",
    ]
    if preset.source_path:
        lines.append(f"Fil: {preset.source_path}")
    lines.extend([
        "",
        "Beskrivning:",
        preset.description or "(ingen beskrivning)",
        "",
        "Kolumnläge:",
        *[f"- {x}" for x in column_mode],
        "",
        "Filter för _bara_skyddade:",
        f"- Skydds-/naturvårdsflaggor: {'ja' if preset.include_current_protection_filter else 'nej'}",
        f"- Rödlistning: {'ja' if preset.include_redlist_filter else 'nej'}",
        f"- Rödlistningskategorier: {', '.join(preset.redlist_categories) if preset.redlist_categories else '(inga)'}",
        f"- IAS_Union_EU som filter: {'ja' if preset.include_ias_union_eu_filter else 'nej'}",
        "",
        "Originalkolumnkandidater:",
    ])
    lines.extend([f"- {c}" for c in preset.original_column_candidates] or ["(inga)"])
    lines.extend(["", "Enrich-kolumner:"])
    lines.extend([f"- {c}" for c in preset.enrichment_columns] or ["(alla / inga specificerade)"])
    return "\n".join(lines)
