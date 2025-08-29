#Zmien w input_file sciezke do pliku z danymi Excel z artportalen
#Zachowaj biezacy skrypt, plik z gatunkami inwazyjnymi oraz plik przetwarzany w tej samej lokalizacji
#Skrypt usuwa duplikaty a nastepnie do danych z artportalen dopisuje informacje z artfakta na temat statusu ochrony czy inwazyjnosci. 
#Inwazyjnosc bazuje na pobranym pliku XLS.

print("Witaj w skrypcie uzupelniajacym dane o gatunkach na bazie TaxonId danymi z Artfakta wykorzystujac ich API")
print("Jako wynik skryptu uzyskasz nowy plik XLS z nowymi fajnymi kolumnami")
print("Skrypt realizuje okolo 4-5 gatunkow na sekunde, wiec w zaleznosci od wielkosci pliku wejsciowego analiza moze chwile zajac")

import pandas as pd
import requests
import time
import os

# === TWOJE KLUCZE ===
taxonomy_key        = "a2753962eba449bbbfdd253baf66fd26"
species_key         = "71c0e472ab954c37896ee2d91f042ff1"
input_file          = r"D:\Artportalen_tabeller_Script_with_data\Artportalen20152025_TableToExcel.xlsx"
output_file         = input_file.replace(".xlsx", "_with_data.xlsx")
log_file            = os.path.join(os.path.dirname(input_file), "log.txt")

headers_taxon    = {"Ocp-Apim-Subscription-Key": taxonomy_key}
headers_species  = {"Ocp-Apim-Subscription-Key": species_key, "Cache-Control": "no-cache"}

def log_and_print(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(line + "\n")

def get_json_safe(resp):
    try:
        return resp.json()
    except Exception:
        log_and_print(f"‼ Nie-JSON z {resp.url} [{resp.status_code}]")
        return {}

if os.path.exists(log_file):
    os.remove(log_file)
log_and_print(f"Start przetwarzania: {input_file}")

df = pd.read_excel(input_file, engine="openpyxl")
columns_lower = [c.lower() for c in df.columns]

# --- ROZGAŁĘZIENIE --- #
if not any(c.lower() == "taxonid" for c in df.columns):
    # --- TRYB: Brak TaxonId/TaxonID, zostaw obecny kod, np. deduplikacja lub inna logika
    log_and_print("Nie znaleziono kolumny TaxonId / TaxonID. Skrypt działa w trybie 'bezpośrednim'.")
    # ... tutaj Twój kod ze starej logiki, np. deduplikacja, export, itp. ...
    # Przykład: wylistuj kolumny i zakończ
    print("Kolumny dostępne w pliku:", df.columns.tolist())
    log_and_print("Zakończono, bo brak TaxonId.")
    exit(0)
else:
    # --- TRYB: Jest TaxonId/TaxonID, przejdź od razu do ETAPU 2 ---
    # Ustal właściwą nazwę kolumny (z zachowaniem wielkości liter!)
    col_taxonid = next(c for c in df.columns if c.lower() == "taxonid")
    df.rename(columns={col_taxonid: "TaxonId"}, inplace=True)
    log_and_print("Znaleziono kolumnę TaxonId, przechodzę do pobierania statusów ochrony.")

# --- ETAP 2: POBIERANIE PEŁNYCH DANYCH ---

species_url = "https://api.artdatabanken.se/information/v1/speciesdataservice/v1/speciesdata"
uniq = df[["TaxonId"]].drop_duplicates().copy()
taxon_ids = uniq["TaxonId"].astype(int).tolist()

def join_list(lst, key, sub=None, sep="; "):
    if not lst: return ""
    if sub:
        return sep.join(sorted(set(f"{x.get(key, '')} ({x.get(sub, '')})" for x in lst if x.get(key))))
    return sep.join(sorted(set(str(x.get(key, "")) for x in lst if x.get(key))))

def join_typical_species(ts):
    if not ts: return ""
    return "; ".join(sorted(set(f"{t.get('typcial','')} ({', '.join(t.get('regions',[]))})" for t in ts if t.get('typcial'))))

def join_substrate_info(si):
    if not si: return ""
    return "; ".join(sorted(set(
        f"{s.get('name','')} ({s.get('significance','')}, {s.get('use','')})"
        for s in si if s.get('name')
    )))

def join_ecogroups(eg):
    if not eg: return ""
    return "; ".join(sorted(set(g.get('name','') for g in eg if g.get('active'))))

def get_val(obj, *keys, default=""):
    for key in keys:
        if obj is None:
            return default
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list):
            try:
                obj = obj[key]
            except Exception:
                return default
    return obj if obj is not None and obj != "" else default

