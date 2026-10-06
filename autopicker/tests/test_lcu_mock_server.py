"""End-to-end LCU worker tests against a simulated HTTPS/WebSocket League client."""
import asyncio
import contextlib
import os
import time

import pytest

from lolpicker import lcu
from mock_lcu import MockLCU

pytestmark = pytest.mark.asyncio


class Settings:
    def __init__(self, lockfile):
        self.value = {"lockfile_path": str(lockfile), "auto_ready_enabled": True, "auto_pick_enabled": True,
                      "auto_pick_champs": [266, 10], "auto_ban_champs": [51], "bad_matchups": {"266": [222]},
                      "loadouts": {}}

    def snapshot(self):
        return dict(self.value)


def champ_select(pick_in_progress=False, ban_in_progress=False, timer=None):
    return {
        "localPlayerCellId": 1, "queueId": 420,
        "myTeam": [{"cellId": 1, "assignedPosition": "top", "championId": 0, "championPickIntent": 0},
                   {"cellId": 2, "assignedPosition": "jungle", "championId": 0, "championPickIntent": 64}],
        "theirTeam": [{"cellId": 6, "assignedPosition": "top", "championId": 0}],
        "actions": [[{"id": 1, "type": "ban", "actorCellId": 1, "isInProgress": ban_in_progress, "completed": False, "championId": 0}],
                    [{"id": 2, "type": "pick", "actorCellId": 1, "isInProgress": pick_in_progress, "completed": False, "championId": 0}]],
        "bans": {"myTeamBans": [], "theirTeamBans": []},
        "timer": {"phase": timer or ("PLANNING" if not (pick_in_progress or ban_in_progress) else "BAN_PICK")},
    }


async def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return predicate()


@contextlib.asynccontextmanager
async def running(tmp_path, mock, **mock_kwargs):
    await mock.start()
    lockfile = tmp_path / "lockfile"
    lockfile.write_text(mock.lockfile(os.getpid()), encoding="utf-8")
    events = []
    settings = Settings(lockfile)
    monkeypatched = lcu.asyncio.to_thread

    async def inline(fn, *args):
        return fn(*args)

    lcu.asyncio.to_thread = inline
    worker = lcu.LCUWorker(settings, events.append)
    task = asyncio.create_task(worker.main())
    try:
        yield worker, events, settings, lockfile
    finally:
        lcu.asyncio.to_thread = monkeypatched
        worker.stopped.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await mock.stop()


def statuses(events):
    return [e["connected"] for e in events if e["type"] == "status"]


# lcu.py: a server that never answers WebSocket pings and returns 500 while booting must not flicker
async def test_connection_is_stable_without_pongs_and_with_startup_errors(tmp_path):
    mock = MockLCU(answer_pings=False, reject_first_requests=3)
    async with running(tmp_path, mock) as (worker, events, _settings, _lockfile):
        assert await wait_for(lambda: statuses(events) == [True])
        await asyncio.sleep(2.5)
        assert statuses(events) == [True]
        assert worker.connected is True


# lcu.py: closing League and starting it again with new port/password reconnects automatically
async def test_reconnects_after_league_restart_with_new_credentials(tmp_path):
    mock = MockLCU(password="first")
    async with running(tmp_path, mock) as (worker, events, _settings, lockfile):
        assert await wait_for(lambda: statuses(events) == [True])
        await mock.stop()
        assert await wait_for(lambda: statuses(events) == [True, False], timeout=8)
        assert [e for e in events if e["type"] == "phase"][-1]["phase"] == "None"
        lockfile.unlink()
        await asyncio.sleep(2.5)
        assert statuses(events) == [True, False]
        restarted = MockLCU(password="second")
        await restarted.start()
        lockfile.write_text(restarted.lockfile(os.getpid()), encoding="utf-8")
        try:
            assert await wait_for(lambda: statuses(events) == [True, False, True], timeout=10)
            assert worker.base.endswith(str(restarted.port))
        finally:
            await restarted.stop()


