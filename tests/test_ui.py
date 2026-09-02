# -*- coding: utf-8 -*-
"""Unit tests for the modernized single-window UI (Issue #9)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tkinter as tk
from artportalen_enrich.logger_utils import log
from artportalen_enrich.ui import ArtportalenGui


class TestUI(unittest.TestCase):

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()  # Ukryj okno podczas testów jednostkowych
            self.has_tk = True
        except Exception:
            self.has_tk = False

    def tearDown(self):
        if self.has_tk and hasattr(self, "root"):
            try:
                self.root.destroy()
            except Exception:
                pass

    def test_gui_initialization_and_defaults(self):
        """Weryfikacja poprawnej inicjalizacji stanu GUI i zmiennych."""
        if not self.has_tk:
            self.skipTest("Tkinter display not available in environment.")

        gui = ArtportalenGui(self.root)
        self.assertTrue(gui.want_full_var.get())
        self.assertEqual(gui.source_type_var.get(), "auto")
        self.assertEqual(gui.workers_var.get(), 4)
        self.assertFalse(gui.refresh_cache_var.get())

        # Test callbacku postępu
        gui._apply_progress(50.0, "Pobrano 5/10 taksonów")
        self.assertEqual(gui.progress_var.get(), 50.0)
        self.assertIn("5/10", gui.status_var.get())

        # Test kolejkowania logów
        log("Wiadomość testowa dla konsoli GUI")
        self.assertFalse(gui.log_queue.empty())
        msg = gui.log_queue.get_nowait()
        self.assertIn("Wiadomość testowa", msg)


if __name__ == "__main__":
    unittest.main()
