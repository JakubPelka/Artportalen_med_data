# -*- coding: utf-8 -*-
"""Excel-inläsning och kolumnhjälpare."""

import re
from typing import Any, List, Optional

import pandas as pd

from .logger_utils import log


def _normalize_header_value(value: Any) -> str:
    """Normalizuje wartość komórki do porównywania nazw kolumn."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    text = str(value).strip().lower().replace("\ufeff", "")
    text = re.sub(r"\s+", "", text)
    text = text.replace("_", "")
    return text


def detect_artportalen_header_row(input_file: str, max_scan_rows: int = 15) -> int:
    """
    Wykrywa, który wiersz w Excelu jest właściwym nagłówkiem danych.
    Zwraca indeks wiersza w stylu pandas, czyli 0 = pierwszy wiersz.
    """
    preview = pd.read_excel(input_file, engine="openpyxl", header=None, nrows=max_scan_rows)

    strong_markers = {
        "taxonid",
        "taxonsvensktnamn",
        "taxonvetenskapligtnamn",
    }

    weak_markers = {
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
        "artnamn",
        "artgrupp",
    }

    best_row = 0
    best_score = -1.0

    for row_idx, row in preview.iterrows():
        values = [_normalize_header_value(v) for v in row.tolist()]
        values_set = {v for v in values if v}

        score = 0.0
        for marker in strong_markers:
            if marker in values_set:
                score += 10.0

        for marker in weak_markers:
            if marker in values_set:
                score += 2.0

        if any("taxon" in v for v in values_set):
            score += 3.0

        score += min(len(values_set), 25) * 0.1

        if score > best_score:
            best_score = score
            best_row = int(row_idx)

    if best_score < 10.0:
        return 0

    return best_row


def read_artportalen_excel(input_file: str) -> pd.DataFrame:
    """
    Czyta Excel z Artportalen i automatycznie pomija ewentualne wiersze opisowe
    przed właściwym nagłówkiem tabeli.
    """
    header_row = detect_artportalen_header_row(input_file)

    if header_row > 0:
        log(
            f"Wykryto dodatkowe wiersze przed nagłówkiem: {header_row}. "
            f"Czytam dane od wiersza {header_row + 1}."
        )
    else:
        log("Nagłówek danych wykryty w pierwszym wierszu.")

    df = pd.read_excel(input_file, engine="openpyxl", header=header_row)
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.columns = [str(c).strip() if not pd.isna(c) else "" for c in df.columns]
    return df


def find_column(dataframe: pd.DataFrame, names: List[str]) -> Optional[str]:
    low = {str(c).strip().lower(): c for c in dataframe.columns}
    for nm in names:
        if nm.lower() in low:
            return low[nm.lower()]
    return None
