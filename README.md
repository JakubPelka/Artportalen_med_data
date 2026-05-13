# Artportalen_med_data

Skrypt do wzbogacania eksportu z Artportalen o dodatkowe informacje pobierane z API SLU Artdatabanken / ArtDatabanken.

Projekt jest prowadzony w strukturze `dev` / `prod`, żeby można było rozwijać i testować nowe funkcje bez ryzyka uszkodzenia stabilnej wersji produkcyjnej.

---

## 1. Główne zadanie skryptu

Skrypt bierze plik Excel z eksportu Artportalen i dopisuje informacje o taksonach, m.in.:

- nazwy i kategorię taksonomiczną,
- status czerwonej listy,
- kryteria czerwonej listy,
- statusy ochronne,
- konwencje międzynarodowe,
- dyrektywy UE,
- fridlysning,
- åtgärdsprogram,
- Skogsstyrelsens naturvårdsarter,
- habitatdirektiv,
- fågeldirektiv,
- IAS / främmande arter,
- riskklasy dla främmande arter,
- opisy z Artfakta, jeśli są dostępne.

Skrypt automatycznie wykrywa właściwy wiersz nagłówka w eksporcie Artportalen. Oryginalny eksport może mieć na początku dodatkowe wiersze opisowe — nie trzeba ich usuwać ręcznie.

---

## 2. Struktura repozytorium

```text
Artportalen_med_data/
├─ dev/
│  ├─ start.py
│  ├─ AP_extra_uppgifter_DEV.py
│  ├─ artportalen_enrich/
│  │  ├─ __init__.py
│  │  ├─ config.py
│  │  ├─ logger_utils.py
│  │  ├─ ui.py
│  │  ├─ utils.py
│  │  ├─ excel_io.py
│  │  ├─ taxon_client.py
│  │  ├─ species_helpers.py
│  │  ├─ tls_client.py
│  │  ├─ risk_merge.py
│  │  ├─ export_presets.py
│  │  ├─ processing.py
│  │  └─ pipeline.py
│  ├─ export_presets/
│  │  ├─ README.md
│  │  ├─ kungsbacka_standard.json
│  │  ├─ hotade_arter.json
│  │  ├─ ias_union_eu.json
│  │  └─ frammande_invasiva.json
│  └─ test_data/
│
├─ prod/
│  ├─ start.py
│  ├─ AP_extra_uppgifter.py
│  ├─ artportalen_enrich/
│  └─ export_presets/
│
├─ secrets/
│  ├─ taxonomykey.txt
│  ├─ specieskey.txt
│  └─ listskey.txt
│
├─ Riskklassning2024.xlsx
├─ .gitignore
└─ README.md
```

### `dev/`

Folder developerski. Tutaj testujemy nowe funkcje.

### `prod/`

Folder produkcyjny. Powinien zawierać stabilną, sprawdzoną wersję.

### `dev/export_presets/` i `prod/export_presets/`

Foldery z presetami eksportu. Presety nie są trzymane w root repozytorium, tylko przy danej wersji skryptu.

### `secrets/`

Lokalny folder z kluczami API. Nie może być commitowany do GitHub.

---

## 3. Wymagania

Zalecane:

```text
Python 3.10+
```

Pakiety:

```text
pandas
requests
openpyxl
```

Instalacja:

```bash
pip install pandas requests openpyxl
```

---

## 4. Klucze API

Skrypt nie zawiera kluczy API w kodzie. Klucze są czytane z lokalnych plików tekstowych.

W root repozytorium utwórz folder:

```text
secrets/
```

W nim utwórz trzy pliki:

```text
secrets/taxonomykey.txt
secrets/specieskey.txt
secrets/listskey.txt
```

Każdy plik powinien zawierać tylko sam token, bez cudzysłowów i komentarzy.

Przykład:

```text
TU_WKLEJ_TOKEN
```

