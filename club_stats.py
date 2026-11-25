"""Season totals for Top 5 league clubs across available official competitions."""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import requests

import fotmob
from cache import get_cached, set_cached, TTL_CURRENT_SEASON

logger = logging.getLogger(__name__)
_build_lock = threading.Lock()

# Supercups are sometimes labelled with the qualifying season, not the match season.
CUPS = (
    (132, "FA Cup", "season"),
    (133, "EFL Cup", "season"),
    (247, "Community Shield", "supercup"),
    (138, "Copa del Rey", "season"),
    (139, "Supercopa de España", "supercup"),
    (141, "Coppa Italia", "season"),
    (222, "Supercoppa", "supercup"),
    (209, "DFB Pokal", "season"),
    (8924, "German Super Cup", "supercup"),
    (134, "Coupe de France", "season"),
    (150, "Coupe de la Ligue", "season"),
    (207, "Trophée des champions", "supercup"),
    (42, "Champions League", "season"),
    (73, "Europa League", "season"),
    (10216, "Conference League", "season"),
    (10611, "Champions League Qualification", "season"),
    (10613, "Europa League Qualification", "season"),
    (10615, "Conference League Qualification", "season"),
    (74, "UEFA Super Cup", "supercup"),
    (78, "FIFA Club World Cup", "calendar"),
    (10703, "FIFA Intercontinental Cup", "calendar"),
)


def _competition_page(competition_id, season=None):
    for key, league in fotmob.LEAGUES.items():
        if league["id"] == competition_id:
            return fotmob.get_league_page(key, season)
    cache_key = f"club-page:v1:{competition_id}:{season or 'current'}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    url = f"{fotmob.BASE_URL}/leagues/{competition_id}/overview"
    if season:
        url += f"?season={season}"
    page = fotmob._fetch_page(url)
    if page.get("details", {}).get("id") != competition_id:
        raise requests.RequestException(f"Unexpected competition returned for {competition_id}")
    set_cached(cache_key, page, TTL_CURRENT_SEASON)
    return page


def _season_pages(competition_id, kind, season):
    current = _competition_page(competition_id)
    available = current.get("allAvailableSeasons", [])
    start, end = map(int, season.split("/"))
    if kind == "season":
        labels = [season] if season in available else []
    elif kind == "supercup":
        labels = [s for s in (season, f"{start - 1}/{start}") if s in available]
    else:
        labels = [s for s in available if s.isdigit() and start - 1 <= int(s) <= end]
    for label in labels:
        page = (current if current.get("details", {}).get("selectedSeason") == label
                else _competition_page(competition_id, label))
        if page.get("details", {}).get("selectedSeason") != label:
            raise requests.RequestException(f"FotMob did not return {label} for {competition_id}")
        if kind != "season":
            dates = [m.get("status", {}).get("utcTime", "")
                     for m in page.get("fixtures", {}).get("allMatches", [])]
            dates = [d for d in dates if d]
            # Assign the entire edition by its first fixture, including summer Club World Cups.
            if not dates or not f"{start}-07-01" <= min(dates) < f"{end}-07-01":
                continue
        yield page


def _stat_rows(link, stat, ttl):
    cache_key = f"club-stat:v1:{link['TemplateId']}:{link['TournamentId']}:{stat}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    data = fotmob._fetch_json(
        f"{fotmob.DATA_URL}/stats/{link['TemplateId']}/season/{link['TournamentId']}/{stat}.json"
    )
    lists = data.get("TopLists") or []
    if not lists or not isinstance(lists[0].get("StatList"), list):
        raise requests.RequestException(f"FotMob returned no {stat} dataset")
    rows = lists[0]["StatList"]
    set_cached(cache_key, rows, ttl)
    return rows


