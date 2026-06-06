"""
Predictor Module
================
Uses Scikit-Learn Linear Regression to forecast future storage usage
and file counts from historical folder snapshots.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    import numpy as np
    from sklearn.linear_model import LinearRegression
    SK_OK = True
except ImportError:
    SK_OK = False

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

from modules.database import DatabaseManager
from modules.logger import AppLogger


BG = "#1A1A2E"
PAPER_BG = "#16213E"
FONT_COLOR = "#E0E0E0"
GRID_COLOR = "#2A2A4A"


class StoragePredictor:
    """
    Predicts future storage usage and file counts using linear regression
    trained on historical folder snapshots stored in the database.
    """

    HORIZONS = {
        "30 Days":  30,
        "90 Days":  90,
        "180 Days": 180,
    }

    def __init__(self):
        self.db = DatabaseManager()
        self.log = AppLogger()

    def predict(self) -> Dict[str, Any]:
        """
        Returns a predictions dict::

            {
                "horizons": {
                    "30 Days":  {"size_mb": float, "file_count": int},
                    "90 Days":  {...},
                    "180 Days": {...},
                },
                "model_quality": float,   # R² score on training data
                "chart": plotly Figure | None,
                "error": str | None,
            }
        """
        snapshots = self.db.get_snapshots()

        if not SK_OK:
            return {"error": "scikit-learn not installed."}

        if len(snapshots) < 3:
            return {"error": "Need at least 3 snapshots for prediction. "
                             "Run the organizer a few more times to build history."}

        # ── Prepare data ──────────────────────────────────────────────────────
        base_date = datetime.fromisoformat(snapshots[0]["snapshot_at"])
        X = np.array([
            (datetime.fromisoformat(s["snapshot_at"]) - base_date).days
            for s in snapshots
        ]).reshape(-1, 1)
        y_size  = np.array([s["total_size"]  for s in snapshots], dtype=float)
        y_count = np.array([s["total_files"] for s in snapshots], dtype=float)

        # ── Fit models ────────────────────────────────────────────────────────
        model_size  = LinearRegression().fit(X, y_size)
        model_count = LinearRegression().fit(X, y_count)
        r2_size  = model_size.score(X, y_size)
        r2_count = model_count.score(X, y_count)

        today_offset = (datetime.now() - base_date).days
        predictions: Dict[str, Any] = {}

        for label, days in self.HORIZONS.items():
            future_day = today_offset + days
            pred_size  = max(0.0, model_size.predict([[future_day]])[0])
            pred_count = max(0, int(model_count.predict([[future_day]])[0]))
            predictions[label] = {
                "size_mb":    round(pred_size / 1024 / 1024, 2),
                "file_count": pred_count,
            }

        chart = self._build_chart(
            snapshots, base_date, model_size, model_count, today_offset
        ) if PLOTLY_OK else None

        return {
            "horizons":      predictions,
            "model_quality": round((r2_size + r2_count) / 2, 3),
            "chart":         chart,
            "error":         None,
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    def _build_chart(self, snapshots, base_date, model_size, model_count,
                     today_offset: int):
        """Builds a Plotly figure showing historical + predicted values."""
        hist_days  = [(datetime.fromisoformat(s["snapshot_at"]) - base_date).days for s in snapshots]
        hist_dates = [base_date + timedelta(days=d) for d in hist_days]
        hist_sizes = [s["total_size"] / 1024 / 1024 for s in snapshots]

        # Prediction horizon: today → +180 days
        import numpy as np
        future_days  = list(range(today_offset, today_offset + 181, 5))
        future_dates = [base_date + timedelta(days=d) for d in future_days]
        pred_sizes   = [
            max(0, model_size.predict([[d]])[0]) / 1024 / 1024
            for d in future_days
        ]

        fig = go.Figure()

        # Historical
        fig.add_trace(go.Scatter(
            x=[d.strftime("%Y-%m-%d") for d in hist_dates],
            y=hist_sizes,
            mode="lines+markers",
            name="Historical",
            line=dict(color="#6C63FF", width=2),
            marker=dict(size=7),
        ))

        # Predicted
        fig.add_trace(go.Scatter(
            x=[d.strftime("%Y-%m-%d") for d in future_dates],
            y=pred_sizes,
            mode="lines",
            name="Predicted",
            line=dict(color="#43E97B", width=2, dash="dash"),
        ))

        # Horizon markers
        for label, days in self.HORIZONS.items():
            target_date = base_date + timedelta(days=today_offset + days)
            pred_val = max(0, model_size.predict([[today_offset + days]])[0]) / 1024 / 1024
            fig.add_vline(
                x=target_date.strftime("%Y-%m-%d"),
                line_dash="dot", line_color="#FFC107",
                annotation_text=label, annotation_font_color="#FFC107"
            )

        fig.update_layout(
            title="Storage Usage Prediction",
            xaxis=dict(title="Date", gridcolor=GRID_COLOR),
            yaxis=dict(title="Size (MB)", gridcolor=GRID_COLOR),
            plot_bgcolor=BG,
            paper_bgcolor=PAPER_BG,
            font=dict(color=FONT_COLOR, family="Segoe UI, sans-serif"),
            margin=dict(l=40, r=20, t=40, b=40),
        )
        return fig
