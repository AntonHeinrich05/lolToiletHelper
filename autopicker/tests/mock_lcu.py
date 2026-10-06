"""Minimal simulated LCU (HTTPS + WAMP WebSocket) for local connection tests."""
import asyncio
import json
import ssl
import subprocess
import tempfile
from pathlib import Path

from aiohttp import web, WSMsgType


def make_ssl_context():
    directory = Path(tempfile.mkdtemp(prefix="mocklcu"))
    key, cert = directory / "key.pem", directory / "cert.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
                    "-out", str(cert), "-days", "1", "-subj", "/CN=127.0.0.1"], check=True, capture_output=True)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert), str(key))
    return context


class MockLCU:
    def __init__(self, password="secret", answer_pings=True, reject_first_requests=0, fail_completes=0):
        self.password = password
        self.fail_completes = fail_completes
        self.answer_pings = answer_pings
        self.reject_first_requests = reject_first_requests
        self.state = {"phase": "None", "ready": {"state": "Invalid", "playerResponse": "None"}, "session": None,
                      "pickable": [], "bannable": [], "lobby": None, "gameflow": None,
                      "pages": [], "owned_pages": 2, "current_page": None, "my_selection": {}}
        self.next_page_id = 100
        self.calls = []
        self.sockets = set()
        self.runner = None
        self.port = None

    def _authorized(self, request):
        from base64 import b64decode
        header = request.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        return b64decode(header.split()[1]).decode() == f"riot:{self.password}"

    async def handler(self, request):
        if not self._authorized(request):
            return web.Response(status=401, text="unauthorized")
        if self.reject_first_requests > 0:
            self.reject_first_requests -= 1
            return web.Response(status=500, text='{"message":"not ready"}')
        self.calls.append((request.method, request.path, await request.text() if request.can_read_body else ""))
        path, method = request.path, request.method
        if path == "/lol-gameflow/v1/gameflow-phase":
            return web.json_response(self.state["phase"])
        if path == "/lol-gameflow/v1/session":
            return web.json_response(self.state["gameflow"]) if self.state["gameflow"] else web.Response(status=404)
        if path == "/lol-matchmaking/v1/ready-check":
            if method == "GET":
                return web.json_response(self.state["ready"])
        if path == "/lol-matchmaking/v1/ready-check/accept":
            self.state["ready"]["playerResponse"] = "Accepted"
            return web.Response(status=204)
        if path == "/lol-lobby/v2/lobby":
            return web.json_response(self.state["lobby"]) if self.state["lobby"] else web.Response(status=404)
        if path == "/lol-champ-select/v1/session":
            return web.json_response(self.state["session"]) if self.state["session"] else web.Response(status=404)
        if path == "/lol-champ-select/v1/session/my-selection" and method == "GET":
            return web.json_response({"selectedSkinId": self.state.get("skin", 0), **self.state["my_selection"]})
        if path == "/lol-champ-select/v1/session/my-selection" and method == "PATCH":
            body = json.loads(self.calls[-1][2] or "{}")
            if body.get("selectedSkinId") != self.state.get("skin", 0):
                return web.Response(status=400, text='{"message":"selectedSkinId missing"}')  # strict like the schema
            body = {k: v for k, v in body.items() if k != "selectedSkinId"}
            self.state["my_selection"].update(body)
            for player in (self.state["session"] or {}).get("myTeam", []):
                if player["cellId"] == self.state["session"]["localPlayerCellId"]:
                    player["spell1Id"], player["spell2Id"] = body.get("spell1Id"), body.get("spell2Id")
            return web.Response(status=204)
        if path == "/lol-perks/v1/inventory":
            return web.json_response({"ownedPageCount": self.state["owned_pages"]})
        if path == "/lol-perks/v1/pages" and method == "GET":
            return web.json_response(self.state["pages"])
        if path == "/lol-perks/v1/pages" and method == "POST":
            body = json.loads(self.calls[-1][2] or "{}")
            editable = [p for p in self.state["pages"] if p.get("isEditable", True)]
            if len(editable) >= self.state["owned_pages"]:
                return web.Response(status=400, text='{"message":"Max pages reached"}')
            page = {**body, "id": self.next_page_id, "isEditable": True, "isDeletable": True, "lastModified": self.next_page_id}
            self.next_page_id += 1
            self.state["pages"].append(page)
            self.state["current_page"] = page["id"]
            return web.json_response(page)
        if path.startswith("/lol-perks/v1/pages/") and method == "DELETE":
            identifier = int(path.rsplit("/", 1)[1])
            self.state["pages"] = [p for p in self.state["pages"] if p["id"] != identifier]
            return web.Response(status=204)
        if path == "/lol-perks/v1/currentpage" and method == "PUT":
            self.state["current_page"] = json.loads(self.calls[-1][2])
            return web.Response(status=204)
        if path == "/lol-champ-select/v1/pickable-champion-ids":
            return web.json_response(self.state["pickable"])
        if path == "/lol-champ-select/v1/bannable-champion-ids":
            return web.json_response(self.state["bannable"])
        if path.startswith("/lol-champ-select/v1/session/actions/"):
            rest = path[len("/lol-champ-select/v1/session/actions/"):]
            if rest.endswith("/complete"):
                identifier = int(rest[:-len("/complete")])
                if self.fail_completes > 0:
                    self.fail_completes -= 1
                    return web.Response(status=500, text='{"message":"busy"}')
                for group in self.state["session"]["actions"]:
                    for action in group:
                        if action["id"] == identifier:
                            action["completed"], action["isInProgress"] = True, False
                            if action["type"] == "pick":
                                for player in self.state["session"]["myTeam"]:
                                    if player["cellId"] == action["actorCellId"]:
                                        player["championId"] = action["championId"]
                            else:
                                self.state["session"]["bans"]["myTeamBans"].append(action["championId"])
                return web.Response(status=204)
            identifier = int(rest)
            body = json.loads(self.calls[-1][2] or "{}")
            for group in self.state["session"]["actions"]:
                for action in group:
                    if action["id"] == identifier:
                        action["championId"] = body.get("championId", action.get("championId"))
                        if action["type"] == "pick":
                            for player in self.state["session"]["myTeam"]:
                                if player["cellId"] == action["actorCellId"]:
                                    player["championPickIntent"] = action["championId"]
            return web.Response(status=204)
        return web.Response(status=404)

    async def websocket(self, request):
        if not self._authorized(request):
            return web.Response(status=401)
        ws = web.WebSocketResponse(autoping=self.answer_pings)
        await ws.prepare(request)
        self.sockets.add(ws)
        try:
            async for message in ws:
                if message.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                    break
        finally:
            self.sockets.discard(ws)
        return ws

    async def publish(self, uri, data, event_type="Update"):
        payload = [8, "OnJsonApiEvent" + uri.replace("/", "_"), {"uri": uri, "data": data, "eventType": event_type}]
        for ws in list(self.sockets):
            await ws.send_json(payload)

    async def set_phase(self, phase):
        self.state["phase"] = phase
        await self.publish("/lol-gameflow/v1/gameflow-phase", phase)

    async def start(self, port=0):
        app = web.Application()
        app.router.add_get("/", self.websocket)
        app.router.add_route("*", "/{tail:.*}", self.handler)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", port, ssl_context=make_ssl_context())
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self):
        for ws in list(self.sockets):
            await ws.close()
        if self.runner:
            await self.runner.cleanup()
        self.runner = None

    def lockfile(self, pid):
        return f"LeagueClient:{pid}:{self.port}:{self.password}:https"