Jeśli `listskey.txt` korzysta z tego samego tokenu co `specieskey.txt`, można wkleić ten sam token do obu plików.

---

## 5. `.gitignore`

Minimalnie:

```gitignore
/secrets/
```

Zalecany pełniejszy wariant:

```gitignore
# Local API keys / secrets
/secrets/
taxonomykey.txt
specieskey.txt
listskey.txt

# Python cache
__pycache__/
*.pyc
*.pyo

# Virtual environments
.venv/
venv/
env/

# Logs, debug and generated outputs
results/
*_log.txt
tls_debug.csv
*_with_data.xlsx
*_bara_skyddade.xlsx
*_frammande_invasiva.xlsx
*_prioriterade_arter.xlsx
*_full_.xlsx
*_full_nodedupe.xlsx
```

---

## 6. Uruchamianie

### DEV

```bash
cd dev
python start.py
```

Alternatywnie:

```bash
python AP_extra_uppgifter_DEV.py
```

### PROD

```bash
cd prod
python start.py
```

Alternatywnie:

```bash
python AP_extra_uppgifter.py
```

Preferowany launcher to zawsze:

```bash
python start.py
```

---

## 7. Jak działa proces?

Po uruchomieniu skryptu użytkownik wybiera w UI:

1. plik wejściowy Excel,
2. folder wyjściowy,
3. tryb DEBUG,
4. preset eksportu.

Następnie skrypt:

1. wykrywa właściwy wiersz nagłówka,
2. czyta plik Excel,
3. sprawdza kolumnę `TaxonId`,
4. jeśli `TaxonId` brakuje, próbuje dopasować takson po nazwie,
5. tworzy listę unikalnych `TaxonId > 0`,
6. odpytuje API tylko raz dla każdego unikalnego `TaxonId`,
7. pobiera dane z SpeciesDataService i TaxonListService,
8. buduje tabelę z dodatkowymi kolumnami,
9. scala dane z pełnym eksportem wejściowym,
10. zapisuje pliki wynikowe,
11. opcjonalnie wykonuje merge z `Riskklassning2024.xlsx`.

Ważne: jeśli ten sam gatunek występuje w eksporcie wiele razy, API jest odpytywane tylko raz dla jego `TaxonId`.

---

## 8. Pliki wynikowe

### `*_full_.xlsx`

Pełna tabela. Zawiera wszystkie obserwacje z pliku wejściowego oraz dopisane dane z API.

Ten plik zachowuje powtórzenia obserwacji.

### `*_with_data.xlsx`

Tabela przeglądowa z danymi dodatkowymi. Zasadniczo deduplikowana po `TaxonId`.

Kolumny zależą od wybranego presetu.

### `*_bara_skyddade.xlsx`

Tabela z taksonami chronionymi, priorytetowymi lub rödlistade od `NT` w górę.

### `*_frammande_invasiva.xlsx`

Tabela z taksonami obcymi, inwazyjnymi lub znajdującymi się na listach ryzyka dla främmande arter.

### `*_log.txt`

Log przebiegu pracy.

### `tls_debug.csv`

Plik debugowy dla TLS, tworzony przy włączonym DEBUG.

---

## 9. Najważniejsze źródła danych w skrypcie

Skrypt korzysta głównie z trzech typów danych:

| Źródło | Do czego służy |
|---|---|
| TaxonService | Dopasowanie nazwy do `TaxonId`, jeśli `TaxonId` nie ma w pliku wejściowym. |
| SpeciesDataService | Dane opisowe, rödlistning, naturvård, Artfakta, alien species risk assessment. |
| TaxonListService | Członkostwo taksonów w listach: CITES, dyrektywy, konwencje, fridlysta arter, IAS, risklista itd. |

W wielu kolumnach skrypt stosuje zasadę:

```text
najpierw TaxonListService, potem fallback z SpeciesDataService / natureConservation.lists
```

