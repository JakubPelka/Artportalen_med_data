# -*- coding: utf-8 -*-
"""Konfiguracja, ścieżki, endpointy i klucze API."""

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR = os.path.dirname(PACKAGE_DIR)   # np. .../dev albo .../prod
REPO_ROOT = os.path.dirname(SCRIPT_DIR)     # katalog główny repozytorium
SECRETS_DIR = os.path.join(REPO_ROOT, "secrets")


def load_secret(filename: str) -> str:
    """
    Wczytuje lokalny plik tekstowy z tokenem API.
    Plik powinien zawierać tylko sam token, bez cudzysłowów i bez dodatkowego opisu.
    """
    path = os.path.join(SECRETS_DIR, filename)

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Brak pliku z kluczem API: {filename}\n"
            f"Oczekiwana lokalizacja: {path}\n"
            f"Utwórz folder 'secrets' w katalogu głównym repozytorium i dodaj tam plik {filename}."
        )

    with open(path, "r", encoding="utf-8") as f:
        token = f.read().strip()

    if not token:
        raise ValueError(
            f"Plik {filename} istnieje, ale jest pusty.\n"
            f"Wpisz do niego sam token API."
        )

    return token


TAXONOMY_KEY = load_secret("taxonomykey.txt")
SPECIES_KEY = load_secret("specieskey.txt")
LISTS_KEY = load_secret("listskey.txt")

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
