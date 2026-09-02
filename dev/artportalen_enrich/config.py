# -*- coding: utf-8 -*-
"""Konfiguracja, ścieżki, endpointy i klucze API."""

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR = os.path.dirname(PACKAGE_DIR)   # np. .../dev albo .../prod
REPO_ROOT = os.path.dirname(SCRIPT_DIR)     # katalog główny repozytorium
SECRETS_DIR = os.path.join(REPO_ROOT, "secrets")


def load_secret(filename: str, env_var: str = "", required: bool = False) -> str:
    """
    Wczytuje token API ze zmiennej środowiskowej lub pliku w katalogu secrets/.
    """
    if env_var:
        env_val = os.getenv(env_var, "").strip()
        if env_val:
            return env_val

    path = os.path.join(SECRETS_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                return token
        except Exception:
            pass

    if required:
        raise FileNotFoundError(
            f"Brak klucza API (zmienna {env_var} lub plik {filename}).\n"
            f"Oczekiwana lokalizacja pliku: {path}\n"
            f"Utwórz folder 'secrets' w katalogu głównym repozytorium i dodaj tam plik {filename}."
        )

    return ""


TAXONOMY_KEY = load_secret("taxonomykey.txt", env_var="TAXONOMY_KEY")
SPECIES_KEY = load_secret("specieskey.txt", env_var="SPECIES_KEY")
LISTS_KEY = load_secret("listskey.txt", env_var="LISTS_KEY")

NAME_QUERY_SLEEP = 0.08
SPECIES_SLEEP = 0.08
TIMEOUT = 30

TAXON_NAME_URL = "https://api.artdatabanken.se/taxonservice/v1/taxa/names"
SPECIES_URL = "https://api.artdatabanken.se/information/v1/speciesdataservice/v1/speciesdata"

TLS_BASE = os.getenv("TLS_BASE", "https://api.artdatabanken.se/taxonlistservice/v1")
TLS_DEFS_URL = f"{TLS_BASE}/definitions"
TLS_TAXA_URL = f"{TLS_BASE}/taxa"

HEADERS_TAXON = {
    "Ocp-Apim-Subscription-Key": TAXONOMY_KEY,
    "Accept": "application/json",
}
HEADERS_SPECIES = {
    "Ocp-Apim-Subscription-Key": SPECIES_KEY,
    "Accept": "application/json",
    "Cache-Control": "no-cache",
}
HEADERS_LISTS = {
    "Ocp-Apim-Subscription-Key": LISTS_KEY,
    "Accept": "application/json",
}

RL_ORDER = {"RE": 0, "CR": 1, "EN": 2, "VU": 3, "NT": 4, "LC": 5, "DD": 6, "NA": 7, "NE": 8}
