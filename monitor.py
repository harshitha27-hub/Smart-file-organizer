"""
Monitor Page
============
Real-time folder monitoring with watchdog. Shows a live event feed,
duplicate scan results, and allows safe duplicate deletion.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from datetime import datetime

from modules.folder_monitor import FolderMonitor, WATCHDOG_AVAILABLE
from modules.duplicate_detector import DuplicateDetector
from modules.logger import AppLogger


def _fmt_size(b: int) -> str:
    if b >= 1_048_576:
        return f"{b/1_048_576:.1f} MB"
    if b >= 1024:
        return f"{b/1024:.1f} KB"
    return f"{b} B"


class MonitorPage(ctk.CTkFrame):
    """Real-time monitoring and duplicate management page."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.monitor  = FolderMonitor(event_callback=self._on_event)
        self.detector = DuplicateDetector(
            progress_callback=self._dup_progress,
            status_callback=self._dup_status,
        )
        self.log = AppLogger()
        self._dup_groups = []
        self._folder = tk.StringVar()
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(self, text="Monitor & Duplicates",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="#6C63FF").pack(anchor="w", pady=(0, 16))

        # ── Folder row ───────────────────────────────────────────────────────
        sel = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        sel.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(sel, text="📂  Watch Folder",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 6))

        row = ctk.CTkFrame(sel, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 12))

        self._entry = ctk.CTkEntry(row, textvariable=self._folder,
                                   placeholder_text="Select a folder…",
                                   height=38, corner_radius=10)
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(row, text="Browse", width=90, height=38,
                      corner_radius=10, fg_color="#6C63FF",
                      command=self._browse).pack(side="left", padx=(0, 8))

        self._start_btn = ctk.CTkButton(row, text="▶  Start Monitor",
                                         width=130, height=38, corner_radius=10,
                                         fg_color="#43E97B", hover_color="#2ABF60",
                                         text_color="#0D0D1A",
                                         command=self._toggle_monitor)
        self._start_btn.pack(side="left", padx=(0, 8))

        self._indicator = ctk.CTkLabel(row, text="⬤  Stopped",
                                        text_color="#FF6584",
                                        font=ctk.CTkFont(size=12))
        self._indicator.pack(side="left")

        # ── Live events ──────────────────────────────────────────────────────
        ev_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        ev_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(ev_frame, text="📡  Live Events",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 4))

        self._event_box = ctk.CTkTextbox(ev_frame, fg_color="#0D0D1A",
                                          text_color="#A0C0D0",
                                          font=ctk.CTkFont(family="Consolas", size=11),
                                          height=140, corner_radius=8)
        self._event_box.pack(fill="x", padx=10, pady=(0, 10))

        if not WATCHDOG_AVAILABLE:
            self._append_event("⚠  watchdog library not installed – monitoring disabled.")

        # ── Duplicate scanner ────────────────────────────────────────────────
        dup_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        dup_frame.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(dup_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(hdr, text="🔁  Duplicate File Detector",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(side="left")

        self._scan_btn = ctk.CTkButton(hdr, text="🔍 Scan for Duplicates",
                                        width=180, height=34, corner_radius=10,
                                        fg_color="#F7971E", hover_color="#CC7010",
                                        text_color="#0D0D1A",
                                        command=self._scan_dups)
        self._scan_btn.pack(side="right", padx=(0, 8))

        self._del_btn = ctk.CTkButton(hdr, text="🗑  Delete All Duplicates",
                                       width=180, height=34, corner_radius=10,
                                       fg_color="#FF6584", hover_color="#CC3355",
                                       command=self._delete_dups,
                                       state="disabled")
        self._del_btn.pack(side="right", padx=(0, 8))

        self._dup_status_lbl = ctk.CTkLabel(dup_frame, text="",
                                             font=ctk.CTkFont(size=11),
                                             text_color="#8888AA")
        self._dup_status_lbl.pack(anchor="w", padx=14)

        self._dup_progress = ctk.CTkProgressBar(dup_frame, height=10,
                                                  progress_color="#F7971E",
                                                  fg_color="#2A2A4A")
        self._dup_progress.pack(fill="x", padx=14, pady=4)
        self._dup_progress.set(0)

        # Duplicate results table
        self._dup_box = ctk.CTkTextbox(dup_frame, fg_color="#0D0D1A",
                                        text_color="#E0E0E0",
                                        font=ctk.CTkFont(family="Consolas", size=11),
                                        corner_radius=8)
        self._dup_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._dup_box.configure(state="disabled")

    # ── Monitor callbacks ─────────────────────────────────────────────────────

    def _browse(self):
        f = filedialog.askdirectory(title="Select Folder to Watch")
        if f:
            self._folder.set(f)

    def _toggle_monitor(self):
        if self.monitor.is_running:
            self.monitor.stop()
            self._start_btn.configure(text="▶  Start Monitor")
            self._indicator.configure(text="⬤  Stopped", text_color="#FF6584")
        else:
            folder = self._folder.get().strip()
            if not folder or not os.path.isdir(folder):
                messagebox.showerror("Error", "Select a valid folder first.")
                return
            ok = self.monitor.start(folder)
            if ok:
                self._start_btn.configure(text="⏹  Stop Monitor")
                self._indicator.configure(text="⬤  Monitoring", text_color="#43E97B")
                self._append_event(f"▶  Monitoring started: {folder}")
            else:
                messagebox.showerror("Error", "Could not start monitoring (watchdog required).")

    def _on_event(self, msg: str, path: str, category: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.after(0, self._append_event, f"[{ts}] {msg}")

    def _append_event(self, text: str):
        self._event_box.configure(state="normal")
        self._event_box.insert("end", text + "\n")
        self._event_box.see("end")
        self._event_box.configure(state="disabled")

    # ── Duplicate callbacks ───────────────────────────────────────────────────

    def _scan_dups(self):
        folder = self._folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Select a folder first.")
            return

        self._scan_btn.configure(state="disabled")
        self._dup_progress.set(0)
        self._dup_box.configure(state="normal")
        self._dup_box.delete("1.0", "end")
        self._dup_box.configure(state="disabled")

        def _worker():
            try:
                groups = self.detector.scan(folder)
                self._dup_groups = groups
                self.after(0, self._show_dup_results, groups)
            except Exception as exc:
                self.after(0, self._dup_status_lbl.configure,
                           {"text": f"Error: {exc}"})
            finally:
                self.after(0, self._scan_btn.configure, {"state": "normal"})

        threading.Thread(target=_worker, daemon=True).start()

    def _show_dup_results(self, groups):
        total_savings = sum(g["savings"] for g in groups)
        self._dup_status_lbl.configure(
            text=f"Found {len(groups)} duplicate groups | "
                 f"Potential savings: {_fmt_size(total_savings)}"
        )
        self._dup_box.configure(state="normal")
        self._dup_box.delete("1.0", "end")

        if not groups:
            self._dup_box.insert("end", "  ✅  No duplicates found!\n")
            self._del_btn.configure(state="disabled")
        else:
            self._del_btn.configure(state="normal")
            for i, g in enumerate(groups, 1):
                self._dup_box.insert(
                    "end",
                    f"  Group {i} — {_fmt_size(g['size'])} each "
                    f"(saves {_fmt_size(g['savings'])})\n"
                    f"    ORIGINAL : {g['original']}\n"
                )
                for dup in g["duplicates"]:
                    self._dup_box.insert("end", f"    DUPLICATE: {dup}\n")
                self._dup_box.insert("end", "\n")

        self._dup_box.configure(state="disabled")

    def _delete_dups(self):
        if not self._dup_groups:
            return
        total = sum(len(g["duplicates"]) for g in self._dup_groups)
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete {total} duplicate file(s)? This cannot be undone."
        ):
            return

        deleted, freed = self.detector.delete_duplicates(self._dup_groups)
        messagebox.showinfo(
            "Done",
            f"Deleted {deleted} file(s)\nFreed {_fmt_size(freed)}"
        )
        self._dup_groups = []
        self._del_btn.configure(state="disabled")
        self._dup_status_lbl.configure(text=f"Deleted {deleted} files, freed {_fmt_size(freed)}.")

    def _dup_progress(self, done: int, total: int):
        self.after(0, self._dup_progress.set, done / total if total else 0)

    def _dup_status(self, msg: str):
        self.after(0, self._dup_status_lbl.configure, {"text": msg})

    def on_destroy(self):
        self.monitor.stop()
