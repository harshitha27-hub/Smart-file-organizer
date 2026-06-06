"""
Smart File Organizer
====================
Main application entry point. Bootstraps the CustomTkinter window,
builds the sidebar, and manages page navigation.

Run:
    python main.py
"""

import sys
import os

# ── Ensure project root is on the Python path ─────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tkinter as tk
import customtkinter as ctk

# ── Apply global theme before any widgets are created ─────────────────────────
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# ── Page imports ──────────────────────────────────────────────────────────────
from gui.dashboard  import DashboardPage
from gui.organizer  import OrganizerPage
from gui.monitor    import MonitorPage
from gui.analytics  import AnalyticsPage
from gui.reports    import ReportsPage
from gui.settings   import SettingsPage
from modules.logger import AppLogger


# ── Constants ─────────────────────────────────────────────────────────────────
APP_NAME    = "Smart File Organizer"
WIN_W, WIN_H = 1280, 800
SIDEBAR_W   = 220

# Sidebar nav items: (label, icon, page_class)
NAV_ITEMS = [
    ("Dashboard",  "📊", DashboardPage),
    ("Organizer",  "📂", OrganizerPage),
    ("Monitor",    "📡", MonitorPage),
    ("Analytics",  "📈", AnalyticsPage),
    ("Reports",    "📄", ReportsPage),
    ("Settings",   "⚙",  SettingsPage),
]

ACCENT       = "#6C63FF"
SIDEBAR_BG   = "#0D0D1A"
CONTENT_BG   = "#12122A"
HOVER_BG     = "#1E1E3A"
ACTIVE_BG    = "#2A2A4A"
TEXT_NORMAL  = "#9999BB"
TEXT_ACTIVE  = "#FFFFFF"


class SidebarButton(ctk.CTkFrame):
    """
    A custom sidebar navigation button with icon, label, and active state.
    """

    def __init__(self, parent, icon: str, label: str,
                 on_click=None, **kwargs):
        super().__init__(parent, fg_color="transparent",
                         corner_radius=12, cursor="hand2", **kwargs)
        self._active   = False
        self._on_click = on_click

        self._icon_lbl = ctk.CTkLabel(
            self, text=icon,
            font=ctk.CTkFont(size=20),
            text_color=TEXT_NORMAL, width=36,
        )
        self._icon_lbl.pack(side="left", padx=(12, 6), pady=12)

        self._text_lbl = ctk.CTkLabel(
            self, text=label,
            font=ctk.CTkFont(size=13),
            text_color=TEXT_NORMAL, anchor="w",
        )
        self._text_lbl.pack(side="left", fill="x", expand=True)

        # Bind click + hover on all children
        for w in (self, self._icon_lbl, self._text_lbl):
            w.bind("<Button-1>",  self._click)
            w.bind("<Enter>",     self._hover_on)
            w.bind("<Leave>",     self._hover_off)

    def set_active(self, active: bool):
        self._active = active
        color  = TEXT_ACTIVE  if active else TEXT_NORMAL
        bg     = ACTIVE_BG    if active else "transparent"
        self._icon_lbl.configure(text_color=color)
        self._text_lbl.configure(text_color=color)
        self.configure(fg_color=bg)

    def _click(self, _event=None):
        if self._on_click:
            self._on_click()

    def _hover_on(self, _event=None):
        if not self._active:
            self.configure(fg_color=HOVER_BG)

    def _hover_off(self, _event=None):
        if not self._active:
            self.configure(fg_color="transparent")


