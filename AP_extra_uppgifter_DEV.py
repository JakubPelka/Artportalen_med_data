# -*- coding: utf-8 -*-
"""
AP_extra_uppgifter.py — Artportalen export → enrich

Wersja zsynchronizowana z AGOL:
• TLS: GET /definitions + POST /taxa → zestawy członków list dla:
  CITES, Bern, Bonn, Fågeldirektivet Bilaga 1, Prioriterade fågelarter i Skogsvårdslagen,
  Fridlyst, Habitatdirektivet (Bilaga 2 / 2-prio / 4 / 5) oraz IAS_Union_EU (UE-lista IAS).
• Fallback: speciesData.natureConservation.lists + protectedText.
• Frid_text z protectedText; Fridlyst = TLS-membership OR lists/protectedText.
• Filtr „skyddade”, porządek sortowania RL, czyszczenie „Nej/False → ""”.
• Tryb DEBUG (opcjonalny) + tls_debug.csv.

Uwaga:
• IAS_Union_EU jest dodane jako osobna kolumna i czyszczone z „Nej/False”,
  ale NIE jest uwzględniane w filtrze „bara_skyddade”.
"""

import os
import sys
import time
import re
import requests
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional, Set

# ==== KLUCZE I ENDPOINTY ====
TAXONOMY_KEY = os.getenv("TAXONOMY_KEY", "a2753962eba449bbbfdd253baf66fd26")
SPECIES_KEY  = os.getenv("SPECIES_KEY",  "71c0e472ab954c37896ee2d91f042ff1")
LISTS_KEY    = os.getenv("LISTS_KEY", os.getenv("SPECIESOBS_KEY", SPECIES_KEY))

NAME_QUERY_SLEEP = 0.08
SPECIES_SLEEP    = 0.08
TIMEOUT          = 30

TAXON_NAME_URL = "https://api.artdatabanken.se/taxonservice/v1/taxa/names"
SPECIES_URL    = "https://api.artdatabanken.se/information/v1/speciesdataservice/v1/speciesdata"

# TLS
TLS_BASE       = os.getenv("TLS_BASE", "https://api.artdatabanken.se/taxonlistservice/v1")
TLS_DEFS_URL   = f"{TLS_BASE}/definitions"
TLS_TAXA_URL   = f"{TLS_BASE}/taxa"   # POST {"conservationListIds":[...], "outputFields":["id"]}

HEADERS_TAXON   = {"Ocp-Apim-Subscription-Key": TAXONOMY_KEY, "Accept": "application/json"}
HEADERS_SPECIES = {"Ocp-Apim-Subscription-Key": SPECIES_KEY,   "Accept": "application/json", "Cache-Control": "no-cache"}
HEADERS_LISTS   = {"Ocp-Apim-Subscription-Key": LISTS_KEY,     "Accept": "application/json"}

# ==== TKINTER – wybór pliku/folderu i przełączniki ====
import tkinter as tk
from tkinter import filedialog, messagebox

def pick_inputs():
    root = tk.Tk(); root.withdraw()
    infile = filedialog.askopenfilename(
        title="Wybierz plik Excel z Artportalen",
        filetypes=[("Excel", "*.xlsx;*.xls"), ("Wszystkie pliki", "*.*")],
    )
    if not infile:
        sys.exit("Przerwano: nie wybrano pliku wejściowego.")
    outdir = filedialog.askdirectory(title="Wybierz folder zapisu wyników")
    if not outdir:
        outdir = os.path.dirname(infile)
    base = os.path.splitext(os.path.basename(infile))[0]

    want_full = messagebox.askyesno(
        "Dodatkowy plik?",
        "Czy wygenerować DODATKOWO pełną tabelę BEZ usuwania duplikatów (full_)?",
    )
    want_debug = messagebox.askyesno(
        "Tryb debug?",
        "Włączyć DEBUG (szerszy log + tls_debug.csv)?",
    )

    return {
        "INPUT_FILE": infile,
        "OUTDIR": outdir,
        "OUT_FULL": os.path.join(outdir, f"{base}_full_.xlsx"),
        "OUT_WITH": os.path.join(outdir, f"{base}_with_data.xlsx"),
        "OUT_PROT": os.path.join(outdir, f"{base}_bara_skyddade.xlsx"),
        "LOG_FILE": os.path.join(outdir, f"{base}_log.txt"),
        "DBG_FILE": os.path.join(outdir, "tls_debug.csv"),
        "WANT_FULL": want_full,
        "DEBUG": want_debug,
    }

