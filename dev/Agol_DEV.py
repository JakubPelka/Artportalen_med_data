# -*- coding: utf-8 -*-
"""
AGOL → Artfakta (TLS /definitions + /taxa) + Habitatdirektivet + Risklista 2024 + GUI + DEBUG

Nowe:
- Fallbackowe próby dociągnięcia alienSpeciesRa innymi wariantami żądania (jak w AP + dodatkowe)
- Jeśli nadal brak alienSpeciesRa: merge 4 pól GEIAA z Risklista 2024:
  ['Artens status','Ursprunglig utbredning','Riskkategori, utfall enligt GEIAA metodik','Utslagsgivande kriterier']
- Twardy dump: geiaa_dump.jsonl (gdy --debug)

Reszta (TLS, fridlyst, Habitat-bilagor, IAS_Union_EU, filtr 'skyddade' bez IAS, sort RL, dedupe, URL) bez zmian.
"""

import os
import re
import time
import json
import argparse
from datetime import datetime
from typing import Any, Dict, List, Tuple, Set

import requests
import pandas as pd

try:
    from artportalen_enrich.species_helpers import select_current_or_latest_redlist, is_minskande_fagel
except ImportError:
    def _extract_period_year(period: Any) -> int:
        if not isinstance(period, dict):
            return 0
        yr = period.get("year")
        if yr is not None:
            try:
                return int(yr)
            except (ValueError, TypeError):
                pass
        for field in ("name", "periodTo", "periodFrom"):
            val = str(period.get(field) or "")
            match = re.search(r"\b(19\d\d|20\d\d)\b", val)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, TypeError):
                    pass
        return 0

    def select_current_or_latest_redlist(redlist_info: Any) -> Any:
        if not isinstance(redlist_info, list) or not redlist_info:
            return None
        valid_items = [r for r in redlist_info if isinstance(r, dict)]
        if not valid_items:
            return None
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
        return valid_items[0]

# --- GUI (opcjonalnie) ---
try:
    import tkinter as tk
    from tkinter import filedialog
    GUI_OK = True
except Exception:
    GUI_OK = False

# === KLUCZE / NAGŁÓWKI ===
TAXONOMY_KEY = os.getenv("TAXONOMY_KEY", "..")
SPECIES_KEY  = os.getenv("SPECIES_KEY",  "..")  # primary
LISTS_KEY    = os.getenv("LISTS_KEY", os.getenv("SPECIESOBS_KEY", SPECIES_KEY))

HEADERS_TAXON   = {"Ocp-Apim-Subscription-Key": TAXONOMY_KEY, "Accept": "application/json"}
HEADERS_SPECIES = {"Ocp-Apim-Subscription-Key": SPECIES_KEY,  "Accept": "application/json", "Cache-Control": "no-cache"}
HEADERS_LISTS   = {"Ocp-Apim-Subscription-Key": LISTS_KEY,    "Accept": "application/json"}

# === STAŁE ===
NAME_QUERY_SLEEP = 0.10
SPECIES_SLEEP    = 0.10
TIMEOUT          = 30

# Endpointy
TAXON_NAME_URL = "https://api.artdatabanken.se/taxonservice/v1/taxa/names"
SPECIES_URL    = "https://api.artdatabanken.se/information/v1/speciesdataservice/v1/speciesdata"

# TLS
TLS_BASE       = os.getenv("TLS_BASE", "https://api.artdatabanken.se/taxonlistservice/v1")
TLS_DEFS_URL   = f"{TLS_BASE}/definitions"
TLS_TAXA_URL   = f"{TLS_BASE}/taxa"

# Zmieniane w locie
INPUT_FILE: str = ""
OUTPUT_WITH_DATA: str = ""
OUTPUT_PROTECTED: str = ""
LOG_FILE: str = ""
RISKLISTA_FILE: str = ""
DEBUG: bool = False
DEBUG_ROWS: List[Dict[str, Any]] = []
GEIAA_DUMP_PATH: str = ""

# --- log ---
def ensure_dir(path: str):
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    if LOG_FILE:
        ensure_dir(os.path.dirname(LOG_FILE))
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

