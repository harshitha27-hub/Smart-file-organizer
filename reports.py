"""
Reports Page
============
Generates Excel, CSV, and PDF reports with optional ML prediction data.
Shows report history and allows opening generated files.
"""

import os
import subprocess
import platform
import threading
from tkinter import messagebox
import customtkinter as ctk

from modules.report_generator import ReportGenerator, REPORTS_DIR
from modules.predictor import StoragePredictor
from modules.logger import AppLogger


def _open_file(path: str):
    """Open a file with the default OS application."""
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])
    except Exception:
        pass


class ReportsPage(ctk.CTkFrame):
    """Report generation and management page."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.reporter  = ReportGenerator()
        self.predictor = StoragePredictor()
        self.log       = AppLogger()
        self._preds    = None
        self._build()
        self._refresh_history()

    def _build(self):
        ctk.CTkLabel(self, text="Reports",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="#6C63FF").pack(anchor="w", pady=(0, 16))

        # ── Prediction section ───────────────────────────────────────────────
        pred_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        pred_frame.pack(fill="x", pady=(0, 10))

        hdr = ctk.CTkFrame(pred_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(hdr, text="🤖  ML Storage Prediction",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(side="left")

        ctk.CTkButton(hdr, text="Run Prediction", height=34, corner_radius=10,
                      fg_color="#6C63FF",
                      command=self._run_prediction).pack(side="right")

        self._pred_box = ctk.CTkTextbox(pred_frame, fg_color="#0D0D1A",
                                         text_color="#E0E0E0",
                                         font=ctk.CTkFont(family="Consolas", size=12),
                                         height=140, corner_radius=8)
        self._pred_box.pack(fill="x", padx=10, pady=(0, 10))
        self._pred_box.configure(state="disabled")

        # ── Report generation buttons ─────────────────────────────────────────
        gen_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        gen_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(gen_frame, text="📄  Generate Report",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 6))

        btn_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 12))

        BTNS = [
            ("📊 Excel Report",  self._gen_excel,  "#43E97B", "#0D0D1A"),
            ("📋 CSV Export",    self._gen_csv,    "#F7971E", "#0D0D1A"),
            ("📑 PDF Report",    self._gen_pdf,    "#FF6584", "#FFFFFF"),
        ]
        for text, cmd, color, fg in BTNS:
            ctk.CTkButton(btn_row, text=text, height=42, corner_radius=12,
                          fg_color=color, hover_color="#555",
                          text_color=fg,
                          font=ctk.CTkFont(size=13, weight="bold"),
                          command=cmd).pack(side="left", padx=(0, 10))

        self._gen_status = ctk.CTkLabel(gen_frame, text="",
                                         font=ctk.CTkFont(size=11),
                                         text_color="#8888AA")
        self._gen_status.pack(anchor="w", padx=14, pady=(0, 6))

        # ── Report history ───────────────────────────────────────────────────
        hist_frame = ctk.CTkFrame(self, fg_color="#16213E", corner_radius=16)
        hist_frame.pack(fill="both", expand=True)

        hdr2 = ctk.CTkFrame(hist_frame, fg_color="transparent")
        hdr2.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(hdr2, text="📁  Generated Reports",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(side="left")

        ctk.CTkButton(hdr2, text="🔄 Refresh", width=80, height=30,
                      corner_radius=8, fg_color="#2A2A4A",
                      command=self._refresh_history).pack(side="right")

        self._hist_frame = ctk.CTkScrollableFrame(hist_frame, fg_color="#0D0D1A",
                                                    corner_radius=8)
        self._hist_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ── Public ────────────────────────────────────────────────────────────────

    def _run_prediction(self):
        def _worker():
            result = self.predictor.predict()
            self.after(0, self._show_prediction, result)

        threading.Thread(target=_worker, daemon=True).start()
        self._pred_box.configure(state="normal")
        self._pred_box.delete("1.0", "end")
        self._pred_box.insert("end", "  Running prediction…\n")
        self._pred_box.configure(state="disabled")

    def _show_prediction(self, result: dict):
        self._pred_box.configure(state="normal")
        self._pred_box.delete("1.0", "end")

        if result.get("error"):
            self._pred_box.insert("end", f"  ⚠  {result['error']}\n")
        else:
            self._preds = result
            q = result.get("model_quality", 0)
            self._pred_box.insert("end", f"  Model Quality (R²): {q:.3f}\n\n")
            for horizon, vals in result["horizons"].items():
                self._pred_box.insert(
                    "end",
                    f"  {horizon:<12}  {vals['size_mb']:>8.1f} MB  "
                    f"  {vals['file_count']:>6} files\n"
                )
            if result.get("chart"):
                import webbrowser
                from modules.analytics_engine import AnalyticsEngine
                ae = AnalyticsEngine()
                p = ae.save_chart_html(result["chart"], "prediction_chart.html")
                self._pred_box.insert("end", f"\n  Chart saved: {p}\n")

        self._pred_box.configure(state="disabled")

    def _gen_excel(self):
        def _w():
            path = self.reporter.generate_excel(self._preds)
            self.after(0, self._done, path)
        threading.Thread(target=_w, daemon=True).start()
        self._gen_status.configure(text="Generating Excel…")

    def _gen_csv(self):
        def _w():
            path = self.reporter.generate_csv()
            self.after(0, self._done, path)
        threading.Thread(target=_w, daemon=True).start()
        self._gen_status.configure(text="Generating CSV…")

    def _gen_pdf(self):
        def _w():
            path = self.reporter.generate_pdf(self._preds)
            self.after(0, self._done, path)
        threading.Thread(target=_w, daemon=True).start()
        self._gen_status.configure(text="Generating PDF…")

    def _done(self, path: str):
        if path:
            self._gen_status.configure(text=f"✅  Saved: {os.path.basename(path)}")
            self._refresh_history()
            if messagebox.askyesno("Report Ready", f"Report saved:\n{path}\n\nOpen it now?"):
                _open_file(path)
        else:
            self._gen_status.configure(text="❌  Generation failed (missing library?)")

    def _refresh_history(self):
        for w in self._hist_frame.winfo_children():
            w.destroy()

        if not os.path.isdir(REPORTS_DIR):
            return

        files = sorted(
            [f for f in os.listdir(REPORTS_DIR)
             if f.endswith((".xlsx", ".csv", ".pdf", ".html"))],
            reverse=True
        )

        if not files:
            ctk.CTkLabel(self._hist_frame, text="  No reports yet.",
                         text_color="#8888AA").pack(anchor="w", padx=8, pady=8)
            return

        ICONS = {".xlsx": "📊", ".csv": "📋", ".pdf": "📑", ".html": "🌐"}
        for fname in files:
            fpath = os.path.join(REPORTS_DIR, fname)
            ext   = os.path.splitext(fname)[1]
            icon  = ICONS.get(ext, "📄")
            size  = os.path.getsize(fpath)

            row = ctk.CTkFrame(self._hist_frame, fg_color="#1A1A2E", corner_radius=8)
            row.pack(fill="x", padx=4, pady=3)

            ctk.CTkLabel(row, text=f"{icon}  {fname}",
                         font=ctk.CTkFont(size=12),
                         text_color="#E0E0E0").pack(side="left", padx=10, pady=8)

            ctk.CTkLabel(row, text=f"{size//1024} KB",
                         font=ctk.CTkFont(size=11),
                         text_color="#8888AA").pack(side="left")

            ctk.CTkButton(row, text="Open", width=70, height=28,
                          corner_radius=8, fg_color="#6C63FF",
                          command=lambda p=fpath: _open_file(p)
                          ).pack(side="right", padx=8, pady=6)
