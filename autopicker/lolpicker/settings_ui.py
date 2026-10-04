"""Transactional hotkey rebinding with visible conflicts, not silent fallback."""
import tkinter as tk
from tkinter import ttk
from .hotkeys import combo_from_event, display_combo
from .storage import DEFAULT_HOTKEYS

LABELS = {"toggle_overlay": "Overlay ein/aus", "open_lolalytics": "Lolalytics öffnen",
          "open_vs": "VS-Matchup öffnen", "close_tab": "Tab speichern & schließen",
          "close_all_browsers": "Alle verwalteten Tabs schließen"}


class SettingsWindow:
    def __init__(self, app):
        from .ui import BG, PANEL, TEXT, GOLD, button
        self.app, self.recording = app, None
        self.win = tk.Toplevel(app.root)
        self.win.title("Einstellungen · LoL Autopicker")
        self.win.configure(bg=BG)
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        body = tk.Frame(self.win, bg=BG, padx=16, pady=16)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="EINSTELLUNGEN", bg=BG, fg=GOLD, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(body, text="Kürzel anklicken und neue Kombination drücken. ESC bricht ab.",
                 bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 12))
        self.buttons = {}
        for action, label in LABELS.items():
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(side="left")
            b = button(row, "", lambda a=action: self.start_recording(a), width=24)
            b.pack(side="right", padx=(16, 0))
            self.buttons[action] = b
        self.info = tk.Label(body, text="", bg=BG, fg=GOLD, wraplength=480, justify="left", font=("Segoe UI", 9))
        self.info.pack(fill="x", pady=8)
        button(body, "Standardkürzel wiederherstellen", lambda: self.commit(DEFAULT_HOTKEYS.copy())).pack(anchor="w", pady=(0, 10))
        values = app.controller.settings.snapshot()
        for key, label in (("live_tracking", "Live-URL-Tracking · gleicher Champion"),
                           ("weak_pc_mode", "Sparmodus · verwaltete Tabs bei Spielstart schließen"),
                           ("debug_mode", "Diagnoseprotokoll aktivieren")):
            variable = tk.BooleanVar(value=values[key])
            tk.Checkbutton(body, text=label, variable=variable, command=lambda k=key, v=variable: app.toggle(k, v),
                           bg=BG, fg=TEXT, selectcolor=PANEL, activebackground=BG, activeforeground=TEXT,
                           font=("Segoe UI", 9)).pack(anchor="w", pady=3)
        tk.Label(body, text="Sparmodus beendet keine fremden Tabs oder Browserprozesse.", bg=BG, fg=GOLD,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 12))
        tk.Label(body, text="Zielbrowser (alternativ auf das Erweiterungssymbol klicken)", bg=BG, fg=TEXT).pack(anchor="w")
        self.clients = app.controller.bridge.listing()
        self.browser = ttk.Combobox(body, state="readonly", values=["Automatisch · nur bei genau einem Browser"] + list(self.clients.values()), width=55)
        current = self.clients.get(values["preferred_browser"], "")
        self.browser.set(current or "Automatisch · nur bei genau einem Browser")
        self.browser.pack(fill="x", pady=6)
        self.browser.bind("<<ComboboxSelected>>", self.select_browser)
        tk.Label(body, text="Optional: kompletter League-Lockfile-Pfad bei Erkennungsproblemen", bg=BG, fg=TEXT).pack(anchor="w", pady=(10, 0))
        self.lockfile = tk.Entry(body, width=55)
        self.lockfile.insert(0, values["lockfile_path"])
        self.lockfile.pack(fill="x", pady=6)
        button(body, "Pfad speichern", lambda: app.update_settings(lockfile_path=self.lockfile.get().strip())).pack(anchor="w")
        tk.Label(body, text="Autostart: Autostart_aktivieren.bat / Autostart_entfernen.bat\nDaten und Logs: %LOCALAPPDATA%\\LoLAutopicker",
                 bg=BG, fg=GOLD, justify="left", font=("Segoe UI", 9)).pack(anchor="w", pady=(14, 0))
        self.win.bind("<KeyPress>", self.on_key)
        self.refresh()

    def refresh(self):
        configured = self.app.controller.settings.snapshot()["hotkeys"]
        for action, button in self.buttons.items():
            text = display_combo(configured[action])
            if configured[action] and action not in self.app.hotkeys.ids.values():
                text += " · INAKTIV"
            button.config(text=text)

    def start_recording(self, action):
        self.cancel_recording()
        self.recording = action
        self.app.hotkeys.suspended = True
        self.app.hotkeys._clear()  # free keys so Tk receives even an existing combination
        self.buttons[action].config(text="Tastenkombination drücken …")
        self.win.focus_force()

    def cancel_recording(self):
        if self.recording:
            self.recording = None
            try:
                self.app.hotkeys.apply(self.app.controller.settings.snapshot()["hotkeys"])
            except ValueError as error:
                self.info.config(text=str(error))
        self.app.hotkeys.suspended = False
        self.refresh()

    def on_key(self, event):
        if not self.recording:
            return
        if event.keysym == "Escape":
            self.cancel_recording()
            return "break"
        try:
            combo = combo_from_event(event)
            if combo:
                values = self.app.controller.settings.snapshot()["hotkeys"]
                values[self.recording] = combo
                self.commit(values)
        except ValueError as error:
            self.info.config(text=str(error))
        return "break"

    def commit(self, bindings):
        old = self.app.controller.settings.snapshot()["hotkeys"]
        try:
            self.app.hotkeys.apply(bindings)
            if not self.app.update_settings(hotkeys=bindings):
                self.app.hotkeys.apply(old)
                raise ValueError("Nicht gespeichert; bisherige Kürzel bleiben aktiv")
            self.info.config(text="Gespeichert und bei Windows registriert. Neue Kürzel sind sofort aktiv.")
        except ValueError as error:
            try:
                self.app.hotkeys.apply(old)
                self.info.config(text=str(error))
            except ValueError as restore_error:
                self.info.config(text=f"{error}. Kürzel inaktiv: {restore_error}")
        finally:
            self.recording = None
            self.app.hotkeys.suspended = False
            self.refresh()

    def select_browser(self, _):
        name = self.browser.get()
        selected = next((key for key, value in self.clients.items() if value == name), "")
        self.app.update_settings(preferred_browser=selected)

    def close(self):
        self.cancel_recording()
        self.win.destroy()
        self.app.settings_window = None