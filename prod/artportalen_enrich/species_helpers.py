# -*- coding: utf-8 -*-
"""Hjälpfunktioner för SpeciesDataService-strukturer."""

from typing import Any, List, Optional


def extract_child_names(childs: Any) -> List[str]:
    out = []
    for c in (childs or []):
        nm = c.get("name") if isinstance(c, dict) else None
        if nm:
            out.append(nm)
        if isinstance(c, dict) and c.get("childs"):
            out.extend(extract_child_names(c.get("childs")))
    return out


def any_child_named(lists: Any, target: str) -> str:
    def has_child_named(childs: Any, name: str) -> bool:
        for c in childs or []:
            if not isinstance(c, dict):
                continue
            if c.get("name", "") == name:
                return True
            if c.get("childs") and has_child_named(c["childs"], name):
                return True
        return False

    for it in lists or []:
        if isinstance(it, dict) and has_child_named(it.get("childs", []), target):
            return "Ja"
    return ""


def join_name_with_attr(items: Any, key: str, sub: Optional[str] = None, sep: str = ", ") -> str:
    if not items:
        return ""

    vals = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if not it.get(key):
            continue
        if sub:
            vals.append(f"{it.get(key, '')} ({it.get(sub, '')})")
        else:
            vals.append(str(it.get(key, "")))

    vals = sorted(set(v for v in vals if v))
    return sep.join(vals)


def join_typical_species(ts: Any) -> str:
    if not ts:
        return ""

    vals = []
    for t in ts:
        if not isinstance(t, dict):
            continue
        nm = t.get("typcial", "") or t.get("typical", "") or t.get("name", "")
        regs = ", ".join(t.get("regions", []) or [])
        if nm:
            vals.append(f"{nm}{' (' + regs + ')' if regs else ''}")

    return ", ".join(sorted(set(vals)))
