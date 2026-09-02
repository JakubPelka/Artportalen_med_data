# -*- coding: utf-8 -*-
"""Sökning och merge av Riskklassning/Risklista."""

import glob
import os
from typing import List, Optional

import pandas as pd

from .config import REPO_ROOT
from .logger_utils import log


def unique_existing_dirs(paths: List[str]) -> List[str]:
    seen = set()
    out = []
    for p in paths:
        if not p:
            continue
        ap = os.path.abspath(p)
        if ap in seen:
            continue
        seen.add(ap)
        if os.path.isdir(ap):
            out.append(ap)
    return out


def find_risk_file(input_dir: str, out_dir: str) -> Optional[str]:
    """
    Szuka pliku Riskklassning/Risklista.
    Priorytet: root repo → folder wejściowy → folder wyjściowy.
    """
    search_dirs = unique_existing_dirs([
        REPO_ROOT,
        input_dir,
        out_dir,
    ])

    exact_names = [
        "Riskklassning2024.xlsx",
        "Risklista2024.xlsx",
        "Riskklassning.xlsx",
    ]
    patterns = [
        "Riskklassning*.xlsx",
        "Risklista*.xlsx",
    ]

    for folder in search_dirs:
        for name in exact_names:
            candidate = os.path.join(folder, name)
            if os.path.exists(candidate):
                return candidate

        for pattern in patterns:
            matches = sorted(glob.glob(os.path.join(folder, pattern)))
            if matches:
                return matches[0]

    return None


def optional_merge_risk_file(input_dir: str, out_path: str) -> None:
    out_dir = os.path.dirname(out_path)
    target = find_risk_file(input_dir, out_dir)

    if not target:
        log(
            "Riskklassning*.xlsx nie znaleziony — pomijam merge. "
            f"Szukano najpierw w root repo: {REPO_ROOT}"
        )
        return

    try:
        log(f"Riskklassning: używam pliku {target}")

        df_main = pd.read_excel(out_path, engine="openpyxl")
        risk_df = pd.read_excel(target, engine="openpyxl")

        risk_tax_col = None
        for c in risk_df.columns:
            lc = str(c).strip().lower()
            if lc == "taxonid" or ("taxon" in lc and "id" in lc):
                risk_tax_col = c
                break

        if not risk_tax_col:
            log(f"Risk-plik bez kolumny TaxonId: {os.path.basename(target)} — pomijam.")
            return

        merged_final = df_main.merge(
            risk_df,
            left_on="TaxonId",
            right_on=risk_tax_col,
            how="left",
            suffixes=("", "_risk"),
        )

        if risk_tax_col != "TaxonId" and risk_tax_col in merged_final.columns:
            merged_final.drop(columns=[risk_tax_col], inplace=True)

        merged_final.to_excel(out_path, index=False)
        log(f"✅ Dodano kolumny z {os.path.basename(target)} do {os.path.basename(out_path)}")

    except Exception as e:
        log(f"‼ Błąd podczas łączenia z risk-plik: {e}")