Dzięki temu flaga może zostać uzupełniona nawet wtedy, gdy jedna z metod nie zwróci informacji.

---

## 10. Kolumny dodawane przez skrypt z danych API SLU

Poniżej znajduje się opis kolumn dodawanych przez skrypt. To są kolumny wzbogacające eksport z Artportalen.

### 10.1. Podstawowe dane taksonomiczne

| Kolumna | Wyjaśnienie |
|---|---|
| `ScientificName` | Nazwa naukowa taksonu. |
| `SwedishName` | Nazwa szwedzka, jeśli dostępna. |
| `DisplayName` | Nazwa prezentacyjna używana przez API / Artfakta. |
| `Category` | Kategoria taksonomiczna, np. art, släkte, familj. |

---

### 10.2. Czerwona lista

| Kolumna | Wyjaśnienie |
|---|---|
| `ConservationStatus` | Ogólny status naturvård / conservation status, jeśli API go zwraca. |
| `RedListCategory` | Kategoria czerwonej listy, np. `RE`, `CR`, `EN`, `VU`, `NT`, `LC`, `DD`. |
| `RedListCriterion` | Kryterium czerwonej listy, np. kryteria typu A, B, C itd. |
| `RedListPeriodName` | Okres / edycja czerwonej listy użyta w danych. |
| `RedListCriterionText` | Tekstowy opis kryterium czerwonej listy, jeśli jest dostępny. |

Domyślnie do `_bara_skyddade.xlsx` trafiają taksony z kategorią:

```text
RE, CR, EN, VU, NT
```

Kategorie `LC`, `NA`, `NE`, `DD` i puste wartości nie trafiają do `_bara_skyddade` samą logiką rödlistning, chyba że takson ma inną flagę ochronną/prioriterad.

---

### 10.3. Åtgärdsprogram i naturvård

| Kolumna | Wyjaśnienie |
|---|---|
| `ActionProgramName` | Nazwa åtgärdsprogram, jeśli takson jest nim objęty. |
| `ActionProgramStatus` | Status programu działań. |
| `ActionProgramStart` | Rok startu programu działań. |
| `ActionProgramEnd` | Rok zakończenia programu działań. |
| `TypicalSpecies` | Typiska arter, jeśli takson jest wskazany jako typowy dla określonych siedlisk / naturtypów. |
| `ForestrySignal` | Flaga signalarter / forestry board signal species, jeśli API ją zwraca. |
| `ForestrySignalSpecies` | Nazwy powiązane z forestry signal species, jeśli są dostępne. |
| `SkogsstyrelsensNaturvardsarter` | Członkostwo w liście Skogsstyrelsens naturvårdsarter. Lista przydatna dla kontekstu leśnego i naturvård. |
| `LandscapeType` | Typy krajobrazu powiązane z taksonem. |
| `Biotopes` | Biotopy powiązane z taksonem. |

---

### 10.4. Konwencje międzynarodowe

| Kolumna | Wyjaśnienie |
|---|---|
| `CITES` | Takson znajduje się na liście CITES. Dotyczy regulacji handlu gatunkami zagrożonymi. |
| `Bernkonventionen` | Takson znajduje się na liście powiązanej z Konwencją Berneńską. |
| `Bonnkonventionen` | Takson znajduje się na liście powiązanej z Konwencją Bońską / CMS. |

---

### 10.5. Fågeldirektivet

| Kolumna | Wyjaśnienie |
|---|---|
| `FågeldirektivetBilaga1` | Takson znajduje się w Fågeldirektivet Bilaga 1. |
| `FågeldirektivetBilaga2` | Takson znajduje się w Fågeldirektivet Bilaga 2. |
| `PrioriteradeFågelarterSkogsvårdslagen` | Ptak priorytetowy według Skogsvårdslagen / powiązanej listy. |
| `ProtectedBirds` | Informacja z SpeciesDataService dotycząca chronionych ptaków, jeśli dostępna. |

