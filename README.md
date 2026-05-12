# Artportalen_med_data

Skrypt do wzbogacania eksportu z Artportalen o dodatkowe informacje o statusie ochronnym, czerwonej liście, listach taksonomicznych i wybranych klasyfikacjach przyrodniczych.

Projekt jest rozwijany w układzie `dev` / `prod`, żeby można było bezpiecznie testować nowe funkcje bez psucia działającej wersji produkcyjnej.

---

## 1. Co robi skrypt?

Skrypt bierze plik Excel z eksportu Artportalen i dopisuje dane pobierane z API ArtDatabanken, m.in.:

- nazwę naukową i szwedzką,
- kategorię taksonomiczną,
- status czerwonej listy,
- kryteria czerwonej listy,
- informacje o fridlysning,
- CITES,
- Bernkonventionen,
- Bonnkonventionen,
- Fågeldirektivet Bilaga 1,
- Habitatdirektivet Bilaga 2 / 2-prio / 4 / 5,
- Prioriterade fågelarter i Skogsvårdslagen,
- typiska arter,
- signalarter / ForestrySignal,
- åtgärdsprogram,
- IAS Union EU,
- teksty opisowe z Artfakta / ArtDatabanken, jeśli są dostępne.

Skrypt może pracować zarówno na eksporcie, który ma od razu poprawny nagłówek w pierwszym wierszu, jak i na oryginalnym eksporcie Artportalen, który zawiera na początku dodatkowe wiersze opisowe. Właściwy wiersz nagłówka jest wykrywany automatycznie.

---

## 2. Aktualna struktura repozytorium

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
│  │  └─ ias_union_eu.json
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

Folder developerski. Tutaj testujemy nowe funkcje, refaktoryzację i zmiany w logice eksportu.

### `prod/`

Folder produkcyjny. Powinien zawierać stabilną wersję skryptu, która działa i może być używana operacyjnie.

### `dev/export_presets/` i `prod/export_presets/`

Lokalny folder presetów dla danej wersji skryptu.

Presety **nie są trzymane w root repozytorium**, tylko przy konkretnej wersji:

```text
dev/export_presets/
prod/export_presets/
```

Dzięki temu DEV i PROD mogą mieć różne zestawy presetów bez mieszania konfiguracji.

### `secrets/`

Lokalny folder z kluczami API. Ten folder **nie może trafić do GitHub**.

### `Riskklassning2024.xlsx`

Opcjonalny plik używany do merge z klasyfikacją ryzyka. Domyślnie skrypt szuka go najpierw w katalogu głównym repozytorium.

---

## 3. Wymagania

Zalecane:

```text
Python 3.10+
```

Pakiety Python:

```text
pandas
requests
openpyxl
```

Instalacja pakietów:

```bash
pip install pandas requests openpyxl
```

Na Windows `tkinter` zwykle jest dostępny razem z Pythonem. Na Linuxie może wymagać osobnej instalacji.

---

## 4. Klucze API

Klucze API nie są zapisane w kodzie. Skrypt czyta je z lokalnego folderu:

```text
/secrets
```

W katalogu głównym repozytorium utwórz folder:

```text
secrets/
```

Następnie dodaj trzy pliki tekstowe:

```text
secrets/taxonomykey.txt
secrets/specieskey.txt
secrets/listskey.txt
```

Każdy plik powinien zawierać tylko sam token, bez cudzysłowów i bez komentarzy.

Przykład zawartości pliku:

```text
TU_WKLEJ_TOKEN
```

Jeśli `listskey.txt` używa tego samego tokenu co `specieskey.txt`, można wkleić ten sam token do obu plików.

---

## 5. `.gitignore`

Folder `secrets/` musi być ignorowany przez Git.

