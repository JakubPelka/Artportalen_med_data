# AGENT INSTRUCTION — Artportalen_med_data facelift 2026

## Cel nadrzędny

Przeprowadź kompleksowy facelift repozytorium **bez utraty dotychczasowej funkcjonalności**. Priorytetem jest **poprawność i wiarygodność danych**, następnie stabilność, a dopiero później szybkość i UX.

Repo obsługuje dwa główne typy wejścia:

- eksport Artportalen,
- dane / eksport AGOL.

Musi zachować kompatybilność z istniejącymi presetami, filtrami ochronnymi, plikami Excel i workflow użytkownika na Windows, macOS i Ubuntu.

---

# Najważniejsza zasada

> **QUALITY FIRST. Nie optymalizuj kodu, którego wyniku jeszcze nie potrafimy zweryfikować.**

Każda większa zmiana musi mieć test regresji lub inny jednoznaczny sposób potwierdzenia równoważności.

Nie łącz wielu etapów w jeden duży refactor. Pracuj **issue po issue**, wykonując po każdym etapie osobny commit/checkpoint.

Jeśli implementacja danego issue wymaga zmiany z innego etapu, zatrzymaj się i opisz zależność zamiast wykonywać niekontrolowany refactor kilku warstw naraz.

---

# Git / bezpieczeństwo zmian

1. Pracuj na osobnej gałęzi roboczej, np. `facelift-2026`.
2. Przed pierwszą zmianą zapisz SHA punktu startowego.
3. Każde issue zamykaj osobnym logicznym commitem lub małą serią jasno opisanych commitów.
4. Nie usuwaj starej implementacji przed potwierdzeniem równoważności nowej.
5. Nie commituj:
   - `secrets/`,
   - `.cache/`,
   - lokalnych `.venv/`,
   - wygenerowanych wyników użytkownika,
   - tokenów/API keys.

Jeśli test pokaże regresję, popraw ją w danym etapie zamiast maskować zmianą expected output, chyba że została świadomie zmieniona logika biznesowa i jest to udokumentowane.

---

# Kolejność wdrożenia

Realizuj issues w następującej kolejności:

1. **#1 — Rödlistning: usunięcie hardkodu 2020** (`fix it now`).
2. **#2 — Audit poprawności: hardkodowane lata, okresy i aktualność źródeł.**
3. **#3 — Golden dataset i testy regresji Artportalen + AGOL.**
4. **#4 — Jeden wspólny engine DEV/PROD.**
5. **#5 — Audit pokrycia API i rozszerzenie kompletnego datasetu.**
6. **#6 — Wspólna warstwa HTTP: Session/pooling/retry/backoff.**
7. **#7 — Lokalny cache SQLite.**
8. **#8 — Controlled concurrency i benchmark.**
9. **#9 — Facelift GUI.**
10. **#10 — CLI/headless + RunConfig + portable setup/secrets.**

Nie zaczynaj optymalizacji sieci ani concurrency przed ustanowieniem testów regresji.

---

# Zasady dotyczące danych i kolumn

## 1. Nie tracimy żadnej istniejącej informacji

Nie usuwaj istniejących kolumn z kompletnego/full datasetu bez wyraźnej decyzji użytkownika.

Jeśli DEV zawiera pola, których PROD nie posiada, traktuj DEV jako potencjalne źródło brakującej funkcjonalności, ale **zweryfikuj semantykę i działanie przed przeniesieniem**.

Aktualny DEV zawiera m.in. dodatkowe pola takie jak:

- `FågeldirektivetBilaga2`,
- `SkogsstyrelsensNaturvardsarter`,
- `minskande_faglar`,
- `Habitatdirektivet2023`,
- rozszerzone informacje o främmande arter / risklistach.

Niczego z tego nie zgub podczas konsolidacji.

## 2. Chętnie rozszerzamy kompletny dataset

Podczas audytu API sprawdź **cały aktualnie dostępny model odpowiedzi**, a nie tylko pola używane dziś.

Dla każdego pola wykonaj klasyfikację:

- `KEEP` — już poprawnie używane,
- `ADD` — wartościowe i należy dodać do full/maximal dataset,
- `SKIP` — świadomie niepotrzebne,
- `VERIFY` — znaczenie/okres wymaga potwierdzenia.

Dokumentuj wynik w `docs/API_FIELD_COVERAGE.md`.

### Co uznajemy za wartościowe

Preferuj dane przydatne dla GIS, naturvård, ekologii i interpretacji statusu gatunku, np.:

- status i kryteria rödlistning,
- okres/wersja oceny,
- ochrona prawna,
- dyrektywy i konwencje,
- action programs,
- natura/biotop/substrate/ecological groups,
- conservation assessments,
- texty Artfakta,
- främmande arter / invasiveness / risk classification,
- status obecności/pochodzenia,
- inne aktualne pola merytoryczne dostępne w API.

Nie dodawaj bezrefleksyjnie technicznych metadanych API, jeśli nie mają znaczenia użytkowego.