Uwaga techniczna: `FågeldirektivetBilaga2` jest osobną kolumną. Nie jest mieszana z `DirectiveAppendix2`, która dotyczy Habitatdirektivet Bilaga 2.

---

### 10.6. Fridlysning i przepisy ochronne

| Kolumna | Wyjaśnienie |
|---|---|
| `Fridlyst` | Takson jest oznaczony jako fridlyst. Flaga pochodzi z TLS, list naturvård albo tekstu `protectedText`. |
| `Frid_text` | Tekst ochronny / protectedText z API, jeśli istnieje. |
| `ProtectedByWorkProtectionConstitution` | Informacja z API o ochronie w przepisach związanych z Artskyddsförordningen / work protection constitution. |

---

### 10.7. Habitatdirektivet

| Kolumna | Wyjaśnienie |
|---|---|
| `DirectiveAppendix2` | Habitatdirektivet Bilaga 2. W tej wersji logika została zawężona, żeby nie mylić jej z Fågeldirektivet Bilaga 2. |
| `DirectiveAppendix2Priority` | Habitatdirektivet Bilaga 2, gatunek priorytetowy. |
| `DirectiveAppendix4` | Habitatdirektivet Bilaga 4. |
| `DirectiveAppendix5` | Habitatdirektivet Bilaga 5. |
| `Habitatdirektivet2023` | Członkostwo w nowszej liście Habitatdirektivet 2023, jeśli takson występuje w TLS. |
| `Artikel 17 - 2019` | Informacje z raportowania Artikel 17 za okres 2019, jeśli dostępne w conservation assessments. |

---

### 10.8. Teksty Artfakta / opisy gatunku

| Kolumna | Wyjaśnienie |
|---|---|
| `Characteristic` | Opis cech charakterystycznych. |
| `SpreadAndStatus` | Rozmieszczenie i status. |
| `Ecology` | Informacje ekologiczne. |
| `Threat` | Zagrożenia opisane w Artfakta. |
| `ConservationMeasures` | Proponowane lub opisane działania ochronne. |
| `Other` | Inne informacje tekstowe. |

Te pola mogą być dłuższymi tekstami. Ich dostępność zależy od taksonu.

---

### 10.9. Obecność, pochodzenie i ekologia

| Kolumna | Wyjaśnienie |
|---|---|
| `SwedishPresence` | Informacja o obecności w Szwecji. |
| `ImmigrationHistory` | Informacja o historii imigracji / pochodzeniu taksonu w Szwecji. |
| `SubstrateInformation` | Informacje o substratach / podłożu, jeśli dostępne. |
| `EcologicalGroups` | Grupy ekologiczne przypisane do taksonu. |
| `ConservationEcology` | Dane/tekst z części conservation assessments dotyczący ekologii. |
| `ConservationNatureConservation` | Dane/tekst z conservation assessments dotyczący naturvård. |
| `ConservationTreeSpecies` | Dane/tekst z conservation assessments dotyczący drzew / tree species. |

---

### 10.10. Främmande arter, IAS i risklista

| Kolumna | Wyjaśnienie |
|---|---|
| `FrammandeArter` | Takson znajduje się na liście främmande arter / alien species. |
| `FrammandeArterISverige` | Takson znajduje się na liście främmande arter i Sverige. |
| `IAS_Union_EU` | Takson znajduje się na unijnej liście IAS / Union list enligt EU-förordning 1143/2014. |
| `RisklistaFrammandeArter` | Takson jest objęty risklista främmande arter. |
| `Risklista_SE` | Risklista: `SE` — mycket hög risk. |
| `Risklista_HI` | Risklista: `HI` — hög risk. |
| `Risklista_PH` | Risklista: `PH` — potentiellt hög risk. |
| `Risklista_LO` | Risklista: `LO` — låg risk. |
| `Risklista_NK` | Risklista: `NK` — ingen känd risk. |
| `AlienSpeciesRiskCategories` | Kategorie ryzyka z części `alienSpeciesRa`, jeśli API je zwraca. |
| `AlienSpeciesEnvironments` | Środowiska powiązane z oceną alien species risk assessment. |
| `AlienSpeciesEcologyEffect` | Efekty ekologiczne wskazane w ocenie alien species. |
| `AlienSpeciesTaxonLists` | Listy taksonomiczne powiązane z alien species risk assessment. |
| `AlienSpeciesInvationPotentials` | Potencjał inwazyjny z API. Nazwa zachowuje pisownię zgodną z polem w aktualnym kodzie/API. |
| `AlienSpeciesRegions` | Regiony powiązane z oceną alien species. |

