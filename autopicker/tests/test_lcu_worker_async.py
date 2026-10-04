"""Async LCU worker tests for ready-check and pick/ban automation safeguards."""
import asyncio
from base64 import b64decode
import contextlib
import time

import pytest

from lolpicker.lcu import LCUWorker, PHASE, READY, SELECT


def _base_session(action_type="pick", action_id=101):
    return {
        "localPlayerCellId": 1,
        "myTeam": [{"cellId": 1, "assignedPosition": "TOP", "championId": 0}],
        "theirTeam": [{"cellId": 6, "assignedPosition": "TOP", "championId": 222}],
        "actions": [[{"id": action_id, "type": action_type, "actorCellId": 1, "isInProgress": True, "completed": False}]],
        "bans": {"myTeamBans": [], "theirTeamBans": []},
        "queueId": 420,
    }


# lcu.py: ready-check acceptance and stale refresh checks
@pytest.mark.asyncio
async def test_accept_ready_once_and_skip_when_already_accepted(fake_settings):
    emitted = []
    worker = LCUWorker(fake_settings, emitted.append)
    calls = []

    async def fake_request(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET" and path == READY:
            return 200, {"state": "InProgress", "playerResponse": "None"}
        if method == "POST" and path == READY + "/accept":
            return 204, None
        return 200, {}

    worker.request = fake_request
    await worker.accept_ready({"state": "InProgress", "playerResponse": "None"})
    await worker.accept_ready({"state": "InProgress", "playerResponse": "None"})

    assert len([c for c in calls if c[0] == "POST"]) == 1
    assert worker.ready_accepted is True
    assert any(m.get("type") == "ready_accepted" for m in emitted)


@pytest.mark.asyncio
async def test_accept_ready_disabled_and_stale_response(fake_settings):
    emitted = []
    worker = LCUWorker(fake_settings, emitted.append)
    fake_settings.value["auto_ready_enabled"] = False

    calls = []

    async def fake_request(method, path, body=None):
        calls.append((method, path, body))
        return 200, {"state": "InProgress", "playerResponse": "Accepted"}

    worker.request = fake_request
    await worker.accept_ready({"state": "InProgress", "playerResponse": "None"})
    assert calls == []

    fake_settings.value["auto_ready_enabled"] = True
    await worker.accept_ready({"state": "InProgress", "playerResponse": "None"})
    assert len([c for c in calls if c[0] == "POST"]) == 0


# lcu.py: own-action PATCH/POST flow, stale checks and fail-closed behaviour
@pytest.mark.asyncio
async def test_automate_pick_patch_then_complete(fake_settings):
    emitted = []
    worker = LCUWorker(fake_settings, emitted.append)
    worker.attempted = {}
    worker.completed = set()
    session = _base_session("pick", 111)
    fresh = _base_session("pick", 111)
    latest = _base_session("pick", 111)
    latest["actions"][0][0]["championId"] = 266

    calls = []

    async def fake_request(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET" and path == SELECT:
            if len([c for c in calls if c[0] == "GET" and c[1] == SELECT]) == 1:
                return 200, fresh
            return 200, latest
        if method == "GET" and path.endswith("pickable-champion-ids"):
            return 200, [266]
        if method == "PATCH":
            return 204, None
        if method == "POST" and path.endswith("/complete"):
            return 200, {}
        return 200, {}

    worker.request = fake_request
    await worker.automate(session)

    patch = [c for c in calls if c[0] == "PATCH"][0]
    assert patch[2] == {"championId": 266, "completed": True}
    assert any(c[0] == "POST" and c[1].endswith("/complete") for c in calls)
    assert 111 in worker.completed


@pytest.mark.asyncio
async def test_automate_no_post_when_patch_fails_or_disallowed(fake_settings):
    worker = LCUWorker(fake_settings, lambda _m: None)
    worker.attempted = {}
    worker.completed = set()
    session = _base_session("pick", 222)

    calls = []

    async def fail_patch_request(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET" and path == SELECT:
            return 200, _base_session("pick", 222)
        if method == "GET" and path.endswith("pickable-champion-ids"):
            return 200, [266]
        if method == "PATCH":
            return 500, None
        return 200, {}

    worker.request = fail_patch_request
    await worker.automate(session)
    assert not any(c[0] == "POST" and c[1].endswith("/complete") for c in calls)

    calls.clear()
    worker.attempted = {}
    taken = _base_session("pick", 222)
    taken["myTeam"].append({"cellId": 2, "championId": 266})

    async def taken_request(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET" and path == SELECT:
            return 200, taken
        return 200, {}

    worker.request = taken_request
    await worker.automate(session)
    assert not any(c[0] == "PATCH" for c in calls)


# lcu.py: SIMULATED_TRANSPORT reconnect path should rediscover credentials and not reuse old auth/port
@pytest.mark.asyncio
async def test_main_reconnect_rediscovers_credentials_and_cleans_child_tasks(monkeypatch, fake_settings):
    import lolpicker.lcu as lcu_module

    discovered = [
        lcu_module.Credentials(port=5123, password="pw-old", pid=101),
        lcu_module.Credentials(port=6222, password="pw-new", pid=202),
        None,
    ]
    auth_passwords = []
    ws_urls = []
    status_events = []
    event_loop_cancelled = asyncio.Event()
    snapshot_loop_cancelled = asyncio.Event()
    worker = LCUWorker(fake_settings, lambda message: status_events.append(message) if message.get("type") == "status" else None)

    async def fake_to_thread(fn, configured):
        return fn(configured)

    def fake_discover(_configured=""):
        return discovered.pop(0) if discovered else None

    class _FakeWs:
        def __init__(self, close_delay=0.03):
            self.close_delay = close_delay

        def __await__(self):
            async def ready():
                return self
            return ready().__await__()

        async def close(self):
            return None

        async def send_json(self, _payload):
            return None

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(self.close_delay)
            raise StopAsyncIteration

    class _FakeSession:
        def __init__(self, *, headers=None, **_kwargs):
            auth_passwords.append(b64decode(headers["Authorization"].split()[1]).decode().split(":", 1)[1])

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _tb):
            return False

        def ws_connect(self, url, **_kwargs):
            ws_urls.append(url)
            return _FakeWs()

    async def fake_snapshot_loop():
        try:
            while True:
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            snapshot_loop_cancelled.set()
            raise

    async def fake_event_loop(_ws):
        try:
            await asyncio.sleep(0.04)
        except asyncio.CancelledError:
            event_loop_cancelled.set()
            raise

    monkeypatch.setattr(lcu_module, "discover", fake_discover)
    monkeypatch.setattr(lcu_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(lcu_module.aiohttp, "ClientSession", _FakeSession)
    monkeypatch.setattr(worker, "snapshot_loop", fake_snapshot_loop)
    monkeypatch.setattr(worker, "event_loop", fake_event_loop)

    task = asyncio.create_task(worker.main())
    await asyncio.sleep(1.3)
    worker.stop()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)

    assert auth_passwords[:2] == ["pw-old", "pw-new"]
    assert ws_urls[:2] == ["wss://127.0.0.1:5123/", "wss://127.0.0.1:6222/"]
    assert status_events.count({"type": "status", "connected": True}) >= 2
    assert status_events.count({"type": "status", "connected": False}) >= 2
    assert snapshot_loop_cancelled.is_set() is True


# lcu.py: queue_id from gameflow session must be forwarded on mid-game phase transitions
@pytest.mark.asyncio
async def test_phase_handle_fetches_gameflow_queue_and_emits_queue_id(fake_settings):
    emitted = []
    worker = LCUWorker(fake_settings, emitted.append)

    async def fake_request(method, path, body=None):
        if method == "GET" and path == "/lol-gameflow/v1/session":
            return 200, {"gameData": {"queue": {"id": 450}}}
        if method == "GET" and path == READY:
            return 200, {"state": "None", "playerResponse": "Accepted"}
        return 200, {}

    worker.request = fake_request

    for phase in ("GameStart", "InProgress", "ChampSelect"):
        await worker.handle(PHASE, phase)
        phase_events = [m for m in emitted if m.get("type") == "phase" and m.get("phase") == phase]
        assert phase_events and phase_events[-1].get("queue_id") == 450
