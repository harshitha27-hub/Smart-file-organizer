"""
Dashboard Page
==============
Shows headline stats (cards), health score, largest files, and recent activity.
"""

import customtkinter as ctk
from modules.analytics_engine import AnalyticsEngine
from modules.logger import AppLogger


def _fmt_size(b: int) -> str:
    if b >= 1_073_741_824:
        return f"{b/1_073_741_824:.1f} GB"
    if b >= 1_048_576:
        return f"{b/1_048_576:.1f} MB"
    if b >= 1024:
        return f"{b/1024:.1f} KB"
    return f"{b} B"


class DashboardPage(ctk.CTkFrame):
    """Dashboard with KPI cards and summary tables."""

    CARDS = [
        ("Total Files",     "total_files",  "#6C63FF", "📁"),
        ("Storage Used",    "total_size",   "#43E97B", "💾"),
        ("Categories",      "categories",   "#F7971E", "🗂"),
        ("Duplicates Found","duplicates",   "#FF6584", "🔁"),
    ]

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.engine = AnalyticsEngine()
        self.log    = AppLogger()
        self._build()
        self.refresh()

    def _build(self):
        # Title row
        title = ctk.CTkLabel(self, text="Dashboard",
                             font=ctk.CTkFont(size=28, weight="bold"),
                             text_color="#6C63FF")
        title.pack(anchor="w", pady=(0, 16))

        # ── KPI Cards ────────────────────────────────────────────────────────
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 12))
        cards_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="col")

        self._card_labels: dict = {}
        for col, (label, key, color, icon) in enumerate(self.CARDS):
            card = ctk.CTkFrame(cards_frame, fg_color="#16213E", corner_radius=16)
            card.grid(row=0, column=col, padx=8, pady=4, sticky="nsew")

            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=28)).pack(pady=(14, 2))
            val_lbl = ctk.CTkLabel(card, text="—",
                                   font=ctk.CTkFont(size=22, weight="bold"),
                                   text_color=color)
            val_lbl.pack()
            ctk.CTkLabel(card, text=label,
                         font=ctk.CTkFont(size=11),
                         text_color="#8888AA").pack(pady=(0, 14))
            self._card_labels[key] = val_lbl

        # ── Health Score ─────────────────────────────────────────────────────
        health_row = ctk.CTkFrame(self, fg_color="transparent")
        health_row.pack(fill="x", pady=(0, 12))

        health_card = ctk.CTkFrame(health_row, fg_color="#16213E", corner_radius=16)
        health_card.pack(fill="x", padx=0)

        ctk.CTkLabel(health_card, text="🩺  Folder Health Score",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=16, pady=(12, 4))

        self._health_bar = ctk.CTkProgressBar(health_card, height=18,
                                              progress_color="#43E97B",
                                              fg_color="#2A2A4A")
        self._health_bar.pack(fill="x", padx=16, pady=(0, 4))
        self._health_bar.set(0)

        self._health_label = ctk.CTkLabel(health_card, text="—",
                                          font=ctk.CTkFont(size=12),
                                          text_color="#8888AA")
        self._health_label.pack(anchor="w", padx=16, pady=(0, 12))

        # ── Bottom panels: Largest + Recent ──────────────────────────────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="both", expand=True)
        bottom.columnconfigure((0, 1), weight=1, uniform="bot")

        self._largest_box = self._make_table_box(bottom, "📊 Largest Files", 0)
        self._recent_box  = self._make_table_box(bottom, "🕐 Recently Added", 1)

    def _make_table_box(self, parent, title: str, col: int) -> ctk.CTkTextbox:
        frame = ctk.CTkFrame(parent, fg_color="#16213E", corner_radius=16)
        frame.grid(row=0, column=col, padx=8, sticky="nsew")
        ctk.CTkLabel(frame, text=title,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#E0E0E0").pack(anchor="w", padx=14, pady=(12, 4))
        tb = ctk.CTkTextbox(frame, fg_color="#0D0D1A", text_color="#C0C0D0",
                            font=ctk.CTkFont(family="Consolas", size=11),
                            height=200, corner_radius=8)
        tb.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        return tb

    # ── Public ────────────────────────────────────────────────────────────────

    def refresh(self):
        """Pull fresh data from the database and update all widgets."""
        try:
            summary = self.engine.get_summary()
            health  = self.engine.get_health_score()

            # Cards
            for key, lbl in self._card_labels.items():
                val = summary.get(key, 0)
                if key == "total_size":
                    lbl.configure(text=_fmt_size(val))
                else:
                    lbl.configure(text=str(val))

            # Health bar
            score = health["score"] / 100
            self._health_bar.set(score)
            color = "#43E97B" if score > 0.7 else "#F7971E" if score > 0.4 else "#FF6584"
            self._health_bar.configure(progress_color=color)
            self._health_label.configure(
                text=f"{health['score']}/100 — {health['label']}"
            )

            # Largest files
            self._largest_box.configure(state="normal")
            self._largest_box.delete("1.0", "end")
            for f in summary.get("largest", []):
                self._largest_box.insert(
                    "end",
                    f"  {_fmt_size(f['size']):>9}  {f['file_name'][:45]}\n"
                )
            self._largest_box.configure(state="disabled")

            # Recent files
            self._recent_box.configure(state="normal")
            self._recent_box.delete("1.0", "end")
            for f in summary.get("recent", []):
                date = (f.get("date_added") or "")[:10]
                self._recent_box.insert(
                    "end",
                    f"  {date}  {f['file_name'][:45]}\n"
                )
            self._recent_box.configure(state="disabled")

        except Exception as exc:
            self.log.error(f"Dashboard refresh error: {exc}")
