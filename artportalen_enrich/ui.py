# -*- coding: utf-8 -*-
"""Tkinter UI: val av inputfil, outputmapp, exportprofil och körningslägen."""

import os
import sys
from typing import Any, Dict, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText

from .export_presets import (
    CORE_INPUT_COLUMNS,
    EXTERNAL_PRESETS_DIR,
    get_default_preset_id,
    get_known_export_columns,
    get_preset,
    list_presets,
    preset_summary_text,
    save_custom_preset,
    save_preset_copy,
)

REDLIST_CHOICES = ("RE", "CR", "EN", "VU", "NT", "DD", "LC", "NA", "NE")


def _center_window(win: tk.Toplevel, width: int = 760, height: int = 600) -> None:
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(40, (sw - width) // 2)
    y = max(40, (sh - height) // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")


def _bring_to_front(win: tk.Toplevel) -> None:
    try:
        win.lift()
        win.attributes("-topmost", True)
        win.after_idle(win.attributes, "-topmost", False)
        win.focus_force()
    except Exception:
        pass


def _show_preset_preview(root: tk.Tk, preset_id: str) -> None:
    win = tk.Toplevel(root)
    win.title(f"Podgląd profilu eksportu: {preset_id}")
    win.geometry("700x520")
    win.minsize(560, 360)
    win.grab_set()

    outer = tk.Frame(win, padx=12, pady=12)
    outer.pack(fill="both", expand=True)

    text = ScrolledText(outer, wrap="word", height=20)
    text.pack(fill="both", expand=True, pady=(0, 10))
    text.insert("1.0", preset_summary_text(preset_id))
    text.configure(state="disabled")

    btn = tk.Button(outer, text="Zamknij", command=win.destroy, width=14)
    btn.pack(side="right")

    _center_window(win, 700, 520)
    _bring_to_front(win)
    root.wait_window(win)


def _show_preset_editor(root: tk.Tk, preset_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Edytor profilu eksportu: pozwala włączyć/wyłączyć kolumny i filtry."""
    base = get_preset(preset_id)
    result: dict[str, str | None] = {"preset_id": None, "path": None}

    win = tk.Toplevel(root)
    win.title("Edytuj preset / skapa JSON-preset")
    win.geometry("900x720")
    win.minsize(760, 560)
    win.grab_set()

    outer = tk.Frame(win, padx=12, pady=10)
    outer.pack(fill="both", expand=True)

    info = tk.Label(
        outer,
        text=(
            "Edytujesz kopię aktualnego presetu. Po zapisie powstanie nowy plik JSON w "
            "dev/export_presets albo prod/export_presets. Kolejność kolumn jest stała, "
            "zgodna z kolejnością techniczną skryptu."
        ),
        justify="left",
        anchor="w",
        wraplength=850,
    )
    info.pack(fill="x", pady=(0, 8))

    meta_frame = tk.Frame(outer)
    meta_frame.pack(fill="x", pady=(0, 8))

    tk.Label(meta_frame, text="Nazwa presetu:", anchor="w").grid(row=0, column=0, sticky="w")
    label_var = tk.StringVar(master=win, value=f"Kopia av {base.label}")
    tk.Entry(meta_frame, textvariable=label_var, width=80).grid(row=0, column=1, sticky="ew", padx=(8, 0))
    meta_frame.columnconfigure(1, weight=1)

    tk.Label(outer, text="Opis:", anchor="w").pack(fill="x")
    desc = tk.Text(outer, height=4, wrap="word")
    desc.pack(fill="x", pady=(0, 8))
    desc.insert("1.0", base.description or "")

    options = tk.Frame(outer, relief="groove", bd=1, padx=8, pady=8)
    options.pack(fill="x", pady=(0, 8))

    include_all_var = tk.BooleanVar(master=win, value=bool(base.include_all_columns))
    include_original_var = tk.BooleanVar(master=win, value=bool(base.include_original_columns))
    include_current_var = tk.BooleanVar(master=win, value=bool(base.include_current_protection_filter))
    include_redlist_var = tk.BooleanVar(master=win, value=bool(base.include_redlist_filter))
    include_ias_var = tk.BooleanVar(master=win, value=bool(base.include_ias_union_eu_filter))

    tk.Checkbutton(options, text="Eksportuj wszystkie kolumny (ignoruje listę kolumn poniżej)", variable=include_all_var).grid(row=0, column=0, sticky="w", columnspan=3)
    tk.Checkbutton(options, text="Zachowaj oryginalne kolumny z Artportalen", variable=include_original_var).grid(row=1, column=0, sticky="w", columnspan=3)
    tk.Checkbutton(options, text="Filtr _bara_skyddade: obecne flagi ochronne/naturvårdsflaggor", variable=include_current_var).grid(row=2, column=0, sticky="w", columnspan=3)
    tk.Checkbutton(options, text="Filtr _bara_skyddade: rödlistning", variable=include_redlist_var).grid(row=3, column=0, sticky="w")
    tk.Checkbutton(options, text="Filtr _bara_skyddade: IAS_Union_EU", variable=include_ias_var).grid(row=4, column=0, sticky="w", columnspan=3)

    red_frame = tk.Frame(options)
    red_frame.grid(row=3, column=1, sticky="w", padx=(12, 0))
    red_vars: Dict[str, tk.BooleanVar] = {}
    selected_red = {str(x).upper() for x in base.redlist_categories}
    for i, cat in enumerate(REDLIST_CHOICES):
        var = tk.BooleanVar(master=win, value=cat in selected_red)
        red_vars[cat] = var
        tk.Checkbutton(red_frame, text=cat, variable=var).grid(row=0, column=i, sticky="w")

    columns_outer = tk.LabelFrame(outer, text="Kolumny w presecie", padx=8, pady=8)
    columns_outer.pack(fill="both", expand=True)

    column_buttons = tk.Frame(columns_outer)
    column_buttons.pack(fill="x", pady=(0, 6))

    canvas = tk.Canvas(columns_outer, highlightthickness=0)
    scrollbar = tk.Scrollbar(columns_outer, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas)

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    known_columns = get_known_export_columns()
    base_columns = set(base.enrichment_columns)
    if base.include_all_columns:
        base_columns = set(known_columns)

    col_vars: Dict[str, tk.BooleanVar] = {}
    for idx, col in enumerate(known_columns):
        var = tk.BooleanVar(master=win, value=col in base_columns)
        col_vars[col] = var
        r = idx // 2
        c = idx % 2
        tk.Checkbutton(scroll_frame, text=col, variable=var, anchor="w", justify="left").grid(row=r, column=c, sticky="w", padx=(0, 20), pady=1)

    def select_all_columns() -> None:
        for var in col_vars.values():
            var.set(True)

    def clear_columns() -> None:
        for var in col_vars.values():
            var.set(False)

    def select_invasive_columns() -> None:
        invasive_tokens = ("Frammande", "IAS_Union_EU", "Risklista", "AlienSpecies")
        for col, var in col_vars.items():
            if any(token in col for token in invasive_tokens) or col in {"TaxonId", "ScientificName", "SwedishName", "DisplayName", "Category"}:
                var.set(True)

    tk.Button(column_buttons, text="Välj alla kolumner", command=select_all_columns, width=18).pack(side="left")
    tk.Button(column_buttons, text="Avmarkera alla", command=clear_columns, width=16).pack(side="left", padx=(8, 0))
    tk.Button(column_buttons, text="Välj invasiva/främmande", command=select_invasive_columns, width=22).pack(side="left", padx=(8, 0))

    buttons = tk.Frame(outer)
    buttons.pack(fill="x", pady=(10, 0))

    def save() -> None:
        label = label_var.get().strip()
        if not label:
            messagebox.showerror("Brak nazwy", "Podaj nazwę presetu.", parent=win)
            return

        columns = [col for col, var in col_vars.items() if var.get()]
        red_categories = [cat for cat, var in red_vars.items() if var.get()]
        data = {
            "label": label,
            "description": desc.get("1.0", "end").strip(),
            "include_all_columns": bool(include_all_var.get()),
            "include_original_columns": bool(include_original_var.get()),
            "original_column_candidates": list(CORE_INPUT_COLUMNS),
            "enrichment_columns": columns,
            "filter": {
                "include_current_protection_filter": bool(include_current_var.get()),
                "include_redlist_filter": bool(include_redlist_var.get()),
                "redlist_categories": red_categories,
                "include_ias_union_eu_filter": bool(include_ias_var.get()),
            },
        }
        try:
            new_id, path = save_custom_preset(data)
            result["preset_id"] = new_id
            result["path"] = path
            messagebox.showinfo("Preset sparad", f"Preset zapisany jako JSON:\n\n{path}", parent=win)
            win.destroy()
        except Exception as e:
            messagebox.showerror("Błąd zapisu presetu", str(e), parent=win)

    def cancel() -> None:
        win.destroy()

    tk.Button(buttons, text="Zapisz jako nowy JSON", command=save, width=22).pack(side="right", padx=(8, 0))
    tk.Button(buttons, text="Anuluj", command=cancel, width=12).pack(side="right")

    _center_window(win)
    _bring_to_front(win)
    root.wait_window(win)
    return result["preset_id"], result["path"]


def _choose_export_preset(root: tk.Tk) -> str:
    """Visar dialog för val, preview, editor och sparande av exportprofil."""
    default_id = get_default_preset_id()
    selected = tk.StringVar(master=root, value=default_id)
    description_var = tk.StringVar(master=root, value=get_preset(default_id).description)
    folder_var = tk.StringVar(master=root, value=f"Presetfolder: {EXTERNAL_PRESETS_DIR}")
    result = {"preset_id": default_id}

    dialog = tk.Toplevel(root)
    dialog.title("Välj exportprofil")
    dialog.geometry("760x600")
    dialog.minsize(680, 520)

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

    def edit_preset() -> None:
        new_id, path = _show_preset_editor(root, selected.get())
        if new_id:
            selected.set(new_id)
            rebuild_preset_buttons()
            messagebox.showinfo(
                "Preset aktywny",
                f"Nowy preset został zapisany i wybrany:\n\n{path}",
                parent=dialog,
            )

    tk.Button(tool_buttons, text="Podgląd presetu", command=preview, width=18).pack(side="left")
    tk.Button(tool_buttons, text="Edytuj i zapisz JSON", command=edit_preset, width=22).pack(side="left", padx=(8, 0))
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



def _choose_input_source(root: tk.Tk) -> str:
    """Dialog wyboru typu wejścia: Auto, Artportalen albo AGOL."""
    default_source = os.getenv("ARTPORTALEN_DEFAULT_INPUT_SOURCE", "auto").strip().lower()
    if default_source not in {"auto", "artportalen", "agol"}:
        default_source = "auto"
    selected = tk.StringVar(master=root, value=default_source)
    result = {"source": default_source}

    dialog = tk.Toplevel(root)
    dialog.title("Välj datakälla / wybierz źródło danych")
    dialog.geometry("700x360")
    dialog.minsize(620, 320)
    dialog.grab_set()

    outer = tk.Frame(dialog, padx=14, pady=12)
    outer.pack(fill="both", expand=True)

    title = tk.Label(
        outer,
        text=(
            "Wybierz typ pliku wejściowego. Tryb Auto powinien rozpoznać typ po kolumnach, "
            "ale przy eksporcie z ArcGIS Online możesz jawnie wskazać AGOL."
        ),
        justify="left",
        anchor="w",
        wraplength=660,
    )
    title.pack(fill="x", pady=(0, 10))

    options = [
        (
            "auto",
            "Auto-detect",
            "Skrypt sam próbuje rozpoznać Artportalen albo AGOL/generic po kolumnach.",
        ),
        (
            "artportalen",
            "Artportalen export",
            "Dla oryginalnego eksportu Artportalen. Obsługuje dodatkowe wiersze opisowe przed nagłówkiem.",
        ),
        (
            "agol",
            "AGOL / ArcGIS Online export",
            "Dla pliku z AGOL. Nagłówek powinien być w pierwszym wierszu; TaxonId będzie dopasowany po nazwach, jeśli go brakuje.",
        ),
    ]

    for value, label, desc in options:
        frame = tk.Frame(outer, relief="groove", bd=1, padx=8, pady=6)
        frame.pack(fill="x", pady=4)
        rb = tk.Radiobutton(frame, text=label, variable=selected, value=value, anchor="w", justify="left")
        rb.pack(fill="x", anchor="w")
        tk.Label(frame, text=desc, justify="left", anchor="w", wraplength=630, fg="#555555").pack(fill="x", padx=(24, 0))

    buttons = tk.Frame(outer)
    buttons.pack(fill="x", pady=(10, 0))

    def ok() -> None:
        result["source"] = selected.get()
        dialog.destroy()

    def cancel() -> None:
        result["source"] = "auto"
        dialog.destroy()

    tk.Button(buttons, text="OK", command=ok, width=12).pack(side="right", padx=(6, 0))
    tk.Button(buttons, text="Auto / standard", command=cancel, width=18).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", cancel)
    _center_window(dialog)
    _bring_to_front(dialog)
    root.wait_window(dialog)
    return result["source"]


def pick_inputs() -> Dict[str, Any]:
    root = tk.Tk()
    root.withdraw()

    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    infile = filedialog.askopenfilename(
        parent=root,
        title="Wybierz plik wejściowy: Artportalen albo AGOL",
        filetypes=[("Excel/CSV", "*.xlsx;*.xls;*.csv;*.tsv"), ("Excel", "*.xlsx;*.xls"), ("CSV/TSV", "*.csv;*.tsv"), ("Wszystkie pliki", "*.*")],
    )
    if not infile:
        root.destroy()
        sys.exit("Przerwano: nie wybrano pliku wejściowego.")

    outdir = filedialog.askdirectory(parent=root, title="Wybierz folder zapisu wyników")
    if not outdir:
        outdir = os.path.dirname(infile)

    base = os.path.splitext(os.path.basename(infile))[0]

    input_source = _choose_input_source(root)

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
        "OUT_ALIEN": os.path.join(outdir, f"{base}_frammande_invasiva.xlsx"),
        "LOG_FILE": os.path.join(outdir, f"{base}_log.txt"),
        "DBG_FILE": os.path.join(outdir, "tls_debug.csv"),
        "INPUT_SOURCE": input_source,
        "WANT_FULL": want_full,
        "DEBUG": want_debug,
        "EXPORT_PRESET": export_preset,
    }
