# -*- coding: utf-8 -*-
"""Główny przepływ przetwarzania Artportalen/AGOL → enrich.

Enrichment SLU/API jest wspólny. Różnice między Artportalen i AGOL są obsługiwane
na początku procesu przez input_loaders.py.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import pandas as pd

from .config import NAME_QUERY_SLEEP
from .export_presets import EXTERNAL_PRESETS_DIR, apply_export_preset, get_preset
from .input_loaders import InputColumns, read_input_file
from .logger_utils import configure_logging, get_debug_rows, is_debug, log
from .processing import (
    build_enrichment_table,
    make_alien_invasive,
    make_full_enriched,
    make_overview,
    make_protected,
    sort_by_redlist,
    summarize_debug,
)
from .risk_merge import optional_merge_risk_file
from .taxon_client import resolve_taxon_id
from .tls_client import fetch_tls_definitions, tls_build_memberships, tls_definitions_ready
from .ui import pick_inputs


def _as_clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null", "<na>"}:
        return ""
    return text


def _name_key(row: pd.Series, columns: InputColumns) -> tuple[str, str]:
    sv = _as_clean_text(row.get(columns.swedish_name, "")) if columns.swedish_name else ""
    sci = _as_clean_text(row.get(columns.scientific_name, "")) if columns.scientific_name else ""
    return sv, sci


def _resolve_taxon_ids_for_unique_names(
    df: pd.DataFrame,
    columns: InputColumns,
    row_mask: Optional[pd.Series] = None,
) -> dict[tuple[str, str], int]:
    """Resolve TaxonId raz dla każdej unikalnej pary nazwa szwedzka/naukowa."""
    if not columns.swedish_name and not columns.scientific_name:
        return {}

    if row_mask is None:
        subset = df
    else:
        subset = df.loc[row_mask]

    name_keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, row in subset.iterrows():
        key = _name_key(row, columns)
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        name_keys.append(key)

    log(f"Do dopasowania TaxonId po nazwach: {len(name_keys)} unikalnych nazw/par nazw.")

    resolved: dict[tuple[str, str], int] = {}
    for i, key in enumerate(name_keys, start=1):
        sv, sci = key
        rec = {}
        if columns.swedish_name:
            rec[columns.swedish_name] = sv
        if columns.scientific_name:
            rec[columns.scientific_name] = sci

        tid = resolve_taxon_id(rec, columns.swedish_name, columns.scientific_name)
        resolved[key] = int(tid or 0)

        if i % 20 == 0 or i == len(name_keys):
            log(f"→ dopasowano {i}/{len(name_keys)} unikalnych nazw — ostatni TaxonId={tid}")
        time.sleep(NAME_QUERY_SLEEP)

    return resolved


def ensure_taxon_id(df: pd.DataFrame, columns: InputColumns) -> pd.DataFrame:
    """Gwarantuje kolumnę TaxonId, wykorzystując istniejące ID albo dopasowanie po nazwach.

    Dla AGOL kluczowe jest, że dopasowanie po nazwie robimy dla unikalnych nazw,
    a nie dla każdego wiersza z osobna.
    """
    out = df.copy()

    if columns.taxonid:
        out["TaxonId"] = pd.to_numeric(out[columns.taxonid], errors="coerce").fillna(0).astype("int64")
        valid = int((out["TaxonId"] > 0).sum())
        missing_mask = out["TaxonId"] <= 0
        missing = int(missing_mask.sum())
        log(f"Wykryto kolumnę TaxonId — poprawnych TaxonId>0: {valid}, brakujących/niepoprawnych: {missing}.")

        if missing == 0:
            return out

        if not columns.swedish_name and not columns.scientific_name:
            log("Brakujące TaxonId pozostają jako 0 — brak kolumn nazw do fallbackowego dopasowania.")
            return out

        log("Uzupełniam brakujące TaxonId przez dopasowanie po nazwach.")
        resolved = _resolve_taxon_ids_for_unique_names(out, columns, missing_mask)
        if resolved:
            filled = 0
            for idx, row in out.loc[missing_mask].iterrows():
                tid = resolved.get(_name_key(row, columns), 0)
                if tid:
                    out.at[idx, "TaxonId"] = int(tid)
                    filled += 1
            log(f"Uzupełniono TaxonId dla {filled} wierszy z brakującym/niepoprawnym TaxonId.")
        return out

    if not columns.swedish_name and not columns.scientific_name:
        raise ValueError(
            "Brak kolumny TaxonId oraz nazw do dopasowania TaxonId.\n"
            "Oczekuję jednej z kolumn typu: TaxonId, taxon_svensktNamn, "
            "taxon_vetenskapligtNamn, svenskt namn, vetenskapligt namn.\n"
            f"Znalezione kolumny: {', '.join(list(out.columns))}"
        )

    log("Etap 1: wyznaczanie TaxonId po nazwach — tryb unikalnych nazw, nie po każdym rekordzie.")
    resolved = _resolve_taxon_ids_for_unique_names(out, columns)

    taxon_ids: list[int] = []
    for _, row in out.iterrows():
        taxon_ids.append(int(resolved.get(_name_key(row, columns), 0) or 0))

    out["TaxonId"] = pd.Series(taxon_ids, dtype="int64")
    valid = int((out["TaxonId"] > 0).sum())
    log(f"Dodano kolumnę TaxonId. Poprawnie dopasowane wiersze: {valid}/{len(out)}.")
    return out


def unique_taxon_ids(df: pd.DataFrame) -> list[int]:
    taxon_series = pd.to_numeric(df["TaxonId"], errors="coerce").fillna(0).astype("int64")
    uniq_ids = sorted(set(int(t) for t in taxon_series.tolist() if t > 0))
    valid_count = int((taxon_series > 0).sum())
    duplicate_api_queries = max(valid_count - len(uniq_ids), 0)

    log(
        f"Do API wysyłam {len(uniq_ids)} unikalnych TaxonId>0 "
        f"z {len(df)} wierszy wejściowych."
    )
    if duplicate_api_queries > 0:
        log(
            f"Pominięto {duplicate_api_queries} powtórzonych TaxonId przy zapytaniach API; "
            f"pełna tabela nadal zachowa wszystkie obserwacje."
        )

    return uniq_ids


def write_excel(path: str, df: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    log(f"Zapisano: {path}")


def main() -> None:
    paths = pick_inputs()

    try:
        if os.path.exists(paths["LOG_FILE"]):
            os.remove(paths["LOG_FILE"])
    except Exception:
        pass

    configure_logging(paths["LOG_FILE"], bool(paths["DEBUG"]))

    log(f"Plik wejściowy: {paths['INPUT_FILE']}")
    log(f"Deklarowany typ wejścia: {paths.get('INPUT_SOURCE', 'auto')}")
    log(f"Folder wyjściowy: {paths['OUTDIR']}")

    preset = get_preset(paths.get("EXPORT_PRESET"))
    log(f"Exportprofil: {preset.label}")
    log(f"Exportprofil źródło: {preset.source}{' — ' + preset.source_path if preset.source_path else ''}")
    log(f"Folder presetów: {EXTERNAL_PRESETS_DIR}")
    log(
        "Filtr _bara_skyddade: "
        f"flagi ochronne={'tak' if preset.include_current_protection_filter else 'nie'}, "
        f"rödlistning={'/'.join(preset.redlist_categories) if preset.include_redlist_filter else 'nie'}, "
        f"IAS_Union_EU={'tak' if preset.include_ias_union_eu_filter else 'nie'}."
    )

    input_result = read_input_file(paths["INPUT_FILE"], paths.get("INPUT_SOURCE", "auto"))
    df = ensure_taxon_id(input_result.dataframe, input_result.columns)

    uniq_ids = unique_taxon_ids(df)

    fetch_tls_definitions()
    if tls_definitions_ready():
        tls_build_memberships()
    else:
        log("TLS: /definitions niedostępne — użyję tylko fallbacków z SpeciesDataService.")

    result = build_enrichment_table(uniq_ids)
    full_enriched = make_full_enriched(df, result)

    if paths["WANT_FULL"]:
        full_sorted = sort_by_redlist(full_enriched)
        write_excel(paths["OUT_FULL"], full_sorted)

    overview = make_overview(full_enriched)
    overview_export = apply_export_preset(overview, paths.get("EXPORT_PRESET"))
    write_excel(paths["OUT_WITH"], overview_export)

    protected = make_protected(overview, preset)
    protected_export = apply_export_preset(protected, paths.get("EXPORT_PRESET"))
    write_excel(paths["OUT_PROT"], protected_export)

    alien_invasive = make_alien_invasive(overview)
    alien_export = apply_export_preset(alien_invasive, "frammande_invasiva")
    write_excel(paths["OUT_ALIEN"], alien_export)

    if is_debug():
        try:
            pd.DataFrame(get_debug_rows()).to_csv(paths["DBG_FILE"], index=False, encoding="utf-8-sig")
            log(f"DEBUG zapisano: {paths['DBG_FILE']}")
            summarize_debug(overview)
        except Exception as e:
            log(f"DEBUG zapis CSV nieudany: {e}")

    optional_merge_risk_file(os.path.dirname(paths["INPUT_FILE"]), paths["OUT_WITH"])

    log("Proces zakończony sukcesem!")
