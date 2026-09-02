# -*- coding: utf-8 -*-
"""Wspólna konfiguracja uruchomieniowa RunConfig (Issue #10)."""

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import DEFAULT_MAX_WORKERS, REPO_ROOT
from .export_presets import get_default_preset_id


@dataclass(frozen=True)
class RunConfig:
    """Zunifikowana konfiguracja zadania enrichmentu dla GUI i CLI."""

    input_file: str
    out_dir: Optional[str] = None
    input_source: str = "auto"
    export_preset: Optional[str] = None
    want_full: bool = True
    debug: bool = False
    refresh_cache: bool = False
    max_workers: int = DEFAULT_MAX_WORKERS

    def resolve_paths(self) -> Dict[str, Any]:
        """Buduje kompletny słownik ścieżek i parametrów wykonawczych dla pipeline."""
        input_abs = os.path.abspath(self.input_file)
        if not os.path.exists(input_abs):
            raise FileNotFoundError(f"Plik wejściowy nie istnieje: {input_abs}")

        outdir = self.out_dir
        if not outdir:
            outdir = os.path.dirname(input_abs)
        outdir_abs = os.path.abspath(outdir)
        os.makedirs(outdir_abs, exist_ok=True)

        stem, _ = os.path.splitext(os.path.basename(input_abs))
        preset_id = self.export_preset or get_default_preset_id()

        return {
            "INPUT_FILE": input_abs,
            "INPUT_SOURCE": (self.input_source or "auto").strip().lower(),
            "EXPORT_PRESET": preset_id,
            "OUTDIR": outdir_abs,
            "OUT_WITH": os.path.join(outdir_abs, f"{stem}_med_data.xlsx"),
            "OUT_FULL": os.path.join(outdir_abs, f"{stem}_full_enriched.xlsx"),
            "OUT_PROT": os.path.join(outdir_abs, f"{stem}_bara_skyddade.xlsx"),
            "OUT_ALIEN": os.path.join(outdir_abs, f"{stem}_frammande_invasiva.xlsx"),
            "LOG_FILE": os.path.join(outdir_abs, f"{stem}_enrich.log"),
            "DBG_FILE": os.path.join(outdir_abs, f"{stem}_debug.csv"),
            "WANT_FULL": bool(self.want_full),
            "DEBUG": bool(self.debug),
            "REFRESH_CACHE": bool(self.refresh_cache),
            "MAX_WORKERS": int(self.max_workers),
        }