def json_safe(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        url = getattr(resp, "url", "?")
        log(f"‼ Nie-JSON z {url} [{getattr(resp,'status_code','?')}] — body: {getattr(resp,'text','')[:200]!r}")
        return {}

# --- normalizacje ---
_CLEAN_SCI_RE = re.compile(r"\b(sp\.|cf\.|aff\.|nr\.|gr\.)\b|[\?\(\)\[\]]", re.IGNORECASE)
_DEFUZZ = {"´": "'", "`": "'", "—": "-", "–": "-"}

def clean_scientific(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = _CLEAN_SCI_RE.sub("", (name or "").strip())
    return re.sub(r"\s+", " ", s)

def clean_swedish(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = (name or "").strip()
    for k, v in _DEFUZZ.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s)

def normkey(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "").strip()).lower()

def bool_to_ja(v) -> str:
    if isinstance(v, bool):
        return "Ja" if v else ""
    s = str(v).strip().lower()
    if s in {"true", "1", "ja", "yes", "y"}:
        return "Ja"
    return ""

# === TaxonId resolve ===
def query_taxon_id_by_name(name: str, field: str) -> int:
    params = {
        "searchString": name,
        "searchFields": field,
        "isRecommended": "NotSet",
        "isOkForObservationSystems": "NotSet",
        "culture": "sv_SE",
        "page": 1,
        "pageSize": 100,
    }
    r = requests.get(TAXON_NAME_URL, headers=HEADERS_TAXON, params=params, timeout=TIMEOUT)
    if r.status_code != 200:
        log(f"Błąd {r.status_code} dla '{name}' ({field}): {r.text[:200]!r}")
        return 0
    data = (r.json() or {}).get("data", []) if r.content else []
    if not data:
        return 0
    name_l = (name or "").lower()

    def _tid(item):
        return int(((item or {}).get("taxonInformation") or {}).get("taxonId", 0) or 0)

    exact = [d for d in data if any((
        str(d.get("displayName", "")).lower() == name_l,
        str(d.get("swedishName", "")).lower() == name_l,
        str(d.get("scientificName", "")).lower() == name_l,
    ))]
    if exact:
        return _tid(exact[0])
    rec = [d for d in data if d.get("isRecommended") is True]
    return _tid(rec[0] if rec else data[0])

def resolve_taxon_id(row: Dict[str, Any]) -> int:
    swe = str(row.get("taxon_svensktNamn", "") or "").strip()
    sci = str(row.get("taxon_vetenskapligtNamn", "") or "").strip()
    if swe:
        tid = query_taxon_id_by_name(swe, "Swedish")
        if tid:
            return tid
        cs = clean_swedish(swe)
        if cs and cs != swe:
            tid = query_taxon_id_by_name(cs, "Swedish")
            if tid:
                return tid
    if sci:
        csci = clean_scientific(sci)
        for cand in (csci, sci):
            if cand:
                tid = query_taxon_id_by_name(cand, "Scientific")
                if tid:
                    return tid
    log(f"Brak TaxonId — swe='{swe}' sci='{sci}'")
    return 0

# === TLS: /definitions + /taxa ===
_TLS_DEFS: Dict[int, str] = {}
_TLS_CATSETS: Dict[str, Set[int]] = {}
_TLS_DEFS_READY = False
_TLS_MEMBERS: Dict[str, Set[int]] = {}

def _norm(s: str) -> str:
    return normkey(s).replace("å", "a").replace("ä", "a").replace("ö", "o")

def fetch_tls_definitions():
    global _TLS_DEFS, _TLS_CATSETS, _TLS_DEFS_READY
    _TLS_DEFS, _TLS_CATSETS, _TLS_DEFS_READY = {}, {}, False
    try:
        r = requests.get(TLS_DEFS_URL, headers=HEADERS_LISTS, timeout=TIMEOUT)
        if r.status_code != 200:
            log(f"TLS /definitions {r.status_code}: {r.text[:160]!r}")
            return
        defs = json_safe(r) or {}
        lists = defs.get("conservationLists", []) or []
        for it in lists:
            lid = it.get("id")
            name = it.get("name") or ""
            if isinstance(lid, int) and name:
                _TLS_DEFS[lid] = name

        def find_ids_by_contains(substrs: List[str]) -> Set[int]:
            out: Set[int] = set()
            for lid, name in _TLS_DEFS.items():
                n = _norm(name)
                if any(sub in n for sub in substrs):
                    out.add(lid)
            return out

        _TLS_CATSETS = {
            "CITES": find_ids_by_contains(["cites"]),
            "Bernkonventionen": find_ids_by_contains(["bern"]),
            "Bonnkonventionen": find_ids_by_contains(["bonn", "cms"]),
            "FågeldirektivetBilaga1": find_ids_by_contains(["fageldirektivet bilaga 1", "fågeldirektivet bilaga 1"]),
            "PrioriteradeFågelarterSkogsvårdslagen": find_ids_by_contains([
                "prioriterade fagelarter i skogsvardslagen",
                "prioriterade fågelarter i skogsvårdslagen",
                "skogsvardslagen","skogsvårdslagen"
            ]),
            "Fridlyst": find_ids_by_contains(["fridlysta arter", "fridlysta faglar", "fridlysta fåglar", "fridlysta"]),
        }
        _TLS_CATSETS.update({
            "Habitat_Bilaga2": find_ids_by_contains(["habitatdirektivets bilaga 2","habitatdirektivet bilaga 2","bilaga 2"]),
            "Habitat_Bilaga2_Prio": find_ids_by_contains(["habitatdirektivets bilaga 2","habitatdirektivet bilaga 2","prioriterad","prioriterade","priority"]),
            "Habitat_Bilaga4": find_ids_by_contains(["habitatdirektivets bilaga 4","habitatdirektivet bilaga 4","bilaga 4"]),
            "Habitat_Bilaga5": find_ids_by_contains(["habitatdirektivets bilaga 5","habitatdirektivet bilaga 5","bilaga 5"]),
        })
        _TLS_CATSETS.update({
            "IAS_Union_EU": find_ids_by_contains(["invasiv","invasiva","frammande","eu-forteckning","eu forteckning","unionsforteckning","union list","eu list"]),
        })

        _TLS_DEFS_READY = True
        for cat, ids in _TLS_CATSETS.items():
            sample = ", ".join([f"{i}:{_TLS_DEFS.get(i,'')[:28]}" for i in list(sorted(ids))[:6]])
            log(f"  → {cat}: {len(ids)} id ({sample})")
    except Exception as e:
        log(f"TLS /definitions wyjątek: {e}")

def tls_fetch_members_for_list_ids(list_ids: Set[int]) -> Set[int]:
    if not list_ids:
        return set()
    try:
        payload = {"conservationListIds": sorted(list(list_ids)), "outputFields": ["id"]}
        r = requests.post(TLS_TAXA_URL, headers=HEADERS_LISTS, json=payload, timeout=TIMEOUT)
        if r.status_code != 200 or not r.content:
            log(f"TLS /taxa {r.status_code} — {r.text[:200]!r}")
            return set()
        data = json_safe(r)

        members: Set[int] = set()
        def walk(x):
            if isinstance(x, dict):
                if "id" in x and isinstance(x.get("id"), int):
                    members.add(int(x["id"]))
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for it in x:
                    walk(it)
        walk(data)
        if members:
            preview = ", ".join(str(i) for i in sorted(list(members))[:12])
            log(f"     ↳ członków: {len(members)} (przykład: {preview})")
        else:
            log("     ↳ członków: 0")
        return members
    except Exception as e:
        log(f"TLS /taxa wyjątek: {e}")
        return set()

_TLS_MEMBERS: Dict[str, Set[int]] = {}
def tls_build_memberships():
    global _TLS_MEMBERS
    _TLS_MEMBERS = {}
    for cat, ids in _TLS_CATSETS.items():
        mem = tls_fetch_members_for_list_ids(ids)
        _TLS_MEMBERS[cat] = mem
        log(f"TLS /taxa: {cat} — {len(mem)} taxa")

def tls_flags_by_membership(tid: int) -> Dict[str, str]:
    def hit(cat: str) -> str:
        return "Ja" if tid in _TLS_MEMBERS.get(cat, set()) else ""
    return {
        "CITES": hit("CITES"),
        "Bernkonventionen": hit("Bernkonventionen"),
        "Bonnkonventionen": hit("Bonnkonventionen"),
        "FågeldirektivetBilaga1": hit("FågeldirektivetBilaga1"),
        "PrioriteradeFågelarterSkogsvårdslagen": hit("PrioriteradeFågelarterSkogsvårdslagen"),
        "Fridlyst": hit("Fridlyst"),
        "DirectiveAppendix2": hit("Habitat_Bilaga2"),
        "DirectiveAppendix2Priority": hit("Habitat_Bilaga2_Prio"),
        "DirectiveAppendix4": hit("Habitat_Bilaga4"),
        "DirectiveAppendix5": hit("Habitat_Bilaga5"),
        "IAS_Union_EU": hit("IAS_Union_EU"),
    }

# === RISKLISTA 2024 (IAS + fallback GEIAA 4 pola) ===
def try_read_table(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(path)
    if ext in (".csv", ".tsv"):
        sep = ";" if ext == ".csv" else "\t"
        try:
            return pd.read_csv(path, sep=sep)
        except Exception:
            return pd.read_csv(path)
    raise ValueError("Nieobsługiwany format pliku Risklista: " + ext)

def _ascii(s: str) -> str:
    return (s or "").lower().replace("å","a").replace("ä","a").replace("ö","o")

def build_risk_join_keys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normkey(c) for c in df.columns]

    # rozpoznaj kolumny
    def pick(col_needles: List[str]) -> str:
        for c in df.columns:
            lc = _ascii(c)
            if any(n in lc for n in col_needles):
                return c
        return ""

    cand_tax = pick(["taxonid", "taxon id"])
    cand_sci = pick(["vetenskap", "scientific"])
    cand_swe = pick(["svensk", "svenskt", "art", "namn"])
    risk_col = pick(["riskklass", "riskkategori", "riskkategori"])
    flag_col = pick(["ias", "invas", "framn", "främmande", "inwazy"])

    # cztery pola GEIAA:
    c_status   = pick(["artens status"])
    c_ursprung = pick(["ursprunglig utbredning", "ursprunglig utbred"])
    c_risk     = pick(["riskkategori, utfall", "riskkategori", "utfall enligt geiaa"])
    c_kriter   = pick(["utslagsgivande kriterier", "utslagsgivande", "kriterier"])

    if cand_tax:
        df["__RID_TaxonId__"] = pd.to_numeric(df[cand_tax], errors="coerce").astype("Int64")
    else:
        df["__RID_TaxonId__"] = pd.Series([pd.NA]*len(df), dtype="Int64")
    df["__RID_Sci__"] = df[cand_sci].map(lambda x: normkey(clean_scientific(str(x)))) if cand_sci else ""
    df["__RID_Swe__"] = df[cand_swe].map(lambda x: normkey(clean_swedish(str(x))))   if cand_swe else ""

    df["__RID_Risk__"] = df[risk_col].astype(str) if risk_col else ""
    df["__RID_Flag__"] = df[flag_col].astype(str) if flag_col else ""

    # dodatkowe: przenieś surowe kolumny GEIAA-jeśli są
    if c_status:   df["__RID_GEIAA_Status__"]   = df[c_status].astype(str)
    if c_ursprung: df["__RID_GEIAA_Ursprung__"] = df[c_ursprung].astype(str)
    if c_risk:     df["__RID_GEIAA_RiskTxt__"]  = df[c_risk].astype(str)
    if c_kriter:   df["__RID_GEIAA_Kriter__"]   = df[c_kriter].astype(str)

    return df

def attach_risklista(merged: pd.DataFrame, risk_path: str) -> pd.DataFrame:
    """
    Scal z Risklista 2024:
      • klasy IAS (IAS_Risklista2024, IAS_Riskklass2024, IAS_Källa)
      • 4 pola GEIAA (fallback)
      • rozszerzone opisy IAS (Summering, Invasionspotential, Ekologisk effekt, Efekt av klimat…, Naturvärde…)
    """
    def try_read_table(path: str) -> pd.DataFrame:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".xlsx", ".xlsm", ".xls"):
            return pd.read_excel(path)
        if ext in (".csv", ".tsv"):
            sep = ";" if ext == ".csv" else "\t"
            try:
                return pd.read_csv(path, sep=sep)
            except Exception:
                return pd.read_csv(path)
        raise ValueError("Nieobsługiwany format pliku Risklista: " + ext)

    def normkey(x: str) -> str:
        return re.sub(r"\s+", " ", (str(x) if x is not None else "").strip()).lower()

    def clean_scientific(name: str) -> str:
        s = re.sub(r"\b(sp\.|cf\.|aff\.|nr\.|gr\.)\b|[\?\(\)\[\]]", "", (name or ""), flags=re.I).strip()
        return re.sub(r"\s+", " ", s)

    def clean_swedish(name: str) -> str:
        if not isinstance(name, str):
            return ""
        s = name.strip().replace("´","'").replace("`","'").replace("—","-").replace("–","-")
        return re.sub(r"\s+", " ", s)

    def _ascii(s: str) -> str:
        return (s or "").lower().replace("å","a").replace("ä","a").replace("ö","o")

    # ---- wczytaj Risklista
    try:
        src = try_read_table(risk_path)
    except Exception as e:
        log(f"Risklista: nie udało się wczytać '{risk_path}': {e}")
        return merged

    r = src.copy()
    r_cols_norm = {c: normkey(c) for c in r.columns}

    # heurystyki do odnajdywania kolumn
    def pick(needles: list[str]) -> str:
        for c in r.columns:
            lc = _ascii(c)
            if any(n in lc for n in needles):
                return c
        return ""

    c_tax = pick(["taxonid", "taxon id"])
    c_sci = pick(["vetenskap", "scientific"])
    c_swe = pick(["svensk", "svenskt", "art", "namn"])

    c_riskklass = pick(["riskklass", "riskkategori"])
    c_flag      = pick(["ias", "invas", "framn", "främmande", "inwazy"])

    # 4 klasyczne pola GEIAA
    c_geiaa_status   = pick(["artens status"])
    c_geiaa_ursprung = pick(["ursprunglig utbred"])
    c_geiaa_risktxt  = pick(["riskkategori, utfall", "utfall enligt geiaa", "riskkategori"])
    c_geiaa_kriter   = pick(["utslagsgivande kriter"])

    # rozszerzone opisy IAS (próbujemy różne warianty nazw)
    c_summering = pick(["summering","sammanfatt"])
    c_invasion  = pick(["invasionspotential"])
    c_eko_eff   = pick(["ekologisk effekt","ekologisk effekt"])
    c_klimat    = pick(["effekt av klimat","klimatforand"])
    c_natvard   = pick(["naturvarde","naturvard"])

    # klucze łączeń
    r["__RID_TaxonId__"] = pd.to_numeric(r[c_tax], errors="coerce").astype("Int64") if c_tax else pd.Series([pd.NA]*len(r), dtype="Int64")
    r["__RID_Sci__"] = r[c_sci].map(lambda x: normkey(clean_scientific(str(x)))) if c_sci else ""
    r["__RID_Swe__"] = r[c_swe].map(lambda x: normkey(clean_swedish(str(x))))   if c_swe else ""

    # pomocnicze kolumny z Risklista
    if c_riskklass: r["__RID_Risk__"] = r[c_riskklass].astype(str)
    if c_flag:      r["__RID_Flag__"] = r[c_flag].astype(str)

    # GEIAA 4 pola (surowe)
    if c_geiaa_status:   r["__RID_GEIAA_Status__"]   = r[c_geiaa_status].astype(str)
    if c_geiaa_ursprung: r["__RID_GEIAA_Ursprung__"] = r[c_geiaa_ursprung].astype(str)
    if c_geiaa_risktxt:  r["__RID_GEIAA_RiskTxt__"]  = r[c_geiaa_risktxt].astype(str)
    if c_geiaa_kriter:   r["__RID_GEIAA_Kriter__"]   = r[c_geiaa_kriter].astype(str)

    # rozbudowane opisy
    if c_summering: r["__RID_IAS_Summering__"] = r[c_summering].astype(str)
    if c_invasion:  r["__RID_IAS_Invasion__"]  = r[c_invasion].astype(str)
    if c_eko_eff:   r["__RID_IAS_Ekologi__"]   = r[c_eko_eff].astype(str)
    if c_klimat:    r["__RID_IAS_Klimat__"]    = r[c_klimat].astype(str)
    if c_natvard:   r["__RID_IAS_Naturv__"]    = r[c_natvard].astype(str)

    out = merged.copy()
    out["__JOIN_Swe__"] = out.get("SwedishName", out.get("taxon_svensktNamn","")).map(lambda x: normkey(clean_swedish(str(x))))
    out["__JOIN_Sci__"] = out.get("ScientificName", out.get("taxon_vetenskapligtNamn","")).map(lambda x: normkey(clean_scientific(str(x))))

    # 3-krotne łączenie (TaxonId / Scientific / Swedish)
    m = out.merge(r[[c for c in r.columns if c.startswith("__RID_")]],
                  left_on="TaxonId", right_on="__RID_TaxonId__", how="left")
    m2 = m.merge(
        r[[c for c in r.columns if c.startswith("__RID_")]].rename(columns={k: f"{k}__2" for k in r.columns if k.startswith("__RID_")}),
        left_on="__JOIN_Sci__", right_on="__RID_Sci____2", how="left"
    )
    m3 = m2.merge(
        r[[c for c in r.columns if c.startswith("__RID_")]].rename(columns={k: f"{k}__3" for k in r.columns if k.startswith("__RID_")}),
        left_on="__JOIN_Swe__", right_on="__RID_Swe____3", how="left"
    )

    def coalesce(*vals):
        for v in vals:
            if pd.notna(v) and str(v).strip() not in {"", "nan", "none", "None"}:
                return v
        return ""

    # IAS: risk + flaga
    IAS_RISK, IAS_FLAG = [], []
    for a, b, c, fa, fb, fc in zip(
        m3.get("__RID_Risk__", []), m3.get("__RID_Risk____2", []), m3.get("__RID_Risk____3", []),
        m3.get("__RID_Flag__", []), m3.get("__RID_Flag____2", []), m3.get("__RID_Flag____3", [])
    ):
        IAS_RISK.append(coalesce(a, b, c))
        IAS_FLAG.append(coalesce(fa, fb, fc))

    def _yesish(x: str) -> bool:
        return str(x).strip().lower() in {"ja", "true", "1", "x", "yes", "y"}

    fallback_flag = ["Ja" if _yesish(f) else "" for f in IAS_FLAG]
    m3["IAS_Riskklass2024"] = IAS_RISK
    m3["IAS_Risklista2024"] = [
        ("Ja" if str(k).strip() not in {"", "0", "nan", "None", "-"} else (fallback_flag[i]))
        for i, k in enumerate(m3["IAS_Riskklass2024"])
    ]
    m3["IAS_Källa"] = os.path.basename(risk_path)

    # 4 kolumny GEIAA — uzupełniamy tylko puste
    def co_copy(dst_col, *srcs):
        vals = []
        for i in range(len(m3)):
            vals.append(str(coalesce(*[m3[s].iloc[i] if s in m3.columns else "" for s in srcs])))
        if dst_col not in m3.columns:
            m3[dst_col] = vals
        else:
            m3[dst_col] = [m3[dst_col].iloc[i] if str(m3[dst_col].iloc[i]).strip() not in {"","nan","None"} else vals[i] for i in range(len(m3))]

    co_copy("Artens status", "GEIAA_Status", "__RID_GEIAA_Status__", "__RID_GEIAA_Status____2", "__RID_GEIAA_Status____3")
    co_copy("Ursprunglig utbredning", "GEIAA_Ursprung", "__RID_GEIAA_Ursprung__", "__RID_GEIAA_Ursprung____2", "__RID_GEIAA_Ursprung____3")
    co_copy("Riskkategori, utfall enligt GEIAA metodik", "GEIAA_RiskTxt", "__RID_GEIAA_RiskTxt__", "__RID_GEIAA_RiskTxt____2", "__RID_GEIAA_RiskTxt____3")
    co_copy("Utslagsgivande kriterier", "GEIAA_Kriter", "__RID_GEIAA_Kriter__", "__RID_GEIAA_Kriter____2", "__RID_GEIAA_Kriter____3")

    # >>> Rozszerzone opisy IAS (przenosimy 1:1 z Risklista jeśli są) <<<
    extended_map = {
        "Summering": ["__RID_IAS_Summering__", "__RID_IAS_Summering____2", "__RID_IAS_Summering____3"],
        "Invasionspotential": ["__RID_IAS_Invasion__", "__RID_IAS_Invasion____2", "__RID_IAS_Invasion____3"],
        "Ekologisk effekt": ["__RID_IAS_Ekologi__", "__RID_IAS_Ekologi____2", "__RID_IAS_Ekologi____3"],
        "Effekt av klimatförändringar": ["__RID_IAS_Klimat__", "__RID_IAS_Klimat____2", "__RID_IAS_Klimat____3"],
        "Naturvärde": ["__RID_IAS_Naturv__", "__RID_IAS_Naturv____2", "__RID_IAS_Naturv____3"],
    }
    for dst, srcs in extended_map.items():
        co_copy(dst, *srcs)

    # sprzątanie
    drop_cols = [c for c in m3.columns if c.startswith("__RID_") or c.startswith("__JOIN_")]
    m3.drop(columns=drop_cols, inplace=True, errors="ignore")
    return m3

