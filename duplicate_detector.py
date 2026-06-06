"""
Duplicate Detector Module
=========================
Finds duplicate files using SHA-256 hashing with multi-threaded scanning.
Groups files by hash and reports originals vs duplicates with size savings.
"""

import os
import hashlib
from typing import Dict, List, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

from modules.database import DatabaseManager
from modules.logger import AppLogger


def _file_hash(path: str, chunk: int = 65536) -> Optional[str]:
    """Compute SHA-256 of a file. Returns None on read error."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                buf = f.read(chunk)
                if not buf:
                    break
                h.update(buf)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


class DuplicateDetector:
    """
    Scans a directory (recursively) to identify duplicate files by content hash.

    Parameters
    ----------
    progress_callback : callable(int, int)
        Called with (files_done, total_files) during scanning.
    status_callback : callable(str)
        Called with status messages.
    """

    def __init__(self,
                 progress_callback: Optional[Callable] = None,
                 status_callback: Optional[Callable] = None):
        self.db = DatabaseManager()
        self.log = AppLogger()
        self.progress_cb = progress_callback or (lambda *a: None)
        self.status_cb = status_callback or (lambda *a: None)

    def scan(self, directory: str, max_workers: int = 6) -> List[Dict]:
        """
        Scan *directory* and return a list of duplicate groups.

        Each group dict has:
            hash_value, original, duplicates (list of paths), size, savings
        """
        if not os.path.isdir(directory):
            raise ValueError(f"Not a directory: {directory}")

        self.db.clear_duplicates()
        files = self._collect_files(directory)
        total = len(files)
        self.status_cb(f"Hashing {total} files…")

        hash_map: Dict[str, List[str]] = defaultdict(list)
        done = 0

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {pool.submit(_file_hash, fp): fp for fp in files}
            for future in as_completed(future_map):
                fp = future_map[future]
                done += 1
                self.progress_cb(done, total)
                h = future.result()
                if h:
                    hash_map[h].append(fp)

        # Build duplicate groups (any hash with > 1 file)
        groups = []
        for h, paths in hash_map.items():
            if len(paths) < 2:
                continue

            # Sort by modification time – oldest is "original"
            paths.sort(key=lambda p: os.path.getmtime(p))
            original = paths[0]
            duplicates = paths[1:]
            size = os.path.getsize(original) if os.path.exists(original) else 0

            group = {
                "hash_value": h,
                "original": original,
                "duplicates": duplicates,
                "size": size,
                "savings": size * len(duplicates),
            }
            groups.append(group)

            # Persist to DB
            for dup in duplicates:
                self.db.add_duplicate(original, dup, h, size)
                # Mark in files table
                self.db.upsert_file(
                    file_name=os.path.basename(dup),
                    file_path=dup,
                    category="",
                    size=size,
                    date_added="",
                    date_modified="",
                    hash_value=h,
                    is_duplicate=1,
                )

        self.status_cb(f"Found {len(groups)} duplicate group(s).")
        self.log.info(f"Duplicate scan on '{directory}': {len(groups)} groups found.")
        return groups

    def delete_duplicates(self, groups: List[Dict],
                          delete_callback: Optional[Callable] = None) -> Tuple[int, int]:
        """
        Safely delete all duplicate files (keeps originals).

        Returns (deleted_count, bytes_freed).
        """
        deleted = 0
        freed = 0

        for group in groups:
            for dup_path in group["duplicates"]:
                if not os.path.exists(dup_path):
                    continue
                try:
                    size = os.path.getsize(dup_path)
                    os.remove(dup_path)
                    freed += size
                    deleted += 1
                    self.db.remove_duplicate_record(dup_path)
                    self.db.delete_file_record(dup_path)
                    self.log.log_delete(dup_path, reason="duplicate")
                    if delete_callback:
                        delete_callback(dup_path)
                except (OSError, PermissionError) as exc:
                    self.log.error(f"Could not delete duplicate '{dup_path}': {exc}")

        return deleted, freed

    # ── Internal ───────────────────────────────────────────────────────────────

    def _collect_files(self, directory: str) -> List[str]:
        files = []
        for root, _, filenames in os.walk(directory):
            for fname in filenames:
                fp = os.path.join(root, fname)
                if os.path.isfile(fp):
                    files.append(fp)
        return files
