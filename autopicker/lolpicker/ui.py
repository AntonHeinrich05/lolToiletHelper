"""Small Tk overlay. All widget operations stay on the main thread."""
import queue
import tkinter as tk
from tkinter import ttk
from .hotkeys import Hotkeys
from .settings_ui import SettingsWindow

BG, PANEL, TEXT, MUTED, GOLD = "#0b1119", "#142230", "#f0e6d2", "#9ba9b5", "#c8aa6e"
GREEN, RED = "#57d9ab", "#ef8892"


def button(parent, text, command, **kwargs):
    options = {"padx": 9, "pady": 5, "font": ("Segoe UI", 9), **kwargs}
    return tk.Button(parent, text=text, command=command, bg=PANEL, fg=TEXT, activebackground="#254153",
                     activeforeground=TEXT, relief="flat", **options)


class ChampionList:
    def __init__(self, app, parent, title, setting, on_change=None):
        self.app, self.setting, self.on_change = app, setting, on_change
        self.frame = tk.Frame(parent, bg=BG)
        self.frame.pack(fill="x", pady=5)
        tk.Label(self.frame, text=title, bg=BG, fg=GOLD, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.names = sorted(app.controller.catalog.values())
        self.name_to_id = {v: k for k, v in app.controller.catalog.items()}
        row = tk.Frame(self.frame, bg=BG)
        row.pack(fill="x", pady=4)
        self.search = ttk.Combobox(row, values=self.names, font=("Segoe UI", 9))
        self.search.pack(side="left", fill="x", expand=True)
        self.search.bind("<KeyRelease>", self.filter)
        self.search.bind("<Return>", lambda _: self.add())
        self.search.bind("<<ComboboxSelected>>", lambda _: self.add())
        button(row, "+", self.add).pack(side="right", padx=(4, 0))
        content = tk.Frame(self.frame, bg=BG)
        content.pack(fill="x")
        self.list = tk.Listbox(content, height=3, bg=PANEL, fg=TEXT, selectbackground="#235b69",
                               selectforeground=TEXT, font=("Segoe UI", 9), relief="flat", borderwidth=0,
                               exportselection=False, activestyle="none")
        self.list.pack(side="left", fill="both", expand=True)
        self.list.bind("<<ListboxSelect>>", lambda _: on_change() if on_change else None)
        actions = tk.Frame(content, bg=BG)
        actions.pack(side="right", padx=(4, 0))
        for text, command in (("↑", lambda: self.move(-1)), ("↓", lambda: self.move(1)), ("×", self.remove)):
            button(actions, text, command, width=2, pady=1, font=("Segoe UI", 8)).pack(fill="x", pady=1)
        self.refresh()

    def values(self):
        return self.app.controller.settings.snapshot()[self.setting]

    def filter(self, event):
        if event.keysym in ("Return", "Up", "Down"):
            return
        query = self.search.get().casefold().replace(" ", "").replace("'", "")
        self.search["values"] = [n for n in self.names if query in n.casefold().replace(" ", "").replace("'", "")]

    def commit(self, values, selection=0):
        if self.app.update_settings(**{self.setting: values}):
            self.refresh(selection)
            if self.on_change:
                self.on_change()

    def add(self):
        name = self.search.get().strip()
        champion = self.name_to_id.get(name)
        if not champion:
            candidates = [n for n in self.names if n.casefold().startswith(name.casefold())] if name else []
            if len(candidates) == 1:
                champion = self.name_to_id[candidates[0]]
        if not champion:
            self.app.notice("Champion aus der Vorschlagsliste auswählen")
            return
        values = self.values()
        if champion not in values:
            self.commit(values + [champion], len(values))
        self.search.set("")
        self.search["values"] = self.names

    def selected(self):
        selected = self.list.curselection()
        return selected[0] if selected else None

    def remove(self):
        index = self.selected()
        values = self.values()
        if index is not None:
            values.pop(index)
            self.commit(values, max(0, index - 1))

    def move(self, direction):
        index, values = self.selected(), self.values()
        if index is not None and 0 <= index + direction < len(values):
            values[index], values[index + direction] = values[index + direction], values[index]
            self.commit(values, index + direction)

    def refresh(self, selection=0):
        self.list.delete(0, "end")
        for i, cid in enumerate(self.values(), 1):
            self.list.insert("end", f"{i}. {self.app.controller.catalog.get(cid, str(cid))}")
        if self.list.size():
            self.list.selection_set(min(selection, self.list.size() - 1))


class App:
    def __init__(self, root, controller):
        self.root, self.controller = root, controller
        self.settings_window = None
        root.title("LoL Autopicker 2.0")
        root.configure(bg=BG)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.96)
        root.geometry("390x680")
        root.minsize(360, 600)
        root.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.icon = tk.PhotoImage(file=str(controller.bundle / "assets/icon.png"))
            root.iconphoto(True, self.icon)
        except tk.TclError:
            pass
        self.body = tk.Frame(root, bg=BG, padx=14, pady=12)
        self.body.pack(fill="both", expand=True)
        top = tk.Frame(self.body, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text="AUTOPICKER", bg=BG, fg=GOLD, font=("Segoe UI", 12, "bold")).pack(side="left")
        button(top, "Einstellungen", self.open_settings).pack(side="right")
        self.status = tk.Label(self.body, text="Warte auf League …", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.status.pack(anchor="w", pady=(7, 2))
        self.browser_status = tk.Label(self.body, text="Browser: nicht verbunden", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.browser_status.pack(anchor="w", pady=(0, 8))
        self.auto_ready = tk.BooleanVar(value=controller.settings.snapshot()["auto_ready_enabled"])
        self.auto_pick = tk.BooleanVar(value=controller.settings.snapshot()["auto_pick_enabled"])
        for label, variable, key in (("Auto-Ready", self.auto_ready, "auto_ready_enabled"),
                                     ("Auto-Pick & Ban", self.auto_pick, "auto_pick_enabled")):
            tk.Checkbutton(self.body, text=label, variable=variable, command=lambda v=variable, k=key: self.toggle(k, v),
                           bg=BG, fg=TEXT, selectcolor=PANEL, activebackground=BG, activeforeground=TEXT,
                           font=("Segoe UI", 10)).pack(anchor="w")
        self.picks = ChampionList(self, self.body, "AUTO PICKS · Priorität von oben nach unten", "auto_pick_champs")
        button(self.body, "Bad Matchups für ausgewählten Pick", self.bad_matchups).pack(fill="x", pady=(0, 4))
        self.bans = ChampionList(self, self.body, "AUTO BANS · Team-Hover werden geschützt", "auto_ban_champs")
        self.match = tk.Label(self.body, text="Noch kein Champion gewählt", bg=BG, fg=GOLD,
                              font=("Segoe UI", 10, "bold"), anchor="w", wraplength=345, justify="left")
        self.match.pack(fill="x", pady=(12, 5))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        button(row, "Lolalytics", lambda: controller.open("base")).pack(side="left", fill="x", expand=True)
        self.vs_button = button(row, "VS · unbekannt", lambda: controller.open("vs"))
        self.vs_button.pack(side="left", fill="x", expand=True, padx=(6, 0))
        button(self.body, "Tab speichern & schließen", lambda: controller.enqueue("close")).pack(fill="x", pady=6)
        self.notice_label = tk.Label(self.body, text="Browser-Erweiterung installieren: README, Abschnitt 3", bg=BG, fg=MUTED,
                                     font=("Segoe UI", 9), wraplength=345, justify="left", anchor="nw")
        self.notice_label.pack(fill="both", expand=True, pady=(4, 0))
        self.hotkeys = Hotkeys(root, self.action)
        try:
            self.hotkeys.apply(controller.settings.snapshot()["hotkeys"])
        except ValueError as error:
            self.notice(str(error))
        root.after(100, self.poll)

    def toggle(self, key, variable):
        if not self.update_settings(**{key: variable.get()}):
            variable.set(self.controller.settings.snapshot()[key])

    def update_settings(self, **changes):
        if not self.controller.settings.update(**changes):
            self.notice(self.controller.settings.last_error)
            return False
        self.controller.changed()
        return True

    def notice(self, text):
        self.notice_label.config(text=text)

    def action(self, action):
        if action == "toggle_overlay":
            if self.root.state() == "withdrawn":
                self.root.deiconify()
                self.root.lift()
            else:
                self.root.withdraw()
        elif action == "open_lolalytics":
            self.controller.open("base")
        elif action == "open_vs":
            self.controller.open("vs")
        elif action == "close_tab":
            self.controller.enqueue("close")
        elif action == "close_all_browsers":
            self.controller.enqueue("close_all", all_clients=True)

    def poll(self):
        for _ in range(100):
            try:
                message = self.controller.events.get_nowait()
            except queue.Empty:
                break
            self.controller.handle(message)
            kind = message["type"]
            if kind == "status":
                self.status.config(text="League verbunden" if message["connected"] else "Warte auf League · Wiederverbindung aktiv",
                                   fg=GREEN if message["connected"] else MUTED)
            elif kind == "notice":
                self.notice(message["text"])
            elif kind == "browsers":
                count = len(message["clients"])
                self.browser_status.config(text=f"Browser: {count} Verbindung(en)" if count else "Browser: nicht verbunden",
                                           fg=GREEN if count else MUTED)
            elif kind in ("draft", "live", "phase"):
                c = self.controller
                self.match.config(text=f"{c.current_champion() or 'Noch kein Champion'} · {c.role or c.phase}")
                valid = bool(c.vs_url())
                enemy = c.opponent or {}
                suffix = "" if c.live_confirmed else " · vorläufig"
                self.vs_button.config(text=f"VS {enemy.get('champion', '')}{suffix}" if valid else "VS · unbekannt",
                                      state="normal" if valid else "disabled")
                if kind == "live":
                    self.notice("VS anhand der Spielerdaten korrigiert. Tatsächliche Lane-Swaps können abweichen.")
        self.root.after(100, self.poll)

    def open_settings(self):
        if self.settings_window and self.settings_window.win.winfo_exists():
            self.settings_window.win.lift()
        else:
            self.settings_window = SettingsWindow(self)

    def bad_matchups(self):
        index = self.picks.selected()
        if index is None:
            self.notice("Zuerst einen Pick markieren")
            return
        cid = self.picks.values()[index]
        win = tk.Toplevel(self.root)
        win.title(f"Bad Matchups · {self.controller.catalog[cid]}")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        win.geometry("330x400")
        chosen = set(self.controller.settings.snapshot()["bad_matchups"].get(str(cid), []))
        tk.Label(win, text="Bis zu 6 Gegner · Auswahl bleibt beim Filtern erhalten", bg=BG, fg=TEXT,
                 wraplength=310, font=("Segoe UI", 9)).pack(padx=10, pady=10)
        search = tk.Entry(win)
        search.pack(fill="x", padx=10)
        area = tk.Frame(win, bg=BG)
        area.pack(fill="both", expand=True, padx=10, pady=6)
        listing = tk.Listbox(area, selectmode="multiple", exportselection=False, bg=PANEL, fg=TEXT,
                            selectbackground="#235b69", selectforeground=TEXT)
        listing.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(area, command=listing.yview)
        scroll.pack(side="right", fill="y")
        listing.configure(yscrollcommand=scroll.set)
        visible = []
        hint = tk.Label(win, text="", bg=BG, fg=GOLD)
        hint.pack()

        def capture(_=None):
            chosen.difference_update(visible)
            chosen.update(visible[i] for i in listing.curselection())
            hint.config(text=f"{len(chosen)} / 6 ausgewählt")

        def populate(_=None):
            capture()
            visible.clear()
            listing.delete(0, "end")
            for key, name in sorted(self.controller.catalog.items(), key=lambda pair: pair[1]):
                if search.get().casefold() in name.casefold():
                    visible.append(key)
                    listing.insert("end", name)
                    if key in chosen:
                        listing.selection_set(len(visible) - 1)

        def save():
            capture()
            if len(chosen) > 6:
                hint.config(text="Bitte höchstens 6 Gegner auswählen")
                return
            values = self.controller.settings.snapshot()["bad_matchups"]
            values[str(cid)] = sorted(chosen)
            if self.update_settings(bad_matchups=values):
                win.destroy()

        search.bind("<KeyRelease>", populate)
        listing.bind("<<ListboxSelect>>", capture)
        button(win, "Speichern", save).pack(fill="x", padx=10, pady=10)
        populate()

    def close(self):
        self.hotkeys.close()
        self.controller.close()
        self.root.destroy()