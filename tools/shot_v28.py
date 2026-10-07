"""Renders overlay (ban suggestions scroll, hard counters), settings window and rune window with items; saves screenshots."""
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "autopicker"))
from lolpicker.controller import Controller  # noqa: E402
from lolpicker.ui import App  # noqa: E402

OUT = Path("/app/test_reports")
OUT.mkdir(exist_ok=True)


def pump(root, rounds=6):
    for _ in range(rounds):
        root.update_idletasks()
        root.update()


def shot(root, win, name):
    pump(root)
    x, y, w, h = win.winfo_rootx(), win.winfo_rooty(), win.winfo_width(), win.winfo_height()
    ImageGrab.grab(bbox=(max(0, x - 10), max(0, y - 10), x + w + 10, y + h + 10)).save(OUT / name)
    print(name, w, h)


def main():
    tmp = Path(tempfile.mkdtemp())
    root = tk.Tk()
    controller = Controller(directory=tmp, bundle=Path("/app/autopicker"), start_workers=False)
    controller.settings.update(auto_pick_enabled=True, auto_pick_minimized=False, list_role="jungle",
                               role_lists={"jungle": {"auto_pick_champs": [234, 143, 33], "auto_ban_champs": [19]}})
    app = App(root, controller)
    root.geometry("+40+40")
    pump(root)
    shot(root, root, "v28_overlay_plain.png")

    app._load_ban_suggestions()
    pump(root)
    app.ban_suggest.set_items([(11, "53.1 % WR"), (122, "52.4 % WR"), (233, "52.0 % WR"), (33, "51.7 % WR"), (19, "51.5 % WR"),
                               (141, "51.2 % WR"), (102, "50.9 % WR"), (64, "50.1 % WR")], "Höchste Winrate · Jungle · All Ranks · 30 Tage")
    pump(root)
    app.ban_suggest.scroll.scroll(1)
    shot(root, root, "v28_overlay_ban_scroll.png")
    app._close_ban_suggestions()

    app._toggle_bad_matchups(app.pick_rows[0])
    pump(root)
    app._load_counters(app.active_bm_panel)
    pump(root)
    app.active_bm_panel.suggest.set_items([(33, "43.9 % WR"), (14, "45.8 % WR"), (32, "46.4 % WR"), (19, "46.4 % WR"),
                                           (23, "46.9 % WR"), (113, "46.9 % WR"), (5, "47.4 % WR")], "Hardcounter Viego · jungle · All Ranks · 30 Tage")
    pump(root)
    shot(root, root, "v28_overlay_hardcounter.png")
    app._close_bm_panel()

    app._open_settings()
    settings = app._settings_window
    pump(root)
    shot(root, settings.win, "v28_settings_top.png")
    for _ in range(12):
        settings.scroll.scroll(1)
    pump(root)
    shot(root, settings.win, "v28_settings_scrolled.png")
    settings.close()

    controller.runes.start()
    deadline = time.monotonic() + 90
    while not controller.runes.ready() and time.monotonic() < deadline:
        pump(root)
        time.sleep(0.2)
    app._open_loadout(app.pick_rows[0])
    window = app._loadout_window
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        app.process_queue()
        pump(root)
        if window.preview is not None and window.preview.cget("text").startswith("Lolalytics:") and window.current_build:
            break
        time.sleep(0.2)
    print("preview:", window.preview.cget("text") if window.preview else None)
    pump(root)
    shot(root, window.win, "v28_loadout_items.png")
    app.show_item_rates = True
    window.render_items()
    pump(root)
    window.win.geometry(f"{window.win.winfo_reqwidth()}x{window.win.winfo_reqheight()}")
    shot(root, window.win, "v28_loadout_items_rates.png")
    window.ask_confirm("Eigene Runen/Zauber durch Lolalytics mit den neuen Einstellungen ersetzen?", lambda: None)
    pump(root)
    shot(root, window.win, "v28_loadout_confirm.png")
    app.quit()


if __name__ == "__main__":
    main()
