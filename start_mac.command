#!/usr/bin/env bash
# ==============================================================================
# start_mac.command — Launcher dla macOS (dwuklik w Finderze lub uruchomienie w Terminalu)
# ==============================================================================

# Przejdź do katalogu projektu
cd "$(dirname "$0")" || exit 1

echo "============================================================"
echo "           Artportalen_med_data - macOS Launcher            "
echo "============================================================"

# Sprawdź czy python3 jest zainstalowany
if ! command -v python3 &> /dev/null; then
    echo "[!] Nie znaleziono polecenia 'python3'."
    echo "    Zainstaluj Python 3 ze strony https://www.python.org/ lub przez brew."
    echo ""
    read -n 1 -s -r -p "Naciśnij dowolny klawisz, aby zamknąć..."
    exit 1
fi

# Sprawdź / aktywuj wirtualne środowisko jeśli istnieje
if [ -d ".venv" ]; then
    echo "[*] Aktywowanie wirtualnego środowiska (.venv)..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "[*] Aktywowanie wirtualnego środowiska (venv)..."
    source venv/bin/activate
else
    # Sprawdź czy zależności są zainstalowane w python3
    if ! python3 -c "import pandas, requests, openpyxl" &> /dev/null; then
        echo "[*] Brak wymaganych pakietów. Tworzenie środowiska .venv..."
        python3 -m venv .venv
        source .venv/bin/activate
        echo "[*] Instalowanie zależności z requirements.txt..."
        pip install --upgrade pip
        pip install -r requirements.txt
    fi
fi

# Uruchom start.py
python3 start.py "$@"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -ne 0 ]; then
    echo "[!] Program zakończył działanie z kodem błędu: $EXIT_CODE"
else
    echo "[OK] Zakończono pomyślnie."
fi

echo ""
read -n 1 -s -r -p "Naciśnij dowolny klawisz, aby zamknąć to okno..."
exit $EXIT_CODE
