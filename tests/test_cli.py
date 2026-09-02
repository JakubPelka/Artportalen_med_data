# -*- coding: utf-8 -*-
"""Unit tests for CLI and RunConfig (Issue #10)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from artportalen_enrich.cli import parse_cli_args, run_cli
from artportalen_enrich.run_config import RunConfig


class TestCLI(unittest.TestCase):

    def setUp(self):
        self.fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        self.sample_input = str(self.fixtures_dir / "artportalen_sample.xlsx")

    def test_run_config_path_resolution(self):
        """RunConfig resolve_paths poprawnie generuje wszystkie wymagane ścieżki i flagi."""
        config = RunConfig(
            input_file=self.sample_input,
            out_dir=str(self.fixtures_dir),
            input_source="artportalen",
            export_preset="kungsbacka_standard",
            want_full=True,
            debug=True,
            refresh_cache=True,
            max_workers=2,
        )
        paths = config.resolve_paths()
        self.assertEqual(paths["INPUT_FILE"], os.path.abspath(self.sample_input))
        self.assertEqual(paths["INPUT_SOURCE"], "artportalen")
        self.assertEqual(paths["EXPORT_PRESET"], "kungsbacka_standard")
        self.assertTrue(paths["WANT_FULL"])
        self.assertTrue(paths["DEBUG"])
        self.assertTrue(paths["REFRESH_CACHE"])
        self.assertEqual(paths["MAX_WORKERS"], 2)
        self.assertTrue(paths["OUT_WITH"].endswith("_med_data.xlsx"))
        self.assertTrue(paths["OUT_FULL"].endswith("_full_enriched.xlsx"))

    def test_parse_cli_args_returns_none_for_empty_args(self):
        """Brak argumentów lub tylko --dev/--prod kieruje do trybu GUI (zwraca None)."""
        self.assertIsNone(parse_cli_args([]))
        self.assertIsNone(parse_cli_args(["--dev"]))
        self.assertIsNone(parse_cli_args(["--prod"]))

    def test_parse_cli_args_with_valid_parameters(self):
        """Parametry CLI są poprawnie mapowane do obiektu RunConfig."""
        argv = [
            "--input", self.sample_input,
            "--outdir", "/tmp/results",
            "--source", "agol",
            "--preset", "hotade_arter",
            "--no-full",
            "--debug",
            "--refresh-cache",
            "--workers", "8",
        ]
        config = parse_cli_args(argv)
        self.assertIsNotNone(config)
        self.assertEqual(config.input_file, self.sample_input)
        self.assertEqual(config.out_dir, "/tmp/results")
        self.assertEqual(config.input_source, "agol")
        self.assertEqual(config.export_preset, "hotade_arter")
        self.assertFalse(config.want_full)
        self.assertTrue(config.debug)
        self.assertTrue(config.refresh_cache)
        self.assertEqual(config.max_workers, 8)

    def test_run_cli_executes_pipeline(self):
        """run_cli poprawnie przekazuje sparsowany RunConfig do funkcji wykonawczej pipeline."""
        mock_run = MagicMock()
        argv = ["--input", self.sample_input, "--source", "auto"]

        exit_code = run_cli(run_fn=mock_run, argv=argv)
        self.assertEqual(exit_code, 0)
        self.assertEqual(mock_run.call_count, 1)

        call_kwargs = mock_run.call_args[1]
        self.assertIn("paths", call_kwargs)
        self.assertEqual(call_kwargs["paths"]["INPUT_SOURCE"], "auto")


if __name__ == "__main__":
    unittest.main()
