# -*- coding: utf-8 -*-
"""Golden regression test suite for Artportalen & AGOL enrichment pipelines."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from artportalen_enrich.export_presets import (
    apply_export_preset,
    get_preset,
    list_presets,
)
from artportalen_enrich.input_loaders import read_input_file
from artportalen_enrich.tls_client import fetch_tls_definitions, tls_build_memberships
from artportalen_enrich.pipeline import (
    ensure_taxon_id,
    unique_taxon_ids,
)
from artportalen_enrich.processing import (
    DATA_COLUMNS,
    build_enrichment_table,
    make_alien_invasive,
    make_full_enriched,
    make_overview,
    make_protected,
    sort_by_redlist,
)
from tests.fixtures.mock_data import (
    MOCK_NAME_SEARCH,
    MOCK_SPECIES_DATA,
    MOCK_TLS_DEFINITIONS,
    MOCK_TLS_MEMBERSHIPS_BY_LIST_ID,
)


def mock_requests_get(url, *args, **kwargs):
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    # Taxon names search
    if "taxonservice" in url or "names" in url:
        params = kwargs.get("params", {})
        query = str(params.get("searchString", "")).strip().lower()
        tid = MOCK_NAME_SEARCH.get(query, 0)
        if tid:
            mock_resp.json.return_value = {
                "data": [
                    {
                        "displayName": query.capitalize(),
                        "swedishName": query.capitalize(),
                        "scientificName": query.capitalize(),
                        "taxonInformation": {"taxonId": tid},
                    }
                ]
            }
            mock_resp.content = b'{"data": [...]}'
        else:
            mock_resp.json.return_value = {"data": []}
            mock_resp.content = b'{"data": []}'
        return mock_resp

    # TLS definitions
    if "definitions" in url:
        mock_resp.json.return_value = MOCK_TLS_DEFINITIONS
        mock_resp.content = b'{"conservationLists": [...]}'
        return mock_resp

    # Species data
    if "speciesdata" in url:
        params = kwargs.get("params", {})
        taxa = params.get("taxa")
        if not taxa:
            # parse from url query if taxa={tid}
            if "taxa=" in url:
                taxa = url.split("taxa=")[1].split("&")[0]
        try:
            tid = int(taxa)
        except (ValueError, TypeError):
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

    return mock_resp


class TestGoldenRegression(unittest.TestCase):

    def setUp(self):
        self.fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        self.ap_file = str(self.fixtures_dir / "artportalen_sample.xlsx")
        self.agol_file = str(self.fixtures_dir / "agol_sample.xlsx")

    @patch("requests.get", side_effect=mock_requests_get)
    def test_artportalen_header_detection_and_taxon_resolution(self, mock_get):
        """Verifiera att Artportalen-export med inledande metadata rader tolkas korrekt."""
        input_result = read_input_file(self.ap_file, "auto")
        self.assertEqual(input_result.source_type, "artportalen")
        self.assertEqual(len(input_result.dataframe), 5)
        self.assertIn("Svenskt namn", input_result.dataframe.columns)
        self.assertIn("Vetenskapligt namn", input_result.dataframe.columns)

        # Ensure TaxonId resolution for missing Ejder row
        df_resolved = ensure_taxon_id(input_result.dataframe, input_result.columns)
        self.assertEqual(len(df_resolved), 5)
        # Row 3 (Ejder) should have resolved TaxonId=100021
        ejder_row = df_resolved[df_resolved["Svenskt namn"] == "Ejder"].iloc[0]
        self.assertEqual(int(ejder_row["TaxonId"]), 100021)

    @patch("requests.get", side_effect=mock_requests_get)
    def test_agol_input_loading_and_taxon_resolution(self, mock_get):
        """Verifiera att AGOL-export tolkas korrekt och saknade TaxonId kompletteras."""
        input_result = read_input_file(self.agol_file, "agol")
        self.assertEqual(input_result.source_type, "agol")
        self.assertEqual(len(input_result.dataframe), 4)

        df_resolved = ensure_taxon_id(input_result.dataframe, input_result.columns)
        self.assertEqual(len(df_resolved), 4)
        gronsiska_row = df_resolved[df_resolved["taxon_svensktNamn"] == "Grönsiska"].iloc[0]
        self.assertEqual(int(gronsiska_row["TaxonId"]), 100027)

    @patch("requests.get", side_effect=mock_requests_get)
    @patch("requests.post", side_effect=mock_requests_post)
    def test_full_pipeline_enrichment_regression(self, mock_post, mock_get):
        """Golden test całego pipeline offline: weryfikacja poprawności enrichmentu i flag."""
        # 1. Read input
        input_result = read_input_file(self.ap_file, "artportalen")
        df = ensure_taxon_id(input_result.dataframe, input_result.columns)
        uniq_ids = unique_taxon_ids(df)

        # 4 unique taxa in 5 observations (100007, 100018, 100021, 100027)
        self.assertEqual(len(uniq_ids), 4)

        # Initialize TLS list definitions and memberships
        fetch_tls_definitions()
        tls_build_memberships()

        # 2. Build enrichment table
        enrichment_result = build_enrichment_table(uniq_ids)
        self.assertEqual(len(enrichment_result), 4)

        # Check all DATA_COLUMNS exist
        for col in DATA_COLUMNS:
            self.assertIn(col, enrichment_result.columns)

        # 3. Verify Bergand (100018) data correctness
        bergand = enrichment_result[enrichment_result["TaxonId"] == 100018].iloc[0]
        self.assertEqual(bergand["RedListCategory"], "VU") # 2025 VU preferred over 2020 NT!
        self.assertEqual(bergand["RedListPeriodName"], "Rödlista 2025")
        self.assertEqual(bergand["FågeldirektivetBilaga1"], "Ja")
        self.assertEqual(bergand["minskande_faglar"], "Ja")
        self.assertEqual(bergand["Habitatdirektivet2023"], "Ja")
        self.assertEqual(bergand["ActionProgramName"], "ÅGP Kustfåglar")
        self.assertEqual(bergand["Author"], "(Linnaeus, 1761)")
        self.assertEqual(bergand["SwedishOccurrence"], "Bofast")
        self.assertEqual(bergand["SwedishHistory"], "Spontant etablerad")

        # 4. Verify Grönsiska (100027)
        gronsiska = enrichment_result[enrichment_result["TaxonId"] == 100027].iloc[0]
        self.assertEqual(gronsiska["RedListCategory"], "LC")
        self.assertEqual(gronsiska["minskande_faglar"], "Ja")

        # 5. Verify Gräsand (100007)
        grasand = enrichment_result[enrichment_result["TaxonId"] == 100007].iloc[0]
        self.assertEqual(grasand["RedListCategory"], "LC")
        self.assertEqual(grasand["minskande_faglar"], "")

        # 6. Verify full_enriched preserves all 5 observation rows (duplicate TaxonId preserved!)
        full_enriched = make_full_enriched(df, enrichment_result)
        self.assertEqual(len(full_enriched), 5)

        # 7. Verify overview deduplication (4 rows)
        overview = make_overview(full_enriched)
        self.assertEqual(len(overview), 4)

        # 8. Verify protected species (_bara_skyddade)
        # Bergand (VU), Ejder (NT+Fridlyst), Grönsiska (minskande_faglar) -> 3 species
        # Gräsand (LC without flags) -> excluded!
        protected = make_protected(overview)
        self.assertEqual(len(protected), 3)
        self.assertNotIn(100007, protected["TaxonId"].values)
        self.assertIn(100018, protected["TaxonId"].values)
        self.assertIn(100021, protected["TaxonId"].values)
        self.assertIn(100027, protected["TaxonId"].values)

    def test_export_presets_column_sequence_and_integrity(self):
        """Weryfikacja integralności i kolejności kolumn we wszystkich presetach."""
        presets = list_presets()
        self.assertGreaterEqual(len(presets), 4)

        # Test dummy enriched dataframe
        dummy_data = {col: ["test_val"] for col in DATA_COLUMNS}
        dummy_data["TaxonId"] = [100018]
        dummy_data["Svenskt namn"] = ["Bergand"]
        dummy_df = pd.DataFrame(dummy_data)

        for p in presets:
            exported = apply_export_preset(dummy_df, p.preset_id)
            self.assertGreater(len(exported.columns), 0)
            self.assertIn("TaxonId", exported.columns)
            if p.include_original_columns:
                self.assertIn("Svenskt namn", exported.columns)


if __name__ == "__main__":
    unittest.main()