# ==== LOG ====
LOG_FILE: Optional[str] = None
DEBUG: bool = False
DEBUG_ROWS: List[Dict[str, Any]] = []

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(line + "\n")
        except Exception:
            pass

# ==== UTILS ====
_CLEAN_SCI_RE = re.compile(r"\b(sp\.|cf\.|aff\.|nr\.|gr\.)\b|[\?\(\)\[\]]", re.IGNORECASE)
_DEFUZZ_REPLACEMENTS = {"´": "'", "`": "'", "—": "-", "–": "-"}

def json_safe(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        url = getattr(resp, 'url', '?'); sc = getattr(resp, 'status_code', '?'); tb = getattr(resp, 'text', '')
        log(f"‼ Nie-JSON z {url} [{sc}] — body: {tb[:200]!r}")
        return {}

def clean_scientific(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = _CLEAN_SCI_RE.sub("", (name or "").strip())
    return re.sub(r"\s+", " ", s)

def clean_swedish(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = (name or "").strip()
    for k, v in _DEFUZZ_REPLACEMENTS.items():
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

# ==== TAXON ID (gdy brak w wejściu) ====
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
    resp = requests.get(TAXON_NAME_URL, headers=HEADERS_TAXON, params=params, timeout=TIMEOUT)
    if resp.status_code != 200:
        log(f"Błąd {resp.status_code} przy wyszukiwaniu '{name}' ({field}): {resp.text[:200]!r}")
        return 0
    data = (resp.json() or {}).get("data", []) if resp.content else []
    if not data:
        return 0
    name_l = (name or "").lower()
    def _pick_id(item):
        ti = item.get("taxonInformation", {})
        return int(ti.get("taxonId", 0) or 0)
    exact = [d for d in data if any((
        str(d.get("displayName", "")).lower() == name_l,
        str(d.get("swedishName", "")).lower() == name_l,
        str(d.get("scientificName", "")).lower() == name_l,
    ))]
    if exact:
        return _pick_id(exact[0])
    recommended = [d for d in data if d.get("isRecommended") is True]
    if recommended:
        return _pick_id(recommended[0])
    return _pick_id(data[0])

def resolve_taxon_id(row, sv_col, sci_col) -> int:
    swe = str(row.get(sv_col, "") or "").strip() if sv_col else ""
    sci = str(row.get(sci_col, "") or "").strip() if sci_col else ""
    if swe:
        tid = query_taxon_id_by_name(swe, "Swedish")
        if tid: return tid
        cs = clean_swedish(swe)
        if cs and cs != swe:
            tid = query_taxon_id_by_name(cs, "Swedish")
            if tid: return tid
    if sci:
        csci = clean_scientific(sci)
        for cand in (csci, sci):
            if cand:
                tid = query_taxon_id_by_name(cand, "Scientific")
                if tid: return tid
    log(f"Brak TaxonId — swe='{swe}' sci='{sci}'")
    return 0

# ====== SpeciesDataService helpers ======
def extract_child_names(childs):
    out = []
    for c in (childs or []):
        nm = c.get("name")
        if nm:
            out.append(nm)
        if c.get("childs"):
            out.extend(extract_child_names(c.get("childs")))
    return out

def any_child_named(lists, target: str) -> str:
    def has_child_named(childs, name):
        for c in childs or []:
            if c.get("name", "") == name:
                return True
            if c.get("childs") and has_child_named(c["childs"], name):
                return True
        return False
    for it in lists or []:
        if has_child_named(it.get("childs", []), target):
            return "Ja"
    return ""

def join_name_with_attr(items, key, sub=None, sep=", "):
    if not items: return ""
    if sub:
        vals = [f"{it.get(key,'')} ({it.get(sub,'')})" for it in items if it.get(key)]
    else:
        vals = [str(it.get(key, "")) for it in items if it.get(key)]
    vals = sorted(set(v for v in vals if v))
    return sep.join(vals)

def join_typical_species(ts) -> str:
    if not ts: return ""
    vals = []
    for t in ts:
        nm = t.get("typcial", "") or t.get("name", "")
        regs = ", ".join(t.get("regions", []) or [])
        if nm: vals.append(f"{nm}{' ('+regs+')' if regs else ''}")
    return ", ".join(sorted(set(vals)))

# ==== TLS: /definitions + /taxa ====
_TLS_DEFS: Dict[int, str] = {}
_TLS_CATSETS: Dict[str, Set[int]] = {}
_TLS_DEFS_READY = False
_TLS_MEMBERS: Dict[str, Set[int]] = {}

def _norm(s: str) -> str:
    return normkey(s).replace("å", "a").replace("ä", "a").replace("ö", "o")

def fetch_tls_definitions():
    """Mapa ID→nazwa + zbiory ID interesujących list."""
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
            lid = it.get("id"); name = it.get("name") or ""
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
            # Habitatdirektivet – bilagor
            "Habitat_Bilaga2": find_ids_by_contains([
                "habitatdirektivets bilaga 2", "habitatdirektivet bilaga 2", "bilaga 2"
            ]),
            "Habitat_Bilaga2_Prio": find_ids_by_contains([
                "habitatdirektivets bilaga 2", "habitatdirektivet bilaga 2", "prioriterad", "prioriterade", "priority"
            ]),
            "Habitat_Bilaga4": find_ids_by_contains([
                "habitatdirektivets bilaga 4", "habitatdirektivet bilaga 4", "bilaga 4"
            ]),
            "Habitat_Bilaga5": find_ids_by_contains([
                "habitatdirektivets bilaga 5", "habitatdirektivet bilaga 5", "bilaga 5"
            ]),
            # IAS – UE-förteckningen / Union list
            "IAS_Union_EU": find_ids_by_contains([
                "invasiv", "invasiva", "frammande", "eu-forteckning", "eu forteckning",
                "unionsforteckning", "union list", "eu list"
            ]),
        }

        _TLS_DEFS_READY = True
        if DEBUG:
            for cat, ids in _TLS_CATSETS.items():
                sample = ", ".join([f"{i}:{_TLS_DEFS.get(i,'?')[:24]}" for i in list(sorted(ids))[:6]])
                log(f"  → {cat}: {len(ids)} id ({sample})")
    except Exception as e:
        log(f"TLS /definitions wyjątek: {e}")

def tls_fetch_members_for_list_ids(list_ids: Set[int]) -> Set[int]:
    """Zwraca zbiór TaxonId należących do dowolnej z list w list_ids (POST /taxa)."""
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
        if DEBUG:
            if members:
                preview = ", ".join(str(i) for i in sorted(list(members))[:12])
                log(f"     ↳ członków: {len(members)} (przykład: {preview})")
            else:
                log("     ↳ członków: 0")
        return members
    except Exception as e:
        log(f"TLS /taxa wyjątek: {e}")
        return set()

def tls_build_memberships():
    """Buduje _TLS_MEMBERS: nazwa-kategorii → zbiór TaxonId."""
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
        # Habitat
        "DirectiveAppendix2": hit("Habitat_Bilaga2"),
        "DirectiveAppendix2Priority": hit("Habitat_Bilaga2_Prio"),
        "DirectiveAppendix4": hit("Habitat_Bilaga4"),
        "DirectiveAppendix5": hit("Habitat_Bilaga5"),
        # IAS (Union list)
        "IAS_Union_EU": hit("IAS_Union_EU"),
    }

# ==== Riskklassning merge (jak wcześniej) ====
def optional_merge_risk_file(input_dir: str, out_path: str):
    candidates = [
        os.path.join(input_dir, "Riskklassning2024.xlsx"),
        os.path.join(input_dir, "Risklista2024.xlsx"),
        os.path.join(input_dir, "Riskklassning.xlsx"),
        os.path.join(os.path.dirname(out_path), "Riskklassning2024.xlsx"),
        os.path.join(os.path.dirname(out_path), "Risklista2024.xlsx"),
        os.path.join(os.path.dirname(out_path), "Riskklassning.xlsx"),
    ]
    target = next((p for p in candidates if os.path.exists(p)), None)
    if not target:
        log("Riskklassning*.xlsx nie znaleziony — pomijam merge.")
        return
    try:
        df_main = pd.read_excel(out_path, engine="openpyxl")
        risk_df = pd.read_excel(target, engine="openpyxl")
        risk_tax_col = None
        for c in risk_df.columns:
            lc = str(c).strip().lower()
            if lc == "taxonid" or ("taxon" in lc and "id" in lc):
                risk_tax_col = c; break
        if not risk_tax_col:
            log(f"Risk-plik bez kolumny TaxonId: {os.path.basename(target)} — pomijam.")
            return
        merged_final = df_main.merge(risk_df, left_on="TaxonId", right_on=risk_tax_col, how="left", suffixes=("", "_risk"))
        if risk_tax_col != "TaxonId" and risk_tax_col in merged_final.columns:
            merged_final.drop(columns=[risk_tax_col], inplace=True)
        merged_final.to_excel(out_path, index=False)
        log(f"✅ Dodano kolumny z {os.path.basename(target)} do {os.path.basename(out_path)}")
    except Exception as e:
        log(f"‼ Błąd podczas łączenia z risk-plik: {e}")

# ==== GŁÓWNY PRZEPŁYW ====
def main():
    global LOG_FILE, DEBUG, DEBUG_ROWS
    paths = pick_inputs()
    INPUT_FILE = paths["INPUT_FILE"]; OUTDIR = paths["OUTDIR"]
    OUT_FULL = paths["OUT_FULL"]; OUT_WITH = paths["OUT_WITH"]; OUT_PROT = paths["OUT_PROT"]
    LOG_FILE = paths["LOG_FILE"]; DBG_FILE = paths["DBG_FILE"]
    WANT_FULL = paths["WANT_FULL"]; DEBUG = bool(paths["DEBUG"])
    DEBUG_ROWS = []

    try:
        if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
    except Exception:
        pass

    log(f"Plik wejściowy: {INPUT_FILE}")
    log(f"Folder wyjściowy: {OUTDIR}")

    df = pd.read_excel(INPUT_FILE, engine="openpyxl")
    orig_cols = list(df.columns)

    # wykryj kolumny
    def _find(df, names):
        low = {str(c).strip().lower(): c for c in df.columns}
        for nm in names:
            if nm.lower() in low: return low[nm.lower()]
        return None

    col_taxonid = _find(df, ["taxonid", "taxon_id", "taxon id"])
    col_sv      = _find(df, ["taxon_svensktnamn", "taxon_svensktNamn", "svensktnamn", "svensk_namn", "svenskt namn"]) or ("taxon_svensktNamn" if "taxon_svensktNamn" in df.columns else None)
    col_sci     = _find(df, ["taxon_vetenskapligtnamn", "taxon_vetenskapligtNamn", "vetenskapligtnamn", "vetenskapligt_namn", "vetenskapligt namn"]) or ("taxon_vetenskapligtNamn" if "taxon_vetenskapligtNamn" in df.columns else None)

    if col_taxonid:
        df["TaxonId"] = pd.to_numeric(df[col_taxonid], errors="coerce").fillna(0).astype("int64")
        log("Wykryto kolumnę TaxonId — pomijam dopasowanie po nazwach.")
    else:
        if not col_sv and not col_sci:
            raise ValueError(
                "Brak kolumny TaxonId oraz nazw ('taxon_svensktNamn' / 'taxon_vetenskapligtNamn').\n"+
                f"Znalezione kolumny: {', '.join(orig_cols)}"
            )
        log("Etap 1: wyznaczanie TaxonId…")
        taxon_ids = []
        for i, row in enumerate(df.itertuples(index=False), start=1):
            rec = row._asdict() if hasattr(row, "_asdict") else dict(zip(df.columns, row))
            tid = resolve_taxon_id(rec, col_sv, col_sci)
            taxon_ids.append(tid)
            if i % 20 == 0:
                log(f"→ {i}/{len(df)} rekordów — ostatni TaxonId={tid}")
            time.sleep(NAME_QUERY_SLEEP)
        df["TaxonId"] = pd.Series(taxon_ids, dtype="int64")
        log("Dodano kolumnę TaxonId.")

    uniq_ids = sorted(set(int(t) for t in df["TaxonId"].fillna(0).tolist() if t > 0))
    log(f"Pozostało unikalnych TaxonId>0: {len(uniq_ids)} (z {len(df)})")

    # TLS definitions + memberships
    fetch_tls_definitions()
    if _TLS_DEFS_READY:
        tls_build_memberships()
    else:
        log("TLS: /definitions niedostępne — użyję tylko fallbacków z SpeciesDataService.")

    # docelowe kolumny (dodano IAS_Union_EU na końcu)
    cols = [
        "ScientificName","SwedishName","DisplayName","Category","ConservationStatus",
        "RedListCategory","RedListCriterion","RedListPeriodName","RedListCriterionText",
        "ActionProgramName","ActionProgramStatus","ActionProgramStart","ActionProgramEnd",
        "ForestrySignal","ForestrySignalSpecies",
        "TypicalSpecies","LandscapeType","Biotopes",
        "CITES","Bernkonventionen","Bonnkonventionen",
        "PrioriteradeFågelarterSkogsvårdslagen","FågeldirektivetBilaga1",
        "Fridlyst","Frid_text","ProtectedByWorkProtectionConstitution","ProtectedBirds",
        "DirectiveAppendix2","DirectiveAppendix2Priority","DirectiveAppendix4","DirectiveAppendix5",
        "Artikel 17 - 2019",
        "Characteristic","SpreadAndStatus","Ecology","Threat","ConservationMeasures","Other",
        "SwedishPresence","ImmigrationHistory","SubstrateInformation","EcologicalGroups",
        "ConservationEcology","ConservationNatureConservation","ConservationTreeSpecies",
        # GEIAA / Alien species
        "AlienSpeciesRiskCategories","AlienSpeciesEnvironments","AlienSpeciesEcologyEffect",
        "AlienSpeciesTaxonLists","AlienSpeciesInvationPotentials","AlienSpeciesRegions",
        # TLS IAS Union list:
        "IAS_Union_EU",
    ]

    store = {c: [] for c in cols}
    id_bucket = []

    for k, tid in enumerate(uniq_ids, start=1):
        log(f"— {k}/{len(uniq_ids)} — TaxonId={tid}")
        dbg: Dict[str, Any] = {"TaxonId": tid}
        try:
            resp = requests.get(f"{SPECIES_URL}?taxa={tid}&culture=sv-SE", headers=HEADERS_SPECIES, timeout=TIMEOUT)
            data = json_safe(resp) if resp and resp.status_code == 200 else []
            item = (data[0] if isinstance(data, list) and data else data) or {}
            obj = item.get("speciesData", item) or {}

            def gv(*keys, default=""):
                o: Any = obj
                for ky in keys:
                    if isinstance(o, dict):
                        o = o.get(ky)
                    else:
                        o = None
                return o if (o is not None and o != "") else default

            # Podstawowe
            store["ScientificName"].append(obj.get("scientificName") or item.get("scientificName") or "")
            store["SwedishName"].append(gv("swedishName"))
            store["DisplayName"].append(gv("displayName"))
            store["Category"].append(gv("category", "name"))
            store["ConservationStatus"].append(gv("conservationStatus"))

            # Redlist
            redlist_info = obj.get("redlistInfo", []) or []
            red = next((r for r in redlist_info if "2020" in str(((r or {}).get("period") or {}).get("name", ""))), None)
            if not red:
                red = next((r for r in redlist_info if ((r or {}).get("period") or {}).get("current") is True), None)
            if not red and redlist_info:
                red = redlist_info[0]
            store["RedListCategory"].append((red or {}).get("category", ""))
            store["RedListCriterion"].append((red or {}).get("criterion", ""))
            store["RedListPeriodName"].append(((red or {}).get("period") or {}).get("name", ""))
            store["RedListCriterionText"].append((red or {}).get("criterionText", ""))

            # TLS MEMBERSHIP
            tls_flags = tls_flags_by_membership(tid) if (_TLS_DEFS_READY and _TLS_MEMBERS) else {}

            # Nature conservation
            nc = obj.get("natureConservation", {}) or {}
            act = nc.get("actionProgram", {}) or {}
            store["ActionProgramName"].append(act.get("program", ""))
            store["ActionProgramStatus"].append(act.get("status", ""))
            store["ActionProgramStart"].append(act.get("startYear", ""))
            store["ActionProgramEnd"].append(act.get("endYear", ""))

            # ForestrySignal + species-lista
            store["ForestrySignal"].append(((nc.get("forestryBoardSignalSpecies", {}) or {}).get("apply")) or "")
            fs_names = []
            fss = (nc.get("forestryBoardSignalSpecies") or {})
            def _add_names(val):
                if isinstance(val, list):
                    for el in val:
                        if isinstance(el, dict):
                            nm = el.get("name") or el.get("swedishName") or el.get("displayName") or el.get("scientificName")
                            if nm: fs_names.append(str(nm))
                        elif isinstance(el, str):
                            if el.strip(): fs_names.append(el.strip())
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
            store["ForestrySignalSpecies"].append("; ".join(sorted(set(n for n in fs_names if n))))

            store["TypicalSpecies"].append(join_typical_species(nc.get("typicalSpecies", [])))
            store["LandscapeType"].append(join_name_with_attr(obj.get("landscapeTypes", []), "name", "status"))
            store["Biotopes"].append(join_name_with_attr(obj.get("biotopes", []), "name", "significance"))

            # Fallback lists scanner
            lists = nc.get("lists", []) or []
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

            store["CITES"].append(tls_flags.get("CITES") or fb_cites)
            store["Bernkonventionen"].append(tls_flags.get("Bernkonventionen") or fb_bern)
            store["Bonnkonventionen"].append(tls_flags.get("Bonnkonventionen") or fb_bonn)
            store["PrioriteradeFågelarterSkogsvårdslagen"].append(tls_flags.get("PrioriteradeFågelarterSkogsvårdslagen") or fb_prio)
            store["FågeldirektivetBilaga1"].append(tls_flags.get("FågeldirektivetBilaga1") or fb_fd1)

            # FRIDLYST + Frid_text
            prot_txt = (obj.get("protectedText") or "").strip()
            frid_flag = tls_flags.get("Fridlyst") or has_list_flag(lists, "Fridlysta arter") or has_list_flag(lists, "Fridlysta fåglar")
            if not frid_flag and prot_txt and ("fridlyst" in prot_txt.lower()):
                frid_flag = "Ja"
            store["Fridlyst"].append(frid_flag or "")
            store["Frid_text"].append(prot_txt or ""

            )

            # Habitatdirektivet (SpeciesData → fallback) + TLS
            sd_hd2  = bool_to_ja(nc.get("habitatDirectiveAppendix2") or nc.get("habitatdirectiveappendix2"))
            sd_hd2p = bool_to_ja(nc.get("habitatDirectiveAppendix2PrioritizedSpecie")
                                 or nc.get("habitatDirectiveAppendix2PrioritizedSpecies")
                                 or nc.get("habitatdirectiveappendix2prioritizedspecie")
                                 or nc.get("habitatdirectiveappendix2prioritizedspecies"))
            sd_hd4  = bool_to_ja(nc.get("habitatDirectiveAppendix4") or nc.get("habitatdirectiveappendix4"))
            sd_hd5  = bool_to_ja(nc.get("habitatDirectiveAppendix5") or nc.get("habitatdirectiveappendix5"))

            store["DirectiveAppendix2"].append(tls_flags.get("DirectiveAppendix2") or sd_hd2)
            store["DirectiveAppendix2Priority"].append(tls_flags.get("DirectiveAppendix2Priority") or sd_hd2p)
            store["DirectiveAppendix4"].append(tls_flags.get("DirectiveAppendix4") or sd_hd4)
            store["DirectiveAppendix5"].append(tls_flags.get("DirectiveAppendix5") or sd_hd5)

            store["ProtectedByWorkProtectionConstitution"].append(nc.get("protectedByWorkProtectionConstitution", "") or "")
            store["ProtectedBirds"].append(nc.get("protectedBirds", "") or "")

            # Artikel 17 - 2019
            art17 = ""
            ca = obj.get("conservationAssessments", {}) or {}
            for p in (ca.get("periods") or []):
                if "2019" in str(p.get("name", "")):
                    chunks = []
                    for t in (p.get("trends", []) or []):
                        cat = t.get("category", ""); ev = t.get("evaluation", ""); tr = t.get("trend", "")
                        part = f"{cat}: {ev}{(' ('+tr+')') if tr else ''}"
                        if part.strip(): chunks.append(part)
                    art17 = ", ".join(chunks); break
            store["Artikel 17 - 2019"].append(art17)

            # Teksty
            sft = obj.get("speciesFactText", {}) or {}
            store["Characteristic"].append(sft.get("characteristic", "") or "")
            store["SpreadAndStatus"].append(sft.get("spreadAndStatus", "") or "")
            store["Ecology"].append(sft.get("ecology", "") or "")
            store["Threat"].append(sft.get("threat", "") or "")
            store["ConservationMeasures"].append(sft.get("conservationMeasures", "") or "")
            store["Other"].append(sft.get("other", "") or "")

            tri = obj.get("taxonRelatedInformation", {}) or {}
            store["SwedishPresence"].append(tri.get("swedishPresence", "") or "")
            store["ImmigrationHistory"].append(tri.get("immigrationHistory", "") or "")

            sub = obj.get("substrateInformation", []) or []
            store["SubstrateInformation"].append(join_name_with_attr(sub, "name", sub="use"))

            eco = obj.get("ecologicalGroups", []) or []
            eg = ", ".join(sorted(set(g.get("name", "") for g in eco if g.get("active"))))
            store["EcologicalGroups"].append(eg)

            ca2 = obj.get("conservationAssessments", {}) or {}
            store["ConservationEcology"].append((ca2.get("ecology") or ""))
            store["ConservationNatureConservation"].append((ca2.get("natureConservation") or ""))
            store["ConservationTreeSpecies"].append((ca2.get("treeSpecies") or ""))

            # --- GEIAA / Alien species ---
            alien = obj.get("alienSpeciesRa", {}) or {}
            store["AlienSpeciesRiskCategories"].append("; ".join(alien.get("riskCategories", []) or []))
            store["AlienSpeciesEnvironments"].append("; ".join(alien.get("environments", []) or []))
            store["AlienSpeciesEcologyEffect"].append("; ".join(alien.get("ecologyEffect", []) or []))
            store["AlienSpeciesTaxonLists"].append("; ".join(str(x) for x in (alien.get("taxonLists", []) or [])))
            store["AlienSpeciesInvationPotentials"].append("; ".join(alien.get("invationPotentials", []) or []))
            store["AlienSpeciesRegions"].append("; ".join(alien.get("regions", []) or []))

            # --- IAS (Union list) z TLS ---
            store["IAS_Union_EU"].append(tls_flags.get("IAS_Union_EU", ""))

            if DEBUG:
                dbg.update({
                    "SwedishName": store["SwedishName"][-1],
                    "ScientificName": store["ScientificName"][-1],
                    "TLS_CITES": store["CITES"][-1],
                    "TLS_Bern": store["Bernkonventionen"][-1],
                    "TLS_Bonn": store["Bonnkonventionen"][-1],
                    "TLS_FD1": store["FågeldirektivetBilaga1"][-1],
                    "TLS_Prio": store["PrioriteradeFågelarterSkogsvårdslagen"][-1],
                    "TLS_Fridlyst": store["Fridlyst"][-1],
                    "TLS_HD2": store["DirectiveAppendix2"][-1],
                    "TLS_HD2P": store["DirectiveAppendix2Priority"][-1],
                    "TLS_HD4": store["DirectiveAppendix4"][-1],
                    "TLS_HD5": store["DirectiveAppendix5"][-1],
                    "TLS_IAS_Union_EU": store["IAS_Union_EU"][-1],
                })

            id_bucket.append(tid)
            if (k % 10) == 0:
                log(f"→ {k}/{len(uniq_ids)} taksonów ukończono")
            time.sleep(SPECIES_SLEEP)
        except Exception as e:
            log(f"Błąd dla TaxonId {tid}: {e}")
            for c in cols: store[c].append("")
            id_bucket.append(tid)

        if DEBUG:
            DEBUG_ROWS.append(dbg)

    # Złóż wynik
    result = pd.DataFrame({"TaxonId": id_bucket}) if id_bucket else pd.DataFrame(columns=["TaxonId"])
    for c in cols: result[c] = store.get(c, [])
    result.replace(["N/A", "0", 0, None], "", inplace=True)

    # Nie dubluj istniejących kolumn ze źródła
    add_cols = [c for c in result.columns if c != "TaxonId" and c not in df.columns]
    full_enriched = df.merge(result[["TaxonId"] + add_cols] if add_cols else df[["TaxonId"]], on="TaxonId", how="left")

    # Sortowanie po RL (RE→CR→EN→VU→NT→LC→DD→NA→NE)
    RL_ORDER = {"RE":0, "CR":1, "EN":2, "VU":3, "NT":4, "LC":5, "DD":6, "NA":7, "NE":8}

    if paths["WANT_FULL"]:
        fe = full_enriched.copy()
        fe["_rl_order"] = fe.get("RedListCategory", "").astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)
        fe = fe.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
        fe.drop(columns=["_rl_order"], inplace=True)
        with pd.ExcelWriter(paths["OUT_FULL"], engine="openpyxl") as w:
            fe.to_excel(w, index=False)
        log(f"Zapisano: {paths['OUT_FULL']}")

    # Overview: dedupe po TaxonId
    overview = full_enriched[full_enriched["TaxonId"] > 0].drop_duplicates(subset=["TaxonId"], keep="first").copy()
    overview["_rl_order"] = overview.get("RedListCategory", "").astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)
    overview = overview.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
    overview.drop(columns=["_rl_order"], inplace=True)

    # Wyczyść "Nej"/"False" w flagach (DODANO IAS_Union_EU do czyszczenia)
    flag_cols = ["CITES","Bernkonventionen","Bonnkonventionen",
                 "FågeldirektivetBilaga1","PrioriteradeFågelarterSkogsvårdslagen","Fridlyst",
                 "DirectiveAppendix2","DirectiveAppendix2Priority","DirectiveAppendix4",
                 "ProtectedByWorkProtectionConstitution","DirectiveAppendix5",
                 "IAS_Union_EU"]
    for c in flag_cols:
        if c in overview.columns:
            overview[c] = overview[c].astype(str).replace({"Nej":"", "nej":"", "False":"", "false":""})

    with pd.ExcelWriter(paths["OUT_WITH"], engine="openpyxl") as w:
        overview.to_excel(w, index=False)
    log(f"Zapisano: {paths['OUT_WITH']}")

    # bara_skyddade — bez IAS_Union_EU (nie wchodzi do filtra)
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

    protected = overview[overview.apply(lambda r: has_protection(r), axis=1)].copy()
    protected.replace(["N/A", "0", 0, None], "", inplace=True)

    protected["_rl_order"] = protected.get("RedListCategory", "").astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)
    protected = protected.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
    protected.drop(columns=["_rl_order"], inplace=True)

    with pd.ExcelWriter(paths["OUT_PROT"], engine="openpyxl") as w:
        protected.to_excel(w, index=False)
    log(f"Zapisano: {paths['OUT_PROT']}")

    # DEBUG dump
    if DEBUG:
        try:
            pd.DataFrame(DEBUG_ROWS).to_csv(paths["DBG_FILE"], index=False, encoding="utf-8-sig")
            log(f"DEBUG zapisano: {paths['DBG_FILE']}")
            # sumy „Ja”
            def _sum_yes(df_, col):
                return int((df_.get(col,"").astype(str).str.lower() == "ja").sum())
            for col in flag_cols + ["Fridlyst"]:
                log(f"SUMA '{col}=Ja': {_sum_yes(overview, col)}")
        except Exception as e:
            log(f"DEBUG zapis CSV nieudany: {e}")

    # Opcjonalny MERGE risk-plik do WITH
    optional_merge_risk_file(os.path.dirname(paths["INPUT_FILE"]), paths["OUT_WITH"])

    log("Proces zakończony sukcesem!")


if __name__ == "__main__":
    main()
