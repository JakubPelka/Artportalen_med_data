# -*- coding: utf-8 -*-
"""Gemensamma hjälpfunktioner."""

import re
from typing import Any

import pandas as pd

from .logger_utils import log

_CLEAN_SCI_RE = re.compile(r"\b(sp\.|cf\.|aff\.|nr\.|gr\.)\b|[\?\(\)\[\]]", re.IGNORECASE)
_DEFUZZ_REPLACEMENTS = {"´": "'", "`": "'", "—": "-", "–": "-"}


def json_safe(resp: Any) -> Any:
    try:
        return resp.json()
    except Exception:
        url = getattr(resp, "url", "?")
        sc = getattr(resp, "status_code", "?")
        tb = getattr(resp, "text", "")
        log(f"‼ Nie-JSON z {url} [{sc}] — body: {tb[:200]!r}")
        return {}


def clean_scientific(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = _CLEAN_SCI_RE.sub("", (name or "").strip())
    return re.sub(r"\s+", " ", s)


def clean_swedish(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = (name or "").strip()
    for k, v in _DEFUZZ_REPLACEMENTS.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s)


def normkey(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "").strip()).lower()


def bool_to_ja(v: Any) -> str:
    if isinstance(v, bool):
        return "Ja" if v else ""
    s = str(v).strip().lower()
    if s in {"true", "1", "ja", "yes", "y"}:
        return "Ja"
    return ""


def is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    return str(value).strip() in {"", "0", "N/A", "Nej", "nej", "False", "false", "None", "nan"}
