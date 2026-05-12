# -*- coding: utf-8 -*-
"""Tkinter UI: val av inputfil, outputmapp, exportprofil och körningslägen."""

import os
import sys
from typing import Any, Dict

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText

from .export_presets import (
    EXTERNAL_PRESETS_DIR,
    get_default_preset_id,
    get_preset,
    list_presets,
    preset_summary_text,
    save_preset_copy,
)


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


def _show_preset_preview(root: tk.Tk, preset_id: str) -> None:
    """Visar en läsbar förhandsvisning av vald exportprofil."""
    win = tk.Toplevel(root)
    win.title("Podgląd / förhandsvisning presetu")
    win.geometry("760x620")
    win.minsize(640, 420)

    frame = tk.Frame(win, padx=12, pady=12)
    frame.pack(fill="both", expand=True)

    text = ScrolledText(frame, wrap="word", width=90, height=32)
    text.pack(fill="both", expand=True)
    text.insert("1.0", preset_summary_text(preset_id))
    text.configure(state="disabled")

    buttons = tk.Frame(frame)
    buttons.pack(fill="x", pady=(10, 0))
    tk.Button(buttons, text="OK", command=win.destroy, width=12).pack(side="right")

    _center_window(win)
    _bring_to_front(win)
    win.grab_set()
    root.wait_window(win)


def _choose_export_preset(root: tk.Tk) -> str:
    """Visar dialog för val, preview och sparande av exportprofil."""
    default_id = get_default_preset_id()
    selected = tk.StringVar(master=root, value=default_id)
    description_var = tk.StringVar(master=root, value=get_preset(default_id).description)
    folder_var = tk.StringVar(master=root, value=f"Presetfolder: {EXTERNAL_PRESETS_DIR}")
    result = {"preset_id": default_id}

    dialog = tk.Toplevel(root)
    dialog.title("Välj exportprofil")
    dialog.geometry("760x560")
    dialog.minsize(680, 500)

    # Viktigt: använd inte enbart transient(root) när root är withdraw(),
    # eftersom dialogen då kan hamna bakom andra fönster i Windows.
    dialog.grab_set()

    outer = tk.Frame(dialog, padx=14, pady=12)
    outer.pack(fill="both", expand=True)

    title = tk.Label(
        outer,
        text=(
            "Välj vilka kolumner som ska skrivas till _with_data och _bara_skyddade. "
            "Egna JSON-presets läses från dev/export_presets eller prod/export_presets, "
            "beroende på vilken version som körs."
        ),
        justify="left",
        anchor="w",
        wraplength=710,
    )
    title.pack(fill="x", pady=(0, 8))

    folder_label = tk.Label(
        outer,
        textvariable=folder_var,
        justify="left",
        anchor="w",
        wraplength=710,
        fg="#555555",
    )
    folder_label.pack(fill="x", pady=(0, 8))

    preset_frame = tk.Frame(outer, relief="groove", bd=1, padx=8, pady=6)
    preset_frame.pack(fill="both", expand=True)

    def update_description() -> None:
        description_var.set(get_preset(selected.get()).description)

    def rebuild_preset_buttons() -> None:
        for child in preset_frame.winfo_children():
            child.destroy()

        presets = list_presets()
        available_ids = {p.preset_id for p in presets}
        if selected.get() not in available_ids:
            selected.set(default_id)

        for preset in presets:
            source_suffix = ""
            if preset.source == "json":
                source_suffix = "  [JSON]"
            rb = tk.Radiobutton(
                preset_frame,
                text=f"{preset.label}{source_suffix}",
                variable=selected,
                value=preset.preset_id,
                command=update_description,
                anchor="w",
                justify="left",
                wraplength=690,
            )
            rb.pack(fill="x", anchor="w")
        update_description()

    rebuild_preset_buttons()

    desc = tk.Label(
        outer,
        textvariable=description_var,
        justify="left",
        anchor="w",
        wraplength=710,
        relief="groove",
        padx=8,
        pady=6,
    )
    desc.pack(fill="x", pady=(10, 8))

    tool_buttons = tk.Frame(outer)
    tool_buttons.pack(fill="x", pady=(0, 10))

    def preview() -> None:
        _show_preset_preview(root, selected.get())

    def save_copy() -> None:
        current = get_preset(selected.get())
        name = simpledialog.askstring(
            "Spara egen preset",
            "Namn för ny preset JSON:\n\n"
            "Preset sparas i dev/export_presets eller prod/export_presets beroende på var skrypt startas.",
            initialvalue=f"Kopia av {current.label}",
            parent=dialog,
        )
        if not name:
            return
        try:
            new_id, path = save_preset_copy(selected.get(), name)
            selected.set(new_id)
            rebuild_preset_buttons()
            messagebox.showinfo(
                "Preset sparad",
                f"Preset zapisany jako JSON:\n\n{path}\n\nMożesz edytować ten plik ręcznie i uruchomić skrypt ponownie.",
                parent=dialog,
            )
        except Exception as e:
            messagebox.showerror("Błąd zapisu presetu", str(e), parent=dialog)

    tk.Button(tool_buttons, text="Podgląd presetu", command=preview, width=18).pack(side="left")
    tk.Button(tool_buttons, text="Zapisz kopię jako JSON", command=save_copy, width=24).pack(side="left", padx=(8, 0))

    buttons = tk.Frame(outer)
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