# === UI / CLI ===
def pick_paths_via_gui() -> Tuple[str, str, str]:
    root = tk.Tk(); root.withdraw()
    filetypes = [("Excel", "*.xlsx"), ("All files", "*.*")]
    in_path = filedialog.askopenfilename(title="Välj Excel (AGOL-tabell)", filetypes=filetypes)
    if not in_path:
        return "", "", ""
    out_dir = filedialog.askdirectory(title="Välj målmapp (output)", initialdir=os.path.dirname(in_path))
    if not out_dir:
        out_dir = os.path.dirname(in_path)
    risk_path = filedialog.askopenfilename(
        title="Välj Risklista 2024 (valfritt, Avbryt om inte)",
        filetypes=[("Excel/CSV", "*.xlsx;*.csv;*.tsv"), ("All files", "*.*")]
    )
    return in_path, out_dir, (risk_path or "")

def resolve_io_paths(args) -> Tuple[str, str, str]:
    in_path = args.input or ""
    out_dir = args.outdir or ""
    risk_path = args.risklista or ""
    if not in_path and GUI_OK and not args.no_gui:
        in_path, out_dir, rp = pick_paths_via_gui()
        risk_path = risk_path or rp
    if not in_path:
        raise SystemExit("[BŁĄD] Nie podano pliku wejściowego (użyj --input lub GUI).")
    if not out_dir:
        out_dir = os.path.dirname(in_path)
    ensure_dir(out_dir)
    if not risk_path:
        for cand in ["risklista2024.xlsx","Risklista2024.xlsx","Riskklassning2024.xlsx","Riskklassning.xlsx","risklista2024.csv"]:
            guess = os.path.join(os.path.dirname(in_path), cand)
            if os.path.exists(guess):
                risk_path = guess
                break
    return in_path, out_dir, (risk_path or "")

