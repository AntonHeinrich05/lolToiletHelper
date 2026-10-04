"""Controller queue/phase forwarding checks for lane-less queues (ARAM/Arena)."""

from lolpicker.controller import Controller


class _FakeBridge:
    def __init__(self, *_args, **_kwargs):
        self.commands = []

    def listing(self):
        return {}

    def command(self, command, client, **args):
        self.commands.append((command, client, args))
        return {}

    def broadcast_context(self):
        return None

    def close(self):
        return None


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
