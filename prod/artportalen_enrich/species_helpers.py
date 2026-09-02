# -*- coding: utf-8 -*-
"""Hjälpfunktioner för SpeciesDataService-strukturer."""

from typing import Any, List, Optional


def extract_child_names(childs: Any) -> List[str]:
    out = []
    for c in (childs or []):
        nm = c.get("name") if isinstance(c, dict) else None
        if nm:
            out.append(nm)
        if isinstance(c, dict) and c.get("childs"):
            out.extend(extract_child_names(c.get("childs")))
    return out


def any_child_named(lists: Any, target: str) -> str:
    def has_child_named(childs: Any, name: str) -> bool:
        for c in childs or []:
            if not isinstance(c, dict):
                continue
            if c.get("name", "") == name:
                return True
            if c.get("childs") and has_child_named(c["childs"], name):
                return True
        return False

    for it in lists or []:
        if isinstance(it, dict) and has_child_named(it.get("childs", []), target):
            return "Ja"
    return ""


def join_name_with_attr(items: Any, key: str, sub: Optional[str] = None, sep: str = ", ") -> str:
    if not items:
        return ""

    vals = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if not it.get(key):
            continue
        if sub:
            vals.append(f"{it.get(key, '')} ({it.get(sub, '')})")
        else:
            vals.append(str(it.get(key, "")))

    vals = sorted(set(v for v in vals if v))
    return sep.join(vals)


def join_typical_species(ts: Any) -> str:
    if not ts:
        return ""

    vals = []
    for t in ts:
        if not isinstance(t, dict):
            continue
        nm = t.get("typcial", "") or t.get("typical", "") or t.get("name", "")
        regs = ", ".join(t.get("regions", []) or [])
        if nm:
            vals.append(f"{nm}{' (' + regs + ')' if regs else ''}")

    return ", ".join(sorted(set(vals)))


def _extract_period_year(period: Any) -> int:
    """Extraherar årtal från en period-struktur om möjligt."""
    if not isinstance(period, dict):
        return 0

    yr = period.get("year")
    if yr is not None:
        try:
            return int(yr)
        except (ValueError, TypeError):
            pass

    import re

    for field in ("name", "periodTo", "periodFrom"):
        val = str(period.get(field) or "")
        match = re.search(r"\b(19\d\d|20\d\d)\b", val)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                pass

    return 0


def select_current_or_latest_redlist(redlist_info: Any) -> Optional[dict]:
    """
    Väljer rödlistningspost från API:
    1. I första hand posten där period.current is True.
    2. Om API saknar current == True: posten med det senaste årtalet/period-ID.
    3. Sista fallback: första tillgängliga posten.
    """
    if not isinstance(redlist_info, list) or not redlist_info:
        return None

    valid_items = [r for r in redlist_info if isinstance(r, dict)]
    if not valid_items:
        return None

    # 1. period.current is True
    current_items = [
        r for r in valid_items
        if ((r.get("period") or {}).get("current") is True)
    ]
    if current_items:
        if len(current_items) > 1:
            current_items.sort(
                key=lambda r: (
                    _extract_period_year((r.get("period") or {})),
                    int((r.get("period") or {}).get("id") or 0) if str((r.get("period") or {}).get("id", "")).isdigit() else 0,
                ),
                reverse=True,
            )
        return current_items[0]

    # 2. Senaste perioden baserat på årtal och ID
    def _sort_key(r: dict) -> tuple:
        p = r.get("period") or {}
        yr = _extract_period_year(p)
        pid = 0
        try:
            pid = int(p.get("id") or 0)
        except (ValueError, TypeError):
            pass
        return (yr, pid)

    items_with_key = [(r, _sort_key(r)) for r in valid_items]
    if any(k > (0, 0) for _, k in items_with_key):
        items_with_key.sort(key=lambda x: x[1], reverse=True)
        return items_with_key[0][0]

    # 3. Sista fallback
    return valid_items[0]