Te kolumny są używane do tworzenia pliku:

```text
*_frammande_invasiva.xlsx
```

---

## 11. Filtr `_bara_skyddade.xlsx`

Do `_bara_skyddade.xlsx` trafia takson, jeśli spełnia przynajmniej jedno z kryteriów:

1. ma aktywną jedną z kolumn ochronnych/przyrodniczych,
2. ma kategorię czerwonej listy `RE`, `CR`, `EN`, `VU` albo `NT`,
3. wybrany preset dodatkowo włącza inne kryteria, np. IAS.

Domyślne kolumny ochronne/przyrodnicze:

```text
ConservationStatus
Artikel 17 - 2019
TypicalSpecies
CITES
Bernkonventionen
Bonnkonventionen
PrioriteradeFågelarterSkogsvårdslagen
FågeldirektivetBilaga1
SkogsstyrelsensNaturvardsarter
ProtectedByWorkProtectionConstitution
ProtectedBirds
DirectiveAppendix2
DirectiveAppendix2Priority
DirectiveAppendix4
DirectiveAppendix5
Habitatdirektivet2023
ForestrySignal
ActionProgramStatus
ActionProgramStart
ActionProgramEnd
ActionProgramName
Fridlyst
```

Domyślne kategorie rödlistning:

```text
RE, CR, EN, VU, NT
```

---

## 12. Filtr `_frammande_invasiva.xlsx`

Do `_frammande_invasiva.xlsx` trafia takson, jeśli spełnia przynajmniej jedno z kryteriów związanych z främmande arter / IAS / risklista.

Kolumny używane w filtrze:

```text
FrammandeArter
FrammandeArterISverige
IAS_Union_EU
RisklistaFrammandeArter
Risklista_SE
Risklista_HI
Risklista_PH
Risklista_LO
Risklista_NK
AlienSpeciesRiskCategories
AlienSpeciesEnvironments
AlienSpeciesEcologyEffect
AlienSpeciesTaxonLists
AlienSpeciesInvationPotentials
AlienSpeciesRegions
```

Ten plik jest oddzielony od `_bara_skyddade.xlsx`, bo gatunek obcy/inwazyjny nie jest tym samym co gatunek chroniony.

---

## 13. Presety eksportu

Presety sterują tym, które kolumny są widoczne w plikach przeglądowych oraz jakie filtry są aktywne.

Presety są trzymane lokalnie w folderze konkretnej wersji:

```text
dev/export_presets/
prod/export_presets/
```

Nie są trzymane w root repozytorium.

### Przykładowe presety

```text
kungsbacka_standard.json
hotade_arter.json
ias_union_eu.json
frammande_invasiva.json
```

### Podgląd presetu

UI pozwala podejrzeć preset przed startem.

Podgląd pokazuje m.in.:

- nazwę,
- opis,
- liczbę kolumn,
- listę kolumn,
- aktywne filtry,
- kategorie rödlistning,
- filtr IAS.

### Edycja presetu

UI zawiera prosty edytor presetów. Można przez niego:

- zmienić nazwę,
- zmienić opis,
- wybrać kolumny checkboxami,
- włączyć/wyłączyć filtr ochronny,
- włączyć/wyłączyć rödlistning,
- wybrać kategorie rödlistning,
- włączyć/wyłączyć filtr IAS,
- zapisać nowy preset jako JSON.

