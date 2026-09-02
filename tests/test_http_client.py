# -*- coding: utf-8 -*-
"""Unit tests for the centralized HTTP client (Issue #6)."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from artportalen_enrich.config import (
    HEADERS_LISTS,
    HEADERS_SPECIES,
    HEADERS_TAXON,
)
from artportalen_enrich.http_client import HttpClient


class TestHttpClient(unittest.TestCase):

    def setUp(self):
        # Use small backoff in tests to avoid test delays
        self.client = HttpClient(max_retries=3, backoff_factor=0.01)

    def test_successful_get_request(self):
        """200 OK returns immediately on first attempt."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}

        with patch.object(self.client.session, "request", return_value=mock_resp) as mock_req:
            resp = self.client.get("https://api.test/resource")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(mock_req.call_count, 1)

    def test_retry_on_429_too_many_requests(self):
        """429 triggers retry with backoff and succeeds on subsequent try."""
        resp_429 = MagicMock(status_code=429)
        resp_200 = MagicMock(status_code=200)

        with patch.object(self.client.session, "request", side_effect=[resp_429, resp_200]) as mock_req:
            resp = self.client.get("https://api.test/rate-limited")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(mock_req.call_count, 2)

    def test_retry_on_503_service_unavailable(self):
        """503 triggers retry and succeeds."""
        resp_503 = MagicMock(status_code=503)
        resp_200 = MagicMock(status_code=200)

        with patch.object(self.client.session, "request", side_effect=[resp_503, resp_503, resp_200]) as mock_req:
            resp = self.client.get("https://api.test/flaky")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(mock_req.call_count, 3)

    def test_retry_on_timeout_exception(self):
        """Timeout exception triggers retry and succeeds."""
        resp_200 = MagicMock(status_code=200)

        with patch.object(
            self.client.session,
            "request",
            side_effect=[requests.exceptions.Timeout("Read timed out"), resp_200],
        ) as mock_req:
            resp = self.client.get("https://api.test/slow")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(mock_req.call_count, 2)

    def test_no_retry_on_permanent_400_or_401(self):
        """Permanent 4xx errors (400, 401, 403, 404) are NOT retried."""
        for code in (400, 401, 403, 404):
            mock_resp = MagicMock(status_code=code)
            with patch.object(self.client.session, "request", return_value=mock_resp) as mock_req:
                resp = self.client.get(f"https://api.test/error-{code}")
                self.assertEqual(resp.status_code, code)
                self.assertEqual(mock_req.call_count, 1)

    def test_max_retries_exceeded_returns_failing_response(self):
        """When retries exceed max_retries, the failing response is returned."""
        resp_500 = MagicMock(status_code=500)

        with patch.object(
            self.client.session,
            "request",
            return_value=resp_500,
        ) as mock_req:
            resp = self.client.get("https://api.test/broken")
            self.assertEqual(resp.status_code, 500)
            self.assertEqual(mock_req.call_count, 4)  # 1 initial + 3 retries

    def test_service_specific_headers_attached(self):
        """Service methods attach correct API subscription key headers."""
        mock_resp = MagicMock(status_code=200)

        with patch.object(self.client.session, "request", return_value=mock_resp) as mock_req:
            # 1. Taxonomy
            self.client.get_taxonomy("https://api.test/taxon", params={"q": "test"})
            mock_req.assert_called_with(
                method="GET",
                url="https://api.test/taxon",
                headers=HEADERS_TAXON,
                params={"q": "test"},
                json=None,
                timeout=self.client.timeout,
            )

            # 2. Species
            self.client.get_species("https://api.test/species", params={"taxa": 100})
            mock_req.assert_called_with(
                method="GET",
                url="https://api.test/species",
                headers=HEADERS_SPECIES,
                params={"taxa": 100},
                json=None,
                timeout=self.client.timeout,
            )

            # 3. Lists GET
            self.client.get_lists("https://api.test/lists/defs")
            mock_req.assert_called_with(
                method="GET",
                url="https://api.test/lists/defs",
                headers=HEADERS_LISTS,
                params=None,
                json=None,
                timeout=self.client.timeout,
            )

            # 4. Lists POST
            self.client.post_lists("https://api.test/lists/taxa", json_data={"listIds": [1, 2]})
            mock_req.assert_called_with(
                method="POST",
                url="https://api.test/lists/taxa",
                headers=HEADERS_LISTS,
                params=None,
                json={"listIds": [1, 2]},
                timeout=self.client.timeout,
            )


if __name__ == "__main__":
    unittest.main()
