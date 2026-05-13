# Artportalen_med_data

Skrypt do wzbogacania eksportów gatunkowych o dodatkowe informacje pobierane z API SLU Artdatabanken / ArtDatabanken.

Projekt obsługuje obecnie dwa typy danych wejściowych:

```text
1. Eksport Excel z Artportalen
2. Dane / eksport z ArcGIS Online (AGOL)
```

Oba warianty korzystają z tego samego silnika wzbogacania danych. Różni się tylko etap przygotowania wejścia: Artportalen zwykle ma już `TaxonId`, natomiast AGOL może wymagać dopasowania nazw gatunków do `TaxonId`.

Projekt jest prowadzony w strukturze `dev` / `prod`, żeby można było rozwijać i testować nowe funkcje bez ryzyka uszkodzenia stabilnej wersji produkcyjnej.

---

## 1. Główne zadanie skryptu

Skrypt bierze plik Excel z danymi gatunkowymi i dopisuje informacje o taksonach, m.in.:

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

Dla danych AGOL skrypt próbuje rozpoznać kolumny z nazwą szwedzką, nazwą naukową oraz ewentualnym `TaxonId`, a następnie standaryzuje je do wspólnego formatu używanego przez dalszy pipeline.

---

## 2. Struktura repozytorium

```text
Artportalen_med_data/
├─ dev/
│  ├─ start.py
│  ├─ artportalen_enrich/
│  │  ├─ __init__.py
│  │  ├─ config.py
│  │  ├─ logger_utils.py
│  │  ├─ ui.py
│  │  ├─ utils.py
│  │  ├─ excel_io.py
│  │  ├─ input_loaders.py
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

### `start.py`

Główny i docelowo jedyny plik startowy.

Uruchamianie powinno odbywać się przez:

```bash
python start.py
```

Starsze launchery typu `AP_extra_uppgifter_DEV.py` albo `Agol_DEV.py` mogą istnieć tymczasowo tylko jako zgodność wsteczna, ale docelowo nie powinny być potrzebne.

### `artportalen_enrich/input_loaders.py`

Moduł odpowiedzialny za przygotowanie danych wejściowych.

Obsługuje:

```text
Artportalen export
AGOL / ArcGIS Online export
Auto-detect
```

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

### PROD

```bash
cd prod
python start.py
```

Docelowo używamy wyłącznie:

```bash
python start.py
```

Nie ma potrzeby utrzymywania osobnych skryptów startowych dla Artportalen i AGOL.

---

## 7. Źródło danych wejściowych

W UI użytkownik wybiera źródło danych:

```text
Auto-detect
Artportalen export
AGOL / ArcGIS Online export
```

### Auto-detect

Skrypt próbuje sam rozpoznać typ danych po kolumnach wejściowych.

Typowe sygnały Artportalen:

```text
TaxonId
taxon_svensktNamn
taxon_vetenskapligtNamn
```

Typowe sygnały AGOL:

```text
OBJECTID
GlobalID
created_user
created_date
Shape
kolumny z nazwą gatunku / artnamn / svenskt namn / vetenskapligt namn
```

Jeśli auto-detekcja jest niepewna, najlepiej ręcznie wybrać źródło w UI.

### Artportalen export

Eksport Artportalen może zawierać dodatkowe wiersze opisowe przed właściwym nagłówkiem. Skrypt potrafi je wykryć i pominąć.

### AGOL / ArcGIS Online export

Dane AGOL mogą nie mieć `TaxonId`. Wtedy skrypt próbuje dopasować takson po nazwie szwedzkiej lub naukowej.

Ważne: dla AGOL dopasowanie `TaxonId` jest wykonywane po unikalnych parach nazw, a nie naiwnie rekord po rekordzie. Jeśli ta sama nazwa występuje wiele razy, TaxonService jest odpytywany tylko raz dla tej nazwy.

---

## 8. Jak działa proces?

Po uruchomieniu skryptu użytkownik wybiera w UI:

1. plik wejściowy Excel,
2. folder wyjściowy,
3. źródło danych: `Auto-detect`, `Artportalen` albo `AGOL`,
4. tryb DEBUG,
5. preset eksportu.

Następnie skrypt:

1. wczytuje plik wejściowy odpowiednim importerem,
2. dla Artportalen wykrywa właściwy wiersz nagłówka,
3. dla AGOL standaryzuje kolumny nazw i `TaxonId`,
4. sprawdza kolumnę `TaxonId`,
5. jeśli `TaxonId` brakuje, próbuje dopasować takson po nazwie,
6. tworzy listę unikalnych `TaxonId > 0`,
7. odpytuje API tylko raz dla każdego unikalnego `TaxonId`,
8. pobiera dane z SpeciesDataService i TaxonListService,
9. buduje tabelę z dodatkowymi kolumnami,
10. scala dane z pełnym eksportem wejściowym,
11. zapisuje pliki wynikowe,
12. opcjonalnie wykonuje merge z `Riskklassning2024.xlsx`.

---

## 9. Pliki wynikowe

### `*_full_.xlsx`

Pełna tabela. Zawiera wszystkie rekordy z pliku wejściowego oraz dopisane dane z API.

Ten plik zachowuje powtórzenia obserwacji / rekordów.

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

## 10. Najważniejsze źródła danych w skrypcie

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

---

## 11. Kolumny dodawane przez skrypt z danych API SLU

Poniżej znajduje się opis kolumn dodawanych przez skrypt. To są kolumny wzbogacające dane wejściowe z Artportalen albo AGOL.

### 11.1. Podstawowe dane taksonomiczne

| Kolumna | Wyjaśnienie |
|---|---|
| `ScientificName` | Nazwa naukowa taksonu. |
| `SwedishName` | Nazwa szwedzka, jeśli dostępna. |
| `DisplayName` | Nazwa prezentacyjna używana przez API / Artfakta. |
| `Category` | Kategoria taksonomiczna, np. art, släkte, familj. |

---

### 11.2. Czerwona lista

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

### 11.3. Åtgärdsprogram i naturvård

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

### 11.4. Konwencje międzynarodowe

| Kolumna | Wyjaśnienie |
|---|---|
| `CITES` | Takson znajduje się na liście CITES. Dotyczy regulacji handlu gatunkami zagrożonymi. |
| `Bernkonventionen` | Takson znajduje się na liście powiązanej z Konwencją Berneńską. |
| `Bonnkonventionen` | Takson znajduje się na liście powiązanej z Konwencją Bońską / CMS. |

---

### 11.5. Fågeldirektivet

| Kolumna | Wyjaśnienie |
|---|---|
| `FågeldirektivetBilaga1` | Takson znajduje się w Fågeldirektivet Bilaga 1. |
| `FågeldirektivetBilaga2` | Takson znajduje się w Fågeldirektivet Bilaga 2. |
| `PrioriteradeFågelarterSkogsvårdslagen` | Ptak priorytetowy według Skogsvårdslagen / powiązanej listy. |
| `ProtectedBirds` | Informacja z SpeciesDataService dotycząca chronionych ptaków, jeśli dostępna. |

Uwaga techniczna: `FågeldirektivetBilaga2` jest osobną kolumną. Nie jest mieszana z `DirectiveAppendix2`, która dotyczy Habitatdirektivet Bilaga 2.

---

### 11.6. Fridlysning i przepisy ochronne

| Kolumna | Wyjaśnienie |
|---|---|
| `Fridlyst` | Takson jest oznaczony jako fridlyst. Flaga pochodzi z TLS, list naturvård albo tekstu `protectedText`. |
| `Frid_text` | Tekst ochronny / protectedText z API, jeśli istnieje. |
| `ProtectedByWorkProtectionConstitution` | Informacja z API o ochronie w przepisach związanych z Artskyddsförordningen / work protection constitution. |

---

### 11.7. Habitatdirektivet

| Kolumna | Wyjaśnienie |
|---|---|
| `DirectiveAppendix2` | Habitatdirektivet Bilaga 2. Logika jest zawężona, żeby nie mylić jej z Fågeldirektivet Bilaga 2. |
| `DirectiveAppendix2Priority` | Habitatdirektivet Bilaga 2, gatunek priorytetowy. |
| `DirectiveAppendix4` | Habitatdirektivet Bilaga 4. |
| `DirectiveAppendix5` | Habitatdirektivet Bilaga 5. |
| `Habitatdirektivet2023` | Członkostwo w nowszej liście Habitatdirektivet 2023, jeśli takson występuje w TLS. |
| `Artikel 17 - 2019` | Informacje z raportowania Artikel 17 za okres 2019, jeśli dostępne w conservation assessments. |

---

### 11.8. Teksty Artfakta / opisy gatunku

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

### 11.9. Obecność, pochodzenie i ekologia

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

### 11.10. Främmande arter, IAS i risklista

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

## 12. Filtr `_bara_skyddade.xlsx`

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

## 13. Filtr `_frammande_invasiva.xlsx`

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

## 14. Presety eksportu

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

---

## 16. AGOL: dopasowanie nazw do `TaxonId`

Dane AGOL mogą mieć różne nazwy kolumn. Skrypt próbuje rozpoznać m.in. kolumny oznaczające:

```text
TaxonId
nazwa szwedzka
nazwa naukowa
```

Jeśli `TaxonId` nie istnieje albo jest pusty, skrypt próbuje dopasować `TaxonId` przez TaxonService.

Zasada działania:

```text
1. Wyciągnij unikalne nazwy / pary nazw.
2. Odpytaj TaxonService tylko raz dla każdej unikalnej nazwy.
3. Dopisz TaxonId z powrotem do wszystkich rekordów.
4. Użyj wspólnego enrichmentu po TaxonId.
```

To pozwala używać tego samego pipeline zarówno dla Artportalen, jak i dla danych z AGOL.

---

## 17. Riskklassning

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

## 18. Ważne założenia techniczne

### API tylko dla unikalnych `TaxonId`

Skrypt zachowuje wszystkie rekordy w `*_full_.xlsx`, ale nie odpytuje API dla każdego powtórzonego rekordu.

Przykład:

```text
Eksport wejściowy: 1200 wierszy
Unikalne TaxonId: 240
Zapytania API: około 240, nie 1200
```

### `TaxonId` jest głównym kluczem

Najlepiej, jeśli dane wejściowe zawierają kolumnę:

```text
TaxonId
```

Jeśli jej brakuje, skrypt próbuje znaleźć `TaxonId` po nazwie szwedzkiej lub naukowej.

### `full_` zachowuje rekordy

```text
*_full_.xlsx
```

zachowuje wszystkie rekordy z wejścia.

```text
*_with_data.xlsx
```

jest przeglądem deduplikowanym po `TaxonId`.

---

## 19. Tryb DEBUG

Tryb DEBUG dodaje więcej informacji diagnostycznych i może zapisać:

```text
tls_debug.csv
```

Przy normalnym użyciu DEBUG może być wyłączony.

---

## 20. Zalecany workflow

### Rozwój

1. Zmieniaj tylko `dev/`.
2. Testuj osobno pliki Artportalen i AGOL.
3. Sprawdź log.
4. Sprawdź pliki wynikowe.
5. Po testach przenieś do `prod/`.

### Przenoszenie do PROD

1. Przenieś sprawdzone moduły z `dev/` do `prod/`.
2. Utrzymuj `start.py` jako jedyny punkt startowy.
3. Sprawdź, czy `prod/export_presets/` zawiera potrzebne presety.
4. Uruchom test na małym pliku.

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

## 21. Szybka diagnoza problemów

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

### Auto-detect rozpoznaje zły typ źródła

W UI wybierz ręcznie:

```text
Artportalen export
```

albo:

```text
AGOL / ArcGIS Online export
```

### AGOL nie dopasował `TaxonId`

Sprawdź, czy plik zawiera czytelną kolumnę z nazwą gatunku, np. nazwę szwedzką albo naukową.

Jeśli nazwa kolumny jest nietypowa, importer AGOL może wymagać rozszerzenia listy rozpoznawanych nazw kolumn.

### Wynik ma więcej wierszy niż oczekiwano

Sprawdź, który plik oglądasz:

```text
*_full_.xlsx
```

zachowuje wszystkie rekordy.

```text
*_with_data.xlsx
```

jest przeglądem po `TaxonId`.

---

## 22. Status projektu

Aktualny stan:

```text
✅ działa na eksporcie Artportalen
✅ obsługuje dane / eksport AGOL przez wspólny pipeline
✅ ma Auto-detect źródła danych
✅ czyta tokeny z lokalnego /secrets
✅ ma strukturę dev/prod
✅ używa start.py jako głównego launchera
✅ ma modularną strukturę kodu
✅ automatycznie wykrywa nagłówek eksportu Artportalen
✅ dla AGOL dopasowuje TaxonId po unikalnych nazwach
✅ ogranicza zapytania API do unikalnych TaxonId
✅ zachowuje pełne rekordy w full export
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
⚠️ AGOL wymaga testów na realnych danych eksportowych
⚠️ Auto-detect może wymagać dopracowania, jeśli AGOL ma nietypowe nazwy kolumn
⚠️ wymaga ostrożności przy przenoszeniu zmian z dev do prod
```

---

## 23. TL;DR

```text
1. Tokeny trzymaj lokalnie w /secrets.
2. Uruchamiaj przez python start.py.
3. DEV rozwijaj w dev/.
4. PROD trzymaj stabilny w prod/.
5. W UI wybierz źródło: Auto / Artportalen / AGOL.
6. Presety DEV trzymaj w dev/export_presets/.
7. Presety PROD trzymaj w prod/export_presets/.
8. full_ zachowuje wszystkie rekordy.
9. with_data jest przeglądem po TaxonId.
10. bara_skyddade zawiera ochronne/prioriterade + RedListCategory RE/CR/EN/VU/NT.
11. frammande_invasiva zawiera främmande arter, IAS i risklista SE/HI/PH/LO/NK.
12. Riskklassning2024.xlsx trzymaj najlepiej w root repo.
13. secrets/ i results/ nie commitować.