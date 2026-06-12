"""
ITFlow Quick Ticket - Windows tray app

Lets end users submit an ITFlow support ticket (with an optional full-screen
screenshot) in a few clicks, without logging in to the client portal.

Configuration is read from (in order of preference):
  1. %ProgramData%\\ITFlowQuickTicket\\config.json
  2. config.json next to this script / the packaged .exe

See config.json for the expected fields.
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
from tkinter import messagebox

APP_NAME = "ITFlow Quick Ticket"


def app_dir():
    """Directory containing this script, or the PyInstaller .exe."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def config_paths():
    paths = []
    program_data = os.environ.get("ProgramData")
    if program_data:
        paths.append(os.path.join(program_data, "ITFlowQuickTicket", "config.json"))
    paths.append(os.path.join(app_dir(), "config.json"))
    return paths


def load_config():
    for path in config_paths():
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["_source"] = path
            return cfg
    raise FileNotFoundError(
        "config.json not found. Checked:\n" + "\n".join(config_paths())
    )


def build_tray_icon_image():
    """Generate a simple fallback tray icon (a blue square with 'IT')."""
    icon_path = os.path.join(app_dir(), "assets", "icon.ico")
    if os.path.isfile(icon_path):
        return Image.open(icon_path)

    size = 64
    img = Image.new("RGB", (size, size), (0, 123, 198))
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, size - 5, size - 5], outline=(255, 255, 255), width=3)
    draw.text((14, 18), "IT", fill=(255, 255, 255))
    return img


class TicketWindow:
    """The popup ticket-entry window. One instance reused per open."""

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.screenshot_bytes = None
        self.window = None

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
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self.window = win

        pad = {"padx": 10, "pady": 4}

        tk.Label(win, text="Subject", anchor="w").grid(row=0, column=0, sticky="w", **pad)
        self.subject_entry = tk.Entry(win, width=50)
        self.subject_entry.grid(row=1, column=0, columnspan=2, sticky="we", **pad)

        tk.Label(win, text="Describe the issue", anchor="w").grid(row=2, column=0, sticky="w", **pad)
        self.details_text = tk.Text(win, width=50, height=8)
        self.details_text.grid(row=3, column=0, columnspan=2, sticky="we", **pad)

        # Screenshot preview area
        self.preview_label = tk.Label(win, text="(no screenshot attached)", relief="groove", width=40, height=6)
        self.preview_label.grid(row=4, column=0, columnspan=2, sticky="we", **pad)

        self.screenshot_btn = tk.Button(win, text="Attach Screenshot", command=self.take_screenshot)
        self.screenshot_btn.grid(row=5, column=0, sticky="we", **pad)

        self.remove_btn = tk.Button(win, text="Remove Screenshot", command=self.remove_screenshot, state="disabled")
        self.remove_btn.grid(row=5, column=1, sticky="we", **pad)

        self.status_label = tk.Label(win, text="", fg="green")
        self.status_label.grid(row=6, column=0, columnspan=2, sticky="we", **pad)

        self.submit_btn = tk.Button(win, text="Submit", command=self.submit, bg="#007bc6", fg="white")
        self.submit_btn.grid(row=7, column=0, columnspan=2, sticky="we", **pad)

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
        finally:
            self.window.deiconify()
            self.window.lift()

        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        self.screenshot_bytes = buf.getvalue()

        thumb = screenshot.copy()
        thumb.thumbnail((240, 135))
        self.thumb_image = ImageTk.PhotoImage(thumb)
        self.preview_label.configure(image=self.thumb_image, text="")

        self.screenshot_btn.configure(text="Retake Screenshot")
        self.remove_btn.configure(state="normal")

    def remove_screenshot(self):
        self.screenshot_bytes = None
        self.preview_label.configure(image="", text="(no screenshot attached)")
        self.screenshot_btn.configure(text="Attach Screenshot")
        self.remove_btn.configure(state="disabled")

    def submit(self):
        subject = self.subject_entry.get().strip()
        details = self.details_text.get("1.0", "end").strip()

        if not subject:
            messagebox.showwarning(APP_NAME, "Please enter a subject.")
            return

        self.submit_btn.configure(state="disabled", text="Submitting...")
        self.status_label.configure(text="", fg="green")
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
        self.status_label.configure(text="Ticket submitted successfully!", fg="green")
        self.window.update()
        self.window.after(1500, self._close)

    def _submit_error(self, message):
        self.submit_btn.configure(state="normal", text="Submit")
        self.status_label.configure(text=f"Failed to submit: {message}", fg="red")

    def _close(self):
        if self.window is not None:
            self.window.destroy()
            self.window = None


def main():
    try:
        config = load_config()
    except Exception as exc:
        # Show a one-off error dialog; the user has no way to fix config
        # themselves so just inform them clearly.
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, str(exc))
        sys.exit(1)

    root = tk.Tk()
    root.withdraw()  # hidden root, used only to host Toplevel windows

    ticket_window = TicketWindow(root, config)

    def open_window(icon=None, item=None):
        root.after(0, ticket_window.show)

    def quit_app(icon, item):
        icon.stop()
        root.after(0, root.quit)

    menu = pystray.Menu(
        pystray.MenuItem("New Ticket", open_window, default=True),
        pystray.MenuItem("Exit", quit_app),
    )

    icon = pystray.Icon(APP_NAME, build_tray_icon_image(), APP_NAME, menu)

    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()

    root.mainloop()


if __name__ == "__main__":
    main()
