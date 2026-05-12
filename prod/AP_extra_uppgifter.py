# -*- coding: utf-8 -*-
"""
AP_extra_uppgifter_DEV.py — Artportalen export → enrich

Wersja developerska.

Zmiany względem poprzedniej wersji DEV:
• Klucze API są czytane z lokalnych plików w /secrets:
  taxonomykey.txt, specieskey.txt, listskey.txt.
• Eksport z Artportalen może mieć początkowe wiersze opisowe.
  Skrypt automatycznie wykrywa właściwy wiersz nagłówka i ignoruje wiersze powyżej.
• Riskklassning*.xlsx jest szukany najpierw w katalogu głównym repozytorium,
  potem w folderze wejściowym, wyjściowym i folderze skryptu.
• Zapytania do SpeciesDataService są wykonywane tylko raz dla każdego unikalnego TaxonId>0.
  Pełny wynik full_ zachowuje wszystkie obserwacje z pliku wejściowego.

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

import glob
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import requests

# ==== KLUCZE I ENDPOINTY ====
# Klucze API są czytane z lokalnego folderu /secrets w katalogu głównym repozytorium.
# Folder /secrets musi być dodany do .gitignore i nie powinien trafiać do GitHub.

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
SECRETS_DIR = os.path.join(REPO_ROOT, "secrets")


def load_secret(filename: str) -> str:
    """
    Wczytuje lokalny plik tekstowy z tokenem API.
    Plik powinien zawierać tylko sam token, bez cudzysłowów i bez dodatkowego opisu.
    """
    path = os.path.join(SECRETS_DIR, filename)

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Brak pliku z kluczem API: {filename}\n"
            f"Oczekiwana lokalizacja: {path}\n"
            f"Utwórz folder 'secrets' w katalogu głównym repozytorium i dodaj tam plik {filename}."
        )

    with open(path, "r", encoding="utf-8") as f:
        token = f.read().strip()

    if not token:
        raise ValueError(
            f"Plik {filename} istnieje, ale jest pusty.\n"
            f"Wpisz do niego sam token API."
        )

    return token


TAXONOMY_KEY = load_secret("taxonomykey.txt")
SPECIES_KEY = load_secret("specieskey.txt")
LISTS_KEY = load_secret("listskey.txt")

NAME_QUERY_SLEEP = 0.08
SPECIES_SLEEP = 0.08
TIMEOUT = 30

TAXON_NAME_URL = "https://api.artdatabanken.se/taxonservice/v1/taxa/names"
SPECIES_URL = "https://api.artdatabanken.se/information/v1/speciesdataservice/v1/speciesdata"

# TLS
TLS_BASE = os.getenv("TLS_BASE", "https://api.artdatabanken.se/taxonlistservice/v1")
TLS_DEFS_URL = f"{TLS_BASE}/definitions"
TLS_TAXA_URL = f"{TLS_BASE}/taxa"  # POST {"conservationListIds":[...], "outputFields":["id"]}

HEADERS_TAXON = {
    "Ocp-Apim-Subscription-Key": TAXONOMY_KEY,
    "Accept": "application/json",
}
HEADERS_SPECIES = {
    "Ocp-Apim-Subscription-Key": SPECIES_KEY,
    "Accept": "application/json",
    "Cache-Control": "no-cache",
}
HEADERS_LISTS = {
    "Ocp-Apim-Subscription-Key": LISTS_KEY,
    "Accept": "application/json",
}

# ==== TKINTER – wybór pliku/folderu i przełączniki ====

import tkinter as tk
from tkinter import filedialog, messagebox


def pick_inputs() -> Dict[str, Any]:
    root = tk.Tk()
    root.withdraw()

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


def log(msg: str) -> None:
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


def json_safe(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        url = getattr(resp, "url", "?")
        sc = getattr(resp, "status_code", "?")
        tb = getattr(resp, "text", "")
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


def bool_to_ja(v: Any) -> str:
    if isinstance(v, bool):
        return "Ja" if v else ""
    s = str(v).strip().lower()
    if s in {"true", "1", "ja", "yes", "y"}:
        return "Ja"
    return ""


def is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    return str(value).strip() in {"", "0", "N/A", "Nej", "nej", "False", "false", "None", "nan"}


# ==== EXCEL-INLÄSNING: auto-detekcja nagłówka Artportalen ====


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

    Typowy eksport z Artportalen może mieć 1–2 pierwsze wiersze opisowe.
    Funkcja szuka w pierwszych wierszach kolumn takich jak:
    TaxonId, taxon_svensktNamn, taxon_vetenskapligtNamn.

    Zwraca indeks wiersza w stylu pandas, czyli 0 = pierwszy wiersz.
    """
    preview = pd.read_excel(
        input_file,
        engine="openpyxl",
        header=None,
        nrows=max_scan_rows,
    )

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

        # Bonus za wiersz, który wygląda jak szeroka tabela z wieloma nazwami kolumn.
        score += min(len(values_set), 25) * 0.1

        if score > best_score:
            best_score = score
            best_row = int(row_idx)

    # Jeśli nie ma sensownego dopasowania, zachowujemy stare zachowanie: header=0.
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

    df = pd.read_excel(
        input_file,
        engine="openpyxl",
        header=header_row,
    )

    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    df.columns = [str(c).strip() if not pd.isna(c) else "" for c in df.columns]

    return df



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

    def _pick_id(item: Dict[str, Any]) -> int:
        ti = item.get("taxonInformation", {}) or {}
        return int(ti.get("taxonId", 0) or 0)

    exact = [
        d for d in data
        if any((
            str(d.get("displayName", "")).lower() == name_l,
            str(d.get("swedishName", "")).lower() == name_l,
            str(d.get("scientificName", "")).lower() == name_l,
        ))
    ]
    if exact:
        return _pick_id(exact[0])

    recommended = [d for d in data if d.get("isRecommended") is True]
    if recommended:
        return _pick_id(recommended[0])

    return _pick_id(data[0])


