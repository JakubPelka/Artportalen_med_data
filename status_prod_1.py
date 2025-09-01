import os
import sys
import time
import json
import requests
import pandas as pd
from datetime import datetime

"""
Status_V2_from_TaxonId — v2
- Fix: KeyError 'TaxonId' przy merge (zawsze dołączamy kolumnę klucza po prawej stronie).
- Nowość: pytanie (Yes/No) czy zapisać też tabelę **bez deduplikacji** (ALLROWS) — jeśli tak:
  1) zapisujemy pełny plik ALLROWS (bez usuwania duplikatów),
  2) zapisujemy wersję z deduplikacją,
  3) zapisujemy wersję tylko chronione.
- Wcześniejsza deduplikacja po TaxonId (>0) służy tylko do ograniczenia liczby zapytań do API; ALLROWS łączy się potem
  z oryginalną tabelą, więc zachowuje wszystkie wiersze.
- Brak dublowania kolumn wejściowych (case-insensitive) — dodajemy tylko nowe.
- Sort przeglądowej listy (dedupe) wg RedList: RE, CR, EN, VU, NT, DD, LC, NA, NE; potem SwedishName/ScientificName.
"""

# ========= KONFIG ========= #
TAXONOMY_KEY = os.getenv("TAXONOMY_KEY", "a2753962eba449bbbfdd253baf66fd26")
SPECIES_KEY  = os.getenv("SPECIES_KEY",  "71c0e472ab954c37896ee2d91f042ff1")

SPECIES_SLEEP    = 0.10
TIMEOUT          = 30
DEBUG_DUMP_LISTS = False  # ustaw True, by zapisać lists_raw_<TaxonId>.json do OUTPUT_DIR

SPECIES_URL    = "https://api.artdatabanken.se/information/v1/speciesdataservice/v1/speciesdata"
HEADERS_SPECIES = {"Ocp-Apim-Subscription-Key": SPECIES_KEY, "Accept": "application/json", "Cache-Control": "no-cache"}

# Redlist porządek sortowania (niższa wartość = wyżej)
RL_ORDER = {"RE":0, "CR":1, "EN":2, "VU":3, "NT":4, "DD":5, "LC":6, "NA":7, "NE":8}

# ========= UI: okienka ========= #