def _match_stats(data, match, competition_id, team_ids):
    general = data.get("general") or {}
    content = data.get("content") or {}
    fixture_teams = {int(match[side]["id"]) for side in ("home", "away")}
    if (str(general.get("matchId")) != str(match["id"])
            or general.get("parentLeagueId", general.get("leagueId")) != competition_id
            or {general.get("homeTeam", {}).get("id"),
                general.get("awayTeam", {}).get("id")} != fixture_teams
            or not general.get("finished")):
        raise requests.RequestException("Match identity or completed status could not be verified")
    players = content.get("playerStats")
    event_data = (content.get("matchFacts") or {}).get("events") or {}
    events = event_data.get("events")
    header_teams = (data.get("header") or {}).get("teams") or []
    if (not players or not isinstance(events, list) or len(header_teams) != 2
            or any(not isinstance(t.get("score"), int) for t in header_teams)):
        raise requests.RequestException("Match player statistics or scoring events unavailable")

    goals, assists, penalties = {}, {}, {}
    scoring_events = [e for e in events if e.get("type") == "Goal"
                      and not e.get("isPenaltyShootoutEvent")]
    if len(scoring_events) != sum(t["score"] for t in header_teams):
        raise requests.RequestException("Match scoring events do not match the final score")
    for event in scoring_events:
        if event.get("ownGoal"):
            continue
        pid = event.get("playerId")
        if pid is None:
            raise requests.RequestException("Match goal is missing its scorer")
        goals[pid] = goals.get(pid, 0) + 1
        assistant = event.get("assistPlayerId")
        if assistant is not None:
            assists[assistant] = assists.get(assistant, 0) + 1
        if (event.get("penalty") or event.get("goalDescriptionKey") == "penalty"
                or event.get("goalDescription") == "Penalty"):
            penalties[pid] = penalties.get(pid, 0) + 1

    expected_players = set()
    lineup = content.get("lineup") or {}
    for side in ("homeTeam", "awayTeam"):
        team = lineup.get(side) or {}
        if not team.get("starters"):
            raise requests.RequestException("Match starting lineup unavailable")
        expected_players.update(p["id"] for p in team["starters"])
        expected_players.update(
            p["id"] for p in team.get("subs", [])
            if any(e.get("type") == "subIn"
                   for e in (p.get("performance") or {}).get("substitutionEvents", []))
        )
    stats = {stat: {} for stat in (
        "goals", "goal_assist", "mins_played", "rating", "expected_goals", "expected_assists"
    )}
    played = set()
    for player in players.values():
        fields = {
            entry["key"]: (entry.get("stat") or {}).get("value")
            for group in player.get("stats", [])
            for entry in group.get("stats", {}).values() if entry.get("key")
        }
        minutes = fields.get("minutes_played")
        pid, team_id = player["id"], player["teamId"]
        if minutes is None or (minutes == 0 and pid not in expected_players):
            continue
        if not isinstance(minutes, (int, float)) or minutes < 0:
            raise requests.RequestException("Invalid match minutes")
        played.add(pid)
        if team_id not in fixture_teams:
            raise requests.RequestException("Match player belongs to an unexpected team")
        for field, counts in (("goals", goals), ("assists", assists)):
            if fields.get(field) is not None and fields[field] != counts.get(pid, 0):
                raise requests.RequestException(f"Match {field} disagree with scoring events")
        if team_id not in team_ids:
            continue
        row = {
            "ParticiantId": pid, "ParticipantName": player["name"], "TeamId": team_id,
            "TeamName": player["teamName"], "MinutesPlayed": minutes, "MatchesPlayed": 1,
            "SubStatValue": 0, "StatValueCount": 1,
        }
        values = {
            "goals": goals.get(pid, 0), "goal_assist": assists.get(pid, 0),
            "mins_played": minutes, "rating": fields.get("rating_title"),
            "expected_goals": fields.get("expected_goals"),
            "expected_assists": fields.get("expected_assists"),
        }
        for stat, value in values.items():
            if stat == "rating" and value is None:
                continue
            stats[stat][(pid, team_id)] = {
                **row, "StatValue": value,
                "SubStatValue": penalties.get(pid, 0) if stat == "goals" else 0,
            }
    if not expected_players <= played or not (set(goals) | set(assists)) <= played:
        raise requests.RequestException("Match appearance statistics are incomplete")
    return stats


