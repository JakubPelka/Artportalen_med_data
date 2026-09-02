# Audyt Poprawności Okresów, Lat i Źródeł Referencyjnych (Issue #2 / Facelift 2026)

**Data audytu:** 2026-09-02  
**Status:** Zakończony (wszystkie pozycje zweryfikowane)

---

## 1. Cel audytu

Weryfikacja wszystkich miejsc w kodzie `Artportalen_med_data` (zarówno `dev`, jak i `prod`), które operują na rocznikach, okresach referencyjnych, wersjach list oraz zewnętrznych plikach danych, aby wyeliminować nieuzasadnione hardkody i zapewnić najwyższą jakość i aktualność danych.

---

## 2. Podsumowanie audytu

| Obszar / Kolumna | Źródło danych | Mechanizm wyboru | Znaczenie semantyczne | Decyzja | Uzasadnienie |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Rödlistning** (`RedListCategory`, `RedListCriterion`, `RedListPeriodName`, `RedListCriterionText`) | API `SpeciesDataService` (`redlistInfo[]`) | `select_current_or_latest_redlist()` | Bieżący status czerwonej listy (np. Rödlista 2025) | **OK (FIXED)** | Naprawiono w Issue #1 (`ec5d1ad`). Usunięto hardkod `"2020"`, wprowadzono priorytet `period.current is True`, dynamiczny fallback do najnowszego rocznika i testy jednostkowe. |
| **Artikel 17** (`Artikel 17 - 2019`) | API `SpeciesDataService` (`conservationAssessments.periods[]`) | Filtrowanie po nazwie okresu `"2019"` | Raportowanie do Dyrektywy Siedliskowej UE za 6-letni cykl 2013–2018 (raport 2019) | **OK** | Kolumna z nazwy odnosi się ściśle do raportu 2019. Zgodnie z zasadą nienaruszania semantyki kolumn legacy, nie wolno podmieniać jej zawartości na inny okres. Przy udostępnieniu przez API nowego cyklu (np. 2025) zostanie dodane nowe pole `Artikel17_Current` bez zmiany kolumny 2019. |
| **Habitatdirektivet 2023** (`Habitatdirektivet2023`) | API `TaxonListService` (Lista ID 265) | Dopasowanie po nazwie `"habitatdirektiv"` + `"2023"` oraz ID 265 | Krajowa aktualizacja listy gatunków Dyrektywy Siedliskowej przez Naturvårdsverket z 2023 r. | **OK** | Odnosi się do konkretnej rewizji krajowej z 2023 r. Ogólne załączniki dyrektywy (Annex 2, 4, 5) są niezależnie pobierane do pól `DirectiveAppendix2/4/5`. |
| **Riskklassning 2024** | Plik Excel `Riskklassning2024.xlsx` (GEIAA) | Merge po `TaxonId` przez `risk_merge.py` (`find_risk_file()`) | Oficjalna klasyfikacja inwazyjności gatunków obcych z 2024 r. (GEIAA) | **OK** | Plik `find_risk_file()` dynamicznie wyszukuje `Riskklassning2024.xlsx`, `Risklista2024.xlsx`, `Riskklassning.xlsx` i wzorce `Risk*.xlsx`, co pozwala na bezproblemową wymianę pliku w przyszłości. |
| **Minskande fåglar** (`minskande_faglar`) | Plik Excel `minskande_faglar50.xlsx` | `is_minskande_fagel()` | 27 gatunków ptaków o spadku liczebności >50% | **OK** | Dynamicznie ładowane z pliku Excel (z fallbackiem wbudowanym). |
| **IAS Union List** (`IAS_Union_EU`) | API `TaxonListService` (Lista ID 37) | Dopasowanie listy `EU-förordning 1143/2014` / `unionsförteckning` | Unijna lista inwazyjnych gatunków obcych (Rozporządzenie UE 1143/2014) | **OK** | Nazwa rozporządzenia (1143/2014) jest stałym aktem prawnym UE. |
| **Åtgärdsprogram (Action Programs)** | API `SpeciesDataService` (`natureConservation.actionProgram`) | Pola `startYear`, `endYear`, `status`, `program` | Programy ochrony gatunkowej | **OK** | Wszystkie lata pobierane w 100% dynamicznie z API, brak hardkodów. |
| **Konwencje międzynarodowe** (CITES, Bern, Bonn) | API `TaxonListService` + fallback z `SpeciesDataService` | Dopasowanie definicji list | Członkostwo w konwencjach | **OK** | Dopasowanie dynamiczne przez TLS i listy taksonomiczne. |

---

## 3. Szczegółowa analiza znalezionych wystąpień

### 3.1. Rödlistning (Issue #1)
- **Problem pierwotny:** Wyszukiwanie `"2020"` w `period.name` przed weryfikacją `period.current`.
- **Wdrożona poprawka:** Funkcja `select_current_or_latest_redlist()` w `dev` i `prod`:
  1. `period.current is True` (wybiera np. Rödlista 2025).
  2. W razie braku flagi `current` – sortowanie po `(year, id)` malejąco.
  3. Pierwszy element jako ostatni fallback.
- **Weryfikacja:** 6 testów jednostkowych w `tests/test_redlist_selection.py` (wszystkie pass).

### 3.2. `Artikel 17 - 2019`
- **Analiza:** W `processing.py` kod filtruje okresy `ca.get("periods")` pod kątem `"2019"`. Raportowanie Article 17 odbywa się w cyklach 6-letnich (2007, 2013, 2019, 2025).
- **Zasada nienaruszalności:** Nazwa kolumny to `Artikel 17 - 2019`. Zgodnie z wytycznymi faceliftu, nie zmieniamy zawartości kolumny o jawnie zdefiniowanym rocznym tytule.
- **Rekomendacja na etap Issue #5 (API coverage):** Dodanie do pełnego datasetu nowej, uniwersalnej kolumny `Artikel17_Current` + `Artikel17_PeriodName`, przy zachowaniu `Artikel 17 - 2019` w celach kompatybilności wstecznej.

### 3.3. `Habitatdirektivet2023`
- **Analiza:** W `tls_client.py` i `processing.py` flaga ta sprawdza przynależność do listy TLS `Habitatdirektivet 2023` (ID 265).
- **Ocena:** Poprawne, specyficzne dla krajowej aktualizacji z 2023 r.

### 3.4. `Riskklassning2024.xlsx`
- **Analiza:** `risk_merge.py` łączy dane z pliku `Riskklassning2024.xlsx`. Funkcja `find_risk_file()` przeszukuje katalog główny i foldery projektu pod kątem plików `Riskklassning*.xlsx` / `Risklista*.xlsx`.
- **Ocena:** Mechanizm elastyczny i poprawny.

---

## 4. Wnioski i status Issue #2

* Wszystkie wystąpienia lat i okresów zostały zweryfikowane pod kątem semantyki biznesowej.
* Żadne ukryte hardkody nie zniekształcają danych wyjściowych.
* Kryteria akceptacji dla Issue #2 zostały w pełni spełnione.
