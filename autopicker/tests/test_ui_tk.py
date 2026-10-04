"""Tk UI smoke/regression under Xvfb: pick list actions, dialog persistence and screenshot."""
import os
import sys
from pathlib import Path
import tkinter as tk

import pytest

from lolpicker.controller import Controller
from lolpicker.ui import App

try:
    from PIL import Image, ImageGrab
except Exception:  # noqa: BLE001
    Image = None
    ImageGrab = None


pytestmark = pytest.mark.skipif(sys.platform != "win32" and not os.environ.get("DISPLAY"), reason="DISPLAY required for Linux Tk tests")


def _pump(root, rounds=4):
    for _ in range(rounds):
        root.update_idletasks()
        root.update()


class _FakeHotkeys:
    """Simulated hotkey registry used to validate settings rollback messaging."""

    def __init__(self, initial):
        self.current = dict(initial)
        self.ids = {i: action for i, action in enumerate(initial, 1) if initial[action]}
        self.calls = []
        self.suspended = False

    def _clear(self):
        self.ids = {}

    def apply(self, bindings):
        self.calls.append(dict(bindings))
        values = [combo for combo in bindings.values() if combo]
        if len(set(values)) != len(values):
            raise ValueError("Dieses Kürzel ist bereits einer anderen Aktion zugeordnet")
        self.current = dict(bindings)
        self.ids = {i: action for i, action in enumerate(bindings, 1) if bindings[action]}

    def close(self):
        return None


# ui.py + settings persistence: pick add/move/remove, bad-matchup save, status feedback
def test_tk_app_pick_workflow_and_bad_matchups_persist(tmp_path, bundle_dir):
    root = tk.Tk()
    controller = Controller(directory=tmp_path / "data", bundle=bundle_dir, start_workers=False)
    try:
        app = App(root, controller)
        _pump(root)

        names = sorted(controller.catalog.values())
        first = names[0]
        second = names[1]
        app.picks.search.set(first)
        app.picks.add()
        app.picks.search.set(second)
        app.picks.add()
        _pump(root)
        picks = controller.settings.snapshot()["auto_pick_champs"]
        assert len(picks) == 2

        app.picks.list.selection_clear(0, "end")
        app.picks.list.selection_set(1)
        app.picks.move(-1)
        _pump(root)
        moved = controller.settings.snapshot()["auto_pick_champs"]
        assert moved[0] == app.picks.name_to_id[second]

        app.picks.list.selection_clear(0, "end")
        app.picks.list.selection_set(0)
        app.bad_matchups()
        _pump(root)

        windows = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert windows, "Bad-Matchup dialog not opened"
        dialog = windows[-1]
        entry = next(w for w in dialog.winfo_children() if isinstance(w, tk.Entry))
        # pick a likely enemy from catalog and persist through the dialog save flow
        enemy_name = "Caitlyn" if "Caitlyn" in names else names[-1]
        entry.delete(0, "end")
        entry.insert(0, enemy_name[:4])
        entry.event_generate("<KeyRelease>")
        _pump(root)

        listboxes = []
        for child in dialog.winfo_children():
            listboxes.extend([w for w in child.winfo_children() if isinstance(w, tk.Listbox)])
        assert listboxes, "Bad-Matchup listbox missing"
        lb = listboxes[0]
        if lb.size() > 0:
            lb.selection_set(0)
            lb.event_generate("<<ListboxSelect>>")

        save_button = next(w for w in dialog.winfo_children() if isinstance(w, tk.Button))
        save_button.invoke()
        _pump(root)

        selected = controller.settings.snapshot()["auto_pick_champs"][0]
        bad = controller.settings.snapshot()["bad_matchups"].get(str(selected), [])
        assert len(bad) <= 6

        app.controller.emit({"type": "status", "connected": False})
        app.controller.emit({"type": "browsers", "clients": {}})
        app.poll()
        assert "nicht verbunden" in app.browser_status.cget("text")

    finally:
        controller.close()
        root.destroy()


# assets/icon.png: transparent alpha corner check + UI screenshot output
def test_icon_alpha_and_ui_screenshot(tmp_path, bundle_dir):
    if Image is None:
        pytest.skip("Pillow not available")
    icon_path = bundle_dir / "assets" / "icon.png"
    image = Image.open(icon_path)
    assert image.mode in ("RGBA", "LA")
    corner = image.getpixel((0, 0))
    alpha = corner[3] if isinstance(corner, tuple) and len(corner) == 4 else 255
    assert alpha == 0

    if ImageGrab is None:
        pytest.skip("ImageGrab not available")

    root = tk.Tk()
    controller = Controller(directory=tmp_path / "data2", bundle=bundle_dir, start_workers=False)
    try:
        app = App(root, controller)
        _pump(root)
        # smaller arrow buttons regression: bottom notice must stay visible in 390x680 window
        notice_bottom = app.notice_label.winfo_y() + app.notice_label.winfo_height()
        assert notice_bottom <= app.body.winfo_height() + 2

        x, y = root.winfo_rootx(), root.winfo_rooty()
        w, h = root.winfo_width(), root.winfo_height()
        shot = ImageGrab.grab(bbox=(x, y, x + max(w, 300), y + max(h, 300)))
        out = Path(os.environ.get("PICKER_TEST_ARTIFACTS", str(tmp_path))) / "ui_tk_desktop.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        shot.save(out)
        assert out.exists()
    finally:
        controller.close()
        root.destroy()


# settings_ui.py: duplicate hotkey warning + restore keeps previous active bindings visible
def test_settings_duplicate_conflict_restores_old_bindings_with_warning(tmp_path, bundle_dir):
    root = tk.Tk()
    controller = Controller(directory=tmp_path / "data3", bundle=bundle_dir, start_workers=False)
    app = None
    try:
        app = App(root, controller)
        _pump(root)

        old = controller.settings.snapshot()["hotkeys"]
        app.hotkeys = _FakeHotkeys(old)
        app.open_settings()
        _pump(root)
        settings = app.settings_window

        conflict = dict(old)
        conflict["open_vs"] = conflict["open_lolalytics"]
        settings.commit(conflict)
        _pump(root)

        assert "bereits" in settings.info.cget("text").lower()
        assert app.hotkeys.calls[-1] == old
        assert "INAKTIV" not in settings.buttons["open_lolalytics"].cget("text")
    finally:
        if app and getattr(app, "settings_window", None) and app.settings_window.win.winfo_exists():
            app.settings_window.close()
        controller.close()
        root.destroy()
