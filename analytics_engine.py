"""
Analytics Engine Module
=======================
Computes file statistics and generates Plotly charts for the GUI.
Returns chart figures that can be embedded in the CustomTkinter UI
via a temporary HTML render or exported as images.
"""

import os
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

from modules.database import DatabaseManager
from modules.logger import AppLogger


# ── Colour palette ─────────────────────────────────────────────────────────────
PALETTE = [
    "#6C63FF", "#FF6584", "#43E97B", "#F7971E",
    "#12C2E9", "#F64F59", "#C471ED", "#FFC107",
]
BG = "#1A1A2E"
PAPER_BG = "#16213E"
FONT_COLOR = "#E0E0E0"
GRID_COLOR = "#2A2A4A"


def _base_layout(**kwargs) -> Dict:
    return dict(
        plot_bgcolor=BG,
        paper_bgcolor=PAPER_BG,
        font=dict(color=FONT_COLOR, family="Segoe UI, sans-serif"),
        margin=dict(l=40, r=20, t=40, b=40),
        **kwargs,
    )


class AnalyticsEngine:
    """
    Pulls data from DatabaseManager and builds Plotly figures.
    All public methods return a plotly Figure object (or None on error).
    """

    def __init__(self):
        self.db = DatabaseManager()
        self.log = AppLogger()

    # ── Summary stats ──────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Returns headline numbers for the dashboard cards."""
        stats = self.db.get_total_stats()
        largest = self.db.get_largest_files(5)
        recent = self.db.get_recent_files(5)
        return {
            "total_files":  stats.get("total_files", 0),
            "total_size":   stats.get("total_size", 0),
            "categories":   stats.get("categories", 0),
            "duplicates":   stats.get("duplicates", 0),
            "largest":      largest,
            "recent":       recent,
        }

    # ── Plotly charts ──────────────────────────────────────────────────────────

    def category_pie(self) -> Optional[Any]:
        """Pie chart: proportion of files per category."""
        if not PLOTLY_OK:
            return None
        rows = self.db.get_category_stats()
        if not rows:
            return None

        labels = [r[0] for r in rows]
        values = [r[1] for r in rows]

        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.45,
            marker=dict(colors=PALETTE[:len(labels)],
                        line=dict(color="#0D0D1A", width=2)),
            textfont=dict(size=13),
        ))
        fig.update_layout(
            title="File Categories",
            **_base_layout(),
            showlegend=True,
        )
        return fig

    def category_bar(self) -> Optional[Any]:
        """Bar chart: file count and storage per category."""
        if not PLOTLY_OK:
            return None
        rows = self.db.get_category_stats()
        if not rows:
            return None

        cats  = [r[0] for r in rows]
        counts = [r[1] for r in rows]
        sizes  = [round((r[2] or 0) / 1024 / 1024, 2) for r in rows]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(
            name="File Count", x=cats, y=counts,
            marker_color=PALETTE[0], opacity=0.85,
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            name="Size (MB)", x=cats, y=sizes,
            mode="lines+markers",
            line=dict(color=PALETTE[1], width=2),
            marker=dict(size=8),
        ), secondary_y=True)

        fig.update_layout(
            title="Files per Category",
            xaxis=dict(gridcolor=GRID_COLOR),
            yaxis=dict(gridcolor=GRID_COLOR),
            **_base_layout(),
        )
        fig.update_yaxes(title_text="Count", secondary_y=False)
        fig.update_yaxes(title_text="Size (MB)", secondary_y=True)
        return fig

    def growth_line(self) -> Optional[Any]:
        """Line chart: folder size growth over time from snapshots."""
        if not PLOTLY_OK:
            return None
        snaps = self.db.get_snapshots()
        if len(snaps) < 2:
            return None

        dates = [s["snapshot_at"][:10] for s in snaps]
        sizes = [round(s["total_size"] / 1024 / 1024, 2) for s in snaps]
        counts = [s["total_files"] for s in snaps]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=sizes, name="Size (MB)",
            fill="tozeroy", fillcolor="rgba(108,99,255,0.15)",
            line=dict(color=PALETTE[0], width=2),
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=counts, name="File Count",
            yaxis="y2",
            line=dict(color=PALETTE[1], width=2, dash="dot"),
        ))
        fig.update_layout(
            title="Folder Growth Over Time",
            xaxis=dict(gridcolor=GRID_COLOR),
            yaxis=dict(title="Size (MB)", gridcolor=GRID_COLOR),
            yaxis2=dict(title="File Count", overlaying="y", side="right"),
            **_base_layout(),
        )
        return fig

    def save_chart_image(self, fig, filename: str) -> str:
        """Export a Plotly figure as a PNG. Returns the saved path."""
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "reports"
        )
        os.makedirs(export_dir, exist_ok=True)
        path = os.path.join(export_dir, filename)
        try:
            fig.write_image(path, width=900, height=500)
        except Exception as exc:
            self.log.error(f"Chart export failed: {exc}")
        return path

    def save_chart_html(self, fig, filename: str) -> str:
        """Export a Plotly figure as a self-contained HTML file."""
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "reports"
        )
        os.makedirs(export_dir, exist_ok=True)
        path = os.path.join(export_dir, filename)
        try:
            fig.write_html(path)
        except Exception as exc:
            self.log.error(f"HTML chart export failed: {exc}")
        return path

    def get_health_score(self) -> Dict[str, Any]:
        """
        Computes a 0-100 'folder health score' based on:
          - duplicate ratio (lower is better)
          - categorization coverage (higher is better)
          - recency of organization
        """
        stats = self.db.get_total_stats()
        total = stats.get("total_files", 1) or 1
        dups  = stats.get("duplicates", 0) or 0

        dup_penalty   = min(dups / total * 100, 40)
        org_coverage  = min(stats.get("categories", 0) * 10, 40)
        base_score    = 60 - dup_penalty + org_coverage
        score         = max(0, min(100, round(base_score)))

        if score >= 80:
            label = "Excellent"
        elif score >= 60:
            label = "Good"
        elif score >= 40:
            label = "Fair"
        else:
            label = "Needs Attention"

        return {"score": score, "label": label}
