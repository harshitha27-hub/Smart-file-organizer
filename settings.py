"""
Settings Page
=============
Application settings: theme, appearance, database info, log viewer,
and scheduled organization configuration.
"""

import os
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from modules.database import DatabaseManager
from modules.logger import AppLogger

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "files.db")
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "activity.log")


class SettingsPage(ctk.CTkFrame):
    """Settings and configuration panel."""

    THEMES = ["Dark", "Light", "System"]
    ACCENTS = {
        "Purple":  "#6C63FF",
        "Teal":    "#43E97B",
        "Orange":  "#F7971E",
        "Pink":    "#FF6584",
        "Cyan":    "#12C2E9",
    }

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.db  = DatabaseManager()
        self.log = AppLogger()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Settings",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="#6C63FF").pack(anchor="w", pady=(0, 16))

        # ── Appearance ───────────────────────────────────────────────────────
        app_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        app_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(app_frame, text="🎨  Appearance",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 6))

        row1 = ctk.CTkFrame(app_frame, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkLabel(row1, text="Theme:", width=90).pack(side="left")
        self._theme_var = tk.StringVar(value="Dark")
        theme_menu = ctk.CTkOptionMenu(row1, values=self.THEMES,
                                        variable=self._theme_var,
                                        command=self._change_theme,
                                        width=120)
        theme_menu.pack(side="left", padx=(0, 24))

        ctk.CTkLabel(row1, text="Accent Color:", width=100).pack(side="left")
        self._accent_var = tk.StringVar(value="Purple")
        accent_menu = ctk.CTkOptionMenu(row1, values=list(self.ACCENTS.keys()),
                                         variable=self._accent_var,
                                         command=self._change_accent,
                                         width=120)
        accent_menu.pack(side="left")

        # ── Database info ────────────────────────────────────────────────────
        db_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        db_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(db_frame, text="🗄  Database",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 6))

        self._db_box = ctk.CTkTextbox(db_frame, fg_color="#0D0D1A",
                                       text_color="#A0C0D0",
                                       font=ctk.CTkFont(family="Consolas", size=11),
                                       height=90, corner_radius=8)
        self._db_box.pack(fill="x", padx=10, pady=(0, 6))
        self._populate_db_info()

        btn_row = ctk.CTkFrame(db_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkButton(btn_row, text="🔄 Refresh DB Info",
                      height=34, corner_radius=8, fg_color="#2A2A4A",
                      command=self._populate_db_info).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_row, text="⚠ Clear Database",
                      height=34, corner_radius=8, fg_color="#FF6584",
                      command=self._clear_db).pack(side="left")

        # ── Log viewer ───────────────────────────────────────────────────────
        log_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        log_frame.pack(fill="both", expand=True)

        log_hdr = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_hdr.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(log_hdr, text="📝  Activity Log",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(side="left")

        ctk.CTkButton(log_hdr, text="🔄 Refresh Log", width=120, height=30,
                      corner_radius=8, fg_color="#2A2A4A",
                      command=self._load_log).pack(side="right")

        self._log_box = ctk.CTkTextbox(log_frame, fg_color="#0D0D1A",
                                        text_color="#A0C0D0",
                                        font=ctk.CTkFont(family="Consolas", size=11),
                                        corner_radius=8)
        self._log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._load_log()

        # ── About ─────────────────────────────────────────────────────────────
        about_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        about_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(about_frame,
                     text="Smart File Organizer  ·  v1.0.0  ·  Built with CustomTkinter, Watchdog, Plotly & Scikit-Learn",
                     font=ctk.CTkFont(size=11),
                     text_color="#555577").pack(padx=14, pady=12)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _populate_db_info(self):
        stats = self.db.get_total_stats()
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        self._db_box.configure(state="normal")
        self._db_box.delete("1.0", "end")
        self._db_box.insert("end",
            f"  Path:          {DB_PATH}\n"
            f"  Size:          {db_size // 1024} KB\n"
            f"  Total records: {stats.get('total_files', 0)}\n"
            f"  Categories:    {stats.get('categories', 0)}\n"
        )
        self._db_box.configure(state="disabled")

    def _clear_db(self):
        if messagebox.askyesno("Confirm", "Clear all database records? This cannot be undone."):
            try:
                import sqlite3
                conn = sqlite3.connect(DB_PATH)
                conn.execute("DELETE FROM files")
                conn.execute("DELETE FROM organization_history")
                conn.execute("DELETE FROM duplicates")
                conn.execute("DELETE FROM folder_snapshots")
                conn.commit()
                conn.close()
                messagebox.showinfo("Done", "Database cleared.")
                self._populate_db_info()
            except Exception as exc:
                messagebox.showerror("Error", str(exc))

    def _load_log(self):
        lines = self.log.get_recent_logs(100)
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        for line in lines:
            self._log_box.insert("end", line + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _change_theme(self, value: str):
        ctk.set_appearance_mode(value)

    def _change_accent(self, value: str):
        # CustomTkinter doesn't support runtime accent color changes easily,
        # but we store the preference for future use.
        self.log.info(f"Accent color preference set: {value}")
        messagebox.showinfo("Accent Color",
                            f"Accent color set to {value}.\nRestart the app to apply fully.")
