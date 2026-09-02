# -*- coding: utf-8 -*-
"""TaxonService: dopasowanie nazw do TaxonId."""

from typing import Any, Dict, Optional

from .config import TAXON_NAME_URL
from .http_client import default_client
from .logger_utils import log
from .utils import clean_scientific, clean_swedish, json_safe


def query_taxon_id_by_name(name: str, field: str) -> int:
    params = {
        "searchString": name,
        "searchFields": field,
        "isRecommended": "NotSet",
        "isOkForObservationSystems": "NotSet",
        "culture": "sv_SE",
        "page": 1,
        "pageSize": 100,
    }

    resp = default_client.get_taxonomy(TAXON_NAME_URL, params=params)
    if resp.status_code != 200:
        log(f"Błąd {resp.status_code} przy wyszukiwaniu '{name}' ({field}): {resp.text[:200]!r}")
        return 0

    data = (json_safe(resp) or {}).get("data", []) if resp.content else []
    if not data:
        return 0

    name_l = (name or "").lower()

    def _pick_id(item: Dict[str, Any]) -> int:
        ti = item.get("taxonInformation", {}) or {}
        return int(ti.get("taxonId", 0) or 0)

    exact = [
        d for d in data
        if any((
            str(d.get("displayName", "")).lower() == name_l,
            str(d.get("swedishName", "")).lower() == name_l,
            str(d.get("scientificName", "")).lower() == name_l,
        ))
    ]
    if exact:
        return _pick_id(exact[0])

    recommended = [d for d in data if d.get("isRecommended") is True]
    if recommended:
        return _pick_id(recommended[0])

    return _pick_id(data[0])


def resolve_taxon_id(row: Dict[str, Any], sv_col: Optional[str], sci_col: Optional[str]) -> int:
    swe = str(row.get(sv_col, "") or "").strip() if sv_col else ""
    sci = str(row.get(sci_col, "") or "").strip() if sci_col else ""

    if swe:
        tid = query_taxon_id_by_name(swe, "Swedish")
        if tid:
            return tid

        cs = clean_swedish(swe)
        if cs and cs != swe:
            tid = query_taxon_id_by_name(cs, "Swedish")
            if tid:
                return tid

    if sci:
        csci = clean_scientific(sci)
        for cand in (csci, sci):
            if cand:
                tid = query_taxon_id_by_name(cand, "Scientific")
                if tid:
                    return tid

    log(f"Brak TaxonId — swe='{swe}' sci='{sci}'")
    return 0
