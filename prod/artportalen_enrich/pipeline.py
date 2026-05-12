# -*- coding: utf-8 -*-
"""Główny przepływ przetwarzania Artportalen export → enrich."""

import os
import time
from typing import Optional

import pandas as pd

from .config import NAME_QUERY_SLEEP
from .excel_io import find_column, read_artportalen_excel
from .logger_utils import configure_logging, get_debug_rows, is_debug, log
from .processing import (
    FLAG_COLUMNS,
    build_enrichment_table,
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


def _detect_input_columns(df: pd.DataFrame) -> tuple[Optional[str], Optional[str], Optional[str]]:
    col_taxonid = find_column(df, ["taxonid", "taxon_id", "taxon id"])
    col_sv = find_column(
        df,
        [
            "taxon_svensktnamn",
            "taxon_svensktNamn",
            "svensktnamn",
            "svensk_namn",
            "svenskt namn",
        ],
    ) or ("taxon_svensktNamn" if "taxon_svensktNamn" in df.columns else None)
    col_sci = find_column(
        df,
        [
            "taxon_vetenskapligtnamn",
            "taxon_vetenskapligtNamn",
            "vetenskapligtnamn",
            "vetenskapligt_namn",
            "vetenskapligt namn",
        ],
    ) or ("taxon_vetenskapligtNamn" if "taxon_vetenskapligtNamn" in df.columns else None)
    return col_taxonid, col_sv, col_sci


def ensure_taxon_id(df: pd.DataFrame, col_taxonid: Optional[str], col_sv: Optional[str], col_sci: Optional[str]) -> pd.DataFrame:
    out = df.copy()

    if col_taxonid:
        out["TaxonId"] = pd.to_numeric(out[col_taxonid], errors="coerce").fillna(0).astype("int64")
        log("Wykryto kolumnę TaxonId — pomijam dopasowanie po nazwach.")
        return out

    if not col_sv and not col_sci:
        raise ValueError(
            "Brak kolumny TaxonId oraz nazw ('taxon_svensktNamn' / 'taxon_vetenskapligtNamn').\n"
            f"Znalezione kolumny: {', '.join(list(out.columns))}"
        )

    log("Etap 1: wyznaczanie TaxonId…")
    taxon_ids = []
    for i, row in enumerate(out.itertuples(index=False), start=1):
        rec = row._asdict() if hasattr(row, "_asdict") else dict(zip(out.columns, row))
        tid = resolve_taxon_id(rec, col_sv, col_sci)
        taxon_ids.append(tid)

        if i % 20 == 0:
            log(f"→ {i}/{len(out)} rekordów — ostatni TaxonId={tid}")
        time.sleep(NAME_QUERY_SLEEP)

    out["TaxonId"] = pd.Series(taxon_ids, dtype="int64")
    log("Dodano kolumnę TaxonId.")
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
    log(f"Folder wyjściowy: {paths['OUTDIR']}")

    df = read_artportalen_excel(paths["INPUT_FILE"])
    col_taxonid, col_sv, col_sci = _detect_input_columns(df)
    df = ensure_taxon_id(df, col_taxonid, col_sv, col_sci)

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
    write_excel(paths["OUT_WITH"], overview)

    protected = make_protected(overview)
    write_excel(paths["OUT_PROT"], protected)

    if is_debug():
        try:
            pd.DataFrame(get_debug_rows()).to_csv(paths["DBG_FILE"], index=False, encoding="utf-8-sig")
            log(f"DEBUG zapisano: {paths['DBG_FILE']}")
            summarize_debug(overview)
        except Exception as e:
            log(f"DEBUG zapis CSV nieudany: {e}")

    optional_merge_risk_file(os.path.dirname(paths["INPUT_FILE"]), paths["OUT_WITH"])

    log("Proces zakończony sukcesem!")
