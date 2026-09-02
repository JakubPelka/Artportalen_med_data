# -*- coding: utf-8 -*-
"""Unit tests for the SQLite cache layer (Issue #7)."""

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from artportalen_enrich.cache import SqliteCache
from artportalen_enrich.processing import fetch_species_record


class TestCache(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_cache.sqlite")
        self.cache = SqliteCache(db_path=self.db_path, default_ttl=3600)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_miss_then_hit(self):
        """First request is a MISS; after set(), subsequent request is a HIT."""
        # MISS
        val = self.cache.get("species_data", 100018)
        self.assertIsNone(val)

        # SET
        test_payload = {"taxonId": 100018, "name": "Bergand"}
        self.cache.set("species_data", 100018, test_payload)

        # HIT
        val2 = self.cache.get("species_data", 100018)
        self.assertIsNotNone(val2)
        self.assertEqual(val2["taxonId"], 100018)
        self.assertEqual(val2["name"], "Bergand")

    def test_force_refresh_bypasses_cache(self):
        """force_refresh=True returns None even when data is cached."""
        self.cache.set("species_data", 100018, {"name": "Bergand"})

        # Normal lookup -> HIT
        self.assertIsNotNone(self.cache.get("species_data", 100018))

        # Force refresh -> MISS (bypassed)
        self.assertIsNone(self.cache.get("species_data", 100018, force_refresh=True))

    def test_ttl_expiration(self):
        """Expired entries return None (treated as MISS)."""
        # Set with 1 second TTL
        self.cache.set("taxon_name", "swedish:bergand", 100018, ttl_seconds=1)

        # Immediately -> HIT
        self.assertEqual(self.cache.get("taxon_name", "swedish:bergand"), 100018)

        # Simulate expiration by mocking time
        with patch("time.time", return_value=time.time() + 10):
            self.assertIsNone(self.cache.get("taxon_name", "swedish:bergand"))

    def test_clear_and_stats(self):
        """clear() removes entries and stats() returns accurate counts."""
        self.cache.set("species_data", 1, {"id": 1})
        self.cache.set("species_data", 2, {"id": 2})
        self.cache.set("taxon_name", "a", 1)

        stats = self.cache.stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["by_service"]["species_data"], 2)
        self.assertEqual(stats["by_service"]["taxon_name"], 1)

        deleted = self.cache.clear("species_data")
        self.assertEqual(deleted, 2)
        self.assertEqual(self.cache.stats()["total"], 1)

        self.cache.clear()
        self.assertEqual(self.cache.stats()["total"], 0)

    def test_fetch_species_record_uses_cache(self):
        """fetch_species_record retrieves from cache on second call without HTTP request."""
        from artportalen_enrich.http_client import default_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "speciesData": {
                    "taxonId": 100018,
                    "scientificName": "Aythya marila",
                    "swedishName": "Bergand",
                }
            }
        ]
        mock_resp.content = b'[...]'

        with patch("artportalen_enrich.processing.default_cache", self.cache):
            with patch.object(default_client, "get_species", return_value=mock_resp) as mock_get:
                # First call: cache MISS -> calls API
                rec1, _ = fetch_species_record(100018, 1, 1)
                self.assertEqual(rec1["SwedishName"], "Bergand")
                self.assertEqual(mock_get.call_count, 1)

                # Second call: cache HIT -> NO API call
                rec2, _ = fetch_species_record(100018, 1, 1)
                self.assertEqual(rec2["SwedishName"], "Bergand")
                self.assertEqual(mock_get.call_count, 1)  # Call count remains 1!

                # Third call with force_refresh: cache bypassed -> calls API
                rec3, _ = fetch_species_record(100018, 1, 1, force_refresh=True)
                self.assertEqual(rec3["SwedishName"], "Bergand")
                self.assertEqual(mock_get.call_count, 2)  # Incremented to 2!


if __name__ == "__main__":
    unittest.main()
