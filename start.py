#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
start.py — Główny launcher repozytorium Artportalen_med_data.

Umożliwia uruchomienie wersji deweloperskiej (dev) lub produkcyjnej (prod).

Użycie w terminalu:
    python3 start.py          # domyślnie dev (lub menu wyboru)
    python3 start.py --dev    # uruchamia wersję dev
    python3 start.py --prod   # uruchamia wersję prod
"""

import os
import sys
from pathlib import Path


def check_dependencies():
    missing = []
    for pkg in ("pandas", "requests", "openpyxl"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("\n" + "=" * 60)
        print(" [!] Brak wymaganych bibliotek Python:")
        for m in missing:
            print(f"     - {m}")
        print("\n Zainstaluj je poleceniem:")
        print("     pip install -r requirements.txt")
        print("=" * 60 + "\n")
        sys.exit(1)


def check_secrets(repo_root: Path):
    secrets_dir = repo_root / "secrets"
    required_keys = ["taxonomykey.txt", "specieskey.txt", "listskey.txt"]
    missing = []

    if not secrets_dir.exists():
        print("\n" + "=" * 60)
        print(" [!] Brak folderu 'secrets' w katalogu głównym projektu:")
        print(f"     {secrets_dir}")
        print("\n Utwórz folder 'secrets' i umieść w nim pliki z kluczami API:")
        for k in required_keys:
            print(f"     - secrets/{k}")
        print("=" * 60 + "\n")
        return

    for key_file in required_keys:
        kp = secrets_dir / key_file
        if not kp.exists() or kp.stat().st_size == 0:
            missing.append(key_file)

    if missing:
        print("\n" + "=" * 60)
        print(" [!] Brakujące lub puste pliki z kluczami API w secrets/:")
        for m in missing:
            print(f"     - secrets/{m}")
        print("=" * 60 + "\n")


def choose_environment() -> str:
    # 1. Argumenty CLI
    args = [a.lower().strip("-") for a in sys.argv[1:]]
    if "prod" in args:
        return "prod"
    if "dev" in args:
        return "dev"

    # 2. Jeśli uruchomiono bez argumentów
    # Jeśli środowisko nie jest interaktywne (np. subproces), domyślnie dev
    if not sys.stdin.isatty():
        return "dev"

    print("=" * 50)
    print(" Artportalen_med_data Launcher")
    print("=" * 50)
    print(" Wybierz wersję do uruchomienia:")
    print("   [1] DEV  - wersja deweloperska (zalecana)")
    print("   [2] PROD - wersja produkcyjna")
    print("-" * 50)

    try:
        choice = input(" Wybór [1/2, domyślnie 1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nPrzerwano.")
        sys.exit(0)

    if choice == "2":
        return "prod"
    return "dev"


def main():
    repo_root = Path(__file__).resolve().parent

    check_dependencies()
    check_secrets(repo_root)

    env = choose_environment()
    print(f"\n-> Uruchamianie Artportalen enrich (profil: {env.upper()})\n")

    sys.path.insert(0, str(repo_root))

    try:
        from artportalen_enrich.pipeline import main as pipeline_main
        pipeline_main()
    except Exception as e:
        print(f"\n[Błąd krytyczny]: {e}")
        raise


if __name__ == "__main__":
    main()
