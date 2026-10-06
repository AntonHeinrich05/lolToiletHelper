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


def _png(width=32, height=32, rgb=(200, 60, 60)):
    import struct
    import zlib

    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xFFFFFFFF)
    raw = b''.join(b'\x00' + bytes(rgb) * width for _ in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def _fake_rune_tree():
    def style(identifier, name, keystones, rows):
        return {"id": identifier, "key": name, "name": name, "icon": f"perk-images/Styles/{identifier}.png",
                "slots": [{"runes": [{"id": k, "name": f"Schlüssel {k}", "icon": "k.png", "shortDesc": "<b>Test</b>"} for k in keystones]}]
                          + [{"runes": [{"id": r, "name": f"Rune {r}", "icon": "r.png", "shortDesc": "y"} for r in row]} for row in rows]}
    runes = [style(8000, "Präzision", [8005, 8008, 8010], [[9101, 9111, 8009], [9104, 9105, 9103], [8014, 8017, 8299]]),
             style(8100, "Dominanz", [8112, 8128, 9923], [[8126, 8139, 8143], [8137, 8140, 8141], [8135, 8105, 8106]]),
             style(8200, "Zauberei", [8214, 8229, 8230], [[8224, 8226, 8275], [8210, 8234, 8233], [8237, 8232, 8236]])]
    spells = {"data": {str(i): {"key": str(i), "name": f"Zauber {i}", "image": {"full": f"S{i}.png"}} for i in (4, 12, 14, 7, 6, 11, 3, 21, 1, 13, 32)}}
    return runes, spells


# 2.4: ban rows get the neutral frame at ChampSelect start, own ban turns blue, in-game opacity switches,
# loadout window selects like the client and persists runes + spells for the champion
def test_ban_borders_opacity_and_loadout_window(tmp_path, bundle_dir):
    root = tk.Tk()
    controller = Controller(directory=tmp_path / "data4", bundle=bundle_dir, start_workers=False)
    runes, spells = _fake_rune_tree()
    controller.runes.apply(runes, spells)
    controller.runes.loaded.set()
    controller.runes.icon_bytes = lambda icon, fetch=True: _png()
    app = None
    try:
        assert controller.settings.update(auto_pick_champs=[266], auto_ban_champs=[51, 10], auto_pick_enabled=True,
                                          auto_pick_minimized=False, opacity_default=0.9, opacity_ingame=0.4)
        app = App(root, controller)
        _pump(root)
        assert float(app.root.attributes("-alpha")) in (pytest.approx(0.9, abs=0.01), pytest.approx(1.0, abs=0.01))
        assert [row.border_color for row in app.ban_rows] == ['#e74c3c', '#e74c3c']

        controller.emit({'type': 'phase', 'phase': 'ChampSelect', 'queue_id': 420})
        app.process_queue()
        assert [row.border_color for row in app.ban_rows] == ['#818181', '#818181']
        assert [row.border_color for row in app.pick_rows] == ['#818181']
        controller.emit({'type': 'pick_status', 'status': {266: 'ok'}, 'ban_status': {51: 'hovered', 10: 'banned'}})
        app.process_queue()
        assert [row.border_color for row in app.ban_rows] == ['#3a8fd4', '#33ff00']

        controller.emit({'type': 'phase', 'phase': 'InProgress', 'queue_id': 420})
        app.process_queue()
        if sys.platform == "win32":
            assert float(app.root.attributes("-alpha")) == pytest.approx(0.4, abs=0.01)
        controller.emit({'type': 'phase', 'phase': 'None', 'queue_id': 0})
        app.process_queue()
        assert [row.border_color for row in app.ban_rows] == ['#e74c3c', '#e74c3c']

        row = app.pick_rows[0]
        assert row.rune_btn.cget('fg') == '#4f4838'
        app._open_loadout(row)
        window = app._loadout_window
        deadline = 50
        while not window.tiles and deadline:
            _pump(root)
            root.after(20)
            deadline -= 1
            import time
            time.sleep(0.02)
        assert window.tiles, "loadout window did not build"
        assert window.state['primary'] == 8000 and window.state['sub'] == 8100
        window.set_primary(8100)
        assert window.state['primary'] == 8100 and window.state['sub'] == 8000
        assert window.state['perks'][:4] == [8112, 8126, 8137, 8135]
        window.set_perk(0, 9923)
        assert window.state['perks'][4:] == [9101, 9104]
        window.set_sub_perk(9105)  # same row as 9104: replaced in place
        assert window.state['perks'][4:] == [9101, 9105]
        window.set_sub_perk(8014)  # third row: the older selection (9101) is dropped
        assert window.state['perks'][4:] == [9105, 8014]
        window.set_sub_perk(9111)  # row 1 again: 9105 (older) is dropped
        assert window.state['perks'][4:] == [8014, 9111]
        window.set_spell(14)
        assert window.state['spells'] == [12, 14]
        window.set_shard(2, 5011)
        assert any(tile.selected for tile in window.tiles[9923])
        tile = window.tiles[9923][0]
        tile._enter(None)
        assert window.tooltip is not None and 'Schlüssel 9923' in window.tooltip.winfo_children()[0].cget('text')
        tile._leave(None)
        window.save()
        _pump(root)
        saved = controller.settings.snapshot()['loadouts']['266']
        assert saved['primary'] == 8100 and saved['perks'][0] == 9923 and saved['spells'] == [12, 14] and saved['shards'][2] == 5011
        assert row.rune_btn.cget('fg') == '#c8aa6e'
        assert app._loadout_window is None
    finally:
        if app is not None and app.root.winfo_exists():
            app.quit()


# 2.5: role dropdown switches the shown lists and stores them per role; Lolalytics import (mocked) fills loadouts
def test_role_lists_dropdown_and_lolalytics_import(tmp_path, bundle_dir, monkeypatch):
    import lolpicker.ui as ui_module
    root = tk.Tk()
    controller = Controller(directory=tmp_path / "data5", bundle=bundle_dir, start_workers=False)
    runes, spells = _fake_rune_tree()
    controller.runes.apply(runes, spells)
    controller.runes.loaded.set()
    app = None
    try:
        assert controller.settings.update(auto_pick_champs=[266], auto_ban_champs=[51], auto_pick_enabled=True, auto_pick_minimized=False)
        app = App(root, controller)
        _pump(root)
        assert app.role_frame.winfo_ismapped() and 'Alle Rollen' in app.role_btn.cget('text')
        app._select_role('jungle')
        _pump(root)
        assert app.auto_pick_champs == [] and app.ban_rows == [] and 'Jungle' in app.role_btn.cget('text')
        app._add_champ('pick', 64)
        app._add_champ('ban', 10)
        snap = controller.settings.snapshot()
        assert snap['role_lists'] == {'jungle': {'auto_pick_champs': [64], 'auto_ban_champs': [10]}}
        assert snap['auto_pick_champs'] == [266] and snap['auto_ban_champs'] == [51] and snap['list_role'] == 'jungle'
        app._select_role('')
        _pump(root)
        assert app.auto_pick_champs == [266] and [r.champ_id for r in app.ban_rows] == [51]
        app._select_role('jungle')
        assert [r.champ_id for r in app.pick_rows] == [64]

        calls = []

        def fake_fetch(name, lane, tier, patch, build):
            calls.append((name, lane, tier, patch, build))
            return {"perks": [8005, 9101, 9104, 8014, 8126, 8137], "shards": [5008, 5008, 5001], "spells": [4, 14], "lane": lane, "games": 9}
        monkeypatch.setattr(ui_module, 'fetch_build', fake_fetch)
        app.flash_side = 'right'
        app.import_lolalytics(list(app.auto_pick_champs))
        import time
        for _ in range(50):
            _pump(root)
            time.sleep(0.02)
            if '64' in app.loadouts:
                break
        assert calls == [('Lee Sin', 'jungle', 'all', '30', 'pick')]
        saved = controller.settings.snapshot()['loadouts']['64']
        assert saved['primary'] == 8000 and saved['sub'] == 8100 and saved['spells'] == [14, 4]
        assert app.pick_rows[0].rune_btn.cget('fg') == '#c8aa6e'

        # 2.5.1: in champion select the overlay follows the assigned role (list that is really used) and restores afterwards
        controller.emit({'type': 'phase', 'phase': 'ChampSelect', 'queue_id': 420})
        controller.emit({'type': 'pick_status', 'status': {266: 'ok'}, 'ban_status': {51: 'ok'}, 'role': 'top'})
        app.process_queue()
        _pump(root)
        assert 'Alle Rollen' in app.role_btn.cget('text') and [r.champ_id for r in app.pick_rows] == [266]  # no top list -> general list
        assert app.pick_rows[0].border_color == '#818181'
        controller.emit({'type': 'pick_status', 'status': {64: 'hovered'}, 'ban_status': {10: 'ok'}, 'role': 'jungle'})
        app.process_queue()
        _pump(root)
        assert 'Jungle' in app.role_btn.cget('text') and app.pick_rows[0].border_color == '#3a8fd4'
        controller.emit({'type': 'phase', 'phase': 'Lobby', 'queue_id': 420})
        app.process_queue()
        _pump(root)
        assert 'Jungle' in app.role_btn.cget('text') and controller.settings.snapshot()['list_role'] == 'jungle'  # player's own choice
    finally:
        if app is not None and app.root.winfo_exists():
            app.quit()
