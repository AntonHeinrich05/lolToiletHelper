"""Renders the overlay in three states (no champion line, ban suggestions, hard counters) and saves screenshots."""
import os
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "autopicker"))
from lolpicker.controller import Controller  # noqa: E402
from lolpicker.ui import App  # noqa: E402

OUT = Path("/app/test_reports")
OUT.mkdir(exist_ok=True)


def pump(root, rounds=6):
    for _ in range(rounds):
        root.update_idletasks()
        root.update()


def shot(root, name):
    pump(root)
    x, y, w, h = root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height()
    subprocess.run(["import", "-window", "root", "-crop", f"{w + 20}x{h + 20}+{x - 10}+{y - 10}", str(OUT / name)], check=True)
    print(name, w, h)


def main():
    tmp = Path(tempfile.mkdtemp())
    root = tk.Tk()
    controller = Controller(directory=tmp, bundle=Path("/app/autopicker"), start_workers=False)
    controller.settings.update(auto_pick_enabled=True, auto_pick_minimized=False, list_role="jungle",
                               role_lists={"jungle": {"auto_pick_champs": [234, 143, 33, 91, 121], "auto_ban_champs": [19]}})
    app = App(root, controller)
    root.geometry("+40+40")
    pump(root)
    shot(root, "overlay_no_champ_line.png")

    controller.emit({"type": "status", "connected": True})
    controller.emit({"type": "phase", "phase": "ChampSelect", "queue_id": 420})
    controller.emit({"type": "pick_status", "status": {234: "hovered", 143: "ok", 33: "ok", 91: "ok", 121: "ok"},
                     "ban_status": {19: "teammate"}, "role": "jungle"})
    app.process_queue()
    pump(root)
    shot(root, "overlay_teammate_ban.png")

    app._load_ban_suggestions()
    pump(root)
    app.ban_suggest.set_items([(11, "19.8 % Bans"), (122, "14.9 % Bans"), (233, "13.5 % Bans"), (33, "7.2 % Bans"),
                               (19, "7.0 % Bans"), (141, "6.9 % Bans"), (102, "5.1 % Bans")], "Meistgebannt · Jungle · 30 Tage")
    pump(root)
    shot(root, "overlay_ban_suggestions.png")
    app._close_ban_suggestions()

    app._toggle_bad_matchups(app.pick_rows[0])
    pump(root)
    app._load_counters(app.active_bm_panel)
    pump(root)
    app.active_bm_panel.suggest.set_items([(33, "43.9 % WR"), (14, "45.8 % WR"), (32, "46.4 % WR"), (19, "46.4 % WR"),
                                           (23, "46.9 % WR"), (113, "46.9 % WR"), (5, "47.4 % WR")], "Hardcounter Viego (jungle) · WR von Viego")
    pump(root)
    shot(root, "overlay_hardcounter.png")
    app.active_bm_panel.suggest.on_pick(33)
    pump(root)
    shot(root, "overlay_hardcounter_picked.png")
    print("bad_matchups:", controller.settings.snapshot()["bad_matchups"])
    app.quit()


if __name__ == "__main__":
    main()
