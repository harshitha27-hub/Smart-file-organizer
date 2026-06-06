"""
Logger Module
=============
Provides a centralized, rotating file logger for all application activities.
Logs are stored in logs/activity.log with automatic rotation.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


class AppLogger:
    """
    Singleton application logger with both file and console output.
    Uses rotating file handler to cap log size at 5 MB × 3 backups.
    """

    _instance = None
    LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    LOG_FILE = os.path.join(LOG_DIR, "activity.log")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup()
        return cls._instance

    def _setup(self):
        os.makedirs(self.LOG_DIR, exist_ok=True)

        self.logger = logging.getLogger("SmartFileOrganizer")
        self.logger.setLevel(logging.DEBUG)

        if self.logger.handlers:
            return  # Already configured

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)-8s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Rotating file handler – 5 MB max, keep 3 backups
        fh = RotatingFileHandler(
            self.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    # ── Convenience wrappers ──────────────────────

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def debug(self, msg: str):
        self.logger.debug(msg)

    def log_move(self, src: str, dst: str):
        self.info(f"MOVED: '{src}' → '{dst}'")

    def log_delete(self, path: str, reason: str = "duplicate"):
        self.warning(f"DELETED [{reason.upper()}]: '{path}'")

    def log_monitor_event(self, event_type: str, path: str):
        self.info(f"MONITOR [{event_type}]: '{path}'")

    def get_recent_logs(self, n: int = 50) -> list:
        """Return the last n lines from the log file."""
        try:
            with open(self.LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [ln.rstrip() for ln in lines[-n:]]
        except FileNotFoundError:
            return []
