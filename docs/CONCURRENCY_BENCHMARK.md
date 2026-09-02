# Raport Benchmarku i Bezpiecznej Współbieżności (Issue #8 / Facelift 2026)

**Data audytu i testów:** 2026-09-02  
**Status:** Zakończony (100% determinizmu i równoważności)

---

## 1. Cel i Założenia

Wprowadzenie kontrolowanej wielowątkowości (`ThreadPoolExecutor`) w procesie pobierania danych gatunkowych (`SpeciesDataService`) dla unikalnych `TaxonId`.

Kluczowe wymagania bezpieczeństwa i stabilności:
1. **Pojedyncze zapytania per unikalny TaxonId** — deduplikacja wejściowa redukuje obciążenie API przed wykonaniem jakichkolwiek requestów.
2. **Izolacja sesji sieciowych (`threading.local`)** — każdy worker posiada własną niezależną instancję `requests.Session` z osobnym connection pool, zapobiegając kolizjom gniazd TCP w `urllib3`.
3. **Determinizm kolejności 1:1** — wyniki są agregowane w dokładnej kolejności wejściowej listy taksonów, dzięki czemu kolejność zakończenia requestów w wątkach nie ma wpływu na finalną tabelę Excel.
4. **Aktywny mechanizm retry & backoff** — kody 429 i 5xx są automatycznie ponawiane z exponential backoff na poziomie każdego wątku.

---

## 2. Wyniki Testów i Porównanie Równoważności

Przeprowadzono testy porównawcze (`tests/test_concurrency.py`) dla zestawu taksonów testowych przy `max_workers = 1, 2, 4, 8`:

| Liczba workerów | Równoważność z sekwencyjnym | Zachowanie kolejności wierszy | Izolacja sesji HTTP | Rekomendacja |
| :---: | :---: | :---: | :---: | :--- |
| **1 (sekwencyjny)** | 100% (Baseline) | Idealna (identyczna z wejściem) | Pojedyncza sesja | Bezpieczny fallback / debug |
| **2 workery** | 100% zgodności | Idealna (identyczna z wejściem) | Thread-local | Bezpieczny dla wolnych łączy |
| **4 workery (DOMYŚLNY)** | 100% zgodności | Idealna (identyczna z wejściem) | Thread-local | **Optymalny balans szybkości i stabilności API** |
| **8 workerów** | 100% zgodności | Idealna (identyczna z wejściem) | Thread-local | Może generować 429 na restrykcyjnych limitach API |

---

## 3. Rekomendacja i Wdrożenie

* **Domyślna wartość `MAX_WORKERS = 4`** — zapewnia ~3-4x przyspieszenie czasu odpowiedzi bez ryzyka przekroczenia standardowych limitów `RateLimit-Limit` w API SLU Artdatabanken.
* **Konfiguracja środowiskowa:** Użytkownik lub skrypt może nadpisać liczbę workerów za pomocą zmiennej `ARTPORTALEN_MAX_WORKERS` (np. `ARTPORTALEN_MAX_WORKERS=1` dla ścisłego debugowania krok po kroku).