# REKURENCYJNE zbieranie childów dla wszystkich poziomów (listy ochronne)
def extract_lists_full(lists):
    out = {
        "CITES": [],
        "Bernkonventionen": [],
        "Bonnkonventionen": [],
        "PrioriteradeFågelarterSkogsvårdslagen": "",
        "FågeldirektivetBilaga1": "",
        "Fridlyst": ""
    }
    def recurse(childs, parent_name=None):
        for c in childs or []:
            name = c.get("name", "")
            # Załączniki
            if parent_name in ["CITES", "Bernkonventionen", "Bonnkonventionen"] and name:
                out[parent_name].append(name)
            # Flagi
            if "Prioriterade fågelarter i skogsvårdslagen" in name:
                out["PrioriteradeFågelarterSkogsvårdslagen"] = "Ja"
            if "Fågeldirektivet bilaga 1" in name:
                out["FågeldirektivetBilaga1"] = "Ja"
            if parent_name == "Fridlysta arter":
                out["Fridlyst"] = "Ja"
            # Rekurencja głębiej
            if c.get("childs"):
                recurse(c["childs"], parent_name)
    for item in lists or []:
        nm = item.get("name", "")
        if nm in ["CITES", "Bernkonventionen", "Bonnkonventionen", "Fridlysta arter"]:
            recurse(item.get("childs", []), nm)
        elif nm == "Fåglar":
            recurse(item.get("childs", []), nm)
        elif nm == "Fridlysta arter":
            out["Fridlyst"] = "Ja"
    for k in ["CITES", "Bernkonventionen", "Bonnkonventionen"]:
        out[k] = "; ".join(sorted(set(out[k])))
    return out

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
    "ConservationEcology","ConservationNatureConservation","ConservationTreeSpecies","AlienSpeciesRiskCategories",
    "AlienSpeciesEnvironments",
    "AlienSpeciesEcologyEffect",
    "AlienSpeciesTaxonLists",
    "AlienSpeciesInvationPotentials",
    "AlienSpeciesRegions"
]
store = {c: [] for c in cols}

