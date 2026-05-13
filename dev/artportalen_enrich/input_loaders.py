# -*- coding: utf-8 -*-
"""Import i standaryzacja plików wejściowych: Artportalen oraz AGOL.

Ten moduł odpowiada tylko za początek procesu:
- wczytanie pliku wejściowego,
- rozpoznanie źródła danych,
- wskazanie kolumn z TaxonId / nazwą szwedzką / nazwą naukową,
- dodanie kanonicznych kolumn pomocniczych, jeśli w AGOL mają inne nazwy.

Cały enrichment SLU/API pozostaje wspólny i jest wykonywany dalej w pipeline.py.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .excel_io import find_column, read_artportalen_excel
from .logger_utils import log


@dataclass(frozen=True)
class InputColumns:
    """Rozpoznane kolumny wejściowe używane do uzyskania TaxonId."""

    taxonid: Optional[str]
    swedish_name: Optional[str]
    scientific_name: Optional[str]


@dataclass(frozen=True)
class InputReadResult:
    """Wynik wczytania i standaryzacji danych wejściowych."""

    dataframe: pd.DataFrame
    source_type: str
    columns: InputColumns


TAXON_ID_ALIASES = [
    "TaxonId",
    "taxonid",
    "taxon_id",
    "taxon id",
    "taxon-id",
    "artdatabanken taxonid",
    "artdatabanken_taxonid",
    "artfakta taxonid",
    "artfakta_taxonid",
    "artportalen taxonid",
    "artportalen_taxonid",
    "taxon id artdatabanken",
]

SWEDISH_NAME_ALIASES = [
    "taxon_svensktNamn",
    "taxon_svensktnamn",
    "taxon svenskt namn",
    "svensktNamn",
    "svensktnamn",
    "svenskt namn",
    "svenskt_namn",
    "svensk_namn",
    "svensk namn",
    "svenska namn",
    "svenskt artnamn",
    "svenskt_artnamn",
    "artnamn",
    "art namn",
    "art_namn",
    "species swedish",
    "species_swedish",
    "swedish name",
    "swedishname",
]

SCIENTIFIC_NAME_ALIASES = [
    "taxon_vetenskapligtNamn",
    "taxon_vetenskapligtnamn",
    "taxon vetenskapligt namn",
    "vetenskapligtNamn",
    "vetenskapligtnamn",
    "vetenskapligt namn",
    "vetenskapligt_namn",
    "vetenskaplig namn",
    "vetenskaplig_namn",
    "scientific name",
    "scientificname",
    "scientific_name",
    "latin name",
    "latin_name",
    "latinskt namn",
    "latinskt_namn",
]

AGOL_MARKERS = {
    "objectid",
    "globalid",
    "shape",
    "shapearea",
    "shapelength",
    "shape__area",
    "shape__length",
    "createduser",
    "createddate",
    "lastediteduser",
    "lastediteddate",
    "editdate",
    "creator",
    "editor",
}

ARTPORTALEN_MARKERS = {
    "taxonauktor",
    "taxonkategori",
    "taxonrodlistad",
    "taxonrödlistad",
    "lokalnamn",
    "kommun",
    "landskap",
    "provins",
    "startdatum",
    "slutdatum",
    "observationsdatum",
    "fynddatum",
}


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _norm(value: object) -> str:
    text = _strip_accents(str(value or "").strip().lower())
    text = text.replace("å", "a").replace("ä", "a").replace("ö", "o")
    return re.sub(r"[^a-z0-9]+", "", text)


def _norm_columns(df: pd.DataFrame) -> dict[str, str]:
    return {_norm(c): str(c) for c in df.columns}


def _find_column_fuzzy(df: pd.DataFrame, aliases: list[str]) -> Optional[str]:
    """Hittar kolumn med normaliserad jämförelse och faller tillbaka på find_column."""
    direct = find_column(df, aliases)
    if direct:
        return direct

    normalized = _norm_columns(df)
    for alias in aliases:
        hit = normalized.get(_norm(alias))
        if hit:
            return hit
    return None


def _looks_like_bad_name_column(column_name: str) -> bool:
    n = _norm(column_name)
    bad_tokens = (
        "lokal",
        "plats",
        "kommun",
        "lan",
        "landskap",
        "observ",
        "inventer",
        "skapad",
        "andrad",
        "created",
        "edited",
        "global",
        "object",
        "shape",
    )
    return any(token in n for token in bad_tokens)


def _heuristic_swedish_name_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        n = _norm(col)
        if _looks_like_bad_name_column(str(col)):
            continue
        if ("svensk" in n or "svenskt" in n) and ("namn" in n or "art" in n):
            return str(col)

    for col in df.columns:
        n = _norm(col)
        if _looks_like_bad_name_column(str(col)):
            continue
        if n in {"artnamn", "art", "species", "namn"}:
            return str(col)
    return None


def _heuristic_scientific_name_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        n = _norm(col)
        if _looks_like_bad_name_column(str(col)):
            continue
        if "vetenskap" in n or "scientific" in n or "latin" in n:
            return str(col)
    return None


def detect_input_columns(df: pd.DataFrame) -> InputColumns:
    """Rozpoznaje TaxonId i kolumny nazw w Artportalen/AGOL."""
    col_taxonid = _find_column_fuzzy(df, TAXON_ID_ALIASES)
    col_sv = _find_column_fuzzy(df, SWEDISH_NAME_ALIASES) or _heuristic_swedish_name_column(df)
    col_sci = _find_column_fuzzy(df, SCIENTIFIC_NAME_ALIASES) or _heuristic_scientific_name_column(df)
    return InputColumns(col_taxonid, col_sv, col_sci)


def _read_generic_table(input_file: str) -> pd.DataFrame:
    ext = os.path.splitext(input_file)[1].lower()
    if ext in {".xlsx", ".xlsm", ".xls"}:
        df = pd.read_excel(input_file, engine="openpyxl")
    elif ext == ".csv":
        try:
            df = pd.read_csv(input_file, sep=None, engine="python")
        except Exception:
            df = pd.read_csv(input_file)
    elif ext == ".tsv":
        df = pd.read_csv(input_file, sep="\t")
    else:
        raise ValueError(f"Nieobsługiwany format pliku wejściowego: {ext}")

    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.columns = [str(c).strip() if not pd.isna(c) else "" for c in df.columns]
    return df


def detect_input_source(df: pd.DataFrame) -> str:
    """Heurystycznie rozpoznaje źródło danych na podstawie nazw kolumn."""
    normalized = {_norm(c) for c in df.columns}
    agol_score = len(normalized.intersection(AGOL_MARKERS))
    artportalen_score = len(normalized.intersection(ARTPORTALEN_MARKERS))

    # AGOL-eksporty z ArcGIS Pro/Online zwykle mają OBJECTID/GlobalID/Shape/created_*/edited_*.
    if agol_score >= 1 and artportalen_score == 0:
        return "agol"
    if agol_score >= 2:
        return "agol"
    if artportalen_score >= 1:
        return "artportalen"

    # Jeśli nie jesteśmy pewni, traktujemy dane neutralnie jako AGOL/generic.
    # Enrichment i tak opiera się dalej na TaxonId albo nazwach.
    return "auto"


def standardize_input_dataframe(df: pd.DataFrame, source_type: str) -> tuple[pd.DataFrame, InputColumns]:
    """Dodaje kanoniczne kolumny pomocnicze, nie usuwając oryginalnych kolumn."""
    out = df.copy()
    cols = detect_input_columns(out)

    # Kanoniczne kolumny nazw ułatwiają dalsze przetwarzanie, ale zachowujemy też oryginały.
    if cols.swedish_name and "taxon_svensktNamn" not in out.columns:
        out["taxon_svensktNamn"] = out[cols.swedish_name]
        cols = InputColumns(cols.taxonid, "taxon_svensktNamn", cols.scientific_name)

    if cols.scientific_name and "taxon_vetenskapligtNamn" not in out.columns:
        out["taxon_vetenskapligtNamn"] = out[cols.scientific_name]
        cols = InputColumns(cols.taxonid, cols.swedish_name, "taxon_vetenskapligtNamn")

    # Jeśli TaxonId istnieje pod inną nazwą, pipeline i tak utworzy/uzupełni kolumnę TaxonId później.
    return out, cols


def read_input_file(input_file: str, requested_source: str = "auto") -> InputReadResult:
    """Czyta plik wejściowy jako Artportalen albo AGOL/generic."""
    requested = (requested_source or "auto").strip().lower()
    if requested not in {"auto", "artportalen", "agol"}:
        requested = "auto"

    if requested == "artportalen":
        df = read_artportalen_excel(input_file)
        detected = "artportalen"
    elif requested == "agol":
        df = _read_generic_table(input_file)
        detected = "agol"
        log("Wczytano plik jako AGOL/generic — bez pomijania wierszy opisowych Artportalen.")
    else:
        ext = os.path.splitext(input_file)[1].lower()
        if ext in {".csv", ".tsv"}:
            df = _read_generic_table(input_file)
            detected = "agol"
            log("Auto-detect: plik CSV/TSV traktuję jako AGOL/generic.")
        else:
            # Działa dla Artportalen z dodatkowymi wierszami oraz dla zwykłego AGOL XLSX z nagłówkiem w pierwszym wierszu.
            df = read_artportalen_excel(input_file)
            detected = detect_input_source(df)
            if detected == "agol":
                log("Auto-detect: wykryto cechy AGOL/ArcGIS w kolumnach wejściowych.")
            elif detected == "artportalen":
                log("Auto-detect: wykryto cechy eksportu Artportalen.")
            else:
                log("Auto-detect: źródło niejednoznaczne — używam neutralnego trybu generic.")

    standardized, columns = standardize_input_dataframe(df, detected)
    log(f"Typ wejścia: {detected if detected != 'auto' else 'generic'}")
    log(
        "Kolumny wejściowe: "
        f"TaxonId={columns.taxonid or 'brak'}, "
        f"svenskt namn={columns.swedish_name or 'brak'}, "
        f"vetenskapligt namn={columns.scientific_name or 'brak'}"
    )
    return InputReadResult(standardized, detected, columns)