FALLBACK_MINSKANDE_FAGLAR_NAMES = {
    "bergand",
    "bivråk",
    "bläsand",
    "brunand",
    "ejder",
    "entita",
    "fjällvråk",
    "gräshoppsångare",
    "grönsiska",
    "gulsparv",
    "göktyta",
    "havstrut",
    "hussvala",
    "hämpling",
    "järnsparv",
    "kungsfågel",
    "näktergal",
    "rosenfink",
    "rörsångare",
    "skogsduva",
    "stare",
    "strandskata",
    "svärta",
    "sånglärka",
    "sävspar",
    "sävsparv",
    "tallbit",
    "tornseglare",
}

_CACHED_MINSKANDE_FAGLAR: Optional[tuple] = None


def find_minskande_faglar_file() -> Optional[str]:
    """Szuka pliku minskande_faglar50.xlsx w repozytorium."""
    import glob
    import os
    try:
        from .config import REPO_ROOT, SCRIPT_DIR
    except Exception:
        REPO_ROOT = os.getcwd()
        SCRIPT_DIR = os.getcwd()

    search_dirs = [
        REPO_ROOT,
        SCRIPT_DIR,
        os.getcwd(),
    ]
    seen = set()
    unique_dirs = []
    for d in search_dirs:
        if d and os.path.isdir(d):
            ad = os.path.abspath(d)
            if ad not in seen:
                seen.add(ad)
                unique_dirs.append(ad)

    exact_names = [
        "minskande_faglar50.xlsx",
        "minskande_faglar.xlsx",
        "Minskande_faglar50.xlsx",
    ]
    for d in unique_dirs:
        for name in exact_names:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
        matches = sorted(glob.glob(os.path.join(d, "*minskande*faglar*.xlsx")))
        if matches:
            return matches[0]

    return None


def load_minskande_faglar() -> tuple:
    """Ładuje nazwy i identyfikatory gatunków z minskande_faglar50.xlsx."""
    global _CACHED_MINSKANDE_FAGLAR
    if _CACHED_MINSKANDE_FAGLAR is not None:
        return _CACHED_MINSKANDE_FAGLAR

    swe_set = set(FALLBACK_MINSKANDE_FAGLAR_NAMES)
    sci_set = set()
    tid_set = set()

    file_path = find_minskande_faglar_file()
    if file_path:
        try:
            import pandas as pd
            df = pd.read_excel(file_path, engine="openpyxl")
            for c in df.columns:
                lc = str(c).strip().lower()
                if "vetenskap" in lc or "scientific" in lc or "sci" in lc:
                    for val in df[c].dropna():
                        s = str(val).strip().lower()
                        if s:
                            sci_set.add(s)
                elif "taxon" in lc and "id" in lc:
                    for val in df[c].dropna():
                        try:
                            tid_int = int(val)
                            if tid_int > 0:
                                tid_set.add(tid_int)
                        except (ValueError, TypeError):
                            pass
                elif "svensk" in lc or "swedish" in lc or "namn" in lc or "art" in lc:
                    for val in df[c].dropna():
                        s = str(val).strip().lower()
                        if s:
                            swe_set.add(s)
                            if s == "sävsparv":
                                swe_set.add("sävspar")
                            elif s == "sävspar":
                                swe_set.add("sävsparv")
        except Exception:
            pass

    _CACHED_MINSKANDE_FAGLAR = (swe_set, sci_set, tid_set)
    return _CACHED_MINSKANDE_FAGLAR


def is_minskande_fagel(swedish_name: str = "", scientific_name: str = "", taxon_id: int = 0) -> bool:
    """Sprawdza czy dany gatunek należy do minskande fåglar (>50%)."""
    swe_set, sci_set, tid_set = load_minskande_faglar()

    if taxon_id and taxon_id in tid_set:
        return True

    if swedish_name:
        sn = str(swedish_name).strip().lower()
        if sn in swe_set:
            return True
        if sn == "sävspar" and "sävsparv" in swe_set:
            return True
        if sn == "sävsparv" and "sävspar" in swe_set:
            return True

    if scientific_name:
        scn = str(scientific_name).strip().lower()
        if scn in sci_set:
            return True

    return False


