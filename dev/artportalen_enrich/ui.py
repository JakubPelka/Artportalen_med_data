# -*- coding: utf-8 -*-
"""Tkinter UI: val av inputfil, outputmapp och körningslägen."""

import os
import sys
from typing import Any, Dict

import tkinter as tk
from tkinter import filedialog, messagebox


def pick_inputs() -> Dict[str, Any]:
    root = tk.Tk()
    root.withdraw()

    infile = filedialog.askopenfilename(
        title="Wybierz plik Excel z Artportalen",
        filetypes=[("Excel", "*.xlsx;*.xls"), ("Wszystkie pliki", "*.*")],
    )
    if not infile:
        sys.exit("Przerwano: nie wybrano pliku wejściowego.")

    outdir = filedialog.askdirectory(title="Wybierz folder zapisu wyników")
    if not outdir:
        outdir = os.path.dirname(infile)

    base = os.path.splitext(os.path.basename(infile))[0]

    want_full = messagebox.askyesno(
        "Dodatkowy plik?",
        "Czy wygenerować DODATKOWO pełną tabelę BEZ usuwania duplikatów (full_)?",
    )

    want_debug = messagebox.askyesno(
        "Tryb debug?",
        "Włączyć DEBUG (szerszy log + tls_debug.csv)?",
    )

    return {
        "INPUT_FILE": infile,
        "OUTDIR": outdir,
        "OUT_FULL": os.path.join(outdir, f"{base}_full_.xlsx"),
        "OUT_WITH": os.path.join(outdir, f"{base}_with_data.xlsx"),
        "OUT_PROT": os.path.join(outdir, f"{base}_bara_skyddade.xlsx"),
        "LOG_FILE": os.path.join(outdir, f"{base}_log.txt"),
        "DBG_FILE": os.path.join(outdir, "tls_debug.csv"),
        "WANT_FULL": want_full,
        "DEBUG": want_debug,
    }
