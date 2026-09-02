# -*- coding: utf-8 -*-
"""Lokalny cache SQLite z kontrolą świeżości (Issue #7)."""

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from .config import REPO_ROOT
from .logger_utils import is_debug, log

CACHE_SCHEMA_VERSION = 1
DEFAULT_CACHE_DIR = os.path.join(REPO_ROOT, ".cache")
DEFAULT_CACHE_FILE = os.path.join(DEFAULT_CACHE_DIR, "artportalen_cache.sqlite")

# Domyślny czas życia cache (30 dni = 30 * 86400 sekund)
DEFAULT_TTL_SECONDS = 30 * 86400


class SqliteCache:
    """Wątkowo-bezpieczny lokalny cache SQLite dla odpowiedzi API."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        default_ttl: int = DEFAULT_TTL_SECONDS,
        enabled: Optional[bool] = None,
    ):
        if db_path is None:
            db_path = DEFAULT_CACHE_FILE
        self.db_path = os.path.abspath(db_path)
        self.default_ttl = default_ttl

        if enabled is not None:
            self._enabled = enabled
        else:
            self._enabled = os.getenv("ARTPORTALEN_DISABLE_CACHE", "0").strip().lower() not in {"1", "true", "yes"}

        self._ensure_db()

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _ensure_db(self) -> None:
        if not self._enabled:
            return
        try:
            parent_dir = os.path.dirname(self.db_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        cache_key TEXT PRIMARY KEY,
                        service TEXT NOT NULL,
                        identifier TEXT NOT NULL,
                        culture TEXT NOT NULL,
                        schema_version INTEGER NOT NULL,
                        data_json TEXT NOT NULL,
                        fetched_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cache_lookup
                    ON cache_entries (service, identifier, culture);
                """)

                # Sprawdź wersję schematu
                cur = conn.cursor()
                cur.execute("SELECT value FROM cache_meta WHERE key='schema_version'")
                row = cur.fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO cache_meta (key, value) VALUES ('schema_version', ?)",
                        (str(CACHE_SCHEMA_VERSION),),
                    )
                elif int(row[0]) != CACHE_SCHEMA_VERSION:
                    log(f"Zmieniła się wersja schematu cache ({row[0]} -> {CACHE_SCHEMA_VERSION}). Przebudowuję cache.")
                    conn.execute("DROP TABLE cache_entries")
                    conn.execute("""
                        CREATE TABLE cache_entries (
                            cache_key TEXT PRIMARY KEY,
                            service TEXT NOT NULL,
                            identifier TEXT NOT NULL,
                            culture TEXT NOT NULL,
                            schema_version INTEGER NOT NULL,
                            data_json TEXT NOT NULL,
                            fetched_at REAL NOT NULL,
                            expires_at REAL NOT NULL
                        );
                    """)
                    conn.execute(
                        "UPDATE cache_meta SET value=? WHERE key='schema_version'",
                        (str(CACHE_SCHEMA_VERSION),),
                    )
                conn.commit()
        except Exception as e:
            log(f"Ostrzeżenie: Inicjalizacja bazy cache SQLite nie powiodła się: {e}")

    @staticmethod
    def _make_key(service: str, identifier: str, culture: str) -> str:
        return f"{service}:{str(identifier).strip().lower()}:{culture.strip().lower()}:v{CACHE_SCHEMA_VERSION}"

    def get(
        self,
        service: str,
        identifier: Union[str, int],
        culture: str = "sv_SE",
        force_refresh: bool = False,
    ) -> Optional[Any]:
        """Pobiera dane z cache. Zwraca None w przypadku MISS, przeterminowania lub force_refresh."""
        if not self._enabled or force_refresh:
            if force_refresh and is_debug():
                log(f"[CACHE REFRESH] {service}:{identifier}")
            return None

        key = self._make_key(service, str(identifier), culture)
        now = time.time()

        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT data_json, expires_at FROM cache_entries WHERE cache_key = ?",
                    (key,),
                )
                row = cur.fetchone()
                if row is None:
                    if is_debug():
                        log(f"[CACHE MISS] {service}:{identifier}")
                    return None

                data_json, expires_at = row
                if expires_at > 0 and now > expires_at:
                    if is_debug():
                        log(f"[CACHE EXPIRED] {service}:{identifier}")
                    return None

                if is_debug():
                    log(f"[CACHE HIT] {service}:{identifier}")
                return json.loads(data_json)
        except Exception as e:
            log(f"Ostrzeżenie przy odczycie z cache SQLite ({key}): {e}")
            return None

    def set(
        self,
        service: str,
        identifier: Union[str, int],
        data: Any,
        culture: str = "sv_SE",
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Zapisuje dane w cache SQLite."""
        if not self._enabled:
            return

        key = self._make_key(service, str(identifier), culture)
        now = time.time()
        ttl = self.default_ttl if ttl_seconds is None else ttl_seconds
        expires_at = (now + ttl) if ttl > 0 else 0

        try:
            data_json = json.dumps(data, ensure_ascii=False)
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries
                    (cache_key, service, identifier, culture, schema_version, data_json, fetched_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        service,
                        str(identifier).strip().lower(),
                        culture.strip().lower(),
                        CACHE_SCHEMA_VERSION,
                        data_json,
                        now,
                        expires_at,
                    ),
                )
                conn.commit()
                if is_debug():
                    log(f"[CACHE SET] {service}:{identifier} (TTL={ttl}s)")
        except Exception as e:
            log(f"Ostrzeżenie przy zapisie do cache SQLite ({key}): {e}")

    def clear(self, service: Optional[str] = None) -> int:
        """Czyści cały cache lub wybrany serwis."""
        if not os.path.exists(self.db_path):
            return 0
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                if service:
                    cur.execute("DELETE FROM cache_entries WHERE service = ?", (service,))
                else:
                    cur.execute("DELETE FROM cache_entries")
                deleted = cur.rowcount
                conn.commit()
                log(f"Wyczyszczono cache ({deleted} wpisów).")
                return deleted
        except Exception as e:
            log(f"Błąd przy czyszczeniu cache: {e}")
            return 0

    def stats(self) -> Dict[str, Any]:
        """Zwraca statystyki wpisów w cache."""
        if not os.path.exists(self.db_path):
            return {"total": 0, "by_service": {}}
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT service, COUNT(*) FROM cache_entries GROUP BY service")
                by_service = {row[0]: row[1] for row in cur.fetchall()}
                total = sum(by_service.values())
                return {"total": total, "by_service": by_service}
        except Exception as e:
            log(f"Błąd odczytu statystyk cache: {e}")
            return {"total": 0, "by_service": {}}


# Globalna domyślna instancja cache
default_cache = SqliteCache()