def resolve_taxon_id(row: Dict[str, Any], sv_col: Optional[str], sci_col: Optional[str]) -> int:
    swe = str(row.get(sv_col, "") or "").strip() if sv_col else ""
    sci = str(row.get(sci_col, "") or "").strip() if sci_col else ""

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


# ====== SpeciesDataService helpers ======


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


# ==== TLS: /definitions + /taxa ====

_TLS_DEFS: Dict[int, str] = {}
_TLS_CATSETS: Dict[str, Set[int]] = {}
_TLS_DEFS_READY = False
_TLS_MEMBERS: Dict[str, Set[int]] = {}


def _norm(s: str) -> str:
    return normkey(s).replace("å", "a").replace("ä", "a").replace("ö", "o")


def fetch_tls_definitions() -> None:
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
            lid = it.get("id")
            name = it.get("name") or ""
            if isinstance(lid, int) and name:
                _TLS_DEFS[lid] = name

        def find_ids_by_contains(substrs: List[str]) -> Set[int]:
            out: Set[int] = set()
            normalized_substrs = [_norm(sub) for sub in substrs]

            for lid, name in _TLS_DEFS.items():
                n = _norm(name)
                if any(sub in n for sub in normalized_substrs):
                    out.add(lid)

            return out

        _TLS_CATSETS = {
            "CITES": find_ids_by_contains(["cites"]),
            "Bernkonventionen": find_ids_by_contains(["bern"]),
            "Bonnkonventionen": find_ids_by_contains(["bonn", "cms"]),
            "FågeldirektivetBilaga1": find_ids_by_contains([
                "fageldirektivet bilaga 1",
                "fågeldirektivet bilaga 1",
            ]),
            "PrioriteradeFågelarterSkogsvårdslagen": find_ids_by_contains([
                "prioriterade fagelarter i skogsvardslagen",
                "prioriterade fågelarter i skogsvårdslagen",
                "skogsvardslagen",
                "skogsvårdslagen",
            ]),
            "Fridlyst": find_ids_by_contains([
                "fridlysta arter",
                "fridlysta faglar",
                "fridlysta fåglar",
                "fridlysta",
            ]),
            "Habitat_Bilaga2": find_ids_by_contains([
                "habitatdirektivets bilaga 2",
                "habitatdirektivet bilaga 2",
                "bilaga 2",
            ]),
            "Habitat_Bilaga2_Prio": find_ids_by_contains([
                "habitatdirektivets bilaga 2",
                "habitatdirektivet bilaga 2",
                "prioriterad",
                "prioriterade",
                "priority",
            ]),
            "Habitat_Bilaga4": find_ids_by_contains([
                "habitatdirektivets bilaga 4",
                "habitatdirektivet bilaga 4",
                "bilaga 4",
            ]),
            "Habitat_Bilaga5": find_ids_by_contains([
                "habitatdirektivets bilaga 5",
                "habitatdirektivet bilaga 5",
                "bilaga 5",
            ]),
            "IAS_Union_EU": find_ids_by_contains([
                "invasiv",
                "invasiva",
                "frammande",
                "eu-forteckning",
                "eu forteckning",
                "unionsforteckning",
                "union list",
                "eu list",
            ]),
        }

        _TLS_DEFS_READY = True

        if DEBUG:
            for cat, ids in _TLS_CATSETS.items():
                sample = ", ".join(
                    [f"{i}:{_TLS_DEFS.get(i, '?')[:24]}" for i in list(sorted(ids))[:6]]
                )
                log(f" → {cat}: {len(ids)} id ({sample})")

    except Exception as e:
        log(f"TLS /definitions wyjątek: {e}")