class SmartFileOrganizerApp(ctk.CTk):
    """
    Root application window.
    Manages the sidebar, page container, and page lifecycle.
    """

    def __init__(self):
        super().__init__()
        self.log = AppLogger()
        self.log.info("Application started.")

        self._setup_window()
        self._build_ui()
        self._navigate(0)   # Start on Dashboard

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title(APP_NAME)
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(900, 600)
        self.configure(fg_color=CONTENT_BG)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - WIN_W) // 2
        y = (self.winfo_screenheight() - WIN_H) // 2
        self.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Root grid: sidebar | content
        self.columnconfigure(0, minsize=SIDEBAR_W)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Sidebar ───────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self, fg_color=SIDEBAR_BG,
                               corner_radius=0, width=SIDEBAR_W)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # Logo / title area
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(24, 16))

        ctk.CTkLabel(logo_frame, text="🗂",
                     font=ctk.CTkFont(size=32)).pack(anchor="w")
        ctk.CTkLabel(logo_frame, text="Smart File\nOrganizer",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#E0E0E0", justify="left").pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(logo_frame, text="v1.0.0",
                     font=ctk.CTkFont(size=10),
                     text_color="#444466").pack(anchor="w")

        # Divider
        ctk.CTkFrame(sidebar, height=1, fg_color="#1E1E3A").pack(fill="x", padx=12, pady=8)

        # Nav buttons
        nav_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        nav_scroll.pack(fill="both", expand=True, padx=8, pady=4)

        self._nav_btns: list[SidebarButton] = []
        for i, (label, icon, _cls) in enumerate(NAV_ITEMS):
            btn = SidebarButton(nav_scroll, icon=icon, label=label,
                                on_click=lambda idx=i: self._navigate(idx))
            btn.pack(fill="x", pady=2)
            self._nav_btns.append(btn)

        # Bottom accent bar
        ctk.CTkFrame(sidebar, height=3, fg_color=ACCENT).pack(side="bottom",
                                                               fill="x")
        ctk.CTkLabel(sidebar, text="© 2024 SFO",
                     font=ctk.CTkFont(size=9),
                     text_color="#333355").pack(side="bottom", pady=4)

        # ── Content area ──────────────────────────────────────────────────────
        content_outer = ctk.CTkFrame(self, fg_color=CONTENT_BG, corner_radius=0)
        content_outer.grid(row=0, column=1, sticky="nsew")
        content_outer.columnconfigure(0, weight=1)
        content_outer.rowconfigure(1, weight=1)

        # Top bar
        top_bar = ctk.CTkFrame(content_outer, fg_color=SIDEBAR_BG,
                               height=54, corner_radius=0)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_propagate(False)

        self._page_title = ctk.CTkLabel(top_bar, text="Dashboard",
                                         font=ctk.CTkFont(size=16, weight="bold"),
                                         text_color="#E0E0E0")
        self._page_title.pack(side="left", padx=20, pady=14)

        # Notification bell (visual only)
        ctk.CTkLabel(top_bar, text="🔔",
                     font=ctk.CTkFont(size=16),
                     text_color="#555577").pack(side="right", padx=20)

        # Page container
        self._page_container = ctk.CTkFrame(content_outer,
                                             fg_color=CONTENT_BG,
                                             corner_radius=0)
        self._page_container.grid(row=1, column=0, sticky="nsew",
                                   padx=24, pady=16)
        self._page_container.columnconfigure(0, weight=1)
        self._page_container.rowconfigure(0, weight=1)

        self._current_page = None
        self._page_cache: dict = {}

    # ── Navigation ────────────────────────────────────────────────────────────

    def _navigate(self, index: int):
        label, icon, PageClass = NAV_ITEMS[index]

        # Update active button state
        for i, btn in enumerate(self._nav_btns):
            btn.set_active(i == index)

        # Update top bar title
        self._page_title.configure(text=f"{icon}  {label}")

        # Hide current page
        if self._current_page:
            self._current_page.pack_forget()

        # Retrieve or create the page
        if index not in self._page_cache:
            page = PageClass(self._page_container)
            page.grid(row=0, column=0, sticky="nsew")
            self._page_cache[index] = page
        else:
            page = self._page_cache[index]
            page.grid(row=0, column=0, sticky="nsew")

        # Refresh dashboard when revisiting
        if hasattr(page, "refresh") and index == 0:
            page.refresh()

        self._current_page = page
        self.log.debug(f"Navigated to: {label}")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _on_close(self):
        # Stop any active monitor
        monitor_page = self._page_cache.get(2)
        if monitor_page and hasattr(monitor_page, "on_destroy"):
            monitor_page.on_destroy()

        self.log.info("Application closed.")
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    """Launch the Smart File Organizer application."""
    # Ensure required directories exist
    for d in ("database", "reports", "logs", "assets"):
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)

    app = SmartFileOrganizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
