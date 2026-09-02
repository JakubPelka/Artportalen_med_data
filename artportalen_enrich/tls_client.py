# -*- coding: utf-8 -*-
"""TaxonListService: definitioner, medlemskap och skyddsflaggor."""

from typing import Any, Dict, Iterable, List, Optional, Set

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


def _ids_by_known_ids(known_ids: Iterable[int]) -> Set[int]:
    """Returnerar kända TLS-id:n som faktiskt finns i /definitions."""
    return {int(i) for i in known_ids if int(i) in _TLS_DEFS}


def _ids_by_contains_any(substrs: List[str]) -> Set[int]:
    out: Set[int] = set()
    normalized_substrs = [_norm(sub) for sub in substrs]
    for lid, name in _TLS_DEFS.items():
        n = _norm(name)
        if any(sub in n for sub in normalized_substrs):
            out.add(lid)
    return out


def _ids_by_required_groups(
    required_groups: List[List[str]],
    *,
    exclude: Optional[List[str]] = None,
    known_ids: Iterable[int] = (),
) -> Set[int]:
    """Hitta list-id:n där varje termgrupp matchas minst en gång.

    Exempel:
        required_groups=[['habitatdirektiv'], ['bilaga 2', 'annex 2']]

    Detta är striktare än tidigare lösning med bara 'bilaga 2', som riskerade
    att blanda ihop Habitatdirektivets bilaga 2 med Fågeldirektivets bilaga 2.
    """
    out: Set[int] = _ids_by_known_ids(known_ids)
    required = [[_norm(t) for t in group] for group in required_groups]
    excluded = [_norm(t) for t in (exclude or [])]

    for lid, name in _TLS_DEFS.items():
        n = _norm(name)
        if excluded and any(term in n for term in excluded):
            continue
        if all(any(term in n for term in group) for group in required):
            out.add(lid)
    return out


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

        _TLS_CATSETS = {
            "CITES": _ids_by_contains_any(["cites"]),
            "Bernkonventionen": _ids_by_contains_any(["bern"]),
            "Bonnkonventionen": _ids_by_contains_any(["bonn", "cms"]),
            "FågeldirektivetBilaga1": _ids_by_required_groups(
                [["fageldirektivet", "fågeldirektivet", "birds directive"], ["bilaga 1", "annex 1"]],
                known_ids=(46,),
            ),
            "FågeldirektivetBilaga2": _ids_by_required_groups(
                [["fageldirektivet", "fågeldirektivet", "birds directive"], ["bilaga 2", "annex 2"]],
                known_ids=(47,),
            ),
            "PrioriteradeFågelarterSkogsvårdslagen": _ids_by_required_groups(
                [["prioriterade", "priority"], ["fagel", "fågel", "birds"]],
                known_ids=(45,),
            ) | _ids_by_contains_any([
                "prioriterade fagelarter i skogsvardslagen",
                "prioriterade fågelarter i skogsvårdslagen",
                "skogsvardslagen",
                "skogsvårdslagen",
            ]),
            "Fridlyst": _ids_by_required_groups(
                [["fridlysta", "protected by law"]],
                known_ids=(34,),
            ),
            "Habitat_Bilaga2": _ids_by_required_groups(
                [["habitatdirektiv", "habitats directive"], ["bilaga 2", "annex 2"]],
                exclude=["fageldirektiv", "fågeldirektiv", "birds directive", "prioriterad", "priority"],
                known_ids=(9,),
            ),
            "Habitat_Bilaga2_Prio": _ids_by_required_groups(
                [["habitatdirektiv", "habitats directive"], ["bilaga 2", "annex 2"], ["prioriterad", "priority"]],
                exclude=["fageldirektiv", "fågeldirektiv", "birds directive"],
                known_ids=(10,),
            ),
            "Habitat_Bilaga4": _ids_by_required_groups(
                [["habitatdirektiv", "habitats directive"], ["bilaga 4", "annex 4"]],
                exclude=["fageldirektiv", "fågeldirektiv", "birds directive"],
                known_ids=(11,),
            ),
            "Habitat_Bilaga5": _ids_by_required_groups(
                [["habitatdirektiv", "habitats directive"], ["bilaga 5", "annex 5"]],
                exclude=["fageldirektiv", "fågeldirektiv", "birds directive"],
                known_ids=(12,),
            ),
            "Habitatdirektivet2023": _ids_by_required_groups(
                [["habitatdirektiv", "habitats directive"], ["2023"]],
                known_ids=(265,),
            ),
            "SkogsstyrelsensNaturvardsarter": _ids_by_required_groups(
                [["skogsstyrelsens", "swedish forest agency"], ["naturvardsarter", "naturvårdsarter", "nature conservation species"]],
                known_ids=(235,),
            ),
            "FrammandeArter": _ids_by_required_groups(
                [["frammande arter", "främmande arter", "alien species", "invasive species"]],
                known_ids=(35,),
            ),
            "FrammandeArterISverige": _ids_by_required_groups(
                [["frammande arter i sverige", "främmande arter i sverige", "invasive species in sweden", "alien species in sweden"]],
                known_ids=(36,),
            ),
            "IAS_Union_EU": _ids_by_required_groups(
                [["eu-forordning", "eu-förordning", "eu regulation", "1143", "unionsforteckning", "unionsförteckning", "union list"]],
                known_ids=(37,),
            ),
            "RisklistaFrammandeArter": _ids_by_required_groups(
                [["risklista", "risk assessment"]],
                known_ids=(38,),
            ),
            "Risklista_SE": _ids_by_required_groups(
                [["risklista", "risk assessment"], ["mycket hog risk", "mycket hög risk", "severe"]],
                known_ids=(39,),
            ),
            "Risklista_HI": _ids_by_required_groups(
                [["risklista", "risk assessment"], ["hog risk", "hög risk", "high"]],
                exclude=["potentiellt", "potentially", "mycket", "severe"],
                known_ids=(40,),
            ),
            "Risklista_PH": _ids_by_required_groups(
                [["risklista", "risk assessment"], ["potentiellt hog risk", "potentiellt hög risk", "potentially high"]],
                known_ids=(41,),
            ),
            "Risklista_LO": _ids_by_required_groups(
                [["risklista", "risk assessment"], ["lag risk", "låg risk", "low"]],
                known_ids=(42,),
            ),
            "Risklista_NK": _ids_by_required_groups(
                [["risklista", "risk assessment"], ["ingen kand risk", "ingen känd risk", "no known"]],
                known_ids=(43,),
            ),
        }

        _TLS_DEFS_READY = True

        if is_debug():
            for cat, ids in _TLS_CATSETS.items():
                sample = ", ".join(
                    [f"{i}:{_TLS_DEFS.get(i, '?')[:40]}" for i in list(sorted(ids))[:8]]
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
        "FågeldirektivetBilaga2": hit("FågeldirektivetBilaga2"),
        "PrioriteradeFågelarterSkogsvårdslagen": hit("PrioriteradeFågelarterSkogsvårdslagen"),
        "Fridlyst": hit("Fridlyst"),
        "DirectiveAppendix2": hit("Habitat_Bilaga2"),
        "DirectiveAppendix2Priority": hit("Habitat_Bilaga2_Prio"),
        "DirectiveAppendix4": hit("Habitat_Bilaga4"),
        "DirectiveAppendix5": hit("Habitat_Bilaga5"),
        "Habitatdirektivet2023": hit("Habitatdirektivet2023"),
        "SkogsstyrelsensNaturvardsarter": hit("SkogsstyrelsensNaturvardsarter"),
        "FrammandeArter": hit("FrammandeArter"),
        "FrammandeArterISverige": hit("FrammandeArterISverige"),
        "IAS_Union_EU": hit("IAS_Union_EU"),
        "RisklistaFrammandeArter": hit("RisklistaFrammandeArter"),
        "Risklista_SE": hit("Risklista_SE"),
        "Risklista_HI": hit("Risklista_HI"),
        "Risklista_PH": hit("Risklista_PH"),
        "Risklista_LO": hit("Risklista_LO"),
        "Risklista_NK": hit("Risklista_NK"),
    }
