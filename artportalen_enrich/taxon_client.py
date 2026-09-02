# -*- coding: utf-8 -*-
"""TaxonService: dopasowanie nazw do TaxonId."""

from typing import Any, Dict, Optional

from .cache import default_cache
from .config import TAXON_NAME_URL
from .http_client import default_client
from .logger_utils import log
from .utils import clean_scientific, clean_swedish, json_safe


def query_taxon_id_by_name(name: str, field: str, force_refresh: bool = False) -> int:
    cache_ident = f"{field}:{name}".strip().lower()
    cached_id = default_cache.get("taxon_name", cache_ident, force_refresh=force_refresh)
    if cached_id is not None:
        return int(cached_id)

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

    matched_id = 0
    exact = [
        d for d in data
        if any((
            str(d.get("displayName", "")).lower() == name_l,
            str(d.get("swedishName", "")).lower() == name_l,
            str(d.get("scientificName", "")).lower() == name_l,
        ))
    ]
    if exact:
        matched_id = _pick_id(exact[0])
    elif any(d.get("isRecommended") is True for d in data):
        recommended = [d for d in data if d.get("isRecommended") is True]
        matched_id = _pick_id(recommended[0])
    else:
        matched_id = _pick_id(data[0])

    if matched_id > 0:
        default_cache.set("taxon_name", cache_ident, matched_id)

    return matched_id


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