Edycja zapisuje nowy plik JSON w:

```text
dev/export_presets/
```

albo w wersji produkcyjnej:

```text
prod/export_presets/
```

---

## 14. Przykład presetu JSON

```json
{
  "id": "frammande_invasiva",
  "name": "Främmande / invasiva arter",
  "description": "Preset för främmande arter, IAS och risklista.",
  "include_all_columns": false,
  "include_original_columns": true,
  "columns": [
    "TaxonId",
    "taxon_svensktNamn",
    "taxon_vetenskapligtNamn",
    "ScientificName",
    "SwedishName",
    "RedListCategory",
    "FrammandeArter",
    "FrammandeArterISverige",
    "IAS_Union_EU",
    "RisklistaFrammandeArter",
    "Risklista_SE",
    "Risklista_HI",
    "Risklista_PH",
    "Risklista_LO",
    "Risklista_NK",
    "AlienSpeciesRiskCategories",
    "AlienSpeciesEnvironments",
    "AlienSpeciesEcologyEffect",
    "AlienSpeciesInvationPotentials",
    "AlienSpeciesRegions"
  ],
  "filter": {
    "include_current_protection_filter": false,
    "include_redlist_filter": false,
    "redlist_categories": [],
    "include_ias_union_eu_filter": true
  }
}
```

---

## 15. Auto-wykrywanie nagłówka Artportalen

Oryginalny eksport Artportalen może mieć dodatkowe wiersze opisowe przed właściwym nagłówkiem tabeli.

Skrypt szuka w pierwszych wierszach nazw kolumn takich jak:

```text
TaxonId
taxon_svensktNamn
taxon_vetenskapligtNamn
```

Jeśli nagłówek zostanie wykryty np. w trzecim wierszu, skrypt automatycznie czyta dane od tego miejsca.

W logu pojawi się np.:

```text
Wykryto dodatkowe wiersze przed nagłówkiem: 2. Czytam dane od wiersza 3.
```

---

## 16. Riskklassning

Skrypt może wykonać merge z plikiem:

```text
Riskklassning2024.xlsx
```

albo innym plikiem pasującym do wzorca:

```text
Riskklassning*.xlsx
```

Kolejność wyszukiwania:

1. root repozytorium,
2. folder pliku wejściowego,
3. folder wynikowy,
4. folder skryptu.

Zalecane miejsce:

```text
Artportalen_med_data/Riskklassning2024.xlsx
```

Jeśli plik nie zostanie znaleziony, skrypt kontynuuje pracę i zapisuje w logu:

```text
Riskklassning*.xlsx nie znaleziony — pomijam merge.
```

---

## 17. Ważne założenia techniczne

### API tylko dla unikalnych `TaxonId`

Skrypt zachowuje wszystkie obserwacje w `*_full_.xlsx`, ale nie odpytuje API dla każdego powtórzonego rekordu.

Przykład:

```text
Eksport wejściowy: 1200 wierszy
Unikalne TaxonId: 240
Zapytania API: około 240, nie 1200
```

### `TaxonId` jest głównym kluczem

Najlepiej, jeśli eksport Artportalen zawiera kolumnę:

```text
TaxonId
```

Jeśli jej brakuje, skrypt próbuje znaleźć `TaxonId` po nazwie szwedzkiej lub naukowej. Ten tryb jest wolniejszy i mniej pewny.

### `full_` zachowuje obserwacje

```text
*_full_.xlsx
```

zachowuje wszystkie obserwacje z wejścia.

```text
*_with_data.xlsx
```

jest przeglądem deduplikowanym po `TaxonId`.

---

## 18. Tryb DEBUG

Tryb DEBUG dodaje więcej informacji diagnostycznych i może zapisać:

```text
tls_debug.csv
```