# lcu.py: ready check accepted once via WebSocket event, phase badge forwarded
async def test_ready_check_accept_via_event(tmp_path):
    mock = MockLCU()
    async with running(tmp_path, mock) as (_worker, events, _settings, _lockfile):
        assert await wait_for(lambda: statuses(events) == [True])
        await mock.set_phase("ReadyCheck")
        mock.state["ready"] = {"state": "InProgress", "playerResponse": "None"}
        await mock.publish(lcu.READY, dict(mock.state["ready"]))
        assert await wait_for(lambda: any(e["type"] == "ready_accepted" for e in events))
        accepts = [c for c in mock.calls if c[0] == "POST" and c[1].endswith("/accept")]
        assert len(accepts) == 1
        assert any(e["type"] == "phase" and e["phase"] == "ReadyCheck" for e in events)


# lcu.py: planning phase hovers intent, ban turn bans, pick turn avoids bad matchup and locks in
async def test_hover_ban_and_pick_flow(tmp_path):
    mock = MockLCU()
    async with running(tmp_path, mock) as (worker, events, _settings, _lockfile):
        assert await wait_for(lambda: statuses(events) == [True])
        mock.state["session"] = champ_select()
        mock.state["pickable"], mock.state["bannable"] = [266, 10], [51, 64]
        await mock.set_phase("ChampSelect")
        assert await wait_for(lambda: mock.state["session"]["actions"][1][0]["championId"] == 266)
        assert not any(c[0] == "POST" for c in mock.calls)
        assert mock.state["session"]["myTeam"][0]["championPickIntent"] == 266

        mock.state["session"]["actions"][0][0]["isInProgress"] = True
        mock.state["session"]["timer"]["phase"] = "BAN_PICK"
        await mock.publish(lcu.SELECT, mock.state["session"])
        assert await wait_for(lambda: mock.state["session"]["bans"]["myTeamBans"] == [51])

        mock.state["session"]["theirTeam"][0]["championId"] = 222
        mock.state["session"]["actions"][1][0]["isInProgress"] = True
        await mock.publish(lcu.SELECT, mock.state["session"])
        assert await wait_for(lambda: mock.state["session"]["myTeam"][0]["championId"] == 10)
        assert await wait_for(lambda: any(e["type"] == "pick_status" and e["status"].get(10) == "hovered" and e["status"].get(266) == "ok" for e in events))
        assert await wait_for(lambda: any(e["type"] == "draft" and e["champion_id"] == 10 for e in events))


# lcu.py: a failed lock-in is retried every second until the LCU marks the action completed
async def test_lock_in_is_retried_until_completed(tmp_path):
    mock = MockLCU(fail_completes=2)
    async with running(tmp_path, mock) as (_worker, events, _settings, _lockfile):
        assert await wait_for(lambda: statuses(events) == [True])
        mock.state["session"] = champ_select(pick_in_progress=True)
        await mock.set_phase("ChampSelect")
        assert await wait_for(lambda: mock.state["session"]["myTeam"][0]["championId"] == 266, timeout=8)
        completes = [c for c in mock.calls if c[0] == "POST" and c[1].endswith("/complete")]
        assert len(completes) == 3
        patches = [c for c in mock.calls if c[0] == "PATCH"]
        assert all('"completed": true' in c[2] for c in patches)


# lcu.py: PLANNING phase only declares intent even when the LCU flags the own pick action as in progress
async def test_planning_phase_declares_intent_without_locking(tmp_path):
    mock = MockLCU()
    async with running(tmp_path, mock) as (_worker, events, _settings, _lockfile):
        assert await wait_for(lambda: statuses(events) == [True])
        mock.state["session"] = champ_select(pick_in_progress=True, timer="PLANNING")
        await mock.set_phase("ChampSelect")
        assert await wait_for(lambda: mock.state["session"]["myTeam"][0]["championPickIntent"] == 266)
        await asyncio.sleep(1.5)
        assert not any(c[0] == "POST" for c in mock.calls)
        patches = [c for c in mock.calls if c[0] == "PATCH"]
        assert patches and all('"completed": false' in c[2] for c in patches)
        assert any(e["type"] == "pick_status" and e["status"].get(266) == "hovered" for e in events)

        mock.state["session"]["timer"]["phase"] = "BAN_PICK"
        await mock.publish(lcu.SELECT, mock.state["session"])
        assert await wait_for(lambda: mock.state["session"]["myTeam"][0]["championId"] == 266)


