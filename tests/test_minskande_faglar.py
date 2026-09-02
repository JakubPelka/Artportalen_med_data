# -*- coding: utf-8 -*-
"""Unit tests for minskande fåglar list parsing and matching."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from artportalen_enrich.species_helpers import is_minskande_fagel, load_minskande_faglar


class TestMinskandeFaglar(unittest.TestCase):

    def setUp(self):
        self.checkers = [
            ("engine", is_minskande_fagel, load_minskande_faglar),
        ]
        self.expected_species = [
            "bergand",
            "bivråk",
            "bläsand",
            "brunand",
            "ejder",
            "entita",
            "fjällvråk",
            "gräshoppsångare",
            "grönsiska",
            "gulsparv",
            "göktyta",
            "havstrut",
            "hussvala",
            "hämpling",
            "järnsparv",
            "kungsfågel",
            "näktergal",
            "rosenfink",
            "rörsångare",
            "skogsduva",
            "stare",
            "strandskata",
            "svärta",
            "sånglärka",
            "sävspar",
            "sävsparv",
            "tallbit",
            "tornseglare",
        ]

    def test_all_27_species_detected_by_swedish_name(self):
        """Verifiera att alla 27 arter i listan identifieras korrekt (oberoende av skiftläge och blanksteg)."""
        for env_name, is_minskande, _ in self.checkers:
            with self.subTest(env=env_name):
                for name in self.expected_species:
                    self.assertTrue(
                        is_minskande(swedish_name=name),
                        f"Gatunek '{name}' nie został rozpoznany w {env_name}!",
                    )
                    self.assertTrue(
                        is_minskande(swedish_name=name.upper()),
                        f"Gatunek '{name.upper()}' (uppercase) nie został rozpoznany w {env_name}!",
                    )
                    self.assertTrue(
                        is_minskande(swedish_name=f"  {name.capitalize()}  "),
                        f"Gatunek '{name.capitalize()}' z spacjami nie został rozpoznany w {env_name}!",
                    )

    def test_detection_by_taxon_id_and_scientific_name(self):
        """Verifiera igenkänning via TaxonId och vetenskapligt namn."""
        for env_name, is_minskande, _ in self.checkers:
            with self.subTest(env=env_name):
                # Grönsiska (TaxonId: 100027, Spinus spinus)
                self.assertTrue(is_minskande(taxon_id=100027))
                self.assertTrue(is_minskande(scientific_name="Spinus spinus"))

                # Tornseglare (TaxonId: 100012, Apus apus)
                self.assertTrue(is_minskande(taxon_id=100012))
                self.assertTrue(is_minskande(scientific_name="Apus apus"))

    def test_non_matching_species_return_false(self):
        """Gatunki spoza listy nie powinny zwracać True."""
        non_matching = ["gräsand", "koltrast", "talgoxe", "blåmes", "gråsparv"]
        for env_name, is_minskande, _ in self.checkers:
            with self.subTest(env=env_name):
                for name in non_matching:
                    self.assertFalse(
                        is_minskande(swedish_name=name),
                        f"Gatunek '{name}' niesłusznie zwrócił True!",
                    )

    def test_load_minskande_faglar_sets(self):
        """Weryfikacja wczytania zbiorów z pliku minskande_faglar50.xlsx."""
        for env_name, _, load_fn in self.checkers:
            with self.subTest(env=env_name):
                swe_set, sci_set, tid_set = load_fn()
                self.assertGreaterEqual(len(swe_set), 27)
                self.assertIn("bergand", swe_set)
                self.assertIn("tornseglare", swe_set)


if __name__ == "__main__":
    unittest.main()
