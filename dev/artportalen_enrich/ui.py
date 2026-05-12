# -*- coding: utf-8 -*-
"""Tkinter UI: val av inputfil, outputmapp, exportprofil och körningslägen."""

import os
import sys
from typing import Any, Dict

import tkinter as tk
from tkinter import filedialog, messagebox

from .export_presets import get_default_preset_id, get_preset, list_presets


def _center_window(window: tk.Toplevel) -> None:
    """Placera ett Tkinter-fönster ungefär centralt på skärmen."""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"+{x}+{y}")


def _bring_to_front(window: tk.Toplevel) -> None:
    """
    Försök visa dialogen ovanpå andra fönster.

    Detta är viktigt på Windows, där en Toplevel-dialog som skapas från ett
    dolt root-fönster ibland hamnar bakom terminalen. Då ser programmet ut att
    ha hängt sig, trots att det bara väntar på dialogen.
    """
    try:
        window.lift()
        window.attributes("-topmost", True)
        window.after(500, lambda: window.attributes("-topmost", False))
        window.focus_force()
    except Exception:
        pass


def _choose_export_preset(root: tk.Tk) -> str:
    """Visar enkel dialog för val av exportprofil."""
    presets = list_presets()
    default_id = get_default_preset_id()
    selected = tk.StringVar(master=root, value=default_id)
    result = {"preset_id": default_id}

    dialog = tk.Toplevel(root)
    dialog.title("Välj exportprofil")
    dialog.resizable(False, False)

    # Viktigt: använd inte enbart transient(root) när root är withdraw(),
    # eftersom dialogen då kan hamna bakom andra fönster i Windows.
    dialog.grab_set()

    frame = tk.Frame(dialog, padx=14, pady=12)
    frame.pack(fill="both", expand=True)

    title = tk.Label(
        frame,
        text="Välj vilka kolumner som ska skrivas till _with_data och _bara_skyddade.",
        justify="left",
        anchor="w",
        wraplength=620,
    )
    title.pack(fill="x", pady=(0, 10))

    description_var = tk.StringVar(master=root, value=get_preset(default_id).description)

    def update_description() -> None:
        description_var.set(get_preset(selected.get()).description)

    for preset in presets:
        rb = tk.Radiobutton(
            frame,
            text=preset.label,
            variable=selected,
            value=preset.preset_id,
            command=update_description,
            anchor="w",
            justify="left",
            wraplength=620,
        )
        rb.pack(fill="x", anchor="w")

    desc = tk.Label(
        frame,
        textvariable=description_var,
        justify="left",
        anchor="w",
        wraplength=620,
        relief="groove",
        padx=8,
        pady=6,
    )
    desc.pack(fill="x", pady=(12, 12))

    buttons = tk.Frame(frame)
    buttons.pack(fill="x")

    def ok() -> None:
        result["preset_id"] = selected.get()
        dialog.destroy()

    def cancel() -> None:
        result["preset_id"] = default_id
        dialog.destroy()

    tk.Button(buttons, text="OK", command=ok, width=12).pack(side="right", padx=(6, 0))
    tk.Button(buttons, text="Avbryt / standard", command=cancel, width=18).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", cancel)
    _center_window(dialog)
    _bring_to_front(dialog)

    root.wait_window(dialog)
    return result["preset_id"]


def pick_inputs() -> Dict[str, Any]:
    root = tk.Tk()
    root.withdraw()

    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    infile = filedialog.askopenfilename(
        parent=root,
        title="Wybierz plik Excel z Artportalen",
        filetypes=[("Excel", "*.xlsx;*.xls"), ("Wszystkie pliki", "*.*")],
    )
    if not infile:
        root.destroy()
        sys.exit("Przerwano: nie wybrano pliku wejściowego.")

    outdir = filedialog.askdirectory(parent=root, title="Wybierz folder zapisu wyników")
    if not outdir:
        outdir = os.path.dirname(infile)

    base = os.path.splitext(os.path.basename(infile))[0]

    export_preset = _choose_export_preset(root)

    want_full = messagebox.askyesno(
        "Dodatkowy plik?",
        "Czy wygenerować DODATKOWO pełną tabelę BEZ usuwania duplikatów (full_)?",
        parent=root,
    )

    want_debug = messagebox.askyesno(
        "Tryb debug?",
        "Włączyć DEBUG (szerszy log + tls_debug.csv)?",
        parent=root,
    )

    try:
        root.attributes("-topmost", False)
    except Exception:
        pass

    root.destroy()

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
        "EXPORT_PRESET": export_preset,
    }