def _match_snapshot(match, competition_id, name, team_ids, ttl):
    cache_key = f"club-match:v1:{match['id']}"
    data = get_cached(cache_key)
    if data is None:
        data = fotmob._fetch_json(
            f"{fotmob.BASE_URL}/api/data/matchDetails?matchId={match['id']}"
        )
        stats = _match_stats(data, match, competition_id, team_ids)
        set_cached(cache_key, data, ttl)
    else:
        stats = _match_stats(data, match, competition_id, team_ids)
    return {
        "name": name, "stats": stats,
        "teams": {int(match[side]["id"]) for side in ("home", "away")} & team_ids,
    }


def _load_competition(competition, season, team_ids, ttl):
    competition_id, name, kind = competition
    snapshots, warnings = [], []
    complete = True
    seen_matches = set()
    try:
        for page in _season_pages(competition_id, kind, season):
            matches = [
                m for m in page.get("fixtures", {}).get("allMatches", [])
                if m.get("status", {}).get("started") or m.get("status", {}).get("finished")
            ]
            participating = {
                int(m[side]["id"]) for m in matches for side in ("home", "away")
            } & team_ids
            if not participating:
                continue
            metadata = page.get("stats") or {}
            label = page["details"]["selectedSeason"]
            link = next((s for s in metadata.get("seasonStatLinks", [])
                         if s["Name"] == label), None)
            available = {s["name"] for s in metadata.get("players") or []}
            if not link or not {"goals", "goal_assist"} <= available:
                if kind == "supercup":
                    for match in matches:
                        if not ({int(match[side]["id"]) for side in ("home", "away")} & team_ids):
                            continue
                        if match["id"] in seen_matches:
                            continue
                        seen_matches.add(match["id"])
                        try:
                            snapshots.append(_match_snapshot(
                                match, competition_id, name, team_ids, ttl
                            ))
                        except (requests.RequestException, json.JSONDecodeError) as exc:
                            message = f"{name}: match {match['id']} player statistics unavailable"
                            logger.warning("%s (%s): %s", message, season, exc)
                            warnings.append(message)
                            complete = False
                    continue
                message = f"{name}: player statistics unavailable"
                logger.warning("%s (%s)", message, season)
                warnings.append(message)
                continue
            stats = {}
            for stat in ("goals", "goal_assist", "mins_played", "rating",
                         "expected_goals", "expected_assists"):
                stats[stat] = None
                if stat not in available:
                    continue
                try:
                    stats[stat] = {
                        (p["ParticiantId"], p["TeamId"]): p
                        for p in _stat_rows(link, stat, ttl)
                        if p["TeamId"] in participating
                    }
                except (requests.RequestException, json.JSONDecodeError) as exc:
                    message = f"{name}: {stat} temporarily unavailable"
                    logger.warning("%s (%s): %s", message, season, exc)
                    warnings.append(message)
                    complete = False
            if stats["goals"] is not None and stats["goal_assist"] is not None:
                snapshots.append({"name": name, "stats": stats, "teams": participating})
    except (requests.RequestException, json.JSONDecodeError) as exc:
        message = f"{name}: competition data temporarily unavailable"
        logger.warning("%s (%s): %s", message, season, exc)
        warnings.append(message)
        complete = False
    return snapshots, warnings, complete


