# -*- coding: utf-8 -*-
"""Unit tests for redlist period selection logic (Issue #1)."""

import sys
import unittest
from pathlib import Path

# Add dev and prod to sys.path so we can import both
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "dev"))
from artportalen_enrich.species_helpers import select_current_or_latest_redlist as dev_select

sys.path.insert(0, str(REPO_ROOT / "prod"))
from artportalen_enrich.species_helpers import select_current_or_latest_redlist as prod_select


class TestRedlistSelection(unittest.TestCase):

    def setUp(self):
        self.selectors = [
            ("dev", dev_select),
            ("prod", prod_select),
        ]

    def test_current_period_preferred_over_2020(self):
        """Verifiera att period.current is True väljs före äldre perioder som 2020."""
        redlist_info = [
            {
                "category": "NT",
                "criterion": "A2b",
                "period": {
                    "id": 12,
                    "name": "Rödlista 2020",
                    "year": 2020,
                    "current": False,
                },
            },
            {
                "category": "VU",
                "criterion": "B2ab(iii)",
                "period": {
                    "id": 13,
                    "name": "Rödlista 2025",
                    "year": 2025,
                    "current": True,
                },
            },
        ]

        for env_name, select_fn in self.selectors:
            with self.subTest(env=env_name):
                chosen = select_fn(redlist_info)
                self.assertIsNotNone(chosen)
                self.assertEqual(chosen.get("category"), "VU")
                self.assertEqual(chosen.get("period", {}).get("name"), "Rödlista 2025")

    def test_fallback_to_latest_year_when_no_current_flag(self):
        """Om ingen post har current == True, väljs den med senaste årtalet."""
        redlist_info = [
            {
                "category": "LC",
                "period": {
                    "id": 10,
                    "name": "Rödlista 2010",
                    "year": 2010,
                    "current": False,
                },
            },
            {
                "category": "NT",
                "period": {
                    "id": 11,
                    "name": "Rödlista 2015",
                    "year": 2015,
                },
            },
            {
                "category": "EN",
                "period": {
                    "id": 13,
                    "name": "Rödlista 2025",
                    "year": 2025,
                },
            },
            {
                "category": "VU",
                "period": {
                    "id": 12,
                    "name": "Rödlista 2020",
                    "year": 2020,
                },
            },
        ]

        for env_name, select_fn in self.selectors:
            with self.subTest(env=env_name):
                chosen = select_fn(redlist_info)
                self.assertIsNotNone(chosen)
                self.assertEqual(chosen.get("category"), "EN")
                self.assertEqual(chosen.get("period", {}).get("year"), 2025)

    def test_extract_year_from_period_name(self):
        """Om 'year' saknas i period-objektet, ska årtalet extraheras från namnet."""
        redlist_info = [
            {
                "category": "NT",
                "period": {
                    "name": "Rödlista 2020",
                },
            },
            {
                "category": "CR",
                "period": {
                    "name": "Rödlista 2025",
                },
            },
        ]

        for env_name, select_fn in self.selectors:
            with self.subTest(env=env_name):
                chosen = select_fn(redlist_info)
                self.assertIsNotNone(chosen)
                self.assertEqual(chosen.get("category"), "CR")
                self.assertEqual(chosen.get("period", {}).get("name"), "Rödlista 2025")

    def test_extract_year_from_dates(self):
        """Extrahering av årtal från periodFrom / periodTo."""
        redlist_info = [
            {
                "category": "NT",
                "period": {
                    "name": "Gammal",
                    "periodTo": "2020-04-20",
                },
            },
            {
                "category": "VU",
                "period": {
                    "name": "Ny",
                    "periodFrom": "2025-04-22",
                },
            },
        ]

        for env_name, select_fn in self.selectors:
            with self.subTest(env=env_name):
                chosen = select_fn(redlist_info)
                self.assertIsNotNone(chosen)
                self.assertEqual(chosen.get("category"), "VU")

    def test_single_item_fallback(self):
        """Om endast en post finns utan årtal/periodinfo, väljs den."""
        redlist_info = [
            {
                "category": "LC",
            }
        ]

        for env_name, select_fn in self.selectors:
            with self.subTest(env=env_name):
                chosen = select_fn(redlist_info)
                self.assertIsNotNone(chosen)
                self.assertEqual(chosen.get("category"), "LC")

    def test_empty_and_invalid_inputs(self):
        """Testa hantering av None, tomma listor och ogiltiga datatyper."""
        for env_name, select_fn in self.selectors:
            with self.subTest(env=env_name):
                self.assertIsNone(select_fn([]))
                self.assertIsNone(select_fn(None))
                self.assertIsNone(select_fn("invalid"))
                self.assertIsNone(select_fn([None, "not-a-dict"]))


if __name__ == "__main__":
    unittest.main()