def tls_fetch_members_for_list_ids(list_ids: Set[int]) -> Set[int]:
    """Zwraca zbiór TaxonId należących do dowolnej z list w list_ids (POST /taxa)."""
    if not list_ids:
        return set()

    try:
        payload = {
            "conservationListIds": sorted(list(list_ids)),
            "outputFields": ["id"],
        }
        r = requests.post(TLS_TAXA_URL, headers=HEADERS_LISTS, json=payload, timeout=TIMEOUT)

        if r.status_code != 200 or not r.content:
            log(f"TLS /taxa {r.status_code} — {r.text[:200]!r}")
            return set()

        data = json_safe(r)
        members: Set[int] = set()

        def walk(x: Any) -> None:
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
                log(f" ↳ członków: {len(members)} (przykład: {preview})")
            else:
                log(" ↳ członków: 0")

        return members

    except Exception as e:
        log(f"TLS /taxa wyjątek: {e}")
        return set()


def tls_build_memberships() -> None:
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
        "DirectiveAppendix2": hit("Habitat_Bilaga2"),
        "DirectiveAppendix2Priority": hit("Habitat_Bilaga2_Prio"),
        "DirectiveAppendix4": hit("Habitat_Bilaga4"),
        "DirectiveAppendix5": hit("Habitat_Bilaga5"),
        "IAS_Union_EU": hit("IAS_Union_EU"),
    }