# lcu.py: after our pick is locked, a configured loadout creates the rune page, selects it and sets the spells once.
async def test_locked_pick_applies_runes_and_spells_once(tmp_path):
    mock = MockLCU()
    session = champ_select()
    session["myTeam"][0]["championId"] = 266
    session["actions"][1][0].update(completed=True, championId=266)
    mock.state["session"] = session
    mock.state["pages"] = [{"id": 1, "name": "Autopicker alt", "isEditable": True, "isDeletable": True, "lastModified": 5},
                           {"id": 2, "name": "Meine Seite", "isEditable": True, "isDeletable": True, "lastModified": 7},
                           {"id": 3, "name": "Älteste", "isEditable": True, "isDeletable": True, "lastModified": 1}]
    loadout = {"primary": 8000, "sub": 8100, "perks": [8010, 9111, 9104, 8014, 8139, 8135], "shards": [5008, 5008, 5001], "spells": [4, 12]}
    async with running(tmp_path, mock) as (worker, events, settings, _):
        settings.value["loadouts"] = {"266": loadout}
        worker.names = {266: "Aatrox"}
        assert await wait_for(lambda: True in statuses(events))
        await mock.set_phase("ChampSelect")
        await mock.publish("/lol-champ-select/v1/session", session)
        assert await wait_for(lambda: mock.state["my_selection"].get("spell2Id") == 12)
        names = [p["name"] for p in mock.state["pages"]]
        assert names == ["Meine Seite", "Autopicker Aatrox"]  # own old Autopicker page and the oldest page were replaced
        created = mock.state["pages"][-1]
        assert created["selectedPerkIds"] == [8010, 9111, 9104, 8014, 8139, 8135, 5008, 5008, 5001]
        assert mock.state["current_page"] == created["id"]
        ban_states = [e["ban_status"] for e in events if e["type"] == "pick_status"]
        assert ban_states and ban_states[-1] == {51: "ok"}
        await mock.publish("/lol-champ-select/v1/session", session)
        await asyncio.sleep(0.3)
        assert sum(1 for c in mock.calls if c[0] == "POST" and c[1] == "/lol-perks/v1/pages") == 1


# lcu.py: assigned jungle without Smite in the saved spells -> Flash + Smite on the preferred side, verified in the session
async def test_jungle_spell_fallback_and_flash_side(tmp_path):
    mock = MockLCU()
    session = champ_select()
    session["myTeam"][0].update(championId=266, assignedPosition="jungle")
    session["actions"][1][0].update(completed=True, championId=266)
    mock.state["session"] = session
    loadout = {"primary": 8000, "sub": 8100, "perks": [8010, 9111, 9104, 8014, 8139, 8135], "shards": [5008, 5008, 5001], "spells": [4, 12]}
    async with running(tmp_path, mock) as (worker, events, settings, _):
        settings.value["loadouts"] = {"266": loadout}
        settings.value["flash_side"] = "right"
        assert await wait_for(lambda: True in statuses(events))
        await mock.set_phase("ChampSelect")
        await mock.publish("/lol-champ-select/v1/session", session)
        assert await wait_for(lambda: mock.state["my_selection"].get("spell1Id") == 11)
        assert mock.state["my_selection"] == {"spell1Id": 11, "spell2Id": 4}
        assert session["myTeam"][0]["spell1Id"] == 11
        patches = [c for c in mock.calls if c[0] == "PATCH" and c[1].endswith("/my-selection")]
        assert len(patches) == 1  # verified after the first PATCH, no blind retries
