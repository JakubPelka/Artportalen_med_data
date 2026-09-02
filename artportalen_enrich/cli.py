# -*- coding: utf-8 -*-
"""Interfejs wiersza poleceń CLI / headless (Issue #10)."""

import argparse
import os
import sys
from typing import Any, Callable, List, Optional

from .config import DEFAULT_MAX_WORKERS
from .export_presets import get_default_preset_id, list_presets
from .run_config import RunConfig


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="start.py",
        description="🌿 Artportalen & AGOL Data Enricher — CLI / Headless",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--input", "-i",
        dest="input_file",
        help="Ścieżka do pliku wejściowego (.xlsx, .xls, .csv).",
    )
    parser.add_argument(
        "--outdir", "-o",
        dest="out_dir",
        help="Ścieżka do folderu zapisu wyników (domyślnie: folder pliku wejściowego).",
    )
    parser.add_argument(
        "--source", "-s",
        dest="input_source",
        choices=["auto", "artportalen", "agol"],
        default="auto",
        help="Format pliku wejściowego.",
    )
    parser.add_argument(
        "--preset", "-p",
        dest="export_preset",
        default=get_default_preset_id(),
        help="ID profilu eksportu kolumn.",
    )
    parser.add_argument(
        "--full",
        dest="want_full",
        action="store_true",
        default=True,
        help="Zapisz pełny wzbogacony dataset (*_full_enriched.xlsx).",
    )
    parser.add_argument(
        "--no-full",
        dest="want_full",
        action="store_false",
        help="Pomiń zapis pełnego wzbogaconego datasetu.",
    )
    parser.add_argument(
        "--debug", "-d",
        dest="debug",
        action="store_true",
        default=False,
        help="Włącz tryb szczegółowego logowania i eksport pliku *_debug.csv.",
    )
    parser.add_argument(
        "--refresh-cache", "-r",
        dest="refresh_cache",
        action="store_true",
        default=False,
        help="Wymuś pobranie świeżych danych z API SLU, ignorując lokalny cache SQLite.",
    )
    parser.add_argument(
        "--workers", "-w",
        dest="max_workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Liczba współbieżnych wątków roboczych (1 = sekwencyjnie, 2, 4, 8).",
    )
    parser.add_argument(
        "--list-presets",
        dest="list_presets",
        action="store_true",
        help="Wyświetl listę dostępnych profili eksportu i zakończ.",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Uruchom w trybie wsadowym bez sprawdzania środowiska graficznego.",
    )

    # Flagi wstecznej kompatybilności dla dev/prod launcherów
    parser.add_argument("--dev", dest="env_dev", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--prod", dest="env_prod", action="store_true", help=argparse.SUPPRESS)

    return parser


def parse_cli_args(argv: Optional[List[str]] = None) -> Optional[RunConfig]:
    if argv is None:
        argv = sys.argv[1:]

    # Jeśli brak argumentów lub tylko --dev / --prod -> tryb GUI
    clean_args = [a for a in argv if a not in ("--dev", "--prod", "-dev", "-prod")]
    if not clean_args:
        return None

    parser = build_argument_parser()
    parsed = parser.parse_args(argv)

    if parsed.list_presets:
        print("\n=== Dostępne profile eksportu kolumn ===")
        for p in list_presets():
            print(f" • {p.preset_id:25} | {p.label}")
            if p.description:
                print(f"   ↳ {p.description}")
        print("========================================\n")
        sys.exit(0)

    if not parsed.input_file:
        # Podano jakieś argumenty, ale brak --input
        parser.error("Wymagany parametr --input (-i) w trybie CLI.")

    return RunConfig(
        input_file=parsed.input_file,
        out_dir=parsed.out_dir,
        input_source=parsed.input_source,
        export_preset=parsed.export_preset,
        want_full=parsed.want_full,
        debug=parsed.debug,
        refresh_cache=parsed.refresh_cache,
        max_workers=parsed.max_workers,
    )


def run_cli(run_fn: Optional[Callable[..., Any]] = None, argv: Optional[List[str]] = None) -> int:
    config = parse_cli_args(argv)
    if config is None:
        return 1

    paths = config.resolve_paths()

    if run_fn is None:
        from .pipeline import run_pipeline
        run_fn = run_pipeline

    try:
        run_fn(paths=paths)
        return 0
    except Exception as exc:
        print(f"\n[Błąd wykonania CLI]: {exc}", file=sys.stderr)
        return 1
