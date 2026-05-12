# -*- coding: utf-8 -*-
"""Loggning och debug-buffert."""

from datetime import datetime
from typing import Any, Dict, List, Optional

LOG_FILE: Optional[str] = None
DEBUG: bool = False
DEBUG_ROWS: List[Dict[str, Any]] = []


def configure_logging(log_file: str, debug: bool) -> None:
    global LOG_FILE, DEBUG, DEBUG_ROWS
    LOG_FILE = log_file
    DEBUG = bool(debug)
    DEBUG_ROWS = []


def is_debug() -> bool:
    return DEBUG


def add_debug_row(row: Dict[str, Any]) -> None:
    DEBUG_ROWS.append(row)


def get_debug_rows() -> List[Dict[str, Any]]:
    return DEBUG_ROWS


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)

    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(line + "\n")
        except Exception:
            pass
