"""
Database Module
==============
Handles all SQLite database operations for the Smart File Organizer.
Stores file metadata, hashes, and organization history.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import threading


class DatabaseManager:
    """
    Manages SQLite database operations with thread-safe connections.
    Uses connection pooling per thread for concurrent access.
    """

    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "files.db")

    def __init__(self):
        self._local = threading.local()
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        self._initialize_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Returns a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.DB_PATH, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _initialize_db(self):
        """Creates all required tables if they don't exist."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name   TEXT NOT NULL,
                file_path   TEXT NOT NULL UNIQUE,
                category    TEXT,
                size        INTEGER DEFAULT 0,
                date_added  TEXT,
                date_modified TEXT,
                hash_value  TEXT,
                is_duplicate INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS organization_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                original_path TEXT NOT NULL,
                new_path      TEXT NOT NULL,
                action        TEXT NOT NULL,
                timestamp     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS duplicates (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                original_path   TEXT NOT NULL,
                duplicate_path  TEXT NOT NULL,
                hash_value      TEXT NOT NULL,
                size            INTEGER DEFAULT 0,
                detected_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS folder_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_at TEXT NOT NULL,
                total_files INTEGER DEFAULT 0,
                total_size  INTEGER DEFAULT 0,
                category    TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash_value);
            CREATE INDEX IF NOT EXISTS idx_files_category ON files(category);
            CREATE INDEX IF NOT EXISTS idx_files_date ON files(date_added);
        """)
        conn.commit()

    # ──────────────────────────────────────────────
    # File CRUD
    # ──────────────────────────────────────────────

    def upsert_file(self, file_name: str, file_path: str, category: str,
                    size: int, date_added: str, date_modified: str,
                    hash_value: str = "", is_duplicate: int = 0) -> int:
        """Insert or replace a file record. Returns the row id."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO files
                (file_name, file_path, category, size, date_added, date_modified, hash_value, is_duplicate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_name    = excluded.file_name,
                category     = excluded.category,
                size         = excluded.size,
                date_modified= excluded.date_modified,
                hash_value   = excluded.hash_value,
                is_duplicate = excluded.is_duplicate
        """, (file_name, file_path, category, size, date_added, date_modified, hash_value, is_duplicate))
        conn.commit()
        return cursor.lastrowid

    def get_all_files(self) -> List[Dict]:
        """Returns all file records as a list of dicts."""
        cursor = self._get_conn().cursor()
        cursor.execute("SELECT * FROM files ORDER BY date_added DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_files_by_category(self, category: str) -> List[Dict]:
        cursor = self._get_conn().cursor()
        cursor.execute("SELECT * FROM files WHERE category = ? ORDER BY size DESC", (category,))
        return [dict(row) for row in cursor.fetchall()]

    def search_files(self, query: str = "", extension: str = "",
                     min_size: int = 0, max_size: int = 0,
                     date_from: str = "", date_to: str = "") -> List[Dict]:
        """Full-featured search across name, extension, size and date."""
        conn = self._get_conn()
        sql = "SELECT * FROM files WHERE 1=1"
        params: List = []

        if query:
            sql += " AND file_name LIKE ?"
            params.append(f"%{query}%")
        if extension:
            sql += " AND file_name LIKE ?"
            params.append(f"%.{extension.lstrip('.')}")
        if min_size:
            sql += " AND size >= ?"
            params.append(min_size)
        if max_size:
            sql += " AND size <= ?"
            params.append(max_size)
        if date_from:
            sql += " AND date_added >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND date_added <= ?"
            params.append(date_to)

        sql += " ORDER BY date_added DESC LIMIT 500"
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def delete_file_record(self, file_path: str):
        conn = self._get_conn()
        conn.execute("DELETE FROM files WHERE file_path = ?", (file_path,))
        conn.commit()

    # ──────────────────────────────────────────────
    # Organization history
    # ──────────────────────────────────────────────

    def log_move(self, original_path: str, new_path: str, action: str = "MOVE"):
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO organization_history (original_path, new_path, action, timestamp)
            VALUES (?, ?, ?, ?)
        """, (original_path, new_path, action, datetime.now().isoformat()))
        conn.commit()

    def get_history(self, limit: int = 100) -> List[Dict]:
        cursor = self._get_conn().cursor()
        cursor.execute(
            "SELECT * FROM organization_history ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_last_move(self) -> Optional[Dict]:
        cursor = self._get_conn().cursor()
        cursor.execute(
            "SELECT * FROM organization_history WHERE action='MOVE' ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ──────────────────────────────────────────────
    # Duplicates
    # ──────────────────────────────────────────────

    def add_duplicate(self, original: str, duplicate: str, hash_val: str, size: int):
        conn = self._get_conn()
        conn.execute("""
            INSERT OR IGNORE INTO duplicates
                (original_path, duplicate_path, hash_value, size, detected_at)
            VALUES (?, ?, ?, ?, ?)
        """, (original, duplicate, hash_val, size, datetime.now().isoformat()))
        conn.commit()

    def get_duplicates(self) -> List[Dict]:
        cursor = self._get_conn().cursor()
        cursor.execute("SELECT * FROM duplicates ORDER BY detected_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def remove_duplicate_record(self, duplicate_path: str):
        conn = self._get_conn()
        conn.execute("DELETE FROM duplicates WHERE duplicate_path = ?", (duplicate_path,))
        conn.commit()

    def clear_duplicates(self):
        conn = self._get_conn()
        conn.execute("DELETE FROM duplicates")
        conn.commit()

    # ──────────────────────────────────────────────
    # Analytics
    # ──────────────────────────────────────────────

    def get_category_stats(self) -> List[Tuple]:
        """Returns (category, file_count, total_size) tuples."""
        cursor = self._get_conn().cursor()
        cursor.execute("""
            SELECT category, COUNT(*) as cnt, SUM(size) as total_size
            FROM files
            GROUP BY category
            ORDER BY cnt DESC
        """)
        return cursor.fetchall()

    def get_total_stats(self) -> Dict:
        cursor = self._get_conn().cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as total_files,
                COALESCE(SUM(size), 0) as total_size,
                COUNT(DISTINCT category) as categories,
                SUM(is_duplicate) as duplicates
            FROM files
        """)
        row = cursor.fetchone()
        return dict(row) if row else {}

    def get_largest_files(self, limit: int = 10) -> List[Dict]:
        cursor = self._get_conn().cursor()
        cursor.execute(
            "SELECT * FROM files ORDER BY size DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_files(self, limit: int = 10) -> List[Dict]:
        cursor = self._get_conn().cursor()
        cursor.execute(
            "SELECT * FROM files ORDER BY date_added DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def save_snapshot(self, total_files: int, total_size: int, category: str = "ALL"):
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO folder_snapshots (snapshot_at, total_files, total_size, category)
            VALUES (?, ?, ?, ?)
        """, (datetime.now().isoformat(), total_files, total_size, category))
        conn.commit()

    def get_snapshots(self, category: str = "ALL") -> List[Dict]:
        cursor = self._get_conn().cursor()
        cursor.execute("""
            SELECT * FROM folder_snapshots
            WHERE category = ?
            ORDER BY snapshot_at ASC
        """, (category,))
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