Minimalny wpis:

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
*_prioriterade_arter.xlsx
*_full_.xlsx
*_full_nodedupe.xlsx
```

Przed commitem warto sprawdzić:

```bash
git status
```

Folder `secrets/` nie powinien być widoczny jako plik do dodania.

Można też sprawdzić ignorowanie plików:

```bash
git check-ignore -v secrets/taxonomykey.txt secrets/specieskey.txt secrets/listskey.txt
```

---

## 6. Uruchamianie wersji DEV

Przejdź do folderu `dev`:

```bash
cd dev
```

Uruchom:

```bash
python start.py
```

Alternatywnie można uruchomić launcher kompatybilny:

```bash
python AP_extra_uppgifter_DEV.py
```

Preferowane jest jednak:

```bash
python start.py
```

---

## 7. Uruchamianie wersji PROD

Przejdź do folderu `prod`:

```bash
cd prod
```

Uruchom:

```bash
python start.py
```

Jeśli w `prod/` utrzymywany jest także launcher kompatybilny, można ewentualnie uruchomić:

```bash
python AP_extra_uppgifter.py
```

Preferowane jest jednak:

```bash
python start.py
```

---

## 8. Jak działa proces?

Po uruchomieniu skryptu pojawia się proste UI, w którym użytkownik wybiera:

1. plik wejściowy Excel,
2. folder wyjściowy,
3. tryb DEBUG,
4. preset eksportu.

Następnie skrypt:

1. wykrywa właściwy wiersz nagłówka w pliku Excel,
2. czyta dane wejściowe,
3. sprawdza, czy istnieje kolumna `TaxonId`,
4. jeśli `TaxonId` brakuje, próbuje dopasować takson po nazwie szwedzkiej lub naukowej,
5. tworzy listę unikalnych `TaxonId > 0`,
6. odpytuje API tylko raz dla każdego unikalnego `TaxonId`,
7. pobiera dane TLS i species data,
8. buduje tabelę z dodatkowymi kolumnami,
9. scala dane z pełnym eksportem wejściowym,
10. zapisuje pliki wynikowe,
11. opcjonalnie wykonuje merge z `Riskklassning2024.xlsx`, jeśli plik istnieje.

Ważne: skrypt nie odpytuje API dla każdej obserwacji osobno. Jeśli jeden gatunek występuje wiele razy, dane ochronne są pobierane raz dla jego `TaxonId`, a potem scalane z pełną tabelą.

---

## 9. Pliki wynikowe

Skrypt zapisuje pliki do wybranego folderu wynikowego.

### `*_full_.xlsx`

Pełna tabela wynikowa.

Zawiera wszystkie obserwacje z pliku wejściowego oraz dopisane dane z API.

Ten plik zachowuje powtórzenia obserwacji. Jeśli np. sikorka bogatka występuje w eksporcie 50 razy, w `*_full_.xlsx` nadal może wystąpić 50 razy, ale dane ochronne dla tego taksonu są pobrane tylko raz i zmergowane po `TaxonId`.

### `*_with_data.xlsx`

Tabela przeglądowa z danymi dodatkowymi.

Zasadniczo jest deduplikowana po `TaxonId`, więc jeden takson powinien występować raz.

Kolumny w tym pliku zależą od wybranego presetu eksportu.

### `*_bara_skyddade.xlsx`

Tabela przefiltrowana do gatunków chronionych, priorytetowych lub istotnych przyrodniczo zgodnie z aktualnym filtrem.

Obecnie filtr obejmuje także rödlistning od `NT` w górę.

Kolumny w tym pliku zależą od wybranego presetu eksportu.

### `*_log.txt`

Log z przebiegu pracy.

Zawiera informacje m.in. o:

- pliku wejściowym,
- folderze wyjściowym,
- wybranym presecie,
- wykrytym wierszu nagłówka,
- liczbie rekordów,
- liczbie unikalnych `TaxonId`,
- liczbie pominiętych duplikatów przy zapytaniach API,
- zapisanych plikach,
- błędach API,
- braku pliku `Riskklassning*.xlsx`, jeśli nie został znaleziony.

### `tls_debug.csv`

Plik debugowy dla TLS, zapisywany przy włączonym trybie DEBUG.

---

## 10. Filtr `_bara_skyddade`

Plik `_bara_skyddade.xlsx` zawiera taksony, które spełniają przynajmniej jedno z kryteriów ochronnych lub priorytetowych.

### Aktualnie uwzględniane są m.in. kolumny:

```text
ConservationStatus
Artikel 17 - 2019
TypicalSpecies
CITES
Bernkonventionen
Bonnkonventionen
PrioriteradeFågelarterSkogsvårdslagen
FågeldirektivetBilaga1
ProtectedByWorkProtectionConstitution
ProtectedBirds
DirectiveAppendix2
DirectiveAppendix2Priority
DirectiveAppendix4
DirectiveAppendix5
ForestrySignal
ActionProgramStatus
ActionProgramStart
ActionProgramEnd
ActionProgramName
Fridlyst
```

Jeśli którakolwiek z tych kolumn zawiera wartość, takson trafia do `_bara_skyddade.xlsx`.

### Rödlistning

Dodatkowo do `_bara_skyddade.xlsx` trafiają taksony z kategorią czerwonej listy:

```text
RE
CR
EN
VU
NT
```

Czyli od `NT` w górę.

Kategorie niewłączane samą rödlistning-logiką:

```text
LC
NA
NE
DD
puste
```

Uwaga: `DD` można w przyszłości dodać jako opcję, jeśli będzie potrzebna logika „kunskapsbrist też do kontroli”. Aktualnie nie jest częścią domyślnego filtra redlist.

### IAS Union EU

`IAS_Union_EU` jest dostępne jako osobna kolumna.

Domyślnie nie jest traktowane jako formalny filtr `bara_skyddade`, chyba że wybrany preset ma włączony filtr IAS.

---

## 11. Presety eksportu

Wersja DEV obsługuje presety eksportu.

Presety służą do wyboru zestawu kolumn w plikach:

```text
*_with_data.xlsx
*_bara_skyddade.xlsx
```

Mogą również sterować dodatkowymi ustawieniami filtra `_bara_skyddade`, np. tym, czy do filtra ma być włączona rödlistning albo IAS.

Presety nie zmieniają sposobu pobierania danych z API. Zmieniają głównie to, które kolumny są pokazane w wynikowych plikach przeglądowych oraz jakie dodatkowe kryteria filtracji są aktywne.

### Lokalizacja presetów

Presety są trzymane lokalnie przy konkretnej wersji skryptu:

```text
dev/export_presets/
prod/export_presets/
```

Nie są trzymane w root repozytorium.

Dzięki temu DEV i PROD mogą mieć różne zestawy presetów.

### Presety wbudowane i JSON

Skrypt ma presety wbudowane w kodzie jako fallback.

Dodatkowo czyta pliki `.json` z folderu:

```text
export_presets/
```

czyli dla DEV:

```text
dev/export_presets/
```

oraz dla PROD:

```text
prod/export_presets/
```

Presety z plików JSON są widoczne w UI i mogą być oznaczone jako presety zewnętrzne.

### Podgląd presetu

W UI można podejrzeć wybrany preset przed uruchomieniem skryptu.

Podgląd powinien pokazać m.in.:

```text
nazwa presetu
opis
liczba kolumn
lista kolumn
czy aktywny jest filtr ochronny
czy aktywna jest rödlistning
jakie kategorie rödlistning są włączone
czy aktywny jest filtr IAS
```

### Zapis kopii presetu jako JSON

UI pozwala zapisać kopię aktualnie wybranego presetu jako plik JSON.

Dla DEV kopia zapisuje się do:

```text
dev/export_presets/
```

Dla PROD kopia zapisuje się do:

```text
prod/export_presets/
```

To pozwala szybko utworzyć własny preset na bazie istniejącego.

### Przykładowy preset JSON

```json
{
  "id": "kungsbacka_standard",
  "name": "Kungsbacka standard",
  "description": "Standardexport med originalkolumner och viktigaste naturvårdsfält.",
  "columns": [
    "TaxonId",
    "taxon_svensktNamn",
    "taxon_vetenskapligtNamn",
    "RedListCategory",
    "Fridlyst",
    "CITES",
    "Bernkonventionen",
    "FågeldirektivetBilaga1",
    "DirectiveAppendix2",
    "DirectiveAppendix4",
    "IAS_Union_EU"
  ],
  "filter": {
    "include_current_protection_filter": true,
    "include_redlist_filter": true,
    "redlist_categories": ["RE", "CR", "EN", "VU", "NT"],
    "include_ias_union_eu_filter": false
  }
}
```

---

## 12. Auto-wykrywanie nagłówka w eksporcie Artportalen

Oryginalny eksport z Artportalen może zawierać na początku dodatkowe wiersze opisowe. Często są to dwa pierwsze wiersze.

Skrypt nie wymaga ręcznego kasowania tych wierszy. Zamiast tego skanuje początkowe wiersze i szuka właściwego nagłówka po nazwach kolumn takich jak:

```text
TaxonId
taxon_svensktNamn
taxon_vetenskapligtNamn
```

Jeśli nagłówek zostanie wykryty np. w trzecim wierszu, skrypt automatycznie czyta dane od tego miejsca.

W logu pojawi się informacja w stylu:

```text
Wykryto dodatkowe wiersze przed nagłówkiem: 2. Czytam dane od wiersza 3.
```

---

## 13. Riskklassning

Skrypt może wykonać merge z plikiem:

```text
Riskklassning2024.xlsx
```

albo innym plikiem pasującym do wzorca:

```text
Riskklassning*.xlsx
```

Domyślna kolejność wyszukiwania:

1. root repozytorium,
2. folder pliku wejściowego,
3. folder wynikowy,
4. folder skryptu.

Zalecane miejsce przechowywania:

```text
Artportalen_med_data/Riskklassning2024.xlsx
```

Jeśli plik nie zostanie znaleziony, skrypt kontynuuje pracę i zapisuje w logu informację:

```text
Riskklassning*.xlsx nie znaleziony — pomijam merge.
```

---

## 14. Ważne założenia techniczne

### API tylko dla unikalnych `TaxonId`

Skrypt zachowuje wszystkie obserwacje w pliku `*_full_.xlsx`, ale nie wykonuje zapytań API dla każdego powtórzonego rekordu.

Przykład:

```text
Eksport wejściowy: 1200 wierszy
Unikalne TaxonId: 240
Zapytania API: około 240, nie 1200
```

Dzięki temu skrypt działa szybciej i nie wysyła niepotrzebnych zapytań.

### `TaxonId` jest głównym kluczem

Najlepiej, jeśli plik wejściowy zawiera kolumnę:

```text
TaxonId
```

Jeśli jej brakuje, skrypt próbuje znaleźć `TaxonId` po nazwie szwedzkiej lub naukowej. Ten tryb jest wolniejszy i mniej pewny niż bezpośrednie użycie `TaxonId`.

### Czyszczenie wartości pustych

Wyniki typu:

```text
Nej
False
false
None
NaN
```

mogą być czyszczone do pustych wartości w wybranych kolumnach, żeby eksport był czytelniejszy.

---

## 15. Tryb DEBUG

Tryb DEBUG służy do testowania i kontroli działania TLS oraz pobierania danych.

Może generować dodatkowe logi i plik:

```text
tls_debug.csv
```

Na potrzeby normalnej pracy tryb DEBUG może być wyłączony.

---

## 16. Zalecany workflow pracy z repo

### Normalne użycie

1. Używaj wersji z `prod/`.
2. Wybierz eksport Excel z Artportalen.
3. Wybierz folder wynikowy.
4. Wybierz preset eksportu.
5. Sprawdź wynikowe pliki Excel.

### Rozwój i testy

1. Zmieniaj tylko `dev/`.
2. Testuj na plikach z `dev/test_data/` albo lokalnych danych testowych.
3. Sprawdź log.
4. Porównaj wynik z wersją produkcyjną.
5. Dopiero po testach przenieś zmiany do `prod/`.

### Praca z presetami

1. Presety testowe dodawaj najpierw w `dev/export_presets/`.
2. Po sprawdzeniu możesz przenieść je do `prod/export_presets/`.
3. Nie trzymaj presetów w root repozytorium.
4. Jeśli preset zawiera tylko konfigurację kolumn i filtrów, może być commitowany.
5. Nie zapisuj w presetach tokenów, ścieżek prywatnych ani danych wrażliwych.

### Zasada bezpieczeństwa

Nie commitować:

```text
secrets/
results/
plików wynikowych z realnymi danymi
plików z tokenami
plików tymczasowych
```

---

## 17. Planowane / możliwe ulepszenia

Potencjalne następne kroki:

- osobne presety dla `with_data`, `bara_skyddade` i `full`,
- opcjonalne włączanie `DD` do filtra priorytetowego,
- opcjonalne generowanie osobnego pliku dla `IAS_Union_EU`,
- prostszy raport HTML z podsumowaniem liczby gatunków w kategoriach `RE/CR/EN/VU/NT/LC`,
- kontrola jakości wejścia przed startem,
- wykrywanie podejrzanych braków `TaxonId`,
- możliwość uruchomienia bez GUI z argumentami CLI,
- testy jednostkowe dla parserów API i filtrów,
- automatyczny test na plikach z `dev/test_data/`.

---

## 18. Szybka diagnoza problemów

### Skrypt nie startuje i zgłasza brak pliku z kluczem

Sprawdź, czy istnieje folder:

```text
secrets/
```

oraz pliki:

```text
taxonomykey.txt
specieskey.txt
listskey.txt
```

Folder `secrets/` powinien być w root repozytorium, nie w `dev/` ani `prod/`.

### Po wyborze folderu wygląda, jakby program się zawiesił

Sprawdź, czy nie otworzyło się okno wyboru presetu za innym oknem.

Aktualna wersja UI powinna wymuszać pokazanie okna na wierzchu, ale w razie problemów warto sprawdzić pasek zadań albo `Alt+Tab`.

### Skrypt czyta zły nagłówek Excela

Sprawdź log. Powinna być informacja o wykrytym wierszu nagłówka.

Jeśli wykrywanie się myli, warto sprawdzić, czy w pliku wejściowym istnieją kolumny typu:

```text
TaxonId
taxon_svensktNamn
taxon_vetenskapligtNamn
```

### Wynik ma więcej wierszy niż oczekiwano

Sprawdź, który plik oglądasz.

```text
*_full_.xlsx
```

zachowuje wszystkie obserwacje.

```text
*_with_data.xlsx
```

jest tabelą przeglądową deduplikowaną po `TaxonId`.

### API działa wolno

Sprawdź log i liczbę unikalnych `TaxonId`.

Jeśli wejście ma bardzo wiele unikalnych taksonów, czas działania będzie dłuższy. Powtórzone obserwacje tego samego taksonu nie powinny jednak zwiększać liczby zapytań API.

### Nie widzę swojego presetu w UI

Sprawdź, czy plik `.json` znajduje się w odpowiednim folderze:

```text
dev/export_presets/
```

albo, dla wersji produkcyjnej:

```text
prod/export_presets/
```

Sprawdź też, czy JSON jest poprawny składniowo.

---

## 19. Status projektu

Projekt działa, ale nadal jest rozwijany.

Aktualny stan:

```text
✅ działa na eksporcie Artportalen
✅ czyta tokeny z lokalnego /secrets
✅ ma strukturę dev/prod
✅ ma modularną wersję developerską
✅ automatycznie wykrywa nagłówek eksportu
✅ ogranicza zapytania API do unikalnych TaxonId
✅ zachowuje pełne obserwacje w full export
✅ filtruje skyddade/prioriterade z uwzględnieniem RedListCategory od NT w górę
✅ obsługuje presety eksportu
✅ obsługuje presety JSON w dev/export_presets/ i prod/export_presets/
✅ pozwala podejrzeć preset przed uruchomieniem
✅ pozwala zapisać kopię presetu jako JSON
⚠️ wymaga dalszych testów na różnych eksportach
⚠️ wymaga ostrożności przy przenoszeniu zmian z dev do prod
```

---

## 20. Krótkie TL;DR

```text
1. Tokeny trzymaj lokalnie w /secrets.
2. Uruchamiaj DEV przez: python start.py.
3. Presety DEV trzymaj w dev/export_presets/.
4. Presety PROD trzymaj w prod/export_presets/.
5. Wybierz Excel z Artportalen i folder wynikowy.
6. Wybierz preset eksportu.
7. Skrypt sam wykryje nagłówek i pobierze dane po unikalnych TaxonId.
8. full_ zachowuje wszystkie obserwacje.
9. with_data jest przeglądem po TaxonId.
10. bara_skyddade zawiera gatunki chronione / priorytetowe oraz rödlistade od NT w górę.
11. Riskklassning2024.xlsx trzymaj najlepiej w root repo.
12. secrets/ i results/ nie powinny trafiać do GitHub.
```
