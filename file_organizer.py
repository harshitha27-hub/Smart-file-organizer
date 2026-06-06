"""
File Organizer Module
=====================
Core engine that scans a folder, categorizes files by extension,
moves them into sub-folders, and records everything in the database.
Supports undo of the last batch move and automatic backup.
"""

import os
import shutil
import hashlib
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from modules.database import DatabaseManager
from modules.logger import AppLogger


# ── Category → extension mapping ──────────────────────────────────────────────

CATEGORIES: Dict[str, List[str]] = {
    "Documents":  [".pdf", ".docx", ".doc", ".txt", ".pptx", ".ppt",
                   ".xlsx", ".xls", ".odt", ".rtf", ".md", ".csv"],
    "Images":     [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
                   ".svg", ".ico", ".tiff", ".raw", ".heic"],
    "Videos":     [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
                   ".webm", ".m4v", ".3gp"],
    "Audio":      [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a",
                   ".wma", ".opus"],
    "Archives":   [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
                   ".xz", ".iso"],
    "Programs":   [".exe", ".msi", ".dmg", ".deb", ".rpm", ".apk",
                   ".sh", ".bat"],
    "Code":       [".py", ".js", ".ts", ".html", ".css", ".java",
                   ".cpp", ".c", ".h", ".json", ".xml", ".yaml",
                   ".yml", ".sql", ".php", ".rb", ".go", ".rs"],
    "Other":      [],
}


def _ext_to_category(ext: str) -> str:
    ext = ext.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "Other"


def _file_hash(path: str, chunk: int = 65536) -> str:
    """SHA-256 hash of a file, reading in chunks for large files."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                buf = f.read(chunk)
                if not buf:
                    break
                h.update(buf)
    except (OSError, PermissionError):
        return ""
    return h.hexdigest()


class FileOrganizer:
    """
    Organizes files from a source directory into categorized sub-folders.

    Parameters
    ----------
    progress_callback : callable(int, int, str)
        Called with (files_done, total_files, current_file_name) during processing.
    status_callback : callable(str)
        Called with a status message string.
    """

    def __init__(self,
                 progress_callback: Optional[Callable] = None,
                 status_callback: Optional[Callable] = None):
        self.db = DatabaseManager()
        self.log = AppLogger()
        self.progress_cb = progress_callback or (lambda *a: None)
        self.status_cb = status_callback or (lambda *a: None)
        self._cancelled = threading.Event()

    # ── Public API ─────────────────────────────────────────────────────────────

    def organize(self, source_dir: str,
                 backup: bool = False,
                 max_workers: int = 4) -> Dict:
        """
        Organize all files in *source_dir* into sub-folders.

        Returns a summary dict: {moved, skipped, errors, categories}.
        """
        if not os.path.isdir(source_dir):
            raise ValueError(f"Not a valid directory: {source_dir}")

        self._cancelled.clear()

        if backup:
            self._create_backup(source_dir)

        files = self._collect_files(source_dir)
        total = len(files)
        self.status_cb(f"Found {total} files. Organizing…")
        self.db.save_snapshot(total, sum(os.path.getsize(f) for f in files if os.path.exists(f)))

        summary = {"moved": 0, "skipped": 0, "errors": 0, "categories": set()}
        lock = threading.Lock()

        def _process(fp: str) -> Tuple[str, str]:
            if self._cancelled.is_set():
                return ("cancelled", fp)
            try:
                moved_to = self._move_file(fp, source_dir)
                return ("moved", moved_to)
            except Exception as exc:
                self.log.error(f"Error processing {fp}: {exc}")
                return ("error", fp)

        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_process, f): f for f in files}
            for future in as_completed(futures):
                result, path = future.result()
                done += 1
                with lock:
                    if result == "moved":
                        summary["moved"] += 1
                    elif result == "error":
                        summary["errors"] += 1
                    else:
                        summary["skipped"] += 1
                self.progress_cb(done, total, os.path.basename(path))

        self.status_cb("Organization complete!")
        self.log.info(f"Organized '{source_dir}': {summary}")
        return summary

    def cancel(self):
        """Signal the organizer to stop after the current file."""
        self._cancelled.set()

    def undo_last_move(self) -> bool:
        """
        Reverses the most recent MOVE recorded in the database.
        Returns True on success.
        """
        record = self.db.get_last_move()
        if not record:
            return False

        src = record["new_path"]
        dst = record["original_path"]

        if not os.path.exists(src):
            self.log.warning(f"Undo failed – file no longer at: {src}")
            return False

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            self.db.log_move(src, dst, action="UNDO")
            self.db.delete_file_record(src)
            self.log.info(f"UNDO: '{src}' → '{dst}'")
            return True
        except Exception as exc:
            self.log.error(f"Undo failed: {exc}")
            return False

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _collect_files(self, directory: str) -> List[str]:
        """Return all files directly inside *directory* (non-recursive)."""
        files = []
        try:
            for entry in os.scandir(directory):
                if entry.is_file(follow_symlinks=False):
                    files.append(entry.path)
        except PermissionError as exc:
            self.log.error(f"Permission denied: {exc}")
        return files

    def _move_file(self, file_path: str, source_dir: str) -> str:
        """Move a single file to its category sub-folder."""
        ext = os.path.splitext(file_path)[1]
        category = _ext_to_category(ext)
        dest_dir = os.path.join(source_dir, category)
        os.makedirs(dest_dir, exist_ok=True)

        dest_path = os.path.join(dest_dir, os.path.basename(file_path))

        # Avoid overwriting – append counter suffix
        if os.path.exists(dest_path):
            base, suffix = os.path.splitext(dest_path)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = f"{base}_{counter}{suffix}"
                counter += 1

        shutil.move(file_path, dest_path)

        # Record in DB
        stat = os.stat(dest_path)
        h = _file_hash(dest_path)
        self.db.upsert_file(
            file_name=os.path.basename(dest_path),
            file_path=dest_path,
            category=category,
            size=stat.st_size,
            date_added=datetime.now().isoformat(),
            date_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            hash_value=h,
        )
        self.db.log_move(file_path, dest_path)
        self.log.log_move(file_path, dest_path)
        return dest_path

    def _create_backup(self, source_dir: str):
        """Copy entire source_dir to a timestamped backup sibling folder."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        parent = os.path.dirname(source_dir)
        name = os.path.basename(source_dir)
        backup_path = os.path.join(parent, f"{name}_backup_{ts}")
        self.status_cb(f"Creating backup at {backup_path}…")
        try:
            shutil.copytree(source_dir, backup_path)
            self.log.info(f"Backup created: {backup_path}")
        except Exception as exc:
            self.log.error(f"Backup failed: {exc}")


def scan_directory(directory: str) -> List[Dict]:
    """
    Lightweight scan: returns file metadata list without moving anything.
    Used by analytics and the dashboard.
    """
    results = []
    if not os.path.isdir(directory):
        return results

    for root, _, files in os.walk(directory):
        for fname in files:
            fp = os.path.join(root, fname)
            try:
                stat = os.stat(fp)
                ext = os.path.splitext(fname)[1]
                results.append({
                    "file_name": fname,
                    "file_path": fp,
                    "category": _ext_to_category(ext),
                    "size": stat.st_size,
                    "date_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except OSError:
                continue
    return results
