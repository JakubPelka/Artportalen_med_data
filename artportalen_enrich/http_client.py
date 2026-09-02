# -*- coding: utf-8 -*-
"""Centralny klient HTTP: requests.Session, connection pooling, retry i exponential backoff."""

import time
from typing import Any, Dict, List, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import (
    HEADERS_LISTS,
    HEADERS_SPECIES,
    HEADERS_TAXON,
    TIMEOUT,
)
from .logger_utils import is_debug, log

# Przejściowe kody błędów kwalifikujące się do automatycznego ponowienia
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 0.5


class HttpClient:
    """Wspólny klient HTTP z obsługą puli połączeń i bezpiecznego retry."""

    def __init__(
        self,
        max_retries: int = MAX_RETRIES,
        backoff_factor: float = INITIAL_BACKOFF_SECONDS,
        pool_size: int = 20,
        timeout: int = TIMEOUT,
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.pool_size = pool_size
        self.timeout = timeout
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            adapter = HTTPAdapter(
                pool_connections=self.pool_size,
                pool_maxsize=self.pool_size,
                max_retries=0,  # Zarządzamy retry na poziomie aplikacji dla precyzyjnego logowania
            )
            self._session.mount("https://", adapter)
            self._session.mount("http://", adapter)
        return self._session

    def reset_session(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        """Wykonuje request z automatycznym ponawianiem przy błędach przejściowych."""
        req_timeout = timeout or self.timeout
        attempts = 0

        while True:
            attempts += 1
            try:
                resp = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout=req_timeout,
                )

                if resp.status_code in RETRYABLE_STATUS_CODES and attempts <= self.max_retries:
                    backoff = self.backoff_factor * (2 ** (attempts - 1))
                    log(
                        f"Ostrzeżenie: HTTP {resp.status_code} z {url} — ponawiam próbę "
                        f"{attempts}/{self.max_retries} za {backoff:.1f}s..."
                    )
                    time.sleep(backoff)
                    continue

                return resp

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                if attempts <= self.max_retries:
                    backoff = self.backoff_factor * (2 ** (attempts - 1))
                    log(
                        f"Ostrzeżenie: Błąd sieci ({type(exc).__name__}) przy {url} — "
                        f"ponawiam próbę {attempts}/{self.max_retries} za {backoff:.1f}s..."
                    )
                    time.sleep(backoff)
                    continue
                log(f"Błąd krytyczny sieci po {attempts} próbach z {url}: {exc}")
                raise

    def get(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        return self.request("GET", url, headers=headers, params=params, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        return self.request("POST", url, headers=headers, params=params, json=json, timeout=timeout)

    # Dedykowane metody serwisowe z poprawnymi nagłówkami:

    def get_taxonomy(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        return self.get(url, headers=HEADERS_TAXON, params=params)

    def get_species(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        return self.get(url, headers=HEADERS_SPECIES, params=params)

    def get_lists(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        return self.get(url, headers=HEADERS_LISTS, params=params)

    def post_lists(self, url: str, json_data: Optional[Any] = None) -> requests.Response:
        return self.post(url, headers=HEADERS_LISTS, json=json_data)


# Globalna instancja klienta do wspólnego użycia
default_client = HttpClient()