# ==== Riskklassning merge ====


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
    Priorytet: root repo → folder wejściowy → folder wyjściowy → folder skryptu.
    """
    search_dirs = unique_existing_dirs([
        REPO_ROOT,
        input_dir,
        out_dir,
        SCRIPT_DIR,
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


# ==== GŁÓWNY PRZEPŁYW ====


def main() -> None:
    global LOG_FILE, DEBUG, DEBUG_ROWS

    paths = pick_inputs()

    input_file = paths["INPUT_FILE"]
    outdir = paths["OUTDIR"]
    LOG_FILE = paths["LOG_FILE"]
    DEBUG = bool(paths["DEBUG"])
    DEBUG_ROWS = []

    try:
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
    except Exception:
        pass

    log(f"Plik wejściowy: {input_file}")
    log(f"Folder wyjściowy: {outdir}")

    df = read_artportalen_excel(input_file)
    orig_cols = list(df.columns)

    # Wykryj kolumny.
    def _find(dataframe: pd.DataFrame, names: List[str]) -> Optional[str]:
        low = {str(c).strip().lower(): c for c in dataframe.columns}
        for nm in names:
            if nm.lower() in low:
                return low[nm.lower()]
        return None

    col_taxonid = _find(df, ["taxonid", "taxon_id", "taxon id"])
    col_sv = _find(
        df,
        [
            "taxon_svensktnamn",
            "taxon_svensktNamn",
            "svensktnamn",
            "svensk_namn",
            "svenskt namn",
        ],
    ) or ("taxon_svensktNamn" if "taxon_svensktNamn" in df.columns else None)
    col_sci = _find(
        df,
        [
            "taxon_vetenskapligtnamn",
            "taxon_vetenskapligtNamn",
            "vetenskapligtnamn",
            "vetenskapligt_namn",
            "vetenskapligt namn",
        ],
    ) or ("taxon_vetenskapligtNamn" if "taxon_vetenskapligtNamn" in df.columns else None)

    if col_taxonid:
        df["TaxonId"] = pd.to_numeric(df[col_taxonid], errors="coerce").fillna(0).astype("int64")
        log("Wykryto kolumnę TaxonId — pomijam dopasowanie po nazwach.")
    else:
        if not col_sv and not col_sci:
            raise ValueError(
                "Brak kolumny TaxonId oraz nazw ('taxon_svensktNamn' / 'taxon_vetenskapligtNamn').\n"
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

    # Wydajność: do API wysyłamy tylko unikalne TaxonId,
    # ale NIE deduplikujemy df. Dzięki temu full_ zachowuje wszystkie obserwacje.
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

    # TLS definitions + memberships.
    fetch_tls_definitions()
    if _TLS_DEFS_READY:
        tls_build_memberships()
    else:
        log("TLS: /definitions niedostępne — użyję tylko fallbacków z SpeciesDataService.")

    # Docelowe kolumny.
    cols = [
        "ScientificName",
        "SwedishName",
        "DisplayName",
        "Category",
        "ConservationStatus",
        "RedListCategory",
        "RedListCriterion",
        "RedListPeriodName",
        "RedListCriterionText",
        "ActionProgramName",
        "ActionProgramStatus",
        "ActionProgramStart",
        "ActionProgramEnd",
        "ForestrySignal",
        "ForestrySignalSpecies",
        "TypicalSpecies",
        "LandscapeType",
        "Biotopes",
        "CITES",
        "Bernkonventionen",
        "Bonnkonventionen",
        "PrioriteradeFågelarterSkogsvårdslagen",
        "FågeldirektivetBilaga1",
        "Fridlyst",
        "Frid_text",
        "ProtectedByWorkProtectionConstitution",
        "ProtectedBirds",
        "DirectiveAppendix2",
        "DirectiveAppendix2Priority",
        "DirectiveAppendix4",
        "DirectiveAppendix5",
        "Artikel 17 - 2019",
        "Characteristic",
        "SpreadAndStatus",
        "Ecology",
        "Threat",
        "ConservationMeasures",
        "Other",
        "SwedishPresence",
        "ImmigrationHistory",
        "SubstrateInformation",
        "EcologicalGroups",
        "ConservationEcology",
        "ConservationNatureConservation",
        "ConservationTreeSpecies",
        # GEIAA / Alien species.
        "AlienSpeciesRiskCategories",
        "AlienSpeciesEnvironments",
        "AlienSpeciesEcologyEffect",
        "AlienSpeciesTaxonLists",
        "AlienSpeciesInvationPotentials",
        "AlienSpeciesRegions",
        # TLS IAS Union list.
        "IAS_Union_EU",
    ]

    store = {c: [] for c in cols}
    id_bucket = []

    for k, tid in enumerate(uniq_ids, start=1):
        log(f"— {k}/{len(uniq_ids)} — TaxonId={tid}")
        record = {c: "" for c in cols}
        dbg: Dict[str, Any] = {"TaxonId": tid}

        try:
            resp = requests.get(
                f"{SPECIES_URL}?taxa={tid}&culture=sv-SE",
                headers=HEADERS_SPECIES,
                timeout=TIMEOUT,
            )
            data = json_safe(resp) if resp and resp.status_code == 200 else []
            item = (data[0] if isinstance(data, list) and data else data) or {}
            obj = item.get("speciesData", item) or {}

            def gv(*keys: str, default: Any = "") -> Any:
                o: Any = obj
                for ky in keys:
                    if isinstance(o, dict):
                        o = o.get(ky)
                    else:
                        o = None
                return o if (o is not None and o != "") else default

            # Podstawowe.
            record["ScientificName"] = obj.get("scientificName") or item.get("scientificName") or ""
            record["SwedishName"] = gv("swedishName")
            record["DisplayName"] = gv("displayName")
            record["Category"] = gv("category", "name")
            record["ConservationStatus"] = gv("conservationStatus")

            # Redlist.
            redlist_info = obj.get("redlistInfo", []) or []
            red = next(
                (
                    r for r in redlist_info
                    if "2020" in str(((r or {}).get("period") or {}).get("name", ""))
                ),
                None,
            )
            if not red:
                red = next(
                    (
                        r for r in redlist_info
                        if ((r or {}).get("period") or {}).get("current") is True
                    ),
                    None,
                )
            if not red and redlist_info:
                red = redlist_info[0]

            record["RedListCategory"] = (red or {}).get("category", "")
            record["RedListCriterion"] = (red or {}).get("criterion", "")
            record["RedListPeriodName"] = ((red or {}).get("period") or {}).get("name", "")
            record["RedListCriterionText"] = (red or {}).get("criterionText", "")

            # TLS MEMBERSHIP.
            tls_flags = tls_flags_by_membership(tid) if (_TLS_DEFS_READY and _TLS_MEMBERS) else {}

            # Nature conservation.
            nc = obj.get("natureConservation", {}) or {}
            act = nc.get("actionProgram", {}) or {}
            record["ActionProgramName"] = act.get("program", "")
            record["ActionProgramStatus"] = act.get("status", "")
            record["ActionProgramStart"] = act.get("startYear", "")
            record["ActionProgramEnd"] = act.get("endYear", "")

            # ForestrySignal + species-lista.
            record["ForestrySignal"] = ((nc.get("forestryBoardSignalSpecies", {}) or {}).get("apply")) or ""
            fs_names = []
            fss = nc.get("forestryBoardSignalSpecies") or {}

            def _add_names(val: Any) -> None:
                if isinstance(val, list):
                    for el in val:
                        if isinstance(el, dict):
                            nm = (
                                el.get("name")
                                or el.get("swedishName")
                                or el.get("displayName")
                                or el.get("scientificName")
                            )
                            if nm:
                                fs_names.append(str(nm))
                        elif isinstance(el, str) and el.strip():
                            fs_names.append(el.strip())
                elif isinstance(val, dict):
                    nm = (
                        val.get("name")
                        or val.get("swedishName")
                        or val.get("displayName")
                        or val.get("scientificName")
                    )
                    if nm:
                        fs_names.append(str(nm))
                elif isinstance(val, str) and val.strip():
                    fs_names.append(val.strip())

            if isinstance(fss, dict):
                for key in ("speciesNames", "species", "names", "speciesList", "items"):
                    _add_names(fss.get(key))
            elif isinstance(fss, list):
                _add_names(fss)

            record["ForestrySignalSpecies"] = "; ".join(sorted(set(n for n in fs_names if n)))
            record["TypicalSpecies"] = join_typical_species(nc.get("typicalSpecies", []))
            record["LandscapeType"] = join_name_with_attr(obj.get("landscapeTypes", []), "name", "status")
            record["Biotopes"] = join_name_with_attr(obj.get("biotopes", []), "name", "significance")

            # Fallback lists scanner.
            lists = nc.get("lists", []) or []

            def has_list_flag(_lists: Any, list_name: str) -> str:
                ln = (list_name or "").strip().lower()
                for it in (_lists or []):
                    if not isinstance(it, dict):
                        continue
                    nm = str(it.get("name", "")).strip().lower()
                    title = str(it.get("title", "")).strip().lower()
                    if ln and (ln == nm or ln in nm or ln in title):
                        return "Ja"
                    if any_child_named([it], list_name) == "Ja":
                        return "Ja"
                return ""

            fb_cites = has_list_flag(lists, "CITES")
            fb_bern = has_list_flag(lists, "Bernkonventionen")
            fb_bonn = has_list_flag(lists, "Bonnkonventionen")
            fb_prio = has_list_flag(lists, "Prioriterade fågelarter i skogsvårdslagen")
            fb_fd1 = has_list_flag(lists, "Fågeldirektivet bilaga 1")

            record["CITES"] = tls_flags.get("CITES") or fb_cites
            record["Bernkonventionen"] = tls_flags.get("Bernkonventionen") or fb_bern
            record["Bonnkonventionen"] = tls_flags.get("Bonnkonventionen") or fb_bonn
            record["PrioriteradeFågelarterSkogsvårdslagen"] = (
                tls_flags.get("PrioriteradeFågelarterSkogsvårdslagen") or fb_prio
            )
            record["FågeldirektivetBilaga1"] = tls_flags.get("FågeldirektivetBilaga1") or fb_fd1

            # FRIDLYST + Frid_text.
            prot_txt = (obj.get("protectedText") or "").strip()
            frid_flag = (
                tls_flags.get("Fridlyst")
                or has_list_flag(lists, "Fridlysta arter")
                or has_list_flag(lists, "Fridlysta fåglar")
            )
            if not frid_flag and prot_txt and ("fridlyst" in prot_txt.lower()):
                frid_flag = "Ja"

            record["Fridlyst"] = frid_flag or ""
            record["Frid_text"] = prot_txt or ""

            # Habitatdirektivet (SpeciesData → fallback) + TLS.
            sd_hd2 = bool_to_ja(nc.get("habitatDirectiveAppendix2") or nc.get("habitatdirectiveappendix2"))
            sd_hd2p = bool_to_ja(
                nc.get("habitatDirectiveAppendix2PrioritizedSpecie")
                or nc.get("habitatDirectiveAppendix2PrioritizedSpecies")
                or nc.get("habitatdirectiveappendix2prioritizedspecie")
                or nc.get("habitatdirectiveappendix2prioritizedspecies")
            )
            sd_hd4 = bool_to_ja(nc.get("habitatDirectiveAppendix4") or nc.get("habitatdirectiveappendix4"))
            sd_hd5 = bool_to_ja(nc.get("habitatDirectiveAppendix5") or nc.get("habitatdirectiveappendix5"))

            record["DirectiveAppendix2"] = tls_flags.get("DirectiveAppendix2") or sd_hd2
            record["DirectiveAppendix2Priority"] = tls_flags.get("DirectiveAppendix2Priority") or sd_hd2p
            record["DirectiveAppendix4"] = tls_flags.get("DirectiveAppendix4") or sd_hd4
            record["DirectiveAppendix5"] = tls_flags.get("DirectiveAppendix5") or sd_hd5
            record["ProtectedByWorkProtectionConstitution"] = nc.get("protectedByWorkProtectionConstitution", "") or ""
            record["ProtectedBirds"] = nc.get("protectedBirds", "") or ""

            # Artikel 17 - 2019.
            art17 = ""
            ca = obj.get("conservationAssessments", {}) or {}
            for p in (ca.get("periods") or []):
                if "2019" in str(p.get("name", "")):
                    chunks = []
                    for t in (p.get("trends", []) or []):
                        cat = t.get("category", "")
                        ev = t.get("evaluation", "")
                        tr = t.get("trend", "")
                        part = f"{cat}: {ev}{' (' + tr + ')' if tr else ''}"
                        if part.strip():
                            chunks.append(part)
                    art17 = ", ".join(chunks)
                    break
            record["Artikel 17 - 2019"] = art17

            # Teksty.
            sft = obj.get("speciesFactText", {}) or {}
            record["Characteristic"] = sft.get("characteristic", "") or ""
            record["SpreadAndStatus"] = sft.get("spreadAndStatus", "") or ""
            record["Ecology"] = sft.get("ecology", "") or ""
            record["Threat"] = sft.get("threat", "") or ""
            record["ConservationMeasures"] = sft.get("conservationMeasures", "") or ""
            record["Other"] = sft.get("other", "") or ""

            tri = obj.get("taxonRelatedInformation", {}) or {}
            record["SwedishPresence"] = tri.get("swedishPresence", "") or ""
            record["ImmigrationHistory"] = tri.get("immigrationHistory", "") or ""

            sub = obj.get("substrateInformation", []) or []
            record["SubstrateInformation"] = join_name_with_attr(sub, "name", sub="use")

            eco = obj.get("ecologicalGroups", []) or []
            eg = ", ".join(sorted(set(g.get("name", "") for g in eco if g.get("active"))))
            record["EcologicalGroups"] = eg

            ca2 = obj.get("conservationAssessments", {}) or {}
            record["ConservationEcology"] = ca2.get("ecology") or ""
            record["ConservationNatureConservation"] = ca2.get("natureConservation") or ""
            record["ConservationTreeSpecies"] = ca2.get("treeSpecies") or ""

            # GEIAA / Alien species.
            alien = obj.get("alienSpeciesRa", {}) or {}
            record["AlienSpeciesRiskCategories"] = "; ".join(alien.get("riskCategories", []) or [])
            record["AlienSpeciesEnvironments"] = "; ".join(alien.get("environments", []) or [])
            record["AlienSpeciesEcologyEffect"] = "; ".join(alien.get("ecologyEffect", []) or [])
            record["AlienSpeciesTaxonLists"] = "; ".join(str(x) for x in (alien.get("taxonLists", []) or []))
            record["AlienSpeciesInvationPotentials"] = "; ".join(alien.get("invationPotentials", []) or [])
            record["AlienSpeciesRegions"] = "; ".join(alien.get("regions", []) or [])

            # IAS (Union list) z TLS.
            record["IAS_Union_EU"] = tls_flags.get("IAS_Union_EU", "")

            if DEBUG:
                dbg.update({
                    "SwedishName": record["SwedishName"],
                    "ScientificName": record["ScientificName"],
                    "TLS_CITES": record["CITES"],
                    "TLS_Bern": record["Bernkonventionen"],
                    "TLS_Bonn": record["Bonnkonventionen"],
                    "TLS_FD1": record["FågeldirektivetBilaga1"],
                    "TLS_Prio": record["PrioriteradeFågelarterSkogsvårdslagen"],
                    "TLS_Fridlyst": record["Fridlyst"],
                    "TLS_HD2": record["DirectiveAppendix2"],
                    "TLS_HD2P": record["DirectiveAppendix2Priority"],
                    "TLS_HD4": record["DirectiveAppendix4"],
                    "TLS_HD5": record["DirectiveAppendix5"],
                    "TLS_IAS_Union_EU": record["IAS_Union_EU"],
                })

            if (k % 10) == 0:
                log(f"→ {k}/{len(uniq_ids)} taksonów ukończono")
            time.sleep(SPECIES_SLEEP)

        except Exception as e:
            log(f"Błąd dla TaxonId {tid}: {e}")
            dbg["Error"] = str(e)

        id_bucket.append(tid)
        for c in cols:
            store[c].append(record.get(c, ""))

        if DEBUG:
            DEBUG_ROWS.append(dbg)

    # Złóż wynik.
    result = pd.DataFrame({"TaxonId": id_bucket}) if id_bucket else pd.DataFrame(columns=["TaxonId"])
    for c in cols:
        result[c] = store.get(c, [])

    result.replace(["N/A", "0", 0, None], "", inplace=True)

    # Nie dubluj istniejących kolumn ze źródła.
    add_cols = [c for c in result.columns if c != "TaxonId" and c not in df.columns]
    merge_cols = ["TaxonId"] + add_cols
    full_enriched = df.merge(result[merge_cols], on="TaxonId", how="left")

    # Sortowanie po RL (RE→CR→EN→VU→NT→LC→DD→NA→NE).
    RL_ORDER = {"RE": 0, "CR": 1, "EN": 2, "VU": 3, "NT": 4, "LC": 5, "DD": 6, "NA": 7, "NE": 8}

    if paths["WANT_FULL"]:
        fe = full_enriched.copy()
        fe["_rl_order"] = fe.get("RedListCategory", "").astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)
        fe = fe.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
        fe.drop(columns=["_rl_order"], inplace=True)

        with pd.ExcelWriter(paths["OUT_FULL"], engine="openpyxl") as w:
            fe.to_excel(w, index=False)
        log(f"Zapisano: {paths['OUT_FULL']}")

    # Overview: dedupe po TaxonId.
    overview = full_enriched[full_enriched["TaxonId"] > 0].drop_duplicates(subset=["TaxonId"], keep="first").copy()
    overview["_rl_order"] = overview.get("RedListCategory", "").astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)
    overview = overview.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
    overview.drop(columns=["_rl_order"], inplace=True)

    # Wyczyść "Nej"/"False" w flagach, w tym IAS_Union_EU.
    flag_cols = [
        "CITES",
        "Bernkonventionen",
        "Bonnkonventionen",
        "FågeldirektivetBilaga1",
        "PrioriteradeFågelarterSkogsvårdslagen",
        "Fridlyst",
        "DirectiveAppendix2",
        "DirectiveAppendix2Priority",
        "DirectiveAppendix4",
        "ProtectedByWorkProtectionConstitution",
        "DirectiveAppendix5",
        "IAS_Union_EU",
    ]

    for c in flag_cols:
        if c in overview.columns:
            overview[c] = overview[c].astype(str).replace({"Nej": "", "nej": "", "False": "", "false": ""})

    with pd.ExcelWriter(paths["OUT_WITH"], engine="openpyxl") as w:
        overview.to_excel(w, index=False)
    log(f"Zapisano: {paths['OUT_WITH']}")

    # bara_skyddade — bez IAS_Union_EU, czyli IAS nie wchodzi do filtra.
    protection_columns = [
        "ConservationStatus",
        "Artikel 17 - 2019",
        "TypicalSpecies",
        "CITES",
        "Bernkonventionen",
        "Bonnkonventionen",
        "PrioriteradeFågelarterSkogsvårdslagen",
        "FågeldirektivetBilaga1",
        "ProtectedByWorkProtectionConstitution",
        "ProtectedBirds",
        "DirectiveAppendix2",
        "DirectiveAppendix2Priority",
        "DirectiveAppendix4",
        "DirectiveAppendix5",
        "ForestrySignal",
        "ActionProgramStatus",
        "ActionProgramStart",
        "ActionProgramEnd",
        "ActionProgramName",
        "Fridlyst",
    ]

    def has_protection(row: pd.Series) -> bool:
        for col in protection_columns:
            if col in row.index and not is_empty_value(row.get(col)):
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

    # DEBUG dump.
    if DEBUG:
        try:
            pd.DataFrame(DEBUG_ROWS).to_csv(paths["DBG_FILE"], index=False, encoding="utf-8-sig")
            log(f"DEBUG zapisano: {paths['DBG_FILE']}")

            def _sum_yes(df_: pd.DataFrame, col: str) -> int:
                if col not in df_.columns:
                    return 0
                return int((df_[col].astype(str).str.lower() == "ja").sum())

            for col in flag_cols + ["Fridlyst"]:
                log(f"SUMA '{col}=Ja': {_sum_yes(overview, col)}")

        except Exception as e:
            log(f"DEBUG zapis CSV nieudany: {e}")

    # Opcjonalny MERGE risk-plik do WITH.
    optional_merge_risk_file(os.path.dirname(paths["INPUT_FILE"]), paths["OUT_WITH"])

    log("Proces zakończony sukcesem!")


if __name__ == "__main__":
    main()