## 3. Nowe pola najpierw tylko do FULL/MAXIMAL

Rozszerzanie kompletnego datasetu **nie może automatycznie zmieniać istniejących presetów**.

Nowe pola dodaj najpierw do pełnego/maximalnego eksportu. Presety `standard`, `naturvard`, `kort_skyddade`, IAS itd. mają zachować dotychczasowy zakres i kolejność, chyba że w osobnym kroku świadomie zdecydujemy o ich rozszerzeniu.

## 4. Nigdy nie zmieniaj znaczenia kolumny przez podmianę okresu

To krytyczne.

Jeśli istnieje kolumna nazwana np.:

- `Artikel 17 - 2019`,
- `Habitatdirektivet2023`,
- inna kolumna z jawnie zapisanym rokiem,

**nie wolno po prostu zacząć wpisywać do niej danych z 2025/2026/current**.

Jeżeli API ma nowszy okres:

1. zachowaj istniejącą kolumnę jako legacy/okres historyczny, jeśli dane są nadal dostępne,
2. dodaj poprawnie nazwane pole aktualne, np. stabilną nazwę bez roku,
3. dodaj osobne pole okresu/wersji (`...PeriodName`, `...Year`, `...Version`),
4. dopiero później można rozważyć migrację presetów.

Wyjątkiem są istniejące kolumny o semantyce jawnie „aktualnej”, np. `RedListCategory` wraz z `RedListPeriodName`: tam należy wybierać bieżący okres zwracany przez API.

---

# Issue #1 i #2 — correctness audit

Najpierw napraw `Rödlistning 2020` zgodnie z issue #1.

Wybór redlist powinien być:

1. `period.current is True`,
2. jeśli brak `current`: najnowszy możliwy do ustalenia okres,
3. ostatni fallback: pierwszy poprawny rekord.

Nie hardkoduj `2025`, bo problem wróci przy kolejnej Rödlistan.

Następnie przeskanuj repo pod kątem:

- lat `2019`–`2026`,
- `current`,
- `period`,
- `year`,
- `version`,
- `RedList`,
- `Artikel 17`,
- `Habitatdirektiv`,
- `Riskklassning`,
- lokalnych list/fallbacków.

Dla każdego znalezionego miejsca zapisz decyzję `OK/FIX/VERIFY`.

**Nie zmieniaj czegoś wyłącznie dlatego, że rok jest stary.** Najpierw ustal, czy API lub źródło ma nowszą właściwą wersję i jakie jest znaczenie pola.

---

# Issue #3 — golden regression baseline

Przed dużym refaktorem utwórz małe fixtures Artportalen i AGOL.

Testy muszą kontrolować co najmniej:

- rozpoznanie formatu wejścia,
- nagłówek Artportalen,
- kolumny TaxonId/nazwy,
- mapowanie enrichmentu,
- aktualny RedListPeriodName + category/criterion,
- statusy ochronne,
- IAS/främmande arter,
- kolejność kolumn,
- każdy istniejący preset,
- `_bara_skyddade`,
- pełny/full eksport,
- zachowanie wszystkich obserwacji przy deduplikacji requestów API.

Preferuj mocki API dla testów automatycznych. Live API używaj jako osobny integration smoke test.

Nie zapisuj dużych ani wrażliwych danych użytkownika w fixtures.

---

# Issue #4 — jedna architektura, nadal bezpieczny DEV/PROD

Docelowo chcemy jeden engine, np.:

```text
Artportalen_med_data/
├── artportalen_enrich/      # jedno źródło prawdy
├── dev/
│   ├── start.py
│   └── export_presets/
├── prod/
│   ├── start.py
│   └── export_presets/
├── tests/
└── ...
```

`dev/start.py` i `prod/start.py` mają być cienkimi entrypointami do tego samego engine.

Bezpieczeństwo rozwoju realizujemy przez Git/branch/feature flags/config, a nie przez dwie kopiowane wersje całego pakietu.

`Agol_DEV.py` wygaszaj dopiero po potwierdzeniu, że modularny pipeline obsługuje wszystkie realne warianty AGOL.

---

# Issue #5 — API field coverage audit

Przejrzyj aktualne odpowiedzi i/lub oficjalną dokumentację wykorzystywanych API SLU Artdatabanken.

Nie zakładaj, że aktualny parser pokrywa wszystkie wartościowe pola.

Dla co najmniej reprezentatywnego zestawu różnych taksonów zrzutuj strukturę odpowiedzi w test/debug (bez sekretów) i porównaj z `DATA_COLUMNS`.

Zwróć uwagę na:

- pola obecne tylko dla niektórych grup,
- listy zagnieżdżone,
- pola wielookresowe,
- pola current/history,
- wartości `null`, list, dict, bool i tekst,
- różnice dla ptaków, gatunków habitatowych i främmande arter.

Nowe wartościowe pola dodaj do full datasetu wraz z testami.