# === pomocnicze: pobieranie alienSpeciesRa kilkoma wariantami ===
def fetch_alien_ra_variants(tid: int) -> Tuple[Dict[str, Any], str]:
    attempts = [
        ("params_sv_dash",   {"mode":"params", "params":{"taxa": tid, "culture": "sv-SE"}}),
        ("params_sv_under",  {"mode":"params", "params":{"taxa": tid, "culture": "sv_SE"}}),
        ("query_no_culture", {"mode":"url",    "url": f"{SPECIES_URL}?taxa={tid}"}),
        ("params_en_gb",     {"mode":"params", "params":{"taxa": tid, "culture": "en-GB"}}),
    ]
    for label, opt in attempts:
        try:
            if opt["mode"]=="url":
                r = requests.get(opt["url"], headers=HEADERS_SPECIES, timeout=TIMEOUT)
            else:
                r = requests.get(SPECIES_URL, headers=HEADERS_SPECIES, params=opt["params"], timeout=TIMEOUT)
            if r.status_code==200 and r.content:
                data = json_safe(r)
                item = (data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {})
                obj = item.get("speciesData", item) or {}
                alien = obj.get("alienSpeciesRa", {}) or {}
                if alien:
                    return alien, label
        except Exception:
            pass
    return {}, ""

