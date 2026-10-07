"""Controller queue/phase forwarding checks for lane-less queues (ARAM/Arena)."""

import time

from lolpicker.controller import Controller


class _FakeBridge:
    def __init__(self, *_args, **_kwargs):
        self.commands = []
        self._clients = {"opera": "Opera", "edge": "Edge"}

    def listing(self):
        return dict(self._clients)

    def command(self, command, client, **args):
        self.commands.append((command, client, args))
        return {"closed": 1} if command == "close" else {}

    def broadcast_context(self):
        return None

    def close(self):
        return None


def _drain(events):
    items = []
    while not events.empty():
        items.append(events.get_nowait())
    return items


def test_phase_queue_forwarding_blocks_vs_url_for_aram(monkeypatch, tmp_path, bundle_dir):
    import lolpicker.controller as controller_module

    monkeypatch.setattr(controller_module, "BrowserBridge", _FakeBridge)
    controller = Controller(directory=tmp_path / "data", bundle=bundle_dir, start_workers=False)
    try:
        controller.handle({"type": "phase", "phase": "ChampSelect", "queue_id": 450})
        controller.handle({
            "type": "draft",
            "champion_id": 266,
            "role": "TOP",
            "opponent": {"champion_id": 222, "role": "BOTTOM"},
            "queue_id": 450,
        })

        assert controller.queue_id == 450
        assert controller.current_champion().lower() == "aatrox"
        assert controller.vs_url() is None
    finally:
        controller.close()


# weak-pc mode: game_foreground closes ONLY Lolalytics tabs, in every connected browser; no window is closed
def test_weak_pc_mode_game_foreground_closes_lolalytics_tabs_in_all_clients(monkeypatch, tmp_path, bundle_dir):
    import lolpicker.controller as controller_module

    monkeypatch.setattr(controller_module, "BrowserBridge", _FakeBridge)

    controller = Controller(directory=tmp_path / "data2", bundle=bundle_dir, start_workers=False)
    try:
        assert controller.settings.update(weak_pc_mode=True)
        controller.handle({"type": "phase", "phase": "InProgress", "queue_id": 420})
        time.sleep(0.15)
        assert controller.bridge.commands == []

        controller.handle({"type": "game_foreground"})
        time.sleep(0.35)

        closes = [(cmd, client) for (cmd, client, _args) in controller.bridge.commands if cmd == "close"]
        assert set(closes) == {("close", "opera"), ("close", "edge")}
        assert not [cmd for (cmd, _c, _a) in controller.bridge.commands if cmd != "close"]
        closed = [e for e in _drain(controller.events) if e["type"] == "browsers_closed"]
        assert closed and closed[-1]["count"] == 2
    finally:
        controller.close()


# weak-pc disabled: game_foreground event must not close/snapshot browsers
def test_game_foreground_ignored_when_weak_pc_disabled(monkeypatch, tmp_path, bundle_dir):
    import lolpicker.controller as controller_module

    monkeypatch.setattr(controller_module, "BrowserBridge", _FakeBridge)

    controller = Controller(directory=tmp_path / "data3", bundle=bundle_dir, start_workers=False)
    try:
        assert controller.settings.update(weak_pc_mode=False)
        controller.handle({"type": "game_foreground"})
        time.sleep(0.25)
        assert controller.bridge.commands == []
    finally:
        controller.close()



# 2.6: close scope 'browser' closes whole browsers (Win32 first, extension fallback); Alt+Shift+1 uses the selected role list
def test_close_scope_browser_and_selected_role_list(monkeypatch, tmp_path, bundle_dir):
    import lolpicker.controller as controller_module

    monkeypatch.setattr(controller_module, "BrowserBridge", _FakeBridge)
    win32_calls = []
    monkeypatch.setattr(controller_module, "close_browser_windows", lambda only_lolalytics=True: win32_calls.append(only_lolalytics) or 0)
    controller = Controller(directory=tmp_path / "data6", bundle=bundle_dir, start_workers=False)
    try:
        assert controller.settings.update(auto_pick_champs=[103], list_role="jungle",
                                          role_lists={"jungle": {"auto_pick_champs": [64], "auto_ban_champs": []}})
        assert controller.current_champion() == "Lee Sin"  # selected jungle list, not 'Alle Rollen' (Ahri)
        controller.role = "top"
        assert controller.current_champion() == "Lee Sin"  # assigned top without own list -> selected list
        controller.role = ""

        controller.enqueue("close_lolalytics", all_clients=True)
        time.sleep(0.35)
        assert win32_calls == []  # the extension closed tabs in both browsers -> no Win32 fallback needed
        notices = [e["text"] for e in _drain(controller.events) if e["type"] == "notice"]
        assert notices and notices[-1] == "Lolalytics-Tabs geschlossen: 2"
        controller.bridge.commands.clear()
        win32_calls.clear()

        assert controller.settings.update(close_scope="browser")
        controller.enqueue("close_lolalytics", all_clients=True)
        time.sleep(0.35)
        assert win32_calls == [False]  # whole browser windows via Win32 first (returns 0 here -> extension fallback)
        assert {cmd for (cmd, _c, _a) in controller.bridge.commands} == {"close_windows"}
        notices = [e["text"] for e in _drain(controller.events) if e["type"] == "notice"]
        assert notices and notices[-1].startswith("Kein Browserfenster gefunden")
    finally:
        controller.close()