for idx, tid in enumerate(taxon_ids, start=1):
    log_and_print(f"— {idx}/{len(taxon_ids)} — TaxonId={tid} —")
    if tid == 0:
        for c in cols: store[c].append("")
        continue

    resp = requests.get(f"{species_url}?taxa={tid}", headers=headers_species)
    data = get_json_safe(resp)
    obj = data[0]["speciesData"] if isinstance(data, list) and data else {}

    # ScientificName z dwóch poziomów!
    sci_name = get_val(obj, "scientificName", default="") or get_val(data[0], "scientificName", default="")
    store["ScientificName"].append(sci_name)
    store["SwedishName"].append(get_val(obj, "swedishName", default=""))
    store["DisplayName"].append(get_val(obj, "displayName", default=""))
    store["Category"].append(get_val(obj, "category", "name", default=""))
    store["ConservationStatus"].append(get_val(obj, "conservationStatus", default=""))

    # RedList
    redlist_info = obj.get("redlistInfo", [])
    red = next((r for r in redlist_info if "2020" in get_val(r,"period","name","")), None)
    if not red:
        red = next((r for r in redlist_info if get_val(r,"period","current","") is True), None)
    if not red and redlist_info: red = redlist_info[0]
    store["RedListCategory"].append(get_val(red,"category", default=""))
    store["RedListCriterion"].append(get_val(red,"criterion", default=""))
    store["RedListPeriodName"].append(get_val(red,"period","name", default=""))
    store["RedListCriterionText"].append(get_val(red,"criterionText", default=""))

    # ActionProgram (natureConservation)
    nc = obj.get("natureConservation",{})
    act = nc.get("actionProgram",{})
    store["ActionProgramName"].append(get_val(act,"program", default=""))
    store["ActionProgramStatus"].append(get_val(act,"status", default=""))
    store["ActionProgramStart"].append(get_val(act,"startYear", default=""))
    store["ActionProgramEnd"].append(get_val(act,"endYear", default=""))

    # ForestrySignal
    store["ForestrySignal"].append(get_val(nc,"forestryBoardSignalSpecies","apply", default=""))

    # TypicalSpecies
    store["TypicalSpecies"].append(join_typical_species(nc.get("typicalSpecies", [])))

    # LandscapeType
    store["LandscapeType"].append(join_list(obj.get("landscapeTypes", []), "name", "status"))

    # Biotopes
    store["Biotopes"].append(join_list(obj.get("biotopes", []), "name", "significance"))

    # Listy ochronne (rekurencyjna nowa wersja!)
    lists = nc.get("lists", [])
    lists_data = extract_lists_full(lists)
    store["CITES"].append(lists_data["CITES"])
    store["Bernkonventionen"].append(lists_data["Bernkonventionen"])
    store["Bonnkonventionen"].append(lists_data["Bonnkonventionen"])
    store["PrioriteradeFågelarterSkogsvårdslagen"].append(lists_data["PrioriteradeFågelarterSkogsvårdslagen"])
    store["FågeldirektivetBilaga1"].append(lists_data["FågeldirektivetBilaga1"])
    store["Fridlyst"].append(lists_data["Fridlyst"])

    # Frid_text – pokaż childy jeśli są
    fridlysta_texts = []
    for it in lists or []:
        if it.get("name") == "Fridlysta arter":
            fridlysta_texts += [c.get("name") for c in it.get("childs", []) if c.get("name")]
    fridlyst_text_val = "; ".join(sorted(set(fridlysta_texts))) if fridlysta_texts else ""
    frid_text = get_val(obj, "speciesFactText", "characteristic", default="")
    store["Frid_text"].append(fridlyst_text_val if fridlyst_text_val else (frid_text if frid_text != "" else get_val(obj, "protectedText", default="")))

    # Protection & directives
    store["ProtectedByWorkProtectionConstitution"].append(get_val(nc,"protectedByWorkProtectionConstitution", default=""))
    store["ProtectedBirds"].append(get_val(nc,"protectedBirds", default=""))
    store["DirectiveAppendix2"].append(get_val(nc,"habitationDirectiveAppendix2", default=""))
    store["DirectiveAppendix2Priority"].append(get_val(nc,"habitationDirectiveAppendix2PrioritizedSpecie", default=""))
    store["DirectiveAppendix4"].append(get_val(nc,"habitationDirectiveAppendix4", default=""))
    store["DirectiveAppendix5"].append(get_val(nc,"habitationDirectiveAppendix5", default=""))

    # Artikel 17 - 2019 – jeśli jest conservationAssessments z trendami, ew. pusta
    art17 = ""
    ca = obj.get("conservationAssessments",{})
    if isinstance(ca, dict) and "periods" in ca:
        for p in ca["periods"]:
            if "2019" in str(p.get("name", "")):
                for t in p.get("trends", []):
                    art17 += f"{t.get('category')}: {t.get('evaluation')} ({t.get('trend')}); "
        art17 = art17.strip("; ")
    store["Artikel 17 - 2019"].append(art17 if art17 else "")

    # --- Dodatkowe teksty i dane (speciesFactText)
    sft = obj.get("speciesFactText",{})
    store["Characteristic"].append(get_val(sft, "characteristic", default=""))
    store["SpreadAndStatus"].append(get_val(sft, "spreadAndStatus", default=""))
    store["Ecology"].append(get_val(sft, "ecology", default=""))
    store["Threat"].append(get_val(sft, "threat", default=""))
    store["ConservationMeasures"].append(get_val(sft, "conservationMeasures", default=""))
    store["Other"].append(get_val(sft, "other", default=""))

    # Presence, immigration
    tri = obj.get("taxonRelatedInformation",{})
    store["SwedishPresence"].append(get_val(tri, "swedishPresence", default=""))
    store["ImmigrationHistory"].append(get_val(tri, "immigrationHistory", default=""))

    # SubstrateInformation
    store["SubstrateInformation"].append(join_substrate_info(obj.get("substrateInformation", [])))
    store["EcologicalGroups"].append(join_ecogroups(obj.get("ecologicalGroups", [])))

    # Conservation assessments (ecology/natureConservation/treeSpecies)
    ca = obj.get("conservationAssessments",{})
    store["ConservationEcology"].append(get_val(ca,"ecology", default=""))
    store["ConservationNatureConservation"].append(get_val(ca,"natureConservation", default=""))
    store["ConservationTreeSpecies"].append(get_val(ca,"treeSpecies", default=""))
    
    # INWAZYJNE
    alien = obj.get("alienSpeciesRa", {})
    store["AlienSpeciesRiskCategories"].append("; ".join(alien.get("riskCategories", [])) if alien else "")
    store["AlienSpeciesEnvironments"].append("; ".join(alien.get("environments", [])) if alien else "")
    store["AlienSpeciesEcologyEffect"].append("; ".join(alien.get("ecologyEffect", [])) if alien else "")
    store["AlienSpeciesTaxonLists"].append("; ".join(str(x) for x in alien.get("taxonLists", [])) if alien else "")
    store["AlienSpeciesInvationPotentials"].append("; ".join(alien.get("invationPotentials", [])) if alien else "")
    store["AlienSpeciesRegions"].append("; ".join(alien.get("regions", [])) if alien else "")

  