# === PIPELINE ===
def run_pipeline(input_file: str, out_dir: str, prefer_tls: bool, risklista_path: str, debug: bool):
    global INPUT_FILE, OUTPUT_WITH_DATA, OUTPUT_PROTECTED, LOG_FILE, RISKLISTA_FILE, DEBUG, DEBUG_ROWS, GEIAA_DUMP_PATH
    INPUT_FILE = input_file
    OUTPUT_WITH_DATA = os.path.join(out_dir, os.path.splitext(os.path.basename(INPUT_FILE))[0] + "_with_data.xlsx")
    OUTPUT_PROTECTED = os.path.join(out_dir, os.path.splitext(os.path.basename(INPUT_FILE))[0] + "_bara_skyddade.xlsx")
    LOG_FILE = os.path.join(out_dir, "log.txt")
    RISKLISTA_FILE = risklista_path
    DEBUG = bool(debug)
    DEBUG_ROWS = []
    GEIAA_DUMP_PATH = os.path.join(out_dir, "geiaa_dump.jsonl")

    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    if DEBUG and os.path.exists(GEIAA_DUMP_PATH):
        os.remove(GEIAA_DUMP_PATH)

    ensure_dir(out_dir)
    log(f"Start przetwarzania: {INPUT_FILE}")

    # TLS init
    if prefer_tls:
        fetch_tls_definitions()
        if _TLS_DEFS_READY:
            tls_build_memberships()
        else:
            log("TLS: /definitions niedostępne — będę polegał na fallbackach.")

    # Wczytaj dane
    df = pd.read_excel(INPUT_FILE, engine="openpyxl")
    if "taxon_svensktNamn" not in df.columns:
        raise ValueError("Brak wymaganej kolumny 'taxon_svensktNamn' w pliku Excel.")

    # 1) TaxonId
    log("Etap 1: wyznaczanie TaxonId…")
    taxon_ids: List[int] = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        rec = row.to_dict()
        tid = resolve_taxon_id(rec)
        taxon_ids.append(tid)
        if i % 20 == 0:
            log(f"→ {i}/{len(df)} rekordów — ostatni TaxonId={tid}")
        time.sleep(NAME_QUERY_SLEEP)
    df["TaxonId"] = pd.Series(taxon_ids, dtype="int64")
    log("Dodano kolumnę TaxonId.")

    uniq_ids = sorted(set(t for t in taxon_ids if t and t > 0))
    log(f"Unikalnych TaxonId > 0: {len(uniq_ids)}")

    # 2) SpeciesDataService + TLS-membership
    log("Etap 2: pobieranie danych z SpeciesDataService…")

    cols = [
        "ScientificName","SwedishName","DisplayName","Category","ConservationStatus","CITES","Bernkonventionen","Bonnkonventionen","PrioriteradeFågelarterSkogsvårdslagen","FågeldirektivetBilaga1","minskande_faglar",
        "Fridlyst","Frid_text","ProtectedByWorkProtectionConstitution","ProtectedBirds",
        "DirectiveAppendix2","DirectiveAppendix2Priority","DirectiveAppendix4","DirectiveAppendix5",
        "Artikel 17 - 2019", "ForestrySignal","ForestrySignalSpecies",
        "RedListCategory","RedListCriterion","RedListPeriodName","RedListCriterionText",
        "ActionProgramName","ActionProgramStatus","ActionProgramStart","ActionProgramEnd",
        "TypicalSpecies","LandscapeType","Biotopes",
        "Characteristic","SpreadAndStatus","Ecology","Threat","ConservationMeasures","Other",
        "SwedishPresence","ImmigrationHistory","SubstrateInformation","EcologicalGroups",
        "ConservationEcology","ConservationNatureConservation","ConservationTreeSpecies",
        # GEIAA / Alien species (z API)
        "AlienSpeciesRiskCategories","AlienSpeciesEnvironments","AlienSpeciesEcologyEffect",
        "AlienSpeciesTaxonLists","AlienSpeciesInvationPotentials","AlienSpeciesRegions",
        # TLS IAS Union list:
        "IAS_Union_EU",
        # Fallback GEIAA z Risklista (nazwy jak w AGOL)
        "Artens status","Ursprunglig utbredning","Riskkategori, utfall enligt GEIAA metodik","Utslagsgivande kriterier"
    ]

    rows: List[Dict[str, Any]] = []

    for k, tid in enumerate(uniq_ids, start=1):
        log(f"— {k}/{len(uniq_ids)} — TaxonId={tid}")
        rowvals: Dict[str, Any] = {c: "" for c in cols}
        dbg: Dict[str, Any] = {"TaxonId": tid}

        try:
            # główne pobranie (jak dotąd)
            resp = requests.get(SPECIES_URL, headers=HEADERS_SPECIES, params={"taxa": tid, "culture": "sv-SE"}, timeout=TIMEOUT)
            data = json_safe(resp) if resp.status_code == 200 else {}
            item = (data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {})
            obj = item.get("speciesData", item) or {}

            def gv(*keys, default=""):
                o: Any = obj
                for ky in keys:
                    if isinstance(o, dict):
                        o = o.get(ky)
                    else:
                        o = None
                return o if (o is not None and o != "") else default

            rowvals["ScientificName"] = obj.get("scientificName") or item.get("scientificName") or ""
            rowvals["SwedishName"]    = gv("swedishName")
            rowvals["DisplayName"]    = gv("displayName")
            rowvals["Category"]       = gv("category", "name")
            rowvals["ConservationStatus"] = gv("conservationStatus")

            # Redlist
            redlist_info = obj.get("redlistInfo", []) or []
            red = select_current_or_latest_redlist(redlist_info)
            rowvals["RedListCategory"]     = (red or {}).get("category", "")
            rowvals["RedListCriterion"]    = (red or {}).get("criterion", "")
            rowvals["RedListPeriodName"]   = ((red or {}).get("period") or {}).get("name", "")
            rowvals["RedListCriterionText"]= (red or {}).get("criterionText", "")

            # TLS MEMBERSHIP
            tls_flags = tls_flags_by_membership(tid) if (_TLS_DEFS_READY and _TLS_MEMBERS) else {}

            nc = obj.get("natureConservation", {}) or {}
            act = nc.get("actionProgram", {}) or {}
            rowvals["ActionProgramName"]   = act.get("program", "")
            rowvals["ActionProgramStatus"] = act.get("status", "")
            rowvals["ActionProgramStart"]  = act.get("startYear", "")
            rowvals["ActionProgramEnd"]    = act.get("endYear", "")

            rowvals["ForestrySignal"] = ((nc.get("forestryBoardSignalSpecies", {}) or {}).get("apply")) or ""
            fss = (nc.get("forestryBoardSignalSpecies") or {})
            fs_names = []
            def _add_names(val):
                if isinstance(val, list):
                    for el in val:
                        if isinstance(el, dict):
                            nm = el.get("name") or el.get("swedishName") or el.get("displayName") or el.get("scientificName")
                            if nm: fs_names.append(str(nm))
                        elif isinstance(el, str) and el.strip():
                            fs_names.append(el.strip())
                elif isinstance(val, dict):
                    nm = val.get("name") or val.get("swedishName") or val.get("displayName") or val.get("scientificName")
                    if nm: fs_names.append(str(nm))
                elif isinstance(val, str) and val.strip():
                    fs_names.append(val.strip())
            if isinstance(fss, dict):
                for key in ("speciesNames","species","names","speciesList","items"):
                    _add_names(fss.get(key))
            elif isinstance(fss, list):
                _add_names(fss)
            rowvals["ForestrySignalSpecies"] = "; ".join(sorted(set(n for n in fs_names if n)))

            rowvals["TypicalSpecies"] = "; ".join(sorted(set(
                (t.get("name") or t.get("typical") or "") + (f" ({', '.join(t.get('regions', []) or [])})" if t.get("regions") else "")
                for t in (nc.get("typicalSpecies", []) or []) if (t.get("name") or t.get("typical"))
            )))
            rowvals["LandscapeType"]  = "; ".join(sorted(set(
                f"{it.get('name','')} ({it.get('status','')})" for it in (obj.get("landscapeTypes", []) or []) if it.get("name")
            )))
            rowvals["Biotopes"]       = "; ".join(sorted(set(
                f"{it.get('name','')} ({it.get('significance','')})" for it in (obj.get("biotopes", []) or []) if it.get("name")
            )))

            lists = nc.get("lists", []) or []
            def any_child_named(_lists, target: str) -> str:
                def has(childs):
                    for c in childs or []:
                        if c.get("name","")==target: return True
                        if has(c.get("childs")): return True
                    return False
                for it in _lists or []:
                    if has(it.get("childs", [])): return "Ja"
                return ""
            def has_list_flag(_lists, list_name: str) -> str:
                ln = (list_name or "").strip().lower()
                for it in (_lists or []):
                    nm = str(it.get("name", "")).strip().lower()
                    title = str(it.get("title", "")).strip().lower()
                    if ln and (ln == nm or ln in nm or ln in title):
                        return "Ja"
                    if any_child_named([it], list_name) == "Ja":
                        return "Ja"
                return ""

            fb_cites = has_list_flag(lists, "CITES")
            fb_bern  = has_list_flag(lists, "Bernkonventionen")
            fb_bonn  = has_list_flag(lists, "Bonnkonventionen")
            fb_prio  = has_list_flag(lists, "Prioriterade fågelarter i skogsvårdslagen")
            fb_fd1   = has_list_flag(lists, "Fågeldirektivet bilaga 1")

            rowvals["CITES"] = tls_flags.get("CITES") or fb_cites
            rowvals["Bernkonventionen"] = tls_flags.get("Bernkonventionen") or fb_bern
            rowvals["Bonnkonventionen"] = tls_flags.get("Bonnkonventionen") or fb_bonn
            rowvals["PrioriteradeFågelarterSkogsvårdslagen"] = tls_flags.get("PrioriteradeFågelarterSkogsvårdslagen") or fb_prio
            rowvals["FågeldirektivetBilaga1"] = tls_flags.get("FågeldirektivetBilaga1") or fb_fd1
            rowvals["minskande_faglar"] = "Ja" if is_minskande_fagel(rowvals.get("SwedishName", ""), rowvals.get("ScientificName", ""), tid) else ""

            prot_txt = (obj.get("protectedText") or "").strip()
            frid_flag = tls_flags.get("Fridlyst") or has_list_flag(lists, "Fridlysta arter") or has_list_flag(lists, "Fridlysta fåglar")
            if not frid_flag and prot_txt and ("fridlyst" in prot_txt.lower()):
                frid_flag = "Ja"
            rowvals["Fridlyst"] = frid_flag or ""
            rowvals["Frid_text"] = prot_txt or ""

            sd_hd2  = bool_to_ja(nc.get("habitatDirectiveAppendix2") or nc.get("habitatdirectiveappendix2"))
            sd_hd2p = bool_to_ja(nc.get("habitatDirectiveAppendix2PrioritizedSpecie") or nc.get("habitatDirectiveAppendix2PrioritizedSpecies")
                                 or nc.get("habitatdirectiveappendix2prioritizedspecie") or nc.get("habitatdirectiveappendix2prioritizedspecies"))
            sd_hd4  = bool_to_ja(nc.get("habitatDirectiveAppendix4") or nc.get("habitatdirectiveappendix4"))
            sd_hd5  = bool_to_ja(nc.get("habitatDirectiveAppendix5") or nc.get("habitatdirectiveappendix5"))

            rowvals["DirectiveAppendix2"]          = tls_flags.get("DirectiveAppendix2")          or sd_hd2
            rowvals["DirectiveAppendix2Priority"]  = tls_flags.get("DirectiveAppendix2Priority")  or sd_hd2p
            rowvals["DirectiveAppendix4"]          = tls_flags.get("DirectiveAppendix4")          or sd_hd4
            rowvals["DirectiveAppendix5"]          = tls_flags.get("DirectiveAppendix5")          or sd_hd5

            rowvals["ProtectedByWorkProtectionConstitution"] = nc.get("protectedByWorkProtectionConstitution", "") or ""
            rowvals["ProtectedBirds"] = nc.get("protectedBirds", "") or ""

            # Artikel 17 - 2019
            art17 = ""
            ca = obj.get("conservationAssessments", {}) or {}
            for p in (ca.get("periods") or []):
                if "2019" in str(p.get("name", "")):
                    chunks = []
                    for t in p.get("trends", []) or []:
                        cat = t.get("category", ""); ev = t.get("evaluation", ""); tr = t.get("trend", "")
                        part = f"{cat}: {ev}{(' ('+tr+')') if tr else ''}"
                        if part.strip(): chunks.append(part)
                    art17 = "; ".join(chunks); break
            rowvals["Artikel 17 - 2019"] = art17

            sft = obj.get("speciesFactText", {}) or {}
            rowvals["Characteristic"] = sft.get("characteristic", "") or ""
            rowvals["SpreadAndStatus"] = sft.get("spreadAndStatus", "") or ""
            rowvals["Ecology"] = sft.get("ecology", "") or ""
            rowvals["Threat"] = sft.get("threat", "") or ""
            rowvals["ConservationMeasures"] = sft.get("conservationMeasures", "") or ""
            rowvals["Other"] = sft.get("other", "") or ""

            tri = obj.get("taxonRelatedInformation", {}) or {}
            rowvals["SwedishPresence"] = tri.get("swedishPresence", "") or ""
            rowvals["ImmigrationHistory"] = tri.get("immigrationHistory", "") or ""

            sub = obj.get("substrateInformation", []) or []
            rowvals["SubstrateInformation"] = "; ".join(sorted(set(f"{it.get('name','')} ({it.get('use','')})" for it in sub if it.get("name"))))

            eco = obj.get("ecologicalGroups", []) or []
            rowvals["EcologicalGroups"] = "; ".join(sorted(set(g.get("name", "") for g in eco if isinstance(g, dict) and g.get("active"))))

            ca2 = obj.get("conservationAssessments", {}) or {}
            rowvals["ConservationEcology"] = (ca2.get("ecology") or "")
            rowvals["ConservationNatureConservation"] = (ca2.get("natureConservation") or "")
            rowvals["ConservationTreeSpecies"] = (ca2.get("treeSpecies") or "")

            # === GEIAA / Alien species z głównej odpowiedzi
            alien = obj.get("alienSpeciesRa", {}) or {}

            # jeśli pusto — PRÓBY WARIANTÓW (jak w AP + dodatkowe)
            alt_used = ""
            if not alien:
                alien, alt_used = fetch_alien_ra_variants(tid)
                if alien:
                    log(f"   GEIAA alienSpeciesRa znalezione wariantem: {alt_used}")

            # zapis alien → nasze kolumny GEIAA (API)
            rowvals["AlienSpeciesRiskCategories"]     = "; ".join(alien.get("riskCategories", []) or [])
            rowvals["AlienSpeciesEnvironments"]       = "; ".join(alien.get("environments", []) or [])
            rowvals["AlienSpeciesEcologyEffect"]      = "; ".join(alien.get("ecologyEffect", []) or [])
            rowvals["AlienSpeciesTaxonLists"]         = "; ".join(str(x) for x in (alien.get("taxonLists", []) or []))
            rowvals["AlienSpeciesInvationPotentials"] = "; ".join(alien.get("invationPotentials", []) or [])
            rowvals["AlienSpeciesRegions"]            = "; ".join(alien.get("regions", []) or [])

            # IAS Union (z TLS)
            rowvals["IAS_Union_EU"] = tls_flags.get("IAS_Union_EU", "")

            if DEBUG:
                # skrót do CSV
                dbg.update({
                    "SwedishName": rowvals["SwedishName"],
                    "ScientificName": rowvals["ScientificName"],
                    "GEIAA_has_node": bool(alien),
                    "GEIAA_keys": ",".join(sorted(list(alien.keys()))) if isinstance(alien, dict) else "",
                    "GEIAA_variant": alt_used,
                })
                # twardy dump pełnego węzła do JSONL (to co weszło do tabeli)
                try:
                    with open(GEIAA_DUMP_PATH, "a", encoding="utf-8") as f:
                        rec = {
                            "TaxonId": tid,
                            "SwedishName": rowvals["SwedishName"],
                            "ScientificName": rowvals["ScientificName"],
                            "GEIAA_variant": alt_used,
                            "alienSpeciesRa": alien,
                        }
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                except Exception as dump_e:
                    log(f"Dump GEIAA błąd (TaxonId={tid}): {dump_e}")

        except Exception as e:
            log(f"Błąd dla TaxonId {tid}: {e}")

        rowvals["TaxonId"] = tid
        rows.append(rowvals)
        if DEBUG:
            DEBUG_ROWS.append(dbg)

        if k % 10 == 0:
            log(f"→ {k}/{len(uniq_ids)} taksonów ukończono")
        time.sleep(SPECIES_SLEEP)

    # Tabela wynikowa (unikaty + sort + URL)
    result = pd.DataFrame(rows)
    merged = df.merge(result, on="TaxonId", how="left")

    # Risklista 2024 (IAS + fallback 4 pól GEIAA, jeśli puste)
    if RISKLISTA_FILE and os.path.exists(RISKLISTA_FILE):
        log(f"Scalanie z Risklista 2024: {RISKLISTA_FILE}")
        merged = attach_risklista(merged, RISKLISTA_FILE)
    else:
        log("Risklista 2024: plik niepodany/nieznaleziony — pomijam.")

    # DEDUPE + SORT + URL
    RL_ORDER = {"RE":0, "CR":1, "EN":2, "VU":3, "NT":4, "LC":5, "DD":6, "NA":7, "NE":8}
    overview = merged[merged["TaxonId"] > 0].drop_duplicates(subset=["TaxonId"], keep="first").copy()
    overview["__rl_order__"] = overview.get("RedListCategory", "").map(RL_ORDER).fillna(99)
    overview.sort_values(["__rl_order__", "SwedishName", "ScientificName"], inplace=True, na_position="last")
    overview.drop(columns=["__rl_order__"], inplace=True)

    # URL
    def _mk_url(x):
        try:
            xi = int(x)
            return f"https://artfakta.se/taxa/{xi}/information" if xi > 0 else ""
        except Exception:
            return ""
    overview["URL"] = overview["TaxonId"].map(_mk_url)

    # wyczyść "Nej"/"False" w flagach
    flag_cols = ["CITES","Bernkonventionen","Bonnkonventionen",
                 "FågeldirektivetBilaga1","PrioriteradeFågelarterSkogsvårdslagen","Fridlyst",
                 "DirectiveAppendix2","DirectiveAppendix2Priority","DirectiveAppendix4","ProtectedByWorkProtectionConstitution","DirectiveAppendix5",
                 "IAS_Union_EU"]
    for c in flag_cols:
        if c in overview.columns:
            overview[c] = overview[c].astype(str).replace({"Nej":"", "nej":"", "False":"", "false":""})

    with pd.ExcelWriter(OUTPUT_WITH_DATA, engine="openpyxl") as w:
        overview.to_excel(w, index=False)
    log(f"Zapisano: {OUTPUT_WITH_DATA}")

    # bara_skyddade — bez IAS w filtrze
    log("Tworzenie _bara_skyddade…")
    protection_columns = [
        "ConservationStatus", "Artikel 17 - 2019", "TypicalSpecies", "CITES", "Bernkonventionen", "Bonnkonventionen",
        "PrioriteradeFågelarterSkogsvårdslagen", "FågeldirektivetBilaga1", "ProtectedByWorkProtectionConstitution",
        "ProtectedBirds", "DirectiveAppendix2", "DirectiveAppendix2Priority", "DirectiveAppendix4", "DirectiveAppendix5",
        "ForestrySignal", "ActionProgramStatus", "ActionProgramStart", "ActionProgramEnd", "ActionProgramName",
        "Fridlyst",
    ]
    def has_protection(row) -> bool:
        empty_vals = {"N/A", "", 0, "0", "Nej", None}
        for col in protection_columns:
            if row.get(col) not in empty_vals:
                return True
        return False

    filt = overview[overview.apply(lambda r: has_protection(r), axis=1)].copy()
    filt.replace(["N/A", "0", 0, None], "", inplace=True)

    filt["__rl_order__"] = filt.get("RedListCategory", "").map(RL_ORDER).fillna(99)
    filt.sort_values(["__rl_order__", "SwedishName", "ScientificName"], inplace=True, na_position="last")
    filt.drop(columns=["__rl_order__"], inplace=True)

    OUTPUT_PROTECTED = os.path.join(os.path.dirname(OUTPUT_WITH_DATA), os.path.splitext(os.path.basename(OUTPUT_WITH_DATA))[0].replace("_with_data","_bara_skyddade") + ".xlsx")
    with pd.ExcelWriter(OUTPUT_PROTECTED, engine="openpyxl") as w:
        filt.to_excel(w, index=False)
    log(f"Zapisano: {OUTPUT_PROTECTED}")

    # DEBUG
    if DEBUG:
        dbg_path = os.path.join(os.path.dirname(OUTPUT_WITH_DATA), "tls_debug.csv")
        try:
            pd.DataFrame(DEBUG_ROWS).to_csv(dbg_path, index=False, encoding="utf-8-sig")
            log(f"DEBUG zapisano: {dbg_path}")
        except Exception as e:
            log(f"DEBUG zapis CSV nieudany: {e}")

        def _sum_yes(df_, col):
            try:
                return int((df_.get(col,"").astype(str).str.lower() == "ja").sum())
            except Exception:
                return 0
        for col in flag_cols + ["Fridlyst"]:
            log(f"SUMA '{col}=Ja': {_sum_yes(overview, col)}")

        log(f"TWARDY DUMP GEIAA: {GEIAA_DUMP_PATH}")

    log("Proces zakończony sukcesem!")