Jeśli znaczenie pola jest niejasne — `VERIFY`, nie zgaduj.

---

# Issue #6 — warstwa HTTP

Dopiero gdy wynik jest kontrolowany testami:

- centralny API/HTTP client,
- `requests.Session`,
- connection pooling,
- timeout,
- retry dla 429/5xx/timeout,
- exponential backoff,
- sensowne logowanie.

Na tym etapie nadal **jeden worker**.

Wynik enrichmentu przed/po musi być równoważny.

---

# Issue #7 — cache

Preferowany cache: SQLite w `.cache/`.

Wymagania:

- nie zawiera sekretów,
- ma `fetched_at`,
- rozróżnia endpoint/service/TaxonId/culture/schema version,
- ma ręczny refresh,
- może zostać bezpiecznie usunięty i odbudowany,
- nie jest commitowany.

Nie ustawiaj jednego arbitralnego TTL na wszystkie dane bez uzasadnienia.

---

# Issue #8 — concurrency

Concurrency jest ostatnim etapem optymalizacji API.

Benchmarkuj kolejno:

- 1 worker,
- 2,
- 4,
- ewentualnie 8.

Wybierz konserwatywną wartość domyślną na podstawie stabilności, nie maksymalnej liczby requestów/s.

Muszą pozostać:

- retry/backoff,
- poprawna obsługa 429,
- deterministyczna kolejność danych wynikowych,
- identyczny wynik względem trybu sekwencyjnego.

---

# Issue #9 — GUI

Zostań przy Tkinter/ttk.

Jedno okno ma zawierać:

- input,
- output,
- source Auto/Artportalen/AGOL,
- preset + preview,
- Full,
- Debug,
- Refresh cache,
- Start/Cancel,
- progress,
- taxa X/Y,
- ETA,
- live log.

Pipeline nie może działać w głównym wątku GUI.

GUI jest tylko frontendem do tego samego engine, którego używa CLI.

---

# Issue #10 — RunConfig, CLI i portability

Wprowadź jeden `RunConfig` używany przez GUI i CLI.

Uruchomienie bez argumentów -> GUI.

Uruchomienie z argumentami -> headless CLI.

Zadbaj o:

- `requirements.txt`,
- `.xls` -> `xlrd`,
- `.xlsx/.xlsm` -> `openpyxl`,
- Ubuntu `python3-tk`,
- Windows/macOS compatibility,
- ENV secrets -> fallback `secrets/*.txt`,
- czytelne błędy startowe.

Headless pipeline nie powinien wymagać działającego display/Tk.

---

# Zasady dotyczące wydajności

Nie deklaruj zysków typu `3x` lub `10x` bez benchmarku.

Dla performance changes zapisuj:

- dataset testowy,
- liczbę unikalnych TaxonId,
- liczbę requestów,
- cache hits/misses,
- retry/429/5xx,
- czas całkowity,
- workers,
- porównanie danych z baseline.

Najważniejszym kryterium jest zgodność wyniku.

---

# Definition of Done dla całego faceliftu

Facelift jest zakończony dopiero gdy:

- [ ] Rödlistning wybiera aktualny okres bez hardkodu roku.
- [ ] Audyt okresów/datasetów został udokumentowany.
- [ ] Golden regression tests obejmują Artportalen i AGOL.
- [ ] Istnieje jeden wspólny engine.
- [ ] Funkcjonalność DEV nie została utracona przy konsolidacji.
- [ ] API field coverage został udokumentowany.
- [ ] Użyteczne brakujące pola są dostępne w full/maximal dataset.
- [ ] Istniejące presety zachowały kompatybilność, chyba że ich zmiana została osobno zaakceptowana.
- [ ] Warstwa HTTP ma session/pooling/retry/backoff.
- [ ] Cache działa i ma manual refresh.
- [ ] Concurrency został dobrany benchmarkiem i nie zmienia wyniku.
- [ ] GUI jest jednym responsywnym oknem z progress/ETA/log.
- [ ] CLI/headless używa tego samego pipeline.
- [ ] `.xls` i `.xlsx` działają.
- [ ] Instalacja na świeżym Ubuntu jest powtarzalna.
- [ ] Windows i macOS nie zostały świadomie złamane.
- [ ] README odpowiada finalnej strukturze repo.
- [ ] `Agol_DEV.py` jest usunięty lub pozostawiony jedynie jako jawny compatibility wrapper.

---

# Raportowanie pracy przez agenta

Po każdym issue podaj użytkownikowi krótko:

1. co zostało zmienione,
2. jakie pliki,
3. jakie testy uruchomiono i wynik,
4. czy zmienił się output/schema,
5. benchmark, jeśli dotyczy,
6. commit SHA,
7. czy issue można zamknąć,
8. co jest następnym issue.

Jeśli wykryjesz nowy problem jakości danych lub nową wartościową funkcję, **nie chowaj jej w bieżącym refaktorze**. Otwórz osobne issue i powiąż z odpowiednim etapem.
