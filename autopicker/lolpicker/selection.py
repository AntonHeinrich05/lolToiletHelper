"""Pure decisions: never derive lanes from draft order or cell IDs."""
from .urls import LANES, slug


def actions(session):
    return [a for group in session.get("actions", []) for a in group]


def own_player(session):
    return next((p for p in session.get("myTeam", []) if p.get("cellId") == session.get("localPlayerCellId")), {})


def roster(session):
    result = []
    for player in session.get("theirTeam", []):
        champ = player.get("championId", 0)
        if not champ:
            champ = next((a.get("championId", 0) for a in actions(session)
                          if a.get("actorCellId") == player.get("cellId") and a.get("type") == "pick" and a.get("championId")), 0)
        result.append({"champion_id": champ, "role": LANES.get((player.get("assignedPosition") or "").lower(), "")})
    return result


def available(session, champion, action_type="pick"):
    bans = session.get("bans", {}) or {}
    banned = set(bans.get("myTeamBans", []) + bans.get("theirTeamBans", []))
    banned.update(a.get("championId") for a in actions(session) if a.get("type") == "ban" and a.get("completed"))
    if champion in banned:
        return False
    # Only locked picks exclude champions, not our own hover. Avoid banning team hovers.
    for action in actions(session):
        if action.get("type") == "pick" and action.get("completed") and action.get("championId") == champion:
            return False
    if action_type == "ban":
        for player in session.get("myTeam", []):
            if champion in (player.get("championId"), player.get("championPickIntent")):
                return False
    return True


def choose(session, options, action_type):
    key = "auto_pick_champs" if action_type == "pick" else "auto_ban_champs"
    allowed = session.get("pickableChampionIds" if action_type == "pick" else "bannableChampionIds")
    candidates = [c for c in options.get(key, []) if available(session, c, action_type) and (allowed is None or c in allowed)]
    if action_type == "pick":
        enemies = {p["champion_id"] for p in roster(session)}
        safe = [c for c in candidates if not enemies.intersection(options.get("bad_matchups", {}).get(str(c), []))]
        candidates = safe or candidates
    return candidates[0] if candidates else None


def active_action(session):
    me = session.get("localPlayerCellId")
    return next((a for a in actions(session) if me is not None and a.get("actorCellId") == me
                 and a.get("isInProgress") and not a.get("completed") and a.get("type") in ("pick", "ban")), None)


def draft_opponent(session):
    role = LANES.get((own_player(session).get("assignedPosition") or "").lower(), "")
    matches = [p for p in roster(session) if p["role"] == role and p["champion_id"]]
    return matches[0] if role and len(matches) == 1 else None


def player_identity(player):
    full = player.get("riotId")
    if full:
        return str(full).casefold()
    name, tag = player.get("riotIdGameName"), player.get("riotIdTagLine")
    if name and tag:
        return f"{name}#{tag}".casefold()
    return str(player.get("summonerName") or "").casefold()


def live_matchup(data):
    players = data.get("allPlayers", [])
    active = player_identity(data.get("activePlayer", {}))
    mine = [p for p in players if active and player_identity(p) == active]
    if len(mine) != 1:
        return None
    me = mine[0]
    lane = LANES.get(str(me.get("position") or "").lower(), "")
    team = me.get("team")
    enemy = [p for p in players if team and p.get("team") and p.get("team") != team
             and lane and LANES.get(str(p.get("position") or "").lower()) == lane]
    if len(enemy) != 1:
        return None
    def champion(player):
        raw = player.get("rawChampionName", "")
        return slug(raw.removeprefix("game_character_displayname_")) if raw.startswith("game_character_displayname_") else slug(player.get("championName", ""))
    own, opp = champion(me), champion(enemy[0])
    if not own or not opp:
        return None
    return {"champion": own, "opponent": opp, "role": lane, "opponent_role": lane, "source": "live"}