Przy normalnym użyciu DEBUG może być wyłączony.

---

## 19. Zalecany workflow

### Rozwój

1. Zmieniaj tylko `dev/`.
2. Testuj na danych testowych.
3. Sprawdź log.
4. Sprawdź pliki wynikowe.
5. Po testach przenieś do `prod/`.

### Presety

1. Presety testowe dodawaj w `dev/export_presets/`.
2. Po sprawdzeniu przenieś do `prod/export_presets/`.
3. Nie trzymaj presetów w root repozytorium.
4. Nie zapisuj w presetach tokenów, ścieżek prywatnych ani danych wrażliwych.

### Bezpieczeństwo

Nie commitować:

```text
secrets/
results/
plików wynikowych z realnymi danymi
plików z tokenami
plików tymczasowych
```

---

## 20. Szybka diagnoza problemów

### Brak pliku z kluczem

Sprawdź:

```text
secrets/taxonomykey.txt
secrets/specieskey.txt
secrets/listskey.txt
```

Folder `secrets/` powinien być w root repozytorium.

### Program wygląda, jakby się zawiesił po wyborze folderu

Sprawdź, czy okno wyboru presetu nie znajduje się za innym oknem. Aktualna wersja UI próbuje wymusić pokazanie okna na wierzchu.

### Nie widzę swojego presetu

Sprawdź, czy JSON jest w odpowiednim folderze:

```text
dev/export_presets/
```

albo:

```text
prod/export_presets/
```

Sprawdź też poprawność składni JSON.

### Wynik ma więcej wierszy niż oczekiwano

Sprawdź, który plik oglądasz:

```text
*_full_.xlsx
```

zachowuje wszystkie obserwacje.

```text
*_with_data.xlsx
```

jest przeglądem po `TaxonId`.

---

## 21. Status projektu

Aktualny stan:

```text
✅ działa na eksporcie Artportalen
✅ czyta tokeny z lokalnego /secrets
✅ ma strukturę dev/prod
✅ ma modularną strukturę kodu
✅ automatycznie wykrywa nagłówek eksportu
✅ ogranicza zapytania API do unikalnych TaxonId
✅ zachowuje pełne obserwacje w full export
✅ filtruje skyddade/prioriterade z RedListCategory od NT w górę
✅ obsługuje SkogsstyrelsensNaturvardsarter
✅ obsługuje FågeldirektivetBilaga2 jako osobną kolumnę
✅ poprawia rozdzielenie Habitatdirektivet Bilaga 2 od Fågeldirektivet Bilaga 2
✅ obsługuje Habitatdirektivet2023
✅ obsługuje främmande arter, IAS i risklista SE/HI/PH/LO/NK
✅ generuje osobny plik _frammande_invasiva.xlsx
✅ obsługuje presety JSON w dev/export_presets/ i prod/export_presets/
✅ pozwala podejrzeć preset
✅ pozwala edytować i zapisać preset jako JSON
⚠️ wymaga dalszych testów na różnych eksportach Artportalen
⚠️ wymaga ostrożności przy przenoszeniu zmian z dev do prod
```

---

## 22. TL;DR

```text
1. Tokeny trzymaj lokalnie w /secrets.
2. Uruchamiaj przez python start.py.
3. DEV rozwijaj w dev/.
4. PROD trzymaj stabilny w prod/.
5. Presety DEV trzymaj w dev/export_presets/.
6. Presety PROD trzymaj w prod/export_presets/.
7. full_ zachowuje wszystkie obserwacje.
8. with_data jest przeglądem po TaxonId.
9. bara_skyddade zawiera ochronne/prioriterade + RedListCategory RE/CR/EN/VU/NT.
10. frammande_invasiva zawiera främmande arter, IAS i risklista SE/HI/PH/LO/NK.
11. Riskklassning2024.xlsx trzymaj najlepiej w root repo.
12. secrets/ i results/ nie commitować.
```
