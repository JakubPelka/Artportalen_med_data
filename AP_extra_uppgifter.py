import os
import sys
import time
import re
import requests
import pandas as pd
from datetime import datetime

"""
AP_extra_uppgifter.py — Artportalen export → enrich (SpeciesDataService) + GEIAA + opcjonalny merge Riskklassning2024.xlsx

Funkcje zachowane:
- Okno wyboru pliku wejściowego (Artportalen export)
- Okno wyboru folderu zapisu
- Przełącznik: czy zapisać dodatkowo pełną tabelę BEZ usuwania duplikatów
- Enrichment z SpeciesDataService (ArtDatabanken)
- Sortowanie wg RedListCategory (CR, EN, VU, NT, LC, …)
- 2 (lub 3) pliki wynikowe: full_ (opcjonalnie), with_data (overview, bez duplikatów), bara_skyddade (tylko chronione)

Nowości:
- GEIAA / Obce gatunki: kolumny z speciesData.alienSpeciesRa
  (AlienSpeciesRiskCategories, AlienSpeciesEnvironments, AlienSpeciesEcologyEffect,
   AlienSpeciesTaxonLists, AlienSpeciesInvationPotentials, AlienSpeciesRegions)
- Opcjonalny merge dodatkowego Excela (Riskklassning2024.xlsx / Risklista2024.xlsx / Riskklassning.xlsx)
  szukany w tym samym folderze co plik WEJŚCIOWY (fallback: folder wyjściowy)

Publikacje (BFF metadata/publications) — WYŁĄCZONE (brak wiarygodnego filtra po taksonie publicznym endpointem).

Wymagane klucze środowiskowe (lub wpisane niżej):
- TAXONOMY_KEY  – taxonservice (dopasowanie nazw → TaxonId) [tylko jeśli w pliku nie ma TaxonId]
- SPECIES_KEY   – speciesdataservice (pobieranie danych)
"""

# ==== KLUCZE I ENDPOINTY ====
TAXONOMY_KEY = os.getenv("TAXONOMY_KEY", "a2753962eba449bbbfdd253baf66fd26")
SPECIES_KEY  = os.getenv("SPECIES_KEY",  "71c0e472ab954c37896ee2d91f042ff1")

NAME_QUERY_SLEEP = 0.08
SPECIES_SLEEP    = 0.08
TIMEOUT          = 30

TAXON_NAME_URL = "https://api.artdatabanken.se/taxonservice/v1/taxa/names"
SPECIES_URL    = "https://api.artdatabanken.se/information/v1/speciesdataservice/v1/speciesdata"

HEADERS_TAXON   = {"Ocp-Apim-Subscription-Key": TAXONOMY_KEY, "Accept": "application/json"}
HEADERS_SPECIES = {"Ocp-Apim-Subscription-Key": SPECIES_KEY,   "Accept": "application/json", "Cache-Control": "no-cache"}

# ==== TKINTER – wybór pliku/folderu i przełącznik ====
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

    return {
        "INPUT_FILE": infile,
        "OUTDIR": outdir,
        "OUT_FULL": os.path.join(outdir, f"{base}_full_.xlsx"),
        "OUT_WITH": os.path.join(outdir, f"{base}_with_data.xlsx"),
        "OUT_PROT": os.path.join(outdir, f"{base}_bara_skyddade.xlsx"),
        "LOG_FILE": os.path.join(outdir, f"{base}_log.txt"),
        "WANT_FULL": want_full,
    }

# ==== LOG ====
LOG_FILE = None

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")

# ==== UTILS ====
import json

