"""
Analytics Page
==============
Displays interactive Plotly charts in the browser (opens via webbrowser module)
and shows a summary table. Exports charts as HTML or image.
"""

import os
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from modules.analytics_engine import AnalyticsEngine
from modules.database import DatabaseManager
from modules.logger import AppLogger


def _fmt_size(b: int) -> str:
    if b >= 1_048_576:
        return f"{b/1_048_576:.1f} MB"
    if b >= 1024:
        return f"{b/1024:.1f} KB"
    return f"{b} B"


class AnalyticsPage(ctk.CTkFrame):
    """Analytics dashboard with chart controls and data tables."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.engine = AnalyticsEngine()
        self.db     = DatabaseManager()
        self.log    = AppLogger()
        self._figs  = {}
        self._build()
        self.refresh()

    def _build(self):
        ctk.CTkLabel(self, text="Analytics",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="#6C63FF").pack(anchor="w", pady=(0, 16))

        # ── Chart controls ───────────────────────────────────────────────────
        ctrl = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        ctrl.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(ctrl, text="📊  Charts",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 6))

        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 12))

        charts = [
            ("🥧 Category Pie",   "pie",    "#6C63FF"),
            ("📊 Category Bar",   "bar",    "#43E97B"),
            ("📈 Growth Line",    "growth", "#F7971E"),
        ]
        for text, key, color in charts:
            ctk.CTkButton(btn_row,
                          text=text, height=38, corner_radius=10,
                          fg_color=color, hover_color="#555",
                          text_color="#0D0D1A" if color != "#6C63FF" else "#FFFFFF",
                          command=lambda k=key: self._open_chart(k)
                          ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_row, text="💾 Export All Charts",
                      height=38, corner_radius=10,
                      fg_color="#2A2A4A", hover_color="#3A3A5A",
                      command=self._export_all).pack(side="right")

        ctk.CTkButton(btn_row, text="🔄 Refresh",
                      height=38, corner_radius=10,
                      fg_color="#2A2A4A", hover_color="#3A3A5A",
                      command=self.refresh).pack(side="right", padx=(0, 8))

        # ── Category table ───────────────────────────────────────────────────
        tbl_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        tbl_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(tbl_frame, text="🗂  Category Breakdown",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 4))

        self._cat_box = ctk.CTkTextbox(tbl_frame, fg_color="#0D0D1A",
                                        text_color="#E0E0E0",
                                        font=ctk.CTkFont(family="Consolas", size=12),
                                        height=180, corner_radius=8)
        self._cat_box.pack(fill="x", padx=10, pady=(0, 10))
        self._cat_box.configure(state="disabled")

        # ── Largest files ─────────────────────────────────────────────────────
        lf = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        lf.pack(fill="both", expand=True)

        ctk.CTkLabel(lf, text="🏆  Top 10 Largest Files",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 4))

        self._large_box = ctk.CTkTextbox(lf, fg_color="#0D0D1A",
                                          text_color="#E0E0E0",
                                          font=ctk.CTkFont(family="Consolas", size=11),
                                          corner_radius=8)
        self._large_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._large_box.configure(state="disabled")

        # ── Search bar ────────────────────────────────────────────────────────
        srch = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        srch.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(srch, text="🔍  Search Files",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 6))

        s_row = ctk.CTkFrame(srch, fg_color="transparent")
        s_row.pack(fill="x", padx=14, pady=(0, 8))

        self._search_var = tk.StringVar()
        self._ext_var    = tk.StringVar()

        ctk.CTkEntry(s_row, textvariable=self._search_var,
                     placeholder_text="File name…",
                     height=36, corner_radius=10).pack(side="left", fill="x", expand=True, padx=(0,8))
        ctk.CTkEntry(s_row, textvariable=self._ext_var,
                     placeholder_text="Extension (e.g. pdf)…",
                     width=160, height=36, corner_radius=10).pack(side="left", padx=(0,8))
        ctk.CTkButton(s_row, text="Search", height=36, corner_radius=10,
                      fg_color="#6C63FF",
                      command=self._search).pack(side="left")

        self._search_box = ctk.CTkTextbox(srch, fg_color="#0D0D1A",
                                           text_color="#C0C0D0",
                                           font=ctk.CTkFont(family="Consolas", size=11),
                                           height=120, corner_radius=8)
        self._search_box.pack(fill="x", padx=10, pady=(0, 10))
        self._search_box.configure(state="disabled")

    # ── Public ────────────────────────────────────────────────────────────────

    def refresh(self):
        try:
            self._figs = {
                "pie":    self.engine.category_pie(),
                "bar":    self.engine.category_bar(),
                "growth": self.engine.growth_line(),
            }
            self._populate_tables()
        except Exception as exc:
            self.log.error(f"Analytics refresh error: {exc}")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _populate_tables(self):
        cat_rows = self.db.get_category_stats()
        self._cat_box.configure(state="normal")
        self._cat_box.delete("1.0", "end")
        header = f"  {'Category':<14} {'Files':>8} {'Size':>12}\n"
        self._cat_box.insert("end", header)
        self._cat_box.insert("end", "  " + "-" * 36 + "\n")
        for r in cat_rows:
            self._cat_box.insert(
                "end",
                f"  {r[0]:<14} {r[1]:>8}   {_fmt_size(r[2] or 0):>10}\n"
            )
        self._cat_box.configure(state="disabled")

        largest = self.db.get_largest_files(10)
        self._large_box.configure(state="normal")
        self._large_box.delete("1.0", "end")
        for i, f in enumerate(largest, 1):
            self._large_box.insert(
                "end",
                f"  {i:>2}. {_fmt_size(f['size']):>10}  [{f['category']:<12}]  {f['file_name']}\n"
            )
        self._large_box.configure(state="disabled")

    def _open_chart(self, key: str):
        fig = self._figs.get(key)
        if not fig:
            messagebox.showinfo("No Data", "Run the organizer first to generate data.")
            return
        html_path = self.engine.save_chart_html(fig, f"{key}_chart.html")
        webbrowser.open(f"file://{os.path.abspath(html_path)}")

    def _export_all(self):
        exported = []
        for key, fig in self._figs.items():
            if fig:
                path = self.engine.save_chart_html(fig, f"{key}_chart.html")
                exported.append(path)
        if exported:
            messagebox.showinfo("Exported", f"Charts saved to:\n" + "\n".join(exported))
        else:
            messagebox.showwarning("Nothing to Export", "No chart data available.")

    def _search(self):
        results = self.db.search_files(
            query=self._search_var.get(),
            extension=self._ext_var.get(),
        )
        self._search_box.configure(state="normal")
        self._search_box.delete("1.0", "end")
        if not results:
            self._search_box.insert("end", "  No results found.\n")
        else:
            self._search_box.insert("end", f"  Found {len(results)} file(s):\n\n")
            for f in results[:50]:
                self._search_box.insert(
                    "end",
                    f"  {_fmt_size(f['size']):>10}  {f['file_name']}\n"
                )
        self._search_box.configure(state="disabled")