def _aggregate(snapshots, teams):
    players = {}
    incomplete_appearances = set()
    missing_expected = {"xG": set(), "xA": set()}
    missing = {"MinutesPlayed": set(), "MatchesPlayed": set(), "xG": set(), "xA": set()}
    for snapshot in snapshots:
        stats = snapshot["stats"]
        for field, stat in (("MinutesPlayed", "mins_played"), ("MatchesPlayed", "mins_played"),
                            ("xG", "expected_goals"), ("xA", "expected_assists")):
            if stats[stat] is None:
                missing[field].update(snapshot["teams"])
        keys = set().union(*(rows for rows in stats.values() if rows is not None))
        for key in sorted(keys):
            pid, team_id = key
            if team_id not in teams:
                continue
            rows = {stat: values.get(key) if values is not None else None
                    for stat, values in stats.items()}
            source = next(p for p in rows.values() if p is not None)
            if pid not in players:
                players[pid] = {
                    **source, **teams[team_id], "Goals": 0, "Assists": 0, "SubStatValue": 0,
                    "MinutesPlayed": 0, "MatchesPlayed": 0, "xG": 0, "xA": 0,
                    "_rating_sum": 0, "_rated_matches": 0, "_teams": set(),
                }
            player = players[pid]
            player["_teams"].add(team_id)
            for field, stat in (("Goals", "goals"), ("Assists", "goal_assist"),
                                ("xG", "expected_goals"), ("xA", "expected_assists")):
                if rows[stat] and rows[stat]["StatValue"] is None:
                    missing_expected[field].add(pid)
                else:
                    player[field] += rows[stat]["StatValue"] if rows[stat] else 0
            if rows["goals"]:
                player["SubStatValue"] += rows["goals"].get("SubStatValue") or 0
            if rows["mins_played"]:
                player["MinutesPlayed"] += rows["mins_played"]["MinutesPlayed"]
                player["MatchesPlayed"] += rows["mins_played"]["MatchesPlayed"]
            elif any(rows[s] for s in ("goals", "goal_assist")):
                # Scoring without an appearance row must not become zero minutes.
                incomplete_appearances.add(pid)
            rating = rows["rating"]
            if rating and rating.get("StatValueCount", 0) > 0:
                count = rating["StatValueCount"]
                player["_rating_sum"] += rating["StatValue"] * count
                player["_rated_matches"] += count
    for player in players.values():
        count = player.pop("_rated_matches")
        total = player.pop("_rating_sum")
        player["Rating"] = round(total / count, 2) if count else None
        for field, unavailable_teams in missing.items():
            if player["_teams"] & unavailable_teams:
                player[field] = None
        if player["ParticiantId"] in incomplete_appearances:
            player["MinutesPlayed"] = player["MatchesPlayed"] = None
        player.pop("_teams")
        for field in ("Goals", "Assists"):
            player[field] = int(player[field])
        for field in ("xG", "xA"):
            if player["ParticiantId"] in missing_expected[field]:
                player[field] = None
            elif player[field] is not None:
                player[field] = round(player[field], 1)
    return list(players.values())


def _season_totals(season):
    cache_key = f"all-club:v2:{season}"
    result = get_cached(cache_key)
    if result is None:
        teams = {}
        for key, league in fotmob.LEAGUES.items():
            table, _ = fotmob.get_standings(key, season)
            if not table:
                raise requests.RequestException(
                    f"Cannot determine {league['name']} clubs for {season}"
                )
            for team in table:
                teams[team["id"]] = {
                    "league_key": key, "league_id": league["id"], "league_name": league["name"],
                }
        ttl = fotmob._season_ttl(season, fotmob.get_league_page("epl"))
        competitions = [
            (league["id"], league["name"], "season") for league in fotmob.LEAGUES.values()
        ] + list(CUPS)
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(
                lambda competition: _load_competition(competition, season, set(teams), ttl),
                competitions,
            ))
        snapshots = [s for entries, _, _ in results for s in entries]
        result = {
            "players": _aggregate(snapshots, teams),
            "included_competitions": list(dict.fromkeys(s["name"] for s in snapshots)),
            "unavailable_competitions": list(dict.fromkeys(
                warning for _, warnings, _ in results for warning in warnings
            )),
        }
        if all(complete for _, _, complete in results):
            set_cached(cache_key, result, ttl)
    return result


def get_top_club_stats(stat_type, season, limit=30):
    result = get_cached(f"all-club:v2:{season}")
    if result is None:
        with _build_lock:
            result = _season_totals(season)
    result = deepcopy(result)
    for player in result["players"]:
        player["StatValue"] = (
            player["Rating"] if stat_type == "rating" else
            player["Goals"] if stat_type == "goals" else
            player["Assists"] if stat_type == "assists" else player["Goals"] + player["Assists"]
        )
    if stat_type == "rating":
        result["players"] = sorted(
            (p for p in result["players"]
             if p["StatValue"] is not None and p["MatchesPlayed"] is not None and p["MatchesPlayed"] >= 5),
            key=lambda p: (-p["StatValue"], p["ParticipantName"], p["ParticiantId"]),
        )[:limit]
    else:
        result["players"] = sorted(
            (p for p in result["players"] if p["StatValue"] > 0),
            key=lambda p: (-p["StatValue"], p["ParticipantName"], p["ParticiantId"]),
        )[:limit]
    return result
