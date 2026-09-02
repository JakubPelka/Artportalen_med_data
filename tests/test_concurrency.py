# -*- coding: utf-8 -*-
"""Unit and equivalence tests for controlled concurrency (Issue #8)."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from artportalen_enrich.http_client import HttpClient
from artportalen_enrich.processing import build_enrichment_table
from artportalen_enrich.tls_client import fetch_tls_definitions, tls_build_memberships
from tests.fixtures.mock_data import (
    MOCK_NAME_SEARCH,
    MOCK_SPECIES_DATA,
    MOCK_TLS_DEFINITIONS,
    MOCK_TLS_MEMBERSHIPS_BY_LIST_ID,
)


def mock_requests_get(url, *args, **kwargs):
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    if "definitions" in url:
        mock_resp.json.return_value = MOCK_TLS_DEFINITIONS
        mock_resp.content = b'{"conservationLists": [...]}'
        return mock_resp

    if "speciesdata" in url:
        params = kwargs.get("params", {})
        taxa = params.get("taxa")
        if not taxa and "taxa=" in url:
            taxa = url.split("taxa=")[1].split("&")[0]
        try:
            tid = int(taxa)
        except Exception:
            tid = 0

        sp_data = MOCK_SPECIES_DATA.get(tid)
        if sp_data:
            mock_resp.json.return_value = [{"speciesData": sp_data}]
            mock_resp.content = b'[{"speciesData": {...}}]'
        else:
            mock_resp.json.return_value = []
            mock_resp.content = b'[]'
        return mock_resp

    return mock_resp


def mock_requests_post(url, *args, **kwargs):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    if "taxa" in url:
        json_body = kwargs.get("json", {})
        list_ids = json_body.get("conservationListIds", [])
        matched_taxa = set()
        for lid in list_ids:
            for tid in MOCK_TLS_MEMBERSHIPS_BY_LIST_ID.get(lid, []):
                matched_taxa.add(tid)
        mock_resp.json.return_value = [{"id": tid} for tid in sorted(matched_taxa)]
        mock_resp.content = b'[...]'
    return mock_resp


def mock_client_request(self, method, url, *args, **kwargs):
    if method.upper() == "POST":
        return mock_requests_post(url, *args, **kwargs)
    return mock_requests_get(url, *args, **kwargs)


class TestConcurrency(unittest.TestCase):

    @patch("artportalen_enrich.http_client.HttpClient.request", new=mock_client_request)
    def test_deterministic_equivalence_across_worker_counts(self):
        """Weryfikacja 100% równoważności danych i kolejności dla 1, 2, 4 i 8 workerów."""
        # Initialize TLS
        fetch_tls_definitions()
        tls_build_memberships()

        taxa_list = [100018, 100007, 100027, 100021]

        # 1. Baseline: 1 worker (sekwencyjnie)
        df_seq = build_enrichment_table(taxa_list, force_refresh=True, max_workers=1)

        # 2. Test 2, 4, 8 workers
        for num_workers in (2, 4, 8):
            df_concurrent = build_enrichment_table(
                taxa_list, force_refresh=True, max_workers=num_workers
            )
            pd.testing.assert_frame_equal(df_seq, df_concurrent, check_like=False)

    def test_thread_local_isolation(self):
        """Każdy wątek roboczy otrzymuje osobną instancję Session."""
        import concurrent.futures

        client = HttpClient()
        sessions = set()

        def get_thread_session_id():
            sess = client.session
            return id(sess)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(get_thread_session_id) for _ in range(8)]
            for f in futures:
                sessions.add(f.result())

        # Powinno być utworzonych co najmniej kilka unikalnych sesji (dla osobnych wątków)
        self.assertGreater(len(sessions), 1)


if __name__ == "__main__":
    unittest.main()
