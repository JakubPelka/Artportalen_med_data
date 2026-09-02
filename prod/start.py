#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROD launcher: cienki entrypoint delegujący do wspólnego pakietu artportalen_enrich."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from artportalen_enrich.pipeline import main

if __name__ == "__main__":
    main()
