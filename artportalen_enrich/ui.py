# -*- coding: utf-8 -*-
"""
Nowoczesne jednoramkowe GUI (Tkinter/ttk) dla Artportalen_med_data (Issue #9).

Główne cechy:
- Pojedyncze, przejrzyste okno ze wszystkimi opcjami (brak irytujących serii popupów).
- Dedykowany worker thread chroniący interfejs przed zawieszaniem.
- Pasek postępu, status operacji i przewijana konsola logów na żywo.
- Obsługa bezpiecznego anulowania (Cancel) bez uszkadzania plików.
- Pełna integracja z presetami i edytorem JSON.
"""

import os
import queue
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .config import DEFAULT_MAX_WORKERS, REPO_ROOT
from .export_presets import (
    EXTERNAL_PRESETS_DIR,
    get_default_preset_id,
    get_known_export_columns,
    get_preset,
    list_presets,
    preset_summary_text,
    save_custom_preset,
)
from .logger_utils import add_log_listener, remove_log_listener


def _center_window(win: tk.Toplevel, width: int = 760, height: int = 600) -> None:
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(40, (sw - width) // 2)
    y = max(40, (sh - height) // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")


def _show_preset_preview(parent: tk.Misc, preset_id: str) -> None:
    win = tk.Toplevel(parent)
    win.title(f"Podgląd profilu eksportu: {preset_id}")
    win.geometry("700x520")
    win.minsize(560, 360)
    win.grab_set()

    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)

    text = ScrolledText(outer, wrap="word", height=20, font=("TkFixedFont", 10))
    text.pack(fill="both", expand=True, pady=(0, 10))
    text.insert("1.0", preset_summary_text(preset_id))
    text.configure(state="disabled")

    btn = ttk.Button(outer, text="Zamknij", command=win.destroy, width=14)
    btn.pack(side="right")

    _center_window(win, 700, 520)


def _show_preset_editor(parent: tk.Misc, preset_id: str) -> Optional[str]:
    """Edytor profilu eksportu z możliwością tworzenia własnych konfiguracji kolumn."""
    base = get_preset(preset_id)
    saved_preset_id = [None]

    win = tk.Toplevel(parent)
    win.title(f"Edytuj profil: {base.label}")
    win.geometry("860x680")
    win.minsize(700, 500)
    win.grab_set()

    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)

    header = ttk.Label(
        outer,
        text="Utwórz lub zmodyfikuj niestandardowy profil eksportu JSON.",
        font=("TkDefaultFont", 10, "bold"),
    )
    header.pack(fill="x", pady=(0, 6))

    meta_frame = ttk.Frame(outer)
    meta_frame.pack(fill="x", pady=(0, 10))

    ttk.Label(meta_frame, text="Nazwa profilu:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
    label_var = tk.StringVar(value=f"{base.label} (Własny)")
    ttk.Entry(meta_frame, textvariable=label_var, width=40).grid(row=0, column=1, sticky="w", padx=4, pady=2)

    ttk.Label(meta_frame, text="ID profilu:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
    id_var = tk.StringVar(value=f"{base.preset_id}_custom")
    ttk.Entry(meta_frame, textvariable=id_var, width=40).grid(row=1, column=1, sticky="w", padx=4, pady=2)

    ttk.Label(meta_frame, text="Opis:").grid(row=2, column=0, sticky="w", padx=4, pady=2)
    desc_var = tk.StringVar(value=base.description)
    ttk.Entry(meta_frame, textvariable=desc_var, width=40).grid(row=2, column=1, sticky="w", padx=4, pady=2)

    # Kolumny
    cols_frame = ttk.LabelFrame(outer, text="Wybór kolumn wzbogacenia", padding=8)
    cols_frame.pack(fill="both", expand=True, pady=(0, 10))

    cols_canvas = tk.Canvas(cols_frame, highlightthickness=0)
    scrollbar = ttk.Scrollbar(cols_frame, orient="vertical", command=cols_canvas.yview)
    scroll_frame = ttk.Frame(cols_canvas)

    scroll_frame.bind("<Configure>", lambda e: cols_canvas.configure(scrollregion=cols_canvas.bbox("all")))
    cols_canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    cols_canvas.configure(yscrollcommand=scrollbar.set)

    cols_canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    all_cols = get_known_export_columns()
    col_vars: Dict[str, tk.BooleanVar] = {}

    for i, col in enumerate(all_cols):
        var = tk.BooleanVar(value=base.include_all_columns or (col in base.enrichment_columns))
        col_vars[col] = var
        r = i // 2
        c = i % 2
        cb = ttk.Checkbutton(scroll_frame, text=col, variable=var)
        cb.grid(row=r, column=c, sticky="w", padx=10, pady=2)

    def on_save():
        new_id = id_var.get().strip().lower()
        new_label = label_var.get().strip()
        new_desc = desc_var.get().strip()
        if not new_id or not new_label:
            messagebox.showerror("Błąd", "ID i Nazwa profilu nie mogą być puste.", parent=win)
            return

        selected_cols = [col for col, v in col_vars.items() if v.get()]
        if not selected_cols:
            messagebox.showerror("Błąd", "Wybierz co najmniej jedną kolumnę.", parent=win)
            return

        try:
            save_custom_preset(
                preset_id=new_id,
                label=new_label,
                description=new_desc,
                enrichment_columns=tuple(selected_cols),
                include_all_columns=False,
                include_current_protection_filter=base.include_current_protection_filter,
                include_redlist_filter=base.include_redlist_filter,
                redlist_categories=base.redlist_categories,
            )
            saved_preset_id[0] = new_id
            messagebox.showinfo("Sukces", f"Zapisano profil '{new_label}' w {EXTERNAL_PRESETS_DIR}", parent=win)
            win.destroy()
        except Exception as e:
            messagebox.showerror("Błąd zapisu", str(e), parent=win)

    btn_bar = ttk.Frame(outer)
    btn_bar.pack(fill="x")
    ttk.Button(btn_bar, text="Zapisz profil", command=on_save, width=15).pack(side="left")
    ttk.Button(btn_bar, text="Anuluj", command=win.destroy, width=12).pack(side="right")

    _center_window(win, 860, 680)
    parent.wait_window(win)
    return saved_preset_id[0]


class ArtportalenGui:
    """Jedno, nowoczesne okno robocze aplikacji."""

    def __init__(self, root: tk.Tk, run_fn: Optional[Callable[..., Any]] = None):
        self.root = root
        self.run_fn = run_fn
        self.root.title("Artportalen & AGOL Data Enricher (Facelift 2026)")
        self.root.geometry("860x780")
        self.root.minsize(760, 620)

        self.log_queue: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None

        self._init_variables()
        self._build_ui()
        self._setup_logging()
        self._start_queue_listener()

    def _init_variables(self) -> None:
        self.input_file_var = tk.StringVar(value="")
        self.output_dir_var = tk.StringVar(value=os.path.join(REPO_ROOT, "results"))
        self.source_type_var = tk.StringVar(value=os.getenv("ARTPORTALEN_DEFAULT_INPUT_SOURCE", "auto"))

        default_preset = get_default_preset_id()
        self.preset_var = tk.StringVar(value=default_preset)

        self.want_full_var = tk.BooleanVar(value=True)
        self.debug_var = tk.BooleanVar(value=False)
        self.refresh_cache_var = tk.BooleanVar(value=False)
        self.workers_var = tk.IntVar(value=DEFAULT_MAX_WORKERS)

        self.status_var = tk.StringVar(value="Gotowy do pracy. Wybierz plik wejściowy i kliknij 'Uruchom'.")
        self.progress_var = tk.DoubleVar(value=0.0)

    def _build_ui(self) -> None:
        main_container = ttk.Frame(self.root, padding=14)
        main_container.pack(fill="both", expand=True)

        # 1. Nagłówek
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header_frame,
            text="Artportalen & AGOL Data Enricher",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header_frame,
            text="Automatyczne wzbogacanie obserwacji przyrodniczych o statusy ochrony, czerwoną listę i konwencje.",
            font=("TkDefaultFont", 9),
        ).pack(anchor="w")

        # 2. Pliki i ścieżki
        files_frame = ttk.LabelFrame(main_container, text="Pliki i katalogi", padding=10)
        files_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(files_frame, text="Plik wejściowy:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(files_frame, textvariable=self.input_file_var, width=54).grid(row=0, column=1, sticky="we", padx=4, pady=4)
        ttk.Button(files_frame, text="Przeglądaj...", command=self._browse_input).grid(row=0, column=2, padx=4, pady=4)

        ttk.Label(files_frame, text="Folder wyjściowy:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(files_frame, textvariable=self.output_dir_var, width=54).grid(row=1, column=1, sticky="we", padx=4, pady=4)
        ttk.Button(files_frame, text="Wybierz folder...", command=self._browse_output).grid(row=1, column=2, padx=4, pady=4)
        files_frame.columnconfigure(1, weight=1)

        # 3. Konfiguracja i profil eksportu
        config_frame = ttk.LabelFrame(main_container, text="Konfiguracja eksportu", padding=10)
        config_frame.pack(fill="x", pady=(0, 10))

        # Typ wejścia
        source_frame = ttk.Frame(config_frame)
        source_frame.pack(fill="x", pady=(0, 6))
        ttk.Label(source_frame, text="Format danych:").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(source_frame, text="Auto-detect", variable=self.source_type_var, value="auto").pack(side="left", padx=6)
        ttk.Radiobutton(source_frame, text="Artportalen", variable=self.source_type_var, value="artportalen").pack(side="left", padx=6)
        ttk.Radiobutton(source_frame, text="AGOL / generic", variable=self.source_type_var, value="agol").pack(side="left", padx=6)

        # Preset
        preset_row = ttk.Frame(config_frame)
        preset_row.pack(fill="x", pady=(0, 8))
        ttk.Label(preset_row, text="Profil eksportu:").pack(side="left", padx=(0, 10))

        self.preset_combo = ttk.Combobox(
            preset_row,
            textvariable=self.preset_var,
            state="readonly",
            width=32,
        )
        self._refresh_presets_list()
        self.preset_combo.pack(side="left", padx=(0, 8))

        ttk.Button(preset_row, text="Podgląd", command=self._preview_preset, width=10).pack(side="left", padx=4)
        ttk.Button(preset_row, text="Nowy / Edytor", command=self._edit_preset, width=14).pack(side="left", padx=4)

        # Opcje
        opts_frame = ttk.Frame(config_frame)
        opts_frame.pack(fill="x")
        ttk.Checkbutton(opts_frame, text="Pełny eksport (*_full_enriched.xlsx)", variable=self.want_full_var).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(opts_frame, text="Odśwież cache API", variable=self.refresh_cache_var).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(opts_frame, text="Debug CSV", variable=self.debug_var).pack(side="left", padx=(0, 12))

        ttk.Label(opts_frame, text="Wątki:").pack(side="left", padx=(10, 4))
        workers_combo = ttk.Combobox(
            opts_frame,
            textvariable=self.workers_var,
            values=[1, 2, 4, 8],
            width=4,
            state="readonly",
        )
        workers_combo.pack(side="left")

        # 4. Pasek postępu i status
        prog_frame = ttk.LabelFrame(main_container, text="Stan operacji", padding=10)
        prog_frame.pack(fill="x", pady=(0, 10))

        self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100.0)
        self.progress_bar.pack(fill="x", pady=(0, 4))

        self.status_label = ttk.Label(prog_frame, textvariable=self.status_var, font=("TkDefaultFont", 9))
        self.status_label.pack(anchor="w")

        # 5. Konsola logów
        log_frame = ttk.LabelFrame(main_container, text="Dziennik zdarzeń (Log)", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.log_text = ScrolledText(log_frame, wrap="char", height=12, font=("TkFixedFont", 9))
        self.log_text.pack(fill="both", expand=True)

        # 6. Przyciski akcji
        action_frame = ttk.Frame(main_container)
        action_frame.pack(fill="x")

        self.btn_run = ttk.Button(action_frame, text="Uruchom wzbogacanie", command=self._start_enrichment, width=22)
        self.btn_run.pack(side="left", padx=(0, 8))

        self.btn_cancel = ttk.Button(action_frame, text="Anuluj", command=self._cancel_enrichment, state="disabled", width=12)
        self.btn_cancel.pack(side="left", padx=(0, 8))

        ttk.Button(action_frame, text="Wyczyść log", command=self._clear_log, width=12).pack(side="left")
        ttk.Button(action_frame, text="Zamknij", command=self.root.destroy, width=12).pack(side="right")

    def _refresh_presets_list(self) -> None:
        presets = list_presets()
        preset_ids = [p.preset_id for p in presets]
        self.preset_combo["values"] = preset_ids
        if self.preset_var.get() not in preset_ids and preset_ids:
            self.preset_var.set(preset_ids[0])

    def _browse_input(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Wybierz plik z obserwacjami",
            filetypes=[
                ("Pliki Excel i CSV", "*.xlsx *.xls *.csv"),
                ("Skoroszyty Excel (*.xlsx)", "*.xlsx"),
                ("Starszy Excel (*.xls)", "*.xls"),
                ("Pliki CSV (*.csv)", "*.csv"),
                ("Wszystkie pliki", "*.*"),
            ],
        )
        if filename:
            self.input_file_var.set(filename)
            # Jeśli output_dir jest pusty, zaproponuj ten sam folder
            if not self.output_dir_var.get():
                self.output_dir_var.set(os.path.dirname(filename))

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, title="Wybierz folder wyjściowy")
        if folder:
            self.output_dir_var.set(folder)

    def _preview_preset(self) -> None:
        _show_preset_preview(self.root, self.preset_var.get())

    def _edit_preset(self) -> None:
        new_id = _show_preset_editor(self.root, self.preset_var.get())
        if new_id:
            self._refresh_presets_list()
            self.preset_var.set(new_id)

    def _setup_logging(self) -> None:
        add_log_listener(self.log_queue.put)

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def _start_queue_listener(self) -> None:
        try:
            while not self.log_queue.empty():
                msg = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
        except Exception:
            pass
        self.root.after(100, self._start_queue_listener)

    def _start_enrichment(self) -> None:
        input_file = self.input_file_var.get().strip()
        out_dir = self.output_dir_var.get().strip()

        if not input_file or not os.path.exists(input_file):
            messagebox.showerror("Błąd", "Wskaż poprawny, istniejący plik wejściowy.", parent=self.root)
            return

        if not out_dir:
            out_dir = os.path.dirname(input_file)
            self.output_dir_var.set(out_dir)

        os.makedirs(out_dir, exist_ok=True)

        # Generuj nazwy plików wyjściowych
        stem, _ = os.path.splitext(os.path.basename(input_file))
        paths = {
            "INPUT_FILE": input_file,
            "INPUT_SOURCE": self.source_type_var.get(),
            "EXPORT_PRESET": self.preset_var.get(),
            "OUTDIR": out_dir,
            "OUT_WITH": os.path.join(out_dir, f"{stem}_med_data.xlsx"),
            "OUT_FULL": os.path.join(out_dir, f"{stem}_full_enriched.xlsx"),
            "OUT_PROT": os.path.join(out_dir, f"{stem}_bara_skyddade.xlsx"),
            "OUT_ALIEN": os.path.join(out_dir, f"{stem}_frammande_invasiva.xlsx"),
            "LOG_FILE": os.path.join(out_dir, f"{stem}_enrich.log"),
            "DBG_FILE": os.path.join(out_dir, f"{stem}_debug.csv"),
            "WANT_FULL": self.want_full_var.get(),
            "DEBUG": self.debug_var.get(),
            "REFRESH_CACHE": self.refresh_cache_var.get(),
            "MAX_WORKERS": self.workers_var.get(),
        }

        self.cancel_event.clear()
        self.btn_run.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress_var.set(0.0)
        self.status_var.set("Uruchamianie procesu...")

        def _worker():
            try:
                if self.run_fn:
                    self.run_fn(
                        paths=paths,
                        progress_callback=self._update_progress,
                        cancel_event=self.cancel_event,
                    )
                else:
                    from .pipeline import run_pipeline
                    run_pipeline(
                        paths=paths,
                        progress_callback=self._update_progress,
                        cancel_event=self.cancel_event,
                    )
                self.root.after(0, self._on_success, paths["OUT_WITH"])
            except Exception as e:
                self.root.after(0, self._on_error, str(e))

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def _cancel_enrichment(self) -> None:
        self.cancel_event.set()
        self.status_var.set("Zażądano anulowania... Czekam na zakończenie wątków.")
        self.btn_cancel.configure(state="disabled")

    def _update_progress(self, current: int, total: int, message: str) -> None:
        pct = (current / max(1, total)) * 100.0
        self.root.after(0, lambda: self._apply_progress(pct, message))

    def _apply_progress(self, pct: float, message: str) -> None:
        self.progress_var.set(pct)
        self.status_var.set(f"[{int(pct)}%] {message}")

    def _on_success(self, output_file: str) -> None:
        self.btn_run.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.progress_var.set(100.0)
        self.status_var.set("Proces zakończony sukcesem!")
        messagebox.showinfo(
            "Sukces!",
            f"Wzbogacanie danych zakończone pomyślnie!\n\nWyniki zapisano w folderze:\n{os.path.dirname(output_file)}",
            parent=self.root,
        )

    def _on_error(self, err_msg: str) -> None:
        self.btn_run.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.status_var.set(f"Przerwano: {err_msg}")
        if "anulowana" in err_msg.lower():
            messagebox.showwarning("Anulowano", "Przetwarzanie zostało anulowane przez użytkownika.", parent=self.root)
        else:
            messagebox.showerror("Błąd", f"Wystąpił błąd podczas przetwarzania:\n{err_msg}", parent=self.root)


def launch_gui(run_fn: Optional[Callable[..., Any]] = None) -> None:
    root = tk.Tk()
    # Użyj nowoczesnego motywu ttk jeśli dostępny
    try:
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    app = ArtportalenGui(root, run_fn=run_fn)
    root.mainloop()
