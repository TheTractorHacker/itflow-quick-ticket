"""
ITFlow Quick Ticket - shared core

Platform-specific entry points (Windows/tray_app.py, Linux/tray_app.py,
macOS/tray_app.py) import this module and call run_app() with a list of
config file locations to check (in order of preference) and the path to
the tray/window icon image.

This module contains everything that is identical across platforms: config
loading, the ttk styling, the ticket popup window, and the tray icon /
event loop wiring.
"""

import io
import json
import os
import sys
import threading
import time

import requests
from PIL import Image, ImageDraw, ImageGrab, ImageTk
import pystray
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "ITFlow Quick Ticket"

ACCENT = "#2563eb"
ACCENT_DARK = "#1d4ed8"
BG = "#f4f6fb"
CARD_BG = "#ffffff"
BORDER = "#d7dce5"
TEXT_MUTED = "#5b6573"


def app_dir():
    """Directory containing the running script, or the PyInstaller binary."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # .../<Platform>/tray_app.py -> .../<Platform>
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def load_config(extra_paths):
    """Return the first config.json found among extra_paths, then app_dir()."""
    candidates = list(extra_paths) + [os.path.join(app_dir(), "config.json")]
    for path in candidates:
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["_source"] = path
            return cfg
    raise FileNotFoundError(
        "config.json not found. Checked:\n" + "\n".join(c for c in candidates if c)
    )


def build_tray_icon_image(icon_path):
    """Load the bundled tray icon, or fall back to a simple drawn one."""
    if icon_path and os.path.isfile(icon_path):
        return Image.open(icon_path)

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 3, size - 3], fill=(37, 99, 235, 255))
    draw.rectangle([14, 22, size - 15, size - 22], fill=(255, 255, 255, 255))
    return img


def setup_style(root):
    """Configure a clean, modern ttk theme shared by every window."""
    style = ttk.Style(root)
    for theme in ("clam",):
        try:
            style.theme_use(theme)
            break
        except tk.TclError:
            continue

    base_font = ("Segoe UI", 10)
    bold_font = ("Segoe UI", 10, "bold")
    title_font = ("Segoe UI Semibold", 13)

    root.option_add("*Font", base_font)

    style.configure(".", font=base_font, background=BG)
    style.configure("Card.TFrame", background=CARD_BG)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground="#1f2533")
    style.configure("Card.TLabel", background=CARD_BG, foreground="#1f2533")
    style.configure("Title.TLabel", background=BG, font=title_font, foreground="#1f2533")
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED)
    style.configure("Muted.Card.TLabel", background=CARD_BG, foreground=TEXT_MUTED)
    style.configure("FieldLabel.TLabel", background=BG, font=bold_font, foreground="#374151")

    style.configure(
        "TEntry",
        padding=8,
        relief="flat",
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        fieldbackground=CARD_BG,
    )
    style.map("TEntry", bordercolor=[("focus", ACCENT)])

    style.configure(
        "Accent.TButton",
        font=bold_font,
        background=ACCENT,
        foreground="white",
        borderwidth=0,
        padding=(12, 10),
    )
    style.map(
        "Accent.TButton",
        background=[("active", ACCENT_DARK), ("disabled", "#9db4e8")],
    )

    style.configure(
        "Secondary.TButton",
        font=base_font,
        background="#e9edf6",
        foreground="#1f2533",
        borderwidth=0,
        padding=(10, 8),
    )
    style.map(
        "Secondary.TButton",
        background=[("active", "#dbe2f0")],
    )

    return style


class TicketWindow:
    """The popup ticket-entry window. One instance reused per open."""

    def __init__(self, root, config, icon_path=None):
        self.root = root
        self.config = config
        self.icon_path = icon_path
        self.screenshot_bytes = None
        self.window = None
        self._header_img = None
        self._thumb_image = None

    def show(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return

        self.screenshot_bytes = None

        win = tk.Toplevel(self.root)
        win.title(APP_NAME)
        win.resizable(False, False)
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        if self.icon_path and os.path.isfile(self.icon_path):
            try:
                win.iconbitmap(self.icon_path)
            except tk.TclError:
                pass
        self.window = win

        outer = ttk.Frame(win, padding=20, style="TFrame")
        outer.pack(fill="both", expand=True)

        # Header: icon + title
        header = ttk.Frame(outer, style="TFrame")
        header.pack(fill="x", pady=(0, 16))

        if self.icon_path and os.path.isfile(self.icon_path):
            try:
                img = Image.open(self.icon_path)
                img = img.resize((32, 32))
                self._header_img = ImageTk.PhotoImage(img)
                ttk.Label(header, image=self._header_img, style="TLabel").pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_box = ttk.Frame(header, style="TFrame")
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="New Support Ticket", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="We'll get back to you as soon as possible", style="Muted.TLabel").pack(anchor="w")

        # Subject
        ttk.Label(outer, text="Subject", style="FieldLabel.TLabel").pack(anchor="w", pady=(0, 4))
        self.subject_entry = ttk.Entry(outer, width=46)
        self.subject_entry.pack(fill="x", pady=(0, 14))

        # Description
        ttk.Label(outer, text="Describe the issue", style="FieldLabel.TLabel").pack(anchor="w", pady=(0, 4))
        text_frame = tk.Frame(outer, bg=BORDER, padx=1, pady=1)
        text_frame.pack(fill="x", pady=(0, 14))
        self.details_text = tk.Text(
            text_frame,
            width=46,
            height=7,
            relief="flat",
            bg=CARD_BG,
            fg="#1f2533",
            insertbackground="#1f2533",
            font=("Segoe UI", 10),
            padx=8,
            pady=8,
            wrap="word",
        )
        self.details_text.pack(fill="both", expand=True)

        # Screenshot preview area
        preview_frame = tk.Frame(outer, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        preview_frame.pack(fill="x", pady=(0, 10))
        self.preview_label = tk.Label(
            preview_frame,
            text="No screenshot attached",
            fg=TEXT_MUTED,
            bg=CARD_BG,
            font=("Segoe UI", 9),
            height=6,
        )
        self.preview_label.pack(fill="both", expand=True, padx=2, pady=2)

        # Screenshot buttons
        btn_row = ttk.Frame(outer, style="TFrame")
        btn_row.pack(fill="x", pady=(0, 14))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self.screenshot_btn = ttk.Button(
            btn_row, text="Attach Screenshot", style="Secondary.TButton", command=self.take_screenshot
        )
        self.screenshot_btn.grid(row=0, column=0, sticky="we", padx=(0, 6))

        self.remove_btn = ttk.Button(
            btn_row, text="Remove Screenshot", style="Secondary.TButton", command=self.remove_screenshot, state="disabled"
        )
        self.remove_btn.grid(row=0, column=1, sticky="we", padx=(6, 0))

        # Status + submit
        self.status_label = ttk.Label(outer, text="", style="Muted.TLabel", wraplength=380)
        self.status_label.pack(fill="x", pady=(0, 8))

        self.submit_btn = ttk.Button(outer, text="Submit Ticket", style="Accent.TButton", command=self.submit)
        self.submit_btn.pack(fill="x")

        win.update_idletasks()
        # Center on screen
        w, h = win.winfo_width(), win.winfo_height()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        self.subject_entry.focus_set()

    def take_screenshot(self):
        # Hide our window so it isn't part of the capture
        self.window.withdraw()
        self.window.update()
        time.sleep(0.3)

        try:
            screenshot = ImageGrab.grab()
        except Exception as exc:
            self.window.deiconify()
            self.window.lift()
            messagebox.showerror(
                APP_NAME,
                "Couldn't capture a screenshot on this system:\n" + str(exc),
            )
            return
        finally:
            self.window.deiconify()
            self.window.lift()

        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        self.screenshot_bytes = buf.getvalue()

        thumb = screenshot.copy()
        thumb.thumbnail((300, 140))
        self._thumb_image = ImageTk.PhotoImage(thumb)
        self.preview_label.configure(image=self._thumb_image, text="")

        self.screenshot_btn.configure(text="Retake Screenshot")
        self.remove_btn.configure(state="normal")

    def remove_screenshot(self):
        self.screenshot_bytes = None
        self._thumb_image = None
        self.preview_label.configure(image="", text="No screenshot attached")
        self.screenshot_btn.configure(text="Attach Screenshot")
        self.remove_btn.configure(state="disabled")

    def submit(self):
        subject = self.subject_entry.get().strip()
        details = self.details_text.get("1.0", "end").strip()

        if not subject:
            messagebox.showwarning(APP_NAME, "Please enter a subject.")
            return

        self.submit_btn.configure(state="disabled", text="Submitting...")
        self.status_label.configure(text="", style="Muted.TLabel")
        self.window.update()

        threading.Thread(
            target=self._submit_worker, args=(subject, details), daemon=True
        ).start()

    def _submit_worker(self, subject, details):
        try:
            self._send_ticket(subject, details)
            self.window.after(0, self._submit_success)
        except Exception as exc:
            self.window.after(0, self._submit_error, str(exc))

    def _send_ticket(self, subject, details):
        cfg = self.config
        base_url = cfg["itflow_base_url"].rstrip("/")
        url = f"{base_url}/api/v1/tickets"

        data = {
            "subject": subject,
            "details": details,
            "client_id": cfg["client_id"],
            "priority": cfg.get("priority", "Medium"),
        }
        if cfg.get("contact_id"):
            data["contact_id"] = cfg["contact_id"]

        files = None
        if self.screenshot_bytes:
            files = {"file": ("screenshot.png", self.screenshot_bytes, "image/png")}

        resp = requests.post(
            url,
            params={"api_key": cfg["api_key"]},
            data=data,
            files=files,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _submit_success(self):
        self.status_label.configure(text="Ticket submitted successfully!", style="Card.TLabel", foreground="#15803d")
        self.window.update()
        self.window.after(1500, self._close)

    def _submit_error(self, message):
        self.submit_btn.configure(state="normal", text="Submit Ticket")
        self.status_label.configure(text=f"Failed to submit: {message}", style="Card.TLabel", foreground="#b91c1c")

    def _close(self):
        if self.window is not None:
            self.window.destroy()
            self.window = None


def run_app(config_paths, icon_path=None):
    """Load config, build the tray icon + menu, and run the event loop.

    config_paths: list of config.json locations to check, in order of
                   preference (app_dir()/config.json is always checked last).
    icon_path:     path to the tray/window icon image (.ico or .png).
    """
    try:
        config = load_config(config_paths)
    except Exception as exc:
        # Show a one-off error dialog; the user has no way to fix config
        # themselves so just inform them clearly.
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, str(exc))
        sys.exit(1)

    root = tk.Tk()
    root.withdraw()  # hidden root, used only to host Toplevel windows
    setup_style(root)

    ticket_window = TicketWindow(root, config, icon_path=icon_path)

    def open_window(icon=None, item=None):
        root.after(0, ticket_window.show)

    def quit_app(icon, item):
        icon.stop()
        root.after(0, root.quit)

    menu = pystray.Menu(
        pystray.MenuItem("New Ticket", open_window, default=True),
        pystray.MenuItem("Exit", quit_app),
    )

    icon = pystray.Icon(APP_NAME, build_tray_icon_image(icon_path), APP_NAME, menu)

    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()

    root.mainloop()
