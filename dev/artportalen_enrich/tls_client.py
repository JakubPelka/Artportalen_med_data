# -*- coding: utf-8 -*-
"""TaxonListService: definitioner, medlemskap och skyddsflaggor."""

from typing import Any, Dict, List, Set

import requests

from .config import HEADERS_LISTS, TIMEOUT, TLS_DEFS_URL, TLS_TAXA_URL
from .logger_utils import is_debug, log
from .utils import json_safe, normkey

_TLS_DEFS: Dict[int, str] = {}
_TLS_CATSETS: Dict[str, Set[int]] = {}
_TLS_DEFS_READY = False
_TLS_MEMBERS: Dict[str, Set[int]] = {}


def _norm(s: str) -> str:
    return normkey(s).replace("å", "a").replace("ä", "a").replace("ö", "o")


def fetch_tls_definitions() -> None:
    """Mapa ID→nazwa + zbiory ID interesujących list."""
    global _TLS_DEFS, _TLS_CATSETS, _TLS_DEFS_READY

    _TLS_DEFS, _TLS_CATSETS, _TLS_DEFS_READY = {}, {}, False

    try:
        r = requests.get(TLS_DEFS_URL, headers=HEADERS_LISTS, timeout=TIMEOUT)
        if r.status_code != 200:
            log(f"TLS /definitions {r.status_code}: {r.text[:160]!r}")
            return

        defs = json_safe(r) or {}
        lists = defs.get("conservationLists", []) or []

        for it in lists:
            lid = it.get("id")
            name = it.get("name") or ""
            if isinstance(lid, int) and name:
                _TLS_DEFS[lid] = name

        def find_ids_by_contains(substrs: List[str]) -> Set[int]:
            out: Set[int] = set()
            normalized_substrs = [_norm(sub) for sub in substrs]

            for lid, name in _TLS_DEFS.items():
                n = _norm(name)
                if any(sub in n for sub in normalized_substrs):
                    out.add(lid)

            return out

        _TLS_CATSETS = {
            "CITES": find_ids_by_contains(["cites"]),
            "Bernkonventionen": find_ids_by_contains(["bern"]),
            "Bonnkonventionen": find_ids_by_contains(["bonn", "cms"]),
            "FågeldirektivetBilaga1": find_ids_by_contains([
                "fageldirektivet bilaga 1",
                "fågeldirektivet bilaga 1",
            ]),
            "PrioriteradeFågelarterSkogsvårdslagen": find_ids_by_contains([
                "prioriterade fagelarter i skogsvardslagen",
                "prioriterade fågelarter i skogsvårdslagen",
                "skogsvardslagen",
                "skogsvårdslagen",
            ]),
            "Fridlyst": find_ids_by_contains([
                "fridlysta arter",
                "fridlysta faglar",
                "fridlysta fåglar",
                "fridlysta",
            ]),
            "Habitat_Bilaga2": find_ids_by_contains([
                "habitatdirektivets bilaga 2",
                "habitatdirektivet bilaga 2",
                "bilaga 2",
            ]),
            "Habitat_Bilaga2_Prio": find_ids_by_contains([
                "habitatdirektivets bilaga 2",
                "habitatdirektivet bilaga 2",
                "prioriterad",
                "prioriterade",
                "priority",
            ]),
            "Habitat_Bilaga4": find_ids_by_contains([
                "habitatdirektivets bilaga 4",
                "habitatdirektivet bilaga 4",
                "bilaga 4",
            ]),
            "Habitat_Bilaga5": find_ids_by_contains([
                "habitatdirektivets bilaga 5",
                "habitatdirektivet bilaga 5",
                "bilaga 5",
            ]),
            "IAS_Union_EU": find_ids_by_contains([
                "invasiv",
                "invasiva",
                "frammande",
                "eu-forteckning",
                "eu forteckning",
                "unionsforteckning",
                "union list",
                "eu list",
            ]),
        }

        _TLS_DEFS_READY = True

        if is_debug():
            for cat, ids in _TLS_CATSETS.items():
                sample = ", ".join(
                    [f"{i}:{_TLS_DEFS.get(i, '?')[:24]}" for i in list(sorted(ids))[:6]]
                )
                log(f" → {cat}: {len(ids)} id ({sample})")

    except Exception as e:
        log(f"TLS /definitions wyjątek: {e}")


def tls_fetch_members_for_list_ids(list_ids: Set[int]) -> Set[int]:
    """Zwraca zbiór TaxonId należących do dowolnej z list w list_ids."""
    if not list_ids:
        return set()

    try:
        payload = {
            "conservationListIds": sorted(list(list_ids)),
            "outputFields": ["id"],
        }
        r = requests.post(TLS_TAXA_URL, headers=HEADERS_LISTS, json=payload, timeout=TIMEOUT)

        if r.status_code != 200 or not r.content:
            log(f"TLS /taxa {r.status_code} — {r.text[:200]!r}")
            return set()

        data = json_safe(r)
        members: Set[int] = set()

        def walk(x: Any) -> None:
            if isinstance(x, dict):
                if "id" in x and isinstance(x.get("id"), int):
                    members.add(int(x["id"]))
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for it in x:
                    walk(it)

        walk(data)

        if is_debug():
            if members:
                preview = ", ".join(str(i) for i in sorted(list(members))[:12])
                log(f" ↳ członków: {len(members)} (przykład: {preview})")
            else:
                log(" ↳ członków: 0")

        return members

    except Exception as e:
        log(f"TLS /taxa wyjątek: {e}")
        return set()


def tls_build_memberships() -> None:
    """Buduje _TLS_MEMBERS: nazwa-kategorii → zbiór TaxonId."""
    global _TLS_MEMBERS

    _TLS_MEMBERS = {}
    for cat, ids in _TLS_CATSETS.items():
        mem = tls_fetch_members_for_list_ids(ids)
        _TLS_MEMBERS[cat] = mem
        log(f"TLS /taxa: {cat} — {len(mem)} taxa")


def tls_is_ready() -> bool:
    return _TLS_DEFS_READY and bool(_TLS_MEMBERS)


def tls_definitions_ready() -> bool:
    return _TLS_DEFS_READY


def tls_flags_by_membership(tid: int) -> Dict[str, str]:
    def hit(cat: str) -> str:
        return "Ja" if tid in _TLS_MEMBERS.get(cat, set()) else ""

    return {
        "CITES": hit("CITES"),
        "Bernkonventionen": hit("Bernkonventionen"),
        "Bonnkonventionen": hit("Bonnkonventionen"),
        "FågeldirektivetBilaga1": hit("FågeldirektivetBilaga1"),
        "PrioriteradeFågelarterSkogsvårdslagen": hit("PrioriteradeFågelarterSkogsvårdslagen"),
        "Fridlyst": hit("Fridlyst"),
        "DirectiveAppendix2": hit("Habitat_Bilaga2"),
        "DirectiveAppendix2Priority": hit("Habitat_Bilaga2_Prio"),
        "DirectiveAppendix4": hit("Habitat_Bilaga4"),
        "DirectiveAppendix5": hit("Habitat_Bilaga5"),
        "IAS_Union_EU": hit("IAS_Union_EU"),
    }