def json_safe(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        url = getattr(resp, 'url', '?'); sc = getattr(resp, 'status_code', '?'); tb = getattr(resp, 'text', '')
        log(f"‼ Nie-JSON z {url} [{sc}] — body: {tb[:200]!r}")
        return {}

_CLEAN_SCI_RE = re.compile(r"\b(sp\.|cf\.|aff\.|nr\.|gr\.)\b|[\?\(\)\[\]]", re.IGNORECASE)
_DEFUZZ_REPLACEMENTS = {"  ": " ", "´": "'", "`": "'", "—": "-", "–": "-"}

def clean_scientific(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = name.strip()
    s = _CLEAN_SCI_RE.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def clean_swedish(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = name.strip()
    for k, v in _DEFUZZ_REPLACEMENTS.items():
        s = s.replace(k, v)
    s = re.sub(r"s{3,}", "ss", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s

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
    data = resp.json().get("data", []) if resp.content else []
    if not data:
        return 0
    name_l = name.lower()
    def _pick_id(item):
        ti = item.get("taxonInformation", {})
        return int(ti.get("taxonId", 0) or 0)
    exact = [d for d in data if any((str(d.get("displayName", "")).lower() == name_l,
                                     str(d.get("swedishName", "")).lower() == name_l,
                                     str(d.get("scientificName", "")).lower() == name_l))]
    if exact:
        return _pick_id(exact[0])
    recommended = [d for d in data if d.get("isRecommended") is True]
    if recommended:
        return _pick_id(recommended[0])
    return _pick_id(data[0])

def resolve_taxon_id(row, sv_col, sci_col) -> int:
    swe = str(row.get(sv_col, "") or "").strip() if sv_col else ""
    sci = str(row.get(sci_col, "") or "").strip() if sci_col else ""

    tried = []
    if swe:
        tid = query_taxon_id_by_name(swe, "Swedish"); tried.append(("Swedish", swe, tid))
        if tid: return tid
        cs = clean_swedish(swe)
        if cs and cs != swe:
            tid = query_taxon_id_by_name(cs, "Swedish"); tried.append(("Swedish(clean)", cs, tid))
            if tid: return tid
    if sci:
        csci = clean_scientific(sci)
        for cand, tag in [(csci, "Scientific(clean)"), (sci, "Scientific")]:
            if cand:
                tid = query_taxon_id_by_name(cand, "Scientific"); tried.append((tag, cand, tid))
                if tid: return tid
    pretty = "; ".join([f"{t}:{n} -> {tid}" for (t, n, tid) in tried]) or "(brak prób)"
    log(f"Brak TaxonId — swe='{swe}' sci='{sci}'. Próby: {pretty}")
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
        nm = t.get("typcial", "")
        regs = ", ".join(t.get("regions", []) or [])
        if nm: vals.append(f"{nm}{' ('+regs+')' if regs else ''}")
    return ", ".join(sorted(set(vals)))

# ==== Riskklassning merge ====

def optional_merge_risk_file(input_dir: str, out_path: str):
    # Szukaj najpierw w folderze WEJŚCIOWYM, potem w folderze WYJŚCIOWYM
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
        # wykryj kolumnę TaxonId w risk_df
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
    global LOG_FILE
    paths = pick_inputs()
    INPUT_FILE = paths["INPUT_FILE"]; OUTDIR = paths["OUTDIR"]
    OUT_FULL = paths["OUT_FULL"]; OUT_WITH = paths["OUT_WITH"]; OUT_PROT = paths["OUT_PROT"]
    LOG_FILE = paths["LOG_FILE"]; WANT_FULL = paths["WANT_FULL"]

    try:
        if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
    except Exception: pass

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

    # docelowe kolumny — z GEIAA
    cols = [
        "ScientificName","SwedishName","DisplayName","Category","ConservationStatus",
        "RedListCategory","RedListCriterion","RedListPeriodName","RedListCriterionText",
        "ActionProgramName","ActionProgramStatus","ActionProgramStart","ActionProgramEnd",
        "ForestrySignal","TypicalSpecies","LandscapeType","Biotopes","CITES","Bernkonventionen",
        "Bonnkonventionen","PrioriteradeFågelarterSkogsvårdslagen","FågeldirektivetBilaga1",
        "Fridlyst","Frid_text","ProtectedByWorkProtectionConstitution","ProtectedBirds",
        "DirectiveAppendix2","DirectiveAppendix2Priority","DirectiveAppendix4","DirectiveAppendix5",
        "Artikel 17 - 2019",
        "Characteristic","SpreadAndStatus","Ecology","Threat","ConservationMeasures","Other",
        "SwedishPresence","ImmigrationHistory","SubstrateInformation","EcologicalGroups",
        "ConservationEcology","ConservationNatureConservation","ConservationTreeSpecies",
        # --- GEIAA / Alien species ---
        "AlienSpeciesRiskCategories","AlienSpeciesEnvironments","AlienSpeciesEcologyEffect",
        "AlienSpeciesTaxonLists","AlienSpeciesInvationPotentials","AlienSpeciesRegions",
    ]

    store = {c: [] for c in cols}
    id_bucket = []

    for k, tid in enumerate(uniq_ids, start=1):
        log(f"— {k}/{len(uniq_ids)} — TaxonId={tid}")
        try:
            resp = requests.get(f"{SPECIES_URL}?taxa={tid}", headers=HEADERS_SPECIES, timeout=TIMEOUT)
            data = json_safe(resp) if resp and resp.status_code == 200 else []
            obj = (data[0] or {}).get("speciesData", {}) if (isinstance(data, list) and data) else {}

            def gv(*keys, default=""):
                o = obj
                for ky in keys:
                    if isinstance(o, dict):
                        o = o.get(ky)
                    else:
                        o = None
                return o if (o is not None and o != "") else default

            # Podstawowe
            sci_name = gv("scientificName") or (data[0].get("scientificName") if (isinstance(data, list) and data and isinstance(data[0], dict)) else "")
            store["ScientificName"].append(sci_name)
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

            # Nature conservation
            nc = obj.get("natureConservation", {}) or {}
            act = nc.get("actionProgram", {}) or {}
            store["ActionProgramName"].append(act.get("program", ""))
            store["ActionProgramStatus"].append(act.get("status", ""))
            store["ActionProgramStart"].append(act.get("startYear", ""))
            store["ActionProgramEnd"].append(act.get("endYear", ""))
            store["ForestrySignal"].append(((nc.get("forestryBoardSignalSpecies", {}) or {}).get("apply")) or "")
            store["TypicalSpecies"].append(join_typical_species(nc.get("typicalSpecies", [])))
            store["LandscapeType"].append(join_name_with_attr(obj.get("landscapeTypes", []), "name", "status"))
            store["Biotopes"].append(join_name_with_attr(obj.get("biotopes", []), "name", "significance"))

            lists = nc.get("lists", []) or []
            def get_from_lists(lists, list_name):
                vals = []
                for it in lists:
                    if it.get("name") == list_name:
                        vals += extract_child_names(it.get("childs"))
                vals = sorted(set(v for v in vals if v))
                return ", ".join(vals)

            store["CITES"].append(get_from_lists(lists, "CITES"))
            store["Bernkonventionen"].append(get_from_lists(lists, "Bernkonventionen"))
            store["Bonnkonventionen"].append(get_from_lists(lists, "Bonnkonventionen"))
            store["PrioriteradeFågelarterSkogsvårdslagen"].append(any_child_named(lists, "Prioriterade fågelarter i skogsvårdslagen"))
            store["FågeldirektivetBilaga1"].append(any_child_named(lists, "Fågeldirektivet bilaga 1"))
            store["Fridlyst"].append(any_child_named(lists, "Fridlysta arter"))

            frid_names = []
            for it in lists:
                if it.get("name") == "Fridlysta arter":
                    frid_names += [c.get("name") for c in (it.get("childs") or []) if c.get("name")]
            frid_names = ", ".join(sorted(set(frid_names))) if frid_names else ""
            if frid_names:
                store["Frid_text"].append(frid_names)
            else:
                sft_char = ((obj.get("speciesFactText", {}) or {}).get("characteristic")) or ""
                store["Frid_text"].append(sft_char if sft_char else (obj.get("protectedText") or ""))

            store["ProtectedByWorkProtectionConstitution"].append(nc.get("protectedByWorkProtectionConstitution", "") or "")
            store["ProtectedBirds"].append(nc.get("protectedBirds", "") or "")
            store["DirectiveAppendix2"].append(nc.get("habitationDirectiveAppendix2", "") or "")
            store["DirectiveAppendix2Priority"].append(nc.get("habitationDirectiveAppendix2PrioritizedSpecie", "") or "")
            store["DirectiveAppendix4"].append(nc.get("habitationDirectiveAppendix4", "") or "")
            store["DirectiveAppendix5"].append(nc.get("habitationDirectiveAppendix5", "") or "")

            # Artikel 17 - 2019
            art17 = ""; ca = obj.get("conservationAssessments", {}) or {}
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

            ca = obj.get("conservationAssessments", {}) or {}
            store["ConservationEcology"].append((ca.get("ecology") or ""))
            store["ConservationNatureConservation"].append((ca.get("natureConservation") or ""))
            store["ConservationTreeSpecies"].append((ca.get("treeSpecies") or ""))

            # --- GEIAA / Alien species ---
            alien = obj.get("alienSpeciesRa", {}) or {}
            store["AlienSpeciesRiskCategories"].append("; ".join(alien.get("riskCategories", []) or []))
            store["AlienSpeciesEnvironments"].append("; ".join(alien.get("environments", []) or []))
            store["AlienSpeciesEcologyEffect"].append("; ".join(alien.get("ecologyEffect", []) or []))
            store["AlienSpeciesTaxonLists"].append("; ".join(str(x) for x in (alien.get("taxonLists", []) or [])))
            store["AlienSpeciesInvationPotentials"].append("; ".join(alien.get("invationPotentials", []) or []))
            store["AlienSpeciesRegions"].append("; ".join(alien.get("regions", []) or []))

            id_bucket.append(tid)
            if k % 10 == 0:
                log(f"→ {k}/{len(uniq_ids)} taksonów ukończono")
            time.sleep(SPECIES_SLEEP)
        except Exception as e:
            log(f"Błąd dla TaxonId {tid}: {e}")
            for c in cols: store[c].append("")
            id_bucket.append(tid)

    result = pd.DataFrame({"TaxonId": id_bucket}) if id_bucket else pd.DataFrame(columns=["TaxonId"])
    for c in cols: result[c] = store.get(c, [])
    result.replace(["N/A", "0", 0, None], "", inplace=True)

    # Nie dubluj istniejących kolumn ze źródła
    add_cols = [c for c in result.columns if c != "TaxonId" and c not in df.columns]
    full_enriched = df.merge(result[["TaxonId"] + add_cols] if add_cols else df[["TaxonId"]], on="TaxonId", how="left")

    # Sortowanie po RedListCategory (priorytet: CR, EN, VU, NT, LC, …)
    RL_ORDER = {"RE":0, "CR":1, "EN":2, "VU":3, "NT":4, "DD":5, "LC":6, "NA":7, "NE":8}

    if paths["WANT_FULL"]:
        fe = full_enriched.copy()
        fe["_rl_order"] = fe["RedListCategory"].astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)
        fe = fe.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
        fe.drop(columns=["_rl_order"], inplace=True)
        with pd.ExcelWriter(paths["OUT_FULL"], engine="openpyxl") as w:
            fe.to_excel(w, index=False)
        log(f"Zapisano: {paths['OUT_FULL']}")

    # Overview: bez duplikatów po TaxonId
    overview = full_enriched[full_enriched["TaxonId"] > 0].drop_duplicates(subset=["TaxonId"], keep="first").copy()
    overview["_rl_order"] = overview["RedListCategory"].astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)
    overview = overview.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
    overview.drop(columns=["_rl_order"], inplace=True)

    with pd.ExcelWriter(paths["OUT_WITH"], engine="openpyxl") as w:
        overview.to_excel(w, index=False)
    log(f"Zapisano: {paths['OUT_WITH']}")

    # Tylko chronione
    protection_columns = [
        "ConservationStatus", "Artikel 17 - 2019", "TypicalSpecies", "CITES", "Bernkonventionen", "Bonnkonventionen",
        "PrioriteradeFågelarterSkogsvårdslagen", "FågeldirektivetBilaga1", "ProtectedByWorkProtectionConstitution",
        "ProtectedBirds", "DirectiveAppendix2", "DirectiveAppendix2Priority", "DirectiveAppendix4", "DirectiveAppendix5",
        "ForestrySignal", "ActionProgramStatus", "ActionProgramStart", "ActionProgramEnd", "ActionProgramName",
        "Fridlyst", "Frid_text"
    ]

    def has_protection(row) -> bool:
        empty_vals = {"N/A", "", 0, "0", "Nej", None}
        return any(row.get(col) not in empty_vals for col in protection_columns)

    protected = overview[overview.apply(lambda r: has_protection(r), axis=1)].copy()
    protected["_rl_order"] = protected["RedListCategory"].astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)
    protected = protected.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
    protected.drop(columns=["_rl_order"], inplace=True)

    with pd.ExcelWriter(paths["OUT_PROT"], engine="openpyxl") as w:
        protected.to_excel(w, index=False)
    log(f"Zapisano: {paths['OUT_PROT']}")

    # Opcjonalny MERGE: Riskklassning*.xlsx (IN → OUT_WITH)
    optional_merge_risk_file(os.path.dirname(INPUT_FILE), paths["OUT_WITH"])

    log("Proces zakończony sukcesem!")


if __name__ == "__main__":
    main()
