"""Manual screenshot of the loadout window with real Data Dragon data (dev only)."""
import sys
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "autopicker"))
from lolpicker.controller import Controller  # noqa: E402
from lolpicker.ui import App  # noqa: E402
from PIL import ImageGrab  # noqa: E402

out = Path(sys.argv[1])
root = tk.Tk()
controller = Controller(directory=Path("/tmp/lolpicker-shot"), bundle=Path(__file__).resolve().parents[1] / "autopicker", start_workers=False)
controller.runes.start()
controller.settings.update(auto_pick_champs=[876, 266], auto_ban_champs=[51], auto_pick_enabled=True, auto_pick_minimized=False,
                           loadouts={"266": {"primary": 8000, "sub": 8100, "perks": [8010, 9111, 9104, 8014, 8139, 8135], "shards": [5008, 5008, 5001], "spells": [4, 12]}})
app = App(root, controller)
app.root.geometry("+20+20")
controller.emit({"type": "status", "connected": True})
controller.emit({"type": "phase", "phase": "ChampSelect", "queue_id": 420})
controller.emit({"type": "pick_status", "status": {876: "hovered", 266: "ok"}, "ban_status": {51: "ok"}})
app.process_queue()
app._open_loadout(app.pick_rows[0])
app._loadout_window.win.geometry("+260+20")
app._open_settings()
app._settings_window.win.geometry("+680+20")
deadline = time.time() + 60
while time.time() < deadline and not app._loadout_window.tiles:
    root.update()
    time.sleep(0.05)
for _ in range(10):
    root.update()
    time.sleep(0.05)
tile = app._loadout_window.tiles[8010][0]
tile._enter(None)
root.update()
time.sleep(0.2)
root.update()
ImageGrab.grab(bbox=(0, 0, 1050, 560)).save(out)
print("tiles", len(app._loadout_window.tiles), "size", app._loadout_window.win.winfo_width(), app._loadout_window.win.winfo_height())
app.quit()