def choose_input_file(initial_dir: str = None) -> str:
    try:
        from tkinter import Tk, filedialog
        root = Tk(); root.withdraw()
        path = filedialog.askopenfilename(
            title="Wybierz plik Excel (z TaxonId)",
            initialdir=initial_dir if (initial_dir and os.path.isdir(initial_dir)) else None,
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        root.destroy(); return path or ""
    except Exception:
        return ""


def choose_output_dir(initial_dir: str = None) -> str:
    try:
        from tkinter import Tk, filedialog
        root = Tk(); root.withdraw()
        path = filedialog.askdirectory(
            title="Wybierz folder zapisu wyników",
            initialdir=initial_dir if (initial_dir and os.path.isdir(initial_dir)) else None,
            mustexist=True,
        )
        root.destroy(); return path or ""
    except Exception:
        return ""


def ask_yes_no(title: str, question: str, default: bool=False) -> bool:
    """Pyta użytkownika o Yes/No przez tkinter; fallback na konsolę."""
    try:
        from tkinter import Tk, messagebox
        root = Tk(); root.withdraw()
        ans = messagebox.askyesno(title, question, icon='question')
        root.destroy(); return bool(ans)
    except Exception:
        try:
            resp = input(f"{question} [y/N]: ").strip().lower()
            return resp in ("y", "yes", "t", "tak")
        except Exception:
            return default

# ========= LOG ========= #
OUTPUT_DIR = None
LOG_FILE = None

def ensure_parent_dir(p):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    if LOG_FILE:
        ensure_parent_dir(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")

# ========= JSON helper ========= #

def json_safe(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        log(f"‼ Nie-JSON z {resp.url} [{resp.status_code}] — body: {resp.text[:200]!r}")
        return {}

# ========= Parsowanie pól ========= #

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
        nm = t.get("typcial", "")            # tak się nazywa w API
        regs = ", ".join(t.get("regions", []) or [])
        if nm: vals.append(f"{nm}{' ('+regs+')' if regs else ''}")
    return ", ".join(sorted(set(vals)))


def extract_lists_full(lists):
    """Rekurencyjnie zbiera wartości z list ochronnych i flag (CITES/Bern/Bonn/Fågeldirektivet/Fridlysta/Prioriterade fågelarter...)."""
    out = {
        "CITES": [],
        "Bernkonventionen": [],
        "Bonnkonventionen": [],
        "PrioriteradeFågelarterSkogsvårdslagen": "",
        "FågeldirektivetBilaga1": "",
        "Fridlyst": "",
        "Frid_text_childs": [],
    }
    def recurse(childs, parent_name=None):
        for c in childs or []:
            name = c.get("name", "")
            if parent_name in ["CITES", "Bernkonventionen", "Bonnkonventionen"] and name:
                out[parent_name].append(name)
            if "Prioriterade fågelarter i skogsvårdslagen" in name:
                out["PrioriteradeFågelarterSkogsvårdslagen"] = "Ja"
            if "Fågeldirektivet bilaga 1" in name:
                out["FågeldirektivetBilaga1"] = "Ja"
            if parent_name == "Fridlysta arter":
                out["Fridlyst"] = "Ja"
                if name:
                    out["Frid_text_childs"].append(name)
            if c.get("childs"):
                recurse(c["childs"], parent_name)
    for item in lists or []:
        nm = item.get("name", "")
        if nm in ["CITES", "Bernkonventionen", "Bonnkonventionen", "Fridlysta arter"]:
            recurse(item.get("childs", []), nm)
        else:
            recurse(item.get("childs", []), nm)
    for k in ["CITES", "Bernkonventionen", "Bonnkonventionen", "Frid_text_childs"]:
        out[k] = ", ".join(sorted(set(out[k])))
    return out

# ========= Resolve ścieżek ========= #

def resolve_paths():
    # 1) input: argv → okienko
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        inp = os.path.abspath(sys.argv[1])
    else:
        inp = choose_input_file(os.getcwd())
    if not inp:
        print("[BŁĄD] Nie wybrano pliku wejściowego."); sys.exit(1)

    # 2) output: okienko → folder wejściowy
    out_dir = choose_output_dir(os.path.dirname(inp)) or os.path.dirname(inp)

    base = os.path.splitext(os.path.basename(inp))[0]
    return inp, out_dir, base

# ========= MAIN ========= #

def main():
    global OUTPUT_DIR, LOG_FILE

    input_path, OUTPUT_DIR, base = resolve_paths()
    LOG_FILE = os.path.join(OUTPUT_DIR, "log.txt")

    OUT_WITH    = os.path.join(OUTPUT_DIR, f"{base}_oversikt_with_data.xlsx")
    OUT_PROT    = os.path.join(OUTPUT_DIR, f"{base}_oversikt_bara_skyddade.xlsx")
    OUT_ALLROWS = os.path.join(OUTPUT_DIR, f"{base}_ALLROWS_with_data.xlsx")

    # czyść log
    if os.path.exists(LOG_FILE):
        try: os.remove(LOG_FILE)
        except Exception: pass

    log(f"Plik wejściowy: {input_path}")
    log(f"Folder wyjściowy: {OUTPUT_DIR}")

    # 1) Wczytaj dane i przygotuj TaxonId
    df = pd.read_excel(input_path, engine="openpyxl")

    # Znajdź kolumnę TaxonId w dowolnej pisowni
    taxon_col = next((c for c in df.columns if c.lower() == "taxonid"), None)
    if not taxon_col:
        raise ValueError("Brak kolumny TaxonId/TaxonID/taxonid w pliku wejściowym.")
    if taxon_col != "TaxonId":
        df.rename(columns={taxon_col: "TaxonId"}, inplace=True)

    # 2) Wczesna deduplikacja po TaxonId (>0) na potrzeby zapytań do API
    df_overview = df[pd.to_numeric(df["TaxonId"], errors="coerce").fillna(0) > 0].copy()
    df_overview["TaxonId"] = df_overview["TaxonId"].astype(int)
    df_overview = df_overview.sort_values("TaxonId").drop_duplicates(subset=["TaxonId"], keep="first")
    uniq_ids = df_overview["TaxonId"].tolist()
    log(f"Unikalnych TaxonId > 0: {len(uniq_ids)} (z {len(df)})")

    # 3) Pobierz dane z SpeciesDataService
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
        # Alien (jeśli dostępne)
        "AlienSpeciesRiskCategories","AlienSpeciesEnvironments","AlienSpeciesEcologyEffect",
        "AlienSpeciesTaxonLists","AlienSpeciesInvationPotentials","AlienSpeciesRegions",
    ]
    store = {c: [] for c in cols}
    id_bucket = []

    for k, tid in enumerate(uniq_ids, start=1):
        log(f"— {k}/{len(uniq_ids)} — TaxonId={tid}")
        rowvals = {c: "" for c in cols}
        try:
            resp = requests.get(f"{SPECIES_URL}?taxa={tid}", headers=HEADERS_SPECIES, timeout=TIMEOUT)
            if resp.status_code != 200:
                log(f"  Błąd {resp.status_code} dla TaxonId={tid}: {resp.text[:200]!r}")
                data = []
            else:
                try:
                    data = resp.json()
                except Exception:
                    log(f"‼ Nie-JSON z {resp.url} [{resp.status_code}] — body: {resp.text[:200]!r}")
                    data = []
            obj = (data[0] or {}).get("speciesData", {}) if (isinstance(data, list) and data) else {}

            if DEBUG_DUMP_LISTS:
                try:
                    lists_raw = (obj.get("natureConservation", {}) or {}).get("lists", [])
                    with open(os.path.join(OUTPUT_DIR, f"lists_raw_{tid}.json"), "w", encoding="utf-8") as f:
                        json.dump(lists_raw, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    log(f"  (debug) Nie zapisano lists_raw dla {tid}: {e}")

            def gv(*keys, default=""):
                o = obj
                for ky in keys:
                    if isinstance(o, dict):
                        o = o.get(ky)
                    else:
                        o = None
                return o if (o is not None and o != "") else default

            # Podstawowe
            rowvals["ScientificName"] = gv("scientificName") or (data[0].get("scientificName") if (isinstance(data, list) and data and isinstance(data[0], dict)) else "")
            rowvals["SwedishName"]    = gv("swedishName")
            rowvals["DisplayName"]    = gv("displayName")
            rowvals["Category"]       = gv("category", "name")
            rowvals["ConservationStatus"] = gv("conservationStatus")

            # Redlist (2020 → current → pierwszy)
            redlist_info = obj.get("redlistInfo", []) or []
            red = next((r for r in redlist_info if "2020" in str(((r or {}).get("period") or {}).get("name", ""))), None)
            if not red:
                red = next((r for r in redlist_info if ((r or {}).get("period") or {}).get("current") is True), None)
            if not red and redlist_info:
                red = redlist_info[0]
            rowvals["RedListCategory"]     = (red or {}).get("category", "")
            rowvals["RedListCriterion"]     = (red or {}).get("criterion", "")
            rowvals["RedListPeriodName"]    = ((red or {}).get("period") or {}).get("name", "")
            rowvals["RedListCriterionText"] = (red or {}).get("criterionText", "")

            # NatureConservation
            nc = obj.get("natureConservation", {}) or {}
            act = nc.get("actionProgram", {}) or {}
            rowvals["ActionProgramName"]   = act.get("program", "")
            rowvals["ActionProgramStatus"] = act.get("status", "")
            rowvals["ActionProgramStart"]  = act.get("startYear", "")
            rowvals["ActionProgramEnd"]    = act.get("endYear", "")

            rowvals["ForestrySignal"]  = ((nc.get("forestryBoardSignalSpecies", {}) or {}).get("apply")) or ""
            rowvals["TypicalSpecies"]  = join_typical_species(nc.get("typicalSpecies", []))
            rowvals["LandscapeType"]   = join_name_with_attr(obj.get("landscapeTypes", []), "name", "status")
            rowvals["Biotopes"]        = join_name_with_attr(obj.get("biotopes", []), "name", "significance")

            lists = nc.get("lists", []) or []
            lists_data = extract_lists_full(lists)
            rowvals["CITES"]   = lists_data["CITES"]
            rowvals["Bernkonventionen"] = lists_data["Bernkonventionen"]
            rowvals["Bonnkonventionen"] = lists_data["Bonnkonventionen"]
            rowvals["PrioriteradeFågelarterSkogsvårdslagen"] = lists_data["PrioriteradeFågelarterSkogsvårdslagen"]
            rowvals["FågeldirektivetBilaga1"] = lists_data["FågeldirektivetBilaga1"]
            rowvals["Fridlyst"] = lists_data["Fridlyst"]
            # Frid_text — childy jeżeli są, w przeciwnym razie speciesFactText.characteristic lub protectedText
            rowvals["Frid_text"] = lists_data.get("Frid_text_childs") or ((obj.get("speciesFactText", {}) or {}).get("characteristic") or (obj.get("protectedText") or ""))

            rowvals["ProtectedByWorkProtectionConstitution"] = nc.get("protectedByWorkProtectionConstitution", "") or ""
            rowvals["ProtectedBirds"] = nc.get("protectedBirds", "") or ""
            rowvals["DirectiveAppendix2"] = nc.get("habitationDirectiveAppendix2", "") or ""
            rowvals["DirectiveAppendix2Priority"] = nc.get("habitationDirectiveAppendix2PrioritizedSpecie", "") or ""
            rowvals["DirectiveAppendix4"] = nc.get("habitationDirectiveAppendix4", "") or ""
            rowvals["DirectiveAppendix5"] = nc.get("habitationDirectiveAppendix5", "") or ""

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
            rowvals["Artikel 17 - 2019"] = art17

            # Teksty
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
            rowvals["SubstrateInformation"] = join_name_with_attr(sub, "name", sub="use")

            eco = obj.get("ecologicalGroups", []) or []
            eg = ", ".join(sorted(set(g.get("name", "") for g in eco if g.get("active"))))
            rowvals["EcologicalGroups"] = eg

            ca = obj.get("conservationAssessments", {}) or {}
            rowvals["ConservationEcology"] = (ca.get("ecology") or "")
            rowvals["ConservationNatureConservation"] = (ca.get("natureConservation") or "")
            rowvals["ConservationTreeSpecies"] = (ca.get("treeSpecies") or "")

            # Alien / gatunki obce (jeśli są)
            alien = obj.get("alienSpeciesRa", {}) or {}
            rowvals["AlienSpeciesRiskCategories"]     = ", ".join(alien.get("riskCategories", []) or [])
            rowvals["AlienSpeciesEnvironments"]       = ", ".join(alien.get("environments", []) or [])
            rowvals["AlienSpeciesEcologyEffect"]      = ", ".join(alien.get("ecologyEffect", []) or [])
            rowvals["AlienSpeciesTaxonLists"]         = ", ".join([str(x) for x in (alien.get("taxonLists", []) or [])])
            rowvals["AlienSpeciesInvationPotentials"] = ", ".join(alien.get("invationPotentials", []) or [])
            rowvals["AlienSpeciesRegions"]            = ", ".join(alien.get("regions", []) or [])

        except Exception as e:
            log(f"Błąd dla TaxonId {tid}: {e}")
        finally:
            for c in cols: store[c].append(rowvals[c])
            id_bucket.append(tid)
            if k % 10 == 0: log(f"→ {k}/{len(uniq_ids)} taksonów ukończono")
            time.sleep(SPECIES_SLEEP)

    result = pd.DataFrame({"TaxonId": id_bucket})
    for c in cols: result[c] = store[c]
    result.replace(["N/A", "0", 0, None], "", inplace=True)

    # ======== OPCJA: ALLROWS (bez deduplikacji) ========
    save_allrows = ask_yes_no("Pełna tabela bez deduplikacji?", "Czy chcesz zapisać dodatkowy plik z WSZYSTKIMI wierszami (bez usuwania duplikatów)?")
    if save_allrows:
        existing_lc_full = {c.lower() for c in df.columns}
        add_cols_full = [c for c in result.columns if c.lower() not in existing_lc_full]
        # WAŻNE: zawsze dołączamy klucz łączenia
        merge_cols_full = ["TaxonId"] + [c for c in add_cols_full if c.lower() != "taxonid"]
        merged_full = df.merge(result[merge_cols_full], on="TaxonId", how="left")
        with pd.ExcelWriter(OUT_ALLROWS, engine="openpyxl") as w:
            merged_full.to_excel(w, index=False)
        log(f"Zapisano (ALLROWS): {OUT_ALLROWS}")

    # ======== PRZEGLĄD (UNIKALNE) + sort RL ========
    existing_lc = {c.lower() for c in df_overview.columns}
    add_cols = [c for c in result.columns if c.lower() not in existing_lc]
    merge_cols = ["TaxonId"] + [c for c in add_cols if c.lower() != "taxonid"]
    merged = df_overview.merge(result[merge_cols], on="TaxonId", how="left")

    merged["_rl_order"] = merged["RedListCategory"].astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)
    merged = merged.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
    merged.drop(columns=["_rl_order"], inplace=True)

    with pd.ExcelWriter(OUT_WITH, engine="openpyxl") as w:
        merged.to_excel(w, index=False)
    log(f"Zapisano: {OUT_WITH}")

    # ======== tylko "chronione" ========
    protection_columns = [
        "ConservationStatus", "Artikel 17 - 2019", "TypicalSpecies", "CITES", "Bernkonventionen", "Bonnkonventionen",
        "PrioriteradeFågelarterSkogsvårdslagen", "FågeldirektivetBilaga1", "ProtectedByWorkProtectionConstitution",
        "ProtectedBirds", "DirectiveAppendix2", "DirectiveAppendix2Priority", "DirectiveAppendix4", "DirectiveAppendix5",
        "ForestrySignal", "ActionProgramStatus", "ActionProgramStart", "ActionProgramEnd", "ActionProgramName",
        "Fridlyst", "Frid_text",
    ]
    def has_protection(row) -> bool:
        empty_vals = {"N/A", "", 0, "0", "Nej", None}
        return any(row.get(col) not in empty_vals for col in protection_columns)

    only_prot = merged[merged.apply(lambda r: has_protection(r), axis=1)].copy()

    with pd.ExcelWriter(OUT_PROT, engine="openpyxl") as w:
        only_prot.to_excel(w, index=False)
    log(f"Zapisano: {OUT_PROT}")

    log("Proces zakończony sukcesem!")


if __name__ == "__main__":
    main()