# === CLI ===
def parse_args(argv=None):
    p = argparse.ArgumentParser(description="AGOL → Artfakta enrich (TLS /definitions + /taxa + Risklista 2024 + UI)")
    p.add_argument("--input", "-i", default="", help="Ścieżka do pliku Excel z AGOL")
    p.add_argument("--outdir", "-o", default="", help="Folder wyjściowy (domyślnie obok pliku)")
    p.add_argument("--risklista", "-r", default="", help="Plik Risklista 2024 (opcjonalnie; xlsx/csv)")
    p.add_argument("--prefer-tls", dest="prefer_tls", action="store_true", help="Preferuj Taxon List Service (ON)")
    p.add_argument("--no-prefer-tls", dest="prefer_tls", action="store_false", help="Wyłącz preferencję TLS")
    p.add_argument("--no-gui", action="store_true", help="Nie otwieraj okien dialogowych (tylko CLI)")
    p.add_argument("--debug", action="store_true", help="Włącz szczegółowe logowanie i tls_debug.csv + geiaa_dump.jsonl")
    p.set_defaults(prefer_tls=True)
    return p.parse_args(argv)

if __name__ == "__main__":
    args = parse_args()
    input_path, out_dir, risk_path = resolve_io_paths(args)
    run_pipeline(input_path, out_dir, prefer_tls=args.prefer_tls, risklista_path=risk_path, debug=args.debug)
