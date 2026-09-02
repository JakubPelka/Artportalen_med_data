#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agol_DEV.py — Compatibility shim dla eksportów AGOL.

Automatycznie deleguje do zunifikowanego silnika artportalen_enrich z domyślnym
źródłem danych ustawionym na AGOL.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Wymuś domyślne źródło danych jako AGOL
os.environ["ARTPORTALEN_DEFAULT_INPUT_SOURCE"] = "agol"

from artportalen_enrich.pipeline import main

if __name__ == "__main__":
    main()
