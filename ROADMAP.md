# ROADMAP / Maintenance

## Serwis po dłuższej przerwie — 2026-09-02

Cel: przywrócić skrypt do pewnego działania na świeżym Ubuntu i aktualnych eksportach Artportalen / AGOL, bez psucia stabilnego PROD.

### 1. Zależności i uruchamianie

- [ ] Dodać `requirements.txt` w root repozytorium.
- [ ] Uwzględnić co najmniej:
  - `pandas`
  - `requests`
  - `openpyxl`
  - `xlrd`
- [ ] W README opisać instalację na Ubuntu przez `.venv`.
- [ ] W README dopisać zależność systemową `python3-tk` dla GUI.
- [ ] Dodać prosty smoke test importów, aby brak pakietu był wykrywany od razu, a nie dopiero w środku pipeline.

Przykładowa instalacja na Ubuntu:

```bash
sudo apt install python3-venv python3-pip python3-tk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Obsługa plików Excel `.xls` i `.xlsx`

Aktualny PROD wymusza `engine="openpyxl"` w `prod/artportalen_enrich/excel_io.py` zarówno przy wykrywaniu nagłówka, jak i przy właściwym odczycie pliku.

Efekt dla klasycznego eksportu `.xls` z Artportalen:

```text
zipfile.BadZipFile: File is not a zip file
```

- [ ] Dodać automatyczny wybór silnika:
  - `.xls` -> `xlrd`
  - `.xlsx` / `.xlsm` -> `openpyxl`
- [ ] Użyć tej samej funkcji wyboru silnika w `detect_artportalen_header_row()` i `read_artportalen_excel()`.
- [ ] Dodać czytelny log z wykrytym formatem i użytym silnikiem.
- [ ] Sprawdzić eksport `.xls` faktycznie wygenerowany przez Artportalen.
- [ ] Jeśli zdarzają się pliki z rozszerzeniem `.xls`, które faktycznie są HTML/XML, dodać fallback lub czytelny komunikat diagnostyczny.

### 3. DEV vs PROD — synchronizacja

W repo istnieje rozjazd funkcjonalny między `dev` i `prod`.

Commit `AGOL compatible` z maja 2026 dodał / zmienił w DEV m.in.:

- `dev/artportalen_enrich/input_loaders.py`
- `dev/artportalen_enrich/pipeline.py`
- `dev/artportalen_enrich/ui.py`

Aktualny PROD nie ma `input_loaders.py` i nadal startuje od logiki stricte Artportalen.

- [ ] Porównać `dev/artportalen_enrich/` z `prod/artportalen_enrich/` plik po pliku.
- [ ] Ustalić, które zmiany DEV zostały realnie przetestowane i powinny wejść do PROD.
- [ ] Nie kopiować DEV do PROD w ciemno — najpierw test regresji Artportalen.
- [ ] Po testach zachować zasadę: `start.py` jako jedyny launcher docelowy.

### 4. Test regresji Artportalen

Użyć realnego eksportu, np. podobnego do:

```text
Artportalen_FaglarAlla_1000m_10ar.xls / .xlsx
```

Sprawdzić kolejno:

- [ ] GUI uruchamia się na Ubuntu.
- [ ] Wybór pliku i folderu wynikowego działa.
- [ ] Automatyczne wykrycie wiersza nagłówka działa.
- [ ] `TaxonId` jest poprawnie rozpoznawany.
- [ ] Zapytania do TaxonService / SpeciesDataService / TaxonListService działają z aktualnymi kluczami.
- [ ] Presety eksportu nadal działają.
- [ ] Powstają oczekiwane pliki wynikowe.
- [ ] `_bara_skyddade` zawiera poprawne rekordy.
- [ ] Sortowanie czerwonej listy działa jak wcześniej.
- [ ] Opcjonalne łączenie z `Riskklassning2024.xlsx` nadal działa.
- [ ] Debug CSV / log nie generują nowych błędów.

### 5. Test regresji AGOL

Po ustabilizowaniu Artportalen:

- [ ] Uruchomić aktualny DEV na realnym eksporcie AGOL.
- [ ] Zweryfikować auto-detect źródła.
- [ ] Zweryfikować mapowanie kolumn z nazwą szwedzką, naukową i `TaxonId`.
- [ ] Potwierdzić, że enrichment jest identyczny z tym używanym dla Artportalen.
- [ ] Dopiero po tym przenieść sprawdzoną logikę AGOL do PROD.

### 6. Obsługa błędów / UX

- [ ] Przy braku `secrets/taxonomykey.txt`, `specieskey.txt` lub `listskey.txt` wyświetlać czytelny komunikat w GUI, nie tylko traceback.
- [ ] Przy braku wymaganej biblioteki pokazać wskazówkę instalacyjną.
- [ ] Przy nieobsługiwanym / uszkodzonym Excelu podać konkretną informację o formacie.
- [ ] Rozważyć prosty ekran / log startowy: Python version, platforma, format wejścia, wersje bibliotek.

### 7. Porządki repo

- [ ] Uporządkować `.gitignore` — obecnie `/results` występuje wielokrotnie.
- [ ] Dopisać `.venv/` i standardowe cache Pythona, jeśli jeszcze nie są skutecznie ignorowane.
- [ ] Po zakończeniu serwisu zaktualizować README, żeby odpowiadał realnej strukturze PROD.

## Zasada przy następnej sesji

Najpierw uruchomić aktualny PROD na realnym `.xlsx` i zebrać pełny log do pierwszego kolejnego błędu. Naprawiać problemy krok po kroku. Dopiero po przejściu całego pipeline Artportalen robić większą synchronizację `dev -> prod`.
