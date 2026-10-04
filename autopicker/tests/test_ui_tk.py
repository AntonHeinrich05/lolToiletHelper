"""Tk regression tests for classic restored overlay/settings flows and screenshot output."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
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


def _pump(root, rounds=5):
    for _ in range(rounds):
        root.update_idletasks()
        root.update()


class _FakeHotkeys:
    """Fake hotkey manager for duplicate-binding rollback checks."""

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


# ui classic flow: five suggestions, enter-first add, DnD reorder persistence, BM panel persistence
def test_classic_search_enter_dnd_and_bad_matchups(tmp_path, bundle_dir):
    root = tk.Tk()
    controller = Controller(directory=tmp_path / "data", bundle=bundle_dir, start_workers=False)
    app = None
    try:
        app = App(root, controller)
        app.auto_pick_toggle_var.set(True)
        app.toggle_auto_pick()
        _pump(root)

        app.pick_search_entry.delete(0, tk.END)
        app.pick_search_entry.insert(0, "a")
        app._update_suggestions("pick")
        _pump(root)
        assert app.pick_suggestions_listbox.size() == 5
        app._on_search_enter("pick")
        _pump(root)
        assert len(app.auto_pick_champs) == 1

        app.pick_search_entry.delete(0, tk.END)
        app.pick_search_entry.insert(0, "ka")
        app._update_suggestions("pick")
        app._on_search_enter("pick")
        _pump(root)
        assert len(app.auto_pick_champs) == 2

        app.ban_search_entry.delete(0, tk.END)
        app.ban_search_entry.insert(0, "d")
        app._update_suggestions("ban")
        app._on_search_enter("ban")
        _pump(root)
        assert len(app.auto_ban_champs) == 1

        second_row = app.pick_rows[1]
        fake_event = SimpleNamespace(x_root=120, y_root=120)
        app._dnd_start(fake_event, second_row)
        app._dnd_swap(second_row, 1, 0)
        app._dnd_release(fake_event, second_row)
        _pump(root)

        persisted_picks = controller.settings.snapshot()["auto_pick_champs"]
        assert persisted_picks[0] == app.pick_rows[0].champ_id

        first_row = app.pick_rows[0]
        app._toggle_bad_matchups(first_row)
        _pump(root)
        assert app.active_bm_panel is not None

        panel = app.active_bm_panel
        panel.entry.delete(0, tk.END)
        panel.entry.insert(0, "ka")
        panel._update_suggestions()
        panel._confirm()
        _pump(root)

        saved_bm = controller.settings.snapshot()["bad_matchups"].get(str(first_row.champ_id), [])
        assert len(saved_bm) == 1

        app._toggle_bad_matchups(first_row)
        _pump(root)
        assert app.active_bm_panel is None
    finally:
        if app is not None and app.root.winfo_exists():
            app.quit()


# classic visuals: exact alpha/size/colors + screenshot with populated overlay and settings
def test_classic_overlay_settings_visuals_and_screenshot(tmp_path, bundle_dir):
    if Image is None or ImageGrab is None:
        pytest.skip("Pillow/ImageGrab not available")

    icon_path = bundle_dir / "assets" / "icon.png"
    image = Image.open(icon_path)
    assert image.mode in ("RGBA", "LA")
    corner = image.getpixel((0, 0))
    alpha = corner[3] if isinstance(corner, tuple) and len(corner) == 4 else 255
    assert alpha == 0

    root = tk.Tk()
    controller = Controller(directory=tmp_path / "data2", bundle=bundle_dir, start_workers=False)
    app = None
    try:
        app = App(root, controller)
        app.auto_pick_toggle_var.set(True)
        app.toggle_auto_pick()
        _pump(root)

        overlay_alpha = float(app.root.attributes("-alpha"))
        if sys.platform == "win32":
            assert overlay_alpha == pytest.approx(0.75, abs=0.01)
        else:
            assert overlay_alpha in (pytest.approx(0.75, abs=0.01), pytest.approx(1.0, abs=0.01))
        assert bool(app.root.overrideredirect()) is True
        assert app.root.winfo_width() >= 220

        app.pick_search_entry.delete(0, tk.END)
        app.pick_search_entry.insert(0, "a")
        app._update_suggestions("pick")
        app._on_search_enter("pick")
        _pump(root)

        controller.emit({'type': 'status', 'connected': True})
        controller.emit({'type': 'phase', 'phase': 'ChampSelect', 'queue_id': 420})
        controller.emit({'type': 'draft', 'champion_id': 266, 'role': '', 'queue_id': 420, 'roster': [], 'opponent': None})
        controller.emit({'type': 'phase', 'phase': 'InProgress', 'queue_id': 420})
        app.process_queue()
        app.root.geometry('+40+40')
        app._open_settings()
        _pump(root)
        settings = app._settings_window
        assert settings is not None
        settings_alpha = float(settings.win.attributes("-alpha"))
        if sys.platform == "win32":
            assert settings_alpha == pytest.approx(0.96, abs=0.01)
        else:
            assert settings_alpha in (pytest.approx(0.96, abs=0.01), pytest.approx(1.0, abs=0.01))
        assert settings.win.winfo_width() == 320
        assert settings.win.winfo_height() >= 400
        assert settings.win.cget("bg") == settings.BORDER
        assert settings.BG == "#0b0f16"
        assert settings.ACCENT == "#c8aa6e"

        settings.win.geometry('+290+40')
        _pump(root)
        x1 = min(app.root.winfo_rootx(), settings.win.winfo_rootx())
        y1 = min(app.root.winfo_rooty(), settings.win.winfo_rooty())
        x2 = max(app.root.winfo_rootx() + app.root.winfo_width(), settings.win.winfo_rootx() + settings.win.winfo_width())
        y2 = max(app.root.winfo_rooty() + app.root.winfo_height(), settings.win.winfo_rooty() + settings.win.winfo_height())
        shot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        out = Path(os.environ.get('PICKER_TEST_ARTIFACTS', str(tmp_path))) / 'classic_ui.png'
        out.parent.mkdir(parents=True, exist_ok=True)
        shot.save(out)
        assert out.exists()
    finally:
        if app is not None and app.root.winfo_exists():
            app.quit()


# settings duplicate bind: rollback keeps previous bindings active and visible
def test_settings_duplicate_conflict_rollback_with_hotkey_manager(tmp_path, bundle_dir):
    root = tk.Tk()
    controller = Controller(directory=tmp_path / "data3", bundle=bundle_dir, start_workers=False)
    app = None
    try:
        app = App(root, controller)
        _pump(root)

        old = dict(app.hotkeys)
        fake = _FakeHotkeys(old)
        app.hotkey_manager = fake
        app._open_settings()
        _pump(root)
        settings = app._settings_window
        assert settings is not None

        conflict = dict(old)
        conflict["open_vs"] = conflict["open_lolalytics"]
        settings.commit(conflict)
        _pump(root)

        assert app.hotkeys == old
        assert fake.calls[0] == conflict
        assert fake.calls[-1] == old
        assert settings.message is not None
        assert "bereits" in settings.message.cget("text").lower()
        assert settings.row_buttons["open_lolalytics"].cget("text") == settings._format_hotkey(old["open_lolalytics"])
    finally:
        if app is not None and app.root.winfo_exists():
            app.quit()
