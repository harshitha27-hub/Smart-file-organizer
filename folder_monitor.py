"""
Folder Monitor Module
=====================
Real-time folder monitoring using the watchdog library.
Automatically organizes newly created files and logs all events.
"""

import os
import time
import threading
from typing import Optional, Callable

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from modules.logger import AppLogger
from modules.file_organizer import FileOrganizer, _ext_to_category


class _FileHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """
    Handles filesystem events for a monitored directory.
    On file creation, waits for the file to be fully written then organizes it.
    """

    def __init__(self, watch_dir: str,
                 event_callback: Optional[Callable] = None,
                 organizer: Optional[FileOrganizer] = None):
        if WATCHDOG_AVAILABLE:
            super().__init__()
        self.watch_dir = watch_dir
        self.event_cb = event_callback or (lambda *a: None)
        self.organizer = organizer or FileOrganizer()
        self.log = AppLogger()
        self._pending: set = set()
        self._lock = threading.Lock()

    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        # Debounce – wait for write to finish
        threading.Thread(target=self._handle_new_file, args=(path,), daemon=True).start()

    def _handle_new_file(self, path: str):
        """Wait until the file is fully written, then organize it."""
        with self._lock:
            if path in self._pending:
                return
            self._pending.add(path)

        try:
            # Poll size stability for up to 5 s
            prev_size = -1
            for _ in range(10):
                time.sleep(0.5)
                if not os.path.exists(path):
                    return
                size = os.path.getsize(path)
                if size == prev_size:
                    break
                prev_size = size

            if not os.path.exists(path):
                return

            ext = os.path.splitext(path)[1]
            category = _ext_to_category(ext)
            dest_dir = os.path.join(self.watch_dir, category)
            os.makedirs(dest_dir, exist_ok=True)

            dest_path = os.path.join(dest_dir, os.path.basename(path))
            if os.path.exists(dest_path):
                return  # Already organized

            import shutil
            shutil.move(path, dest_path)
            msg = f"Auto-organized: {os.path.basename(path)} → {category}/"
            self.log.log_monitor_event("CREATED+MOVED", path)
            self.event_cb(msg, dest_path, category)

        except Exception as exc:
            self.log.error(f"Monitor handler error for '{path}': {exc}")
        finally:
            with self._lock:
                self._pending.discard(path)

    def on_moved(self, event):
        if event.is_directory:
            return
        msg = f"Moved: {os.path.basename(event.src_path)} → {os.path.basename(event.dest_path)}"
        self.log.log_monitor_event("MOVED", event.src_path)
        self.event_cb(msg, event.dest_path, "")

    def on_deleted(self, event):
        if event.is_directory:
            return
        msg = f"Deleted: {os.path.basename(event.src_path)}"
        self.log.log_monitor_event("DELETED", event.src_path)
        self.event_cb(msg, event.src_path, "")


class FolderMonitor:
    """
    Starts and stops a watchdog Observer for a given directory.

    Parameters
    ----------
    event_callback : callable(message: str, path: str, category: str)
        Fired on every relevant filesystem event.
    """

    def __init__(self, event_callback: Optional[Callable] = None):
        self.event_cb = event_callback or (lambda *a: None)
        self.log = AppLogger()
        self._observer: Optional["Observer"] = None
        self._watch_dir: str = ""
        self.is_running = False

    def start(self, watch_dir: str) -> bool:
        """
        Begin monitoring *watch_dir*.  Returns True if successful.
        """
        if not WATCHDOG_AVAILABLE:
            self.log.error("watchdog library not installed – monitoring disabled.")
            return False

        if self.is_running:
            self.stop()

        if not os.path.isdir(watch_dir):
            return False

        self._watch_dir = watch_dir
        handler = _FileHandler(watch_dir, event_callback=self.event_cb)
        self._observer = Observer()
        self._observer.schedule(handler, watch_dir, recursive=False)
        self._observer.start()
        self.is_running = True
        self.log.info(f"Monitoring started: '{watch_dir}'")
        return True

    def stop(self):
        """Stop the active observer."""
        if self._observer and self.is_running:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None
            self.is_running = False
            self.log.info(f"Monitoring stopped: '{self._watch_dir}'")

    def __del__(self):
        self.stop()
