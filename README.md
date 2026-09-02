# Artportalen_med_data (Facelift 2026)

Wieloplatformowe narzędzie do automatycznego wzbogacania eksportów obserwacji przyrodniczych (z **Artportalen** oraz **ArcGIS Online / AGOL**) o oficjalne dane taksonomiczne, ochronne i ekologiczne pobierane z API SLU Artdatabanken.

---

## 1. Najważniejsze możliwości

- **Obsługa wielu formatów wejściowych:**
  - Eksporty Excel z Artportalen (automatyczne wykrywanie wiersza nagłówka z pominięciem metadanych),
  - Eksporty z ArcGIS Online (AGOL) / pliki CSV / starsze arkusze `.xls`,
  - Automatyczne uzupełnianie brakujących `TaxonId` na podstawie nazw szwedzkich i naukowych.
- **Kompletne dane ochronne i ekologiczne (SLU Artdatabanken API):**
  - Dynamiczny wybór aktualnej Czerwonej Listy (`Rödlistning` 2025/current),
  - Statusy ochrony prawnej (`Fridlyst`, Dyrektywa Ptasia, Dyrektywa Siedliskowa / `Habitatdirektivet 2023`),
  - Konwencje międzynarodowe (CITES, Bern, Bonn),
  - Programy ochrony gatunkowej (Åtgärdsprogram / ÅGP),
  - Gatunki wskaźnikowe (Signalarter, Skogsstyrelsens naturvårdsarter),
  - Lista ptaków o silnym spadku liczebności (`minskande_faglar`),
  - Gatunki obce i inwazyjne (`IAS_Union_EU`, `FrammandeArter`, oceny ryzyka GEIAA).
- **Wydajność i niezawodność:**
  - **Zcentralizowany klient HTTP:** Pula połączeń, automatyczne ponawianie zapytań (retry) przy błędach przejściowych (429, 5xx, timeout) oraz exponential backoff,
  - **Lokalny cache SQLite (`.cache/`):** Przechowywanie odpowiedzi API z kontrolą świeżości (TTL) i opcją wymuszonego odświeżenia (`--refresh-cache`),
  - **Kontrolowana wielowątkowość (Concurrency):** Równoległe pobieranie danych gatunkowych z deterministycznym zachowaniem kolejności wierszy (domyślnie 4 wątki),
  - **Nowoczesne GUI:** Jedno responsywne okno (Tkinter/ttk) z podglądem postępu, czasem ETA i konsolą logów na żywo.
  - **Pełne wsparcie CLI / Headless:** Wygodne uruchamianie w skryptach i pipeline'ach wsadowych.

---

## 2. Struktura projektu

```text
Artportalen_med_data/
├── artportalen_enrich/       # Główny, zunifikowany silnik aplikacji
│   ├── cache.py              # Lokalny cache SQLite z kontrolą świeżości
│   ├── cli.py                # Interfejs wiersza poleceń CLI / Headless
│   ├── config.py             # Konfiguracja, endpointy i klucze API
│   ├── excel_io.py           # Zapis i odczyt Excel / CSV
│   ├── export_presets.py     # Profile kolumn i filtry eksportu
│   ├── http_client.py        # Centralny klient HTTP z Session pooling i retry
│   ├── input_loaders.py      # Autodetekcja Artportalen oraz AGOL
│   ├── logger_utils.py       # Logowanie i rejestracja zdarzeń
│   ├── pipeline.py           # Główny pipeline przetwarzania
│   ├── processing.py         # Enrichment, budowa tabel i transformacje
│   ├── risk_merge.py         # Scalanie danych z Riskklassning
│   ├── run_config.py         # Wspólna konfiguracja zadań RunConfig
│   ├── species_helpers.py    # Pomocnicze funkcje gatunkowe i minskande fåglar
│   ├── taxon_client.py       # TaxonService (wyszukiwanie po nazwach)
│   ├── tls_client.py         # TaxonListService (listy konwencji i ochrony)
│   └── ui.py                 # Nowoczesne jednoramkowe GUI (Tkinter/ttk)
├── export_presets/           # Profile eksportu (kungsbacka_standard, hotade_arter, itp.)
├── secrets/                  # Klucze API (plikowe)
├── tests/                    # Testy jednostkowe i regresyjne (Golden Dataset)
│   ├── fixtures/             # Przykładowe dane i moki offline
│   ├── test_cache.py
│   ├── test_cli.py
│   ├── test_concurrency.py
│   ├── test_golden_regression.py
│   ├── test_http_client.py
│   ├── test_minskande_faglar.py
│   ├── test_redlist_selection.py
│   └── test_ui.py
├── start.py                  # Główny launcher (automatyczny wybór GUI / CLI)
├── start_mac.command         # Launcher dla macOS
├── requirements.txt          # Zależności Python
└── README.md
```

---

## 3. Wymagania i instalacja

Projekt wymaga Pythona 3.6+ (zalecany Python 3.8 - 3.12).

### Krok 1: Klonowanie repozytorium i utworzenie środowiska wirtualnego

```bash
git clone https://github.com/JakubPelka/Artportalen_med_data.git
cd Artportalen_med_data

# Utworzenie i aktywacja wirtualnego środowiska
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# lub w Windows: .venv\Scripts\activate
```

### Krok 2: Instalacja zależności

```bash
pip install -r requirements.txt
```

> **Uwaga dla użytkowników Linux (Ubuntu / Debian):**  
> Jeśli korzystasz z trybu graficznego GUI, upewnij się, że masz zainstalowany pakiet Tkinter:  
> `sudo apt-get install python3-tk`

### Krok 3: Konfiguracja kluczy API

Klucze API SLU Artdatabanken można przekazać na dwa sposoby:

1. **Pliki w folderze `secrets/` (domyślnie):**
   - `secrets/taxonomykey.txt` — klucz do TaxonService,
   - `secrets/specieskey.txt` — klucz do SpeciesDataService,
   - `secrets/listskey.txt` — klucz do TaxonListService.

2. **Zmienne środowiskowe:**
   ```bash
   export TAXONOMY_KEY="twój_klucz_taxonomy"
   export SPECIES_KEY="twój_klucz_species"
   export LISTS_KEY="twój_klucz_lists"
   ```

---

## 4. Sposób użycia

### A. Tryb graficzny GUI (Domyślny)

Wystarczy uruchomić:
```bash
python3 start.py
```
*(lub kliknąć dwukrotnie `start_mac.command` na macOS)*

### B. Tryb wiersza poleceń (CLI / Headless)

Przykład podstawowy:
```bash
python3 start.py --input dane_obserwacji.xlsx --outdir results/
```

Przykład z pełnymi opcjami:
```bash
python3 start.py \
  --input eksport_artportalen.xlsx \
  --outdir results/ \
  --source auto \
  --preset kungsbacka_standard \
  --full \
  --workers 4 \
  --refresh-cache
```

Wyświetlenie dostępnych profili eksportu:
```bash
python3 start.py --list-presets
```

---

## 5. Testy i kontrola jakości

Projekt posiada obszerny zestaw testów jednostkowych oraz testów regresji (Golden Dataset):

```bash
python3 -m unittest discover -s tests -v
```