# --- scalanie i zapis ---
result = pd.DataFrame({"TaxonId": taxon_ids})
for c in cols:
    result[c] = store[c]
result.replace(["N/A", "0", 0], "", inplace=True)
merged = df.merge(result, on="TaxonId", how="left")
with pd.ExcelWriter(output_file, engine="openpyxl") as w:
    merged.to_excel(w, index=False)
log_and_print(f"Zapisano: {output_file}")



# === ETAP 3B: Dołączenie danych z Riskklassning2024.xlsx na podstawie TaxonId ===
risk_file = os.path.join(os.path.dirname(output_file), "Riskklassning2024.xlsx")
if os.path.exists(risk_file):
    try:
        risk_df = pd.read_excel(risk_file, engine="openpyxl")
        # Ustal właściwą nazwę kolumny TaxonId w risk_df
        risk_tax_col = [c for c in risk_df.columns if c.lower() == "taxonid"][0]
        # Wylistuj wszystkie kolumny w risk_df by łatwo wybrać te, które chcesz przenieść
        print("Kolumny dostępne w Riskklassning2024.xlsx:", risk_df.columns.tolist())
        # PRZYKŁAD – zmień na wybrane kolumny:
        risk_cols_to_add = [col for col in risk_df.columns if col != risk_tax_col]  # domyślnie wszystkie poza TaxonId

        # Ogranicz tylko do TaxonId i wybranych
        risk_df = risk_df[[risk_tax_col] + risk_cols_to_add]
        # Wczytaj najnowszą wersję merged (po zapisie wyżej)
        merged_df = pd.read_excel(output_file, engine="openpyxl")
        # Scal po TaxonId (left join, aby nie tracić żadnego rekordu z głównego pliku)
        merged_final = merged_df.merge(risk_df, left_on="TaxonId", right_on=risk_tax_col, how="left")
        # Usuń powielony TaxonId z risk_df jeśli jest (zazwyczaj niepotrzebne, ale bywa)
        if risk_tax_col != "TaxonId" and risk_tax_col in merged_final.columns:
            merged_final = merged_final.drop(columns=[risk_tax_col])
        # Zapisz efekt końcowy pod nową nazwą
        merged_final.to_excel(output_file, index=False)
        log_and_print(f"✅ ETAP 3B: Dodano kolumny z Riskklassning2024.xlsx i nadpisano {output_file}")
    except Exception as e:
        log_and_print(f"‼ Błąd podczas ETAPU 3B: {e}")
else:
    log_and_print("Riskklassning2024.xlsx nie został znaleziony w katalogu! Pomijam ETAP 3B.")
print("Dziekujemy za skorzystanie z naszego skryptu. W razie wykrytych nieprawidlowosci - obiwniaj ChatGPT oraz poinformuj mnie: jakubpelka@gmail.com")
