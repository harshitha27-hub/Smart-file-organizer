"""
Organizer Page
==============
Lets the user pick a folder, run organization, monitor progress,
search/preview results, and undo the last move.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from modules.file_organizer import FileOrganizer, CATEGORIES
from modules.database import DatabaseManager
from modules.logger import AppLogger


def _fmt_size(b: int) -> str:
    if b >= 1_048_576:
        return f"{b/1_048_576:.1f} MB"
    if b >= 1024:
        return f"{b/1024:.1f} KB"
    return f"{b} B"


class OrganizerPage(ctk.CTkFrame):
    """Main file organization control panel."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.organizer  = FileOrganizer(
            progress_callback=self._on_progress,
            status_callback=self._on_status,
        )
        self.db  = DatabaseManager()
        self.log = AppLogger()
        self._folder   = tk.StringVar(value="")
        self._running  = False
        self._last_preds = None
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(self, text="File Organizer",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="#6C63FF").pack(anchor="w", pady=(0, 16))

        # ── Folder selection ─────────────────────────────────────────────────
        sel_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        sel_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(sel_frame, text="📂  Source Folder",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 6))

        row = ctk.CTkFrame(sel_frame, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 12))

        self._folder_entry = ctk.CTkEntry(row, textvariable=self._folder,
                                          placeholder_text="No folder selected…",
                                          height=38, corner_radius=10)
        self._folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(row, text="Browse", width=90, height=38,
                      corner_radius=10, fg_color="#6C63FF",
                      command=self._browse).pack(side="left")

        # ── Options ──────────────────────────────────────────────────────────
        opt_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        opt_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(opt_frame, text="⚙  Options",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 6))

        opts = ctk.CTkFrame(opt_frame, fg_color="transparent")
        opts.pack(fill="x", padx=14, pady=(0, 12))

        self._backup_var   = tk.BooleanVar(value=True)
        self._workers_var  = tk.IntVar(value=4)

        ctk.CTkSwitch(opts, text="Create Backup Before Organizing",
                      variable=self._backup_var,
                      button_color="#6C63FF").grid(row=0, column=0, sticky="w", padx=(0,24))

        ctk.CTkLabel(opts, text="Threads:").grid(row=0, column=1, sticky="w")
        ctk.CTkSlider(opts, from_=1, to=8, number_of_steps=7,
                      variable=self._workers_var, width=120,
                      button_color="#6C63FF").grid(row=0, column=2, padx=6)
        self._workers_lbl = ctk.CTkLabel(opts, text="4")
        self._workers_lbl.grid(row=0, column=3, sticky="w")
        self._workers_var.trace_add("write",
            lambda *_: self._workers_lbl.configure(text=str(self._workers_var.get())))

        # ── Action buttons ───────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 10))

        self._run_btn = ctk.CTkButton(btn_row, text="▶  Organize Files",
                                      height=42, corner_radius=12,
                                      fg_color="#6C63FF", hover_color="#5650CC",
                                      font=ctk.CTkFont(size=14, weight="bold"),
                                      command=self._start)
        self._run_btn.pack(side="left", padx=(0, 8))

        self._cancel_btn = ctk.CTkButton(btn_row, text="⏹  Cancel",
                                         height=42, corner_radius=12,
                                         fg_color="#FF6584", hover_color="#CC4466",
                                         command=self._cancel, state="disabled")
        self._cancel_btn.pack(side="left", padx=(0, 8))

        self._undo_btn = ctk.CTkButton(btn_row, text="↩  Undo Last Move",
                                       height=42, corner_radius=12,
                                       fg_color="#F7971E", hover_color="#CC7010",
                                       command=self._undo)
        self._undo_btn.pack(side="left")

        # ── Progress ─────────────────────────────────────────────────────────
        prog_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        prog_frame.pack(fill="x", pady=(0, 10))

        self._status_lbl = ctk.CTkLabel(prog_frame, text="Ready",
                                         font=ctk.CTkFont(size=12),
                                         text_color="#8888AA")
        self._status_lbl.pack(anchor="w", padx=14, pady=(10, 4))

        self._progress = ctk.CTkProgressBar(prog_frame, height=16,
                                             progress_color="#6C63FF",
                                             fg_color="#2A2A4A")
        self._progress.pack(fill="x", padx=14, pady=(0, 6))
        self._progress.set(0)

        self._prog_lbl = ctk.CTkLabel(prog_frame, text="0 / 0",
                                       font=ctk.CTkFont(size=11),
                                       text_color="#6888AA")
        self._prog_lbl.pack(anchor="e", padx=14, pady=(0, 10))

        # ── Category legend ──────────────────────────────────────────────────
        leg_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        leg_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(leg_frame, text="📋  Category Map",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 6))

        COLORS = ["#6C63FF","#43E97B","#FF6584","#F7971E",
                  "#12C2E9","#F64F59","#C471ED","#FFC107"]
        grid = ctk.CTkFrame(leg_frame, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0, 12))

        for i, (cat, exts) in enumerate(CATEGORIES.items()):
            row, col = divmod(i, 4)
            chip = ctk.CTkFrame(grid, fg_color="#0D0D1A", corner_radius=8)
            chip.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            grid.columnconfigure(col, weight=1)
            dot = "●"
            color = COLORS[i % len(COLORS)]
            ctk.CTkLabel(chip,
                         text=f"{dot}  {cat}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color).pack(anchor="w", padx=8, pady=(6, 2))
            ctk.CTkLabel(chip,
                         text=", ".join(exts[:6]) + ("…" if len(exts) > 6 else ""),
                         font=ctk.CTkFont(size=10),
                         text_color="#888899",
                         wraplength=180).pack(anchor="w", padx=8, pady=(0, 6))

        # ── Log output ───────────────────────────────────────────────────────
        log_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        log_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(log_frame, text="📝  Activity Log",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 4))

        self._log_box = ctk.CTkTextbox(log_frame, fg_color="#0D0D1A",
                                        text_color="#A0C0D0",
                                        font=ctk.CTkFont(family="Consolas", size=11),
                                        height=160, corner_radius=8)
        self._log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _browse(self):
        folder = filedialog.askdirectory(title="Select Folder to Organize")
        if folder:
            self._folder.set(folder)

    def _start(self):
        folder = self._folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Please select a valid folder.")
            return

        self._running = True
        self._run_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._progress.set(0)
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")

        def _worker():
            try:
                summary = self.organizer.organize(
                    folder,
                    backup=self._backup_var.get(),
                    max_workers=self._workers_var.get(),
                )
                msg = (f"✅  Done — Moved: {summary['moved']}  |  "
                       f"Skipped: {summary['skipped']}  |  "
                       f"Errors: {summary['errors']}")
                self.after(0, self._append_log, msg)
            except Exception as exc:
                self.after(0, self._append_log, f"❌  Error: {exc}")
            finally:
                self.after(0, self._finish)

        threading.Thread(target=_worker, daemon=True).start()

    def _cancel(self):
        self.organizer.cancel()
        self._on_status("Cancelling…")

    def _finish(self):
        self._running = False
        self._run_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._progress.set(1)

    def _undo(self):
        ok = self.organizer.undo_last_move()
        if ok:
            messagebox.showinfo("Undo", "Last file move reversed successfully.")
        else:
            messagebox.showwarning("Undo", "Nothing to undo or file no longer exists.")

    def _on_progress(self, done: int, total: int, name: str):
        frac = done / total if total else 0
        self.after(0, self._progress.set, frac)
        self.after(0, self._prog_lbl.configure, {"text": f"{done} / {total}"})
        self.after(0, self._append_log, f"  ↳ {name}")

    def _on_status(self, msg: str):
        self.after(0, self._status_lbl.configure, {"text": msg})

    def _append_log(self, text: str):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", text + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")
