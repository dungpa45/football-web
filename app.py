"""
FotMob Web App - Modern Glassmorphism UI
Chạy: python app_fotmob.py
"""
import os
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, abort, jsonify, render_template, request, redirect, session, url_for, Response
from pymongo.errors import PyMongoError
from requests.exceptions import RequestException
from mongo import my_db
from club_stats import get_top_club_stats
from fotmob import (
    LEAGUES, get_standings, get_top_scorers, get_top_assists, get_top_goals_assists,
    get_available_seasons, get_player_info,
    get_team_info, get_team_squad, get_team_coach, get_team_venue,
    get_team_coach_history,
    get_top_all_leagues, get_top_ga_all_leagues, get_top_rating_all_leagues,
)
from honours_db import (
    ensure_indexes, get_player_honours, save_player_honours,
    set_verified, seed_from_wikipedia, get_honours_summary, schedule_individual_refresh,
    player_honours as honours_coll, CATEGORY_MAP,
    is_individual_refresh_active, wait_for_individual_refresh,
)
from wiki_honours import is_disqualified_individual_award, sort_individual_awards, normalize_trophy_name

app = Flask(__name__)

APP_ENV = os.getenv("APP_ENV", "development").lower()
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
secret_key = os.getenv("FLASK_SECRET_KEY")
if APP_ENV == "production" and not secret_key:
    raise RuntimeError("FLASK_SECRET_KEY must be configured in production")
if APP_ENV == "production" and (not ADMIN_USER or not ADMIN_PASS):
    raise RuntimeError("ADMIN_USER and ADMIN_PASS must be configured in production")

app.config.update(
    SECRET_KEY=secret_key or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)

logger = logging.getLogger(__name__)


def _csrf_token():
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": _csrf_token}


@app.before_request
def protect_admin_posts():
    if request.method != "POST" or not (request.endpoint or "").startswith("fm_admin_"):
        return
    expected = session.get("_csrf_token", "")
    submitted = request.form.get("_csrf_token", "")
    if not expected or not hmac.compare_digest(expected.encode(), submitted.encode()):
        abort(400, description="Invalid or missing CSRF token")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not ADMIN_USER or not ADMIN_PASS:
            logger.error("Admin access denied because credentials are not configured")
            return Response("Admin access is not configured", 503)
        auth = request.authorization
        if not auth or not (
            hmac.compare_digest(auth.username.encode(), ADMIN_USER.encode())
            and hmac.compare_digest(auth.password.encode(), ADMIN_PASS.encode())
        ):
            return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Admin"'})
        return f(*args, **kwargs)
    return decorated

def _valid_season(season):
    match = re.fullmatch(r"(\d{4})/(\d{4})", season)
    return bool(match and int(match.group(2)) == int(match.group(1)) + 1)


def _available_seasons(league_key):
    try:
        seasons = get_available_seasons(league_key)
        if isinstance(seasons, list):
            seasons = [s for s in seasons if isinstance(s, str) and _valid_season(s)]
            if seasons:
                return seasons
        logger.warning("FotMob returned no valid seasons for %s", league_key)
    except (RequestException, json.JSONDecodeError) as exc:
        logger.warning("Could not retrieve seasons for %s: %s", league_key, exc)

    now = datetime.now(timezone.utc)
    year = now.year if now.month >= 8 else now.year - 1
    return [f"{start}/{start + 1}" for start in range(year, 2015, -1)]


def _ctx(league_key=None, season=None):
    """Context chung cho mọi template."""
    league_key = league_key or request.args.get("league", "epl")
    season = season or request.args.get("season")
    if league_key not in LEAGUES:
        abort(404)
    if season and not _valid_season(season):
        abort(400, description="Invalid season")
    league = LEAGUES[league_key]
    seasons = _available_seasons(league_key)
    if season and season not in seasons:
        seasons = [season, *seasons]
    return {
        "leagues": LEAGUES,
        "current_league": league_key,
        "current_season": season or seasons[0],
        "league_name": league["name"],
        "league_id": league["id"],
        "seasons": seasons,
    }


@app.route("/healthz")
def healthz():
    return jsonify(status="ok")


@app.route("/readyz")
def readyz():
    try:
        my_db.command("ping")
    except PyMongoError as exc:
        logger.warning("MongoDB readiness check failed: %s", exc)
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok")


@app.errorhandler(RequestException)
@app.errorhandler(json.JSONDecodeError)
def handle_upstream_error(error):
    logger.warning("Football data source request failed: %s", error)
    return "Football data is temporarily unavailable", 503


@app.errorhandler(PyMongoError)
def handle_database_error(error):
    logger.exception("MongoDB request failed")
    return "Database is temporarily unavailable", 503


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def fm_home():
    return render_template("home.html", leagues=LEAGUES, seasons=_available_seasons("epl"))


@app.route("/standings")
def fm_standings():
    ''' Hiển thị bảng xếp hạng. URL: /standings?league=epl&season=2024/2025'''
    ctx = _ctx()
    standings, legend = get_standings(ctx["current_league"], ctx["current_season"])
    return render_template("standings.html", standings=standings, legend=legend, **ctx)


@app.route("/topscorers")
def fm_topscorers():
    ctx = _ctx()
    players = get_top_scorers(ctx["current_league"], ctx["current_season"], limit=30)
    return render_template("topscorers.html", players=players, **ctx)


@app.route("/topassists")
def fm_topassists():
    ctx = _ctx()
    players = get_top_assists(ctx["current_league"], ctx["current_season"], limit=30)
    return render_template("topassists.html", players=players, **ctx)


@app.route("/topga")
def fm_topga():
    ctx = _ctx()
    players = get_top_goals_assists(ctx["current_league"], ctx["current_season"], limit=30)
    return render_template("topga.html", players=players, **ctx)


@app.route("/all/topscorers")
def fm_all_topscorers():
    return _render_all_top("goals", "Top Scorers")


@app.route("/all/topassists")
def fm_all_topassists():
    return _render_all_top("assists", "Top Assists")


@app.route("/all/topga")
def fm_all_topga():
    return _render_all_top("ga", "Top G+A")


@app.route("/all/toprating")
def fm_all_toprating():
    return _render_all_top("rating", "Top Rating")


def _render_all_top(stat_type, title):
    scope = request.args.get("scope", "league")
    if scope not in ("league", "all"):
        abort(400, description="Invalid competition scope")
    ctx = _ctx()
    season = ctx["current_season"]
    coverage = {}
    if scope == "all":
        totals = get_top_club_stats(stat_type, season)
        players = totals["players"]
        coverage = {
            "included_competitions": totals["included_competitions"],
            "unavailable_competitions": totals["unavailable_competitions"],
        }
    elif stat_type == "ga":
        players = get_top_ga_all_leagues(season=season, limit_per_league=10)
    elif stat_type == "rating":
        players = get_top_rating_all_leagues(season=season)
    else:
        players = get_top_all_leagues(
            "goals" if stat_type == "goals" else "goal_assist",
            season=season, limit_per_league=10,
        )
    return render_template(
        "top_all.html", players=players[:30], stat_type=stat_type, page_title=title,
        page_subtitle="Top 5 League Clubs · All club competitions" if scope == "all"
                      else "All Top 5 Leagues",
        competition_scope=scope, **coverage, **ctx,
    )


def _parse_player_info(player):
    """Parse playerInformation thành list dễ hiển thị."""
    result = []
    for info in player.get("playerInformation", []):
        title = info.get("title", "")
        val = info.get("value", {})
        fallback = val.get("fallback", "")
        # Contract end: parse dict thành date string
        if title == "Contract end" and isinstance(fallback, dict):
            utc = fallback.get("utcTime", "")
            fallback = utc[:10] if utc else "-"
        result.append({"label": title, "value": fallback})
    birth_date = player.get("birthDate")
    if (isinstance(birth_date, dict) and isinstance(birth_date.get("utcTime"), str)
            and birth_date["utcTime"]
            and not any(info["label"].lower() in ("born", "date of birth") for info in result)):
        result.append({"label": "Born", "value": birth_date["utcTime"][:10]})
    return result


def _aggregate_season_stats(player):
    """Tổng hợp stats current season per tournament + career totals."""
    if not player:
        return [], {}, []

    import re as _re
    from collections import defaultdict

    career_items = player.get("careerHistory", {}).get("careerItems", {})
    stat_seasons = player.get("statSeasons", [])
    matches = player.get("recentMatches")
    if not isinstance(matches, list):
        matches = []

    def _int(v):
        return int(_re.sub(r'\D', '', str(v or 0)) or 0)

    # --- Current season name from statSeasons[0] ---
    season_name = stat_seasons[0]["seasonName"] if stat_seasons else None
    # NT uses single year (e.g. "2026" for season "2025/2026")
    nt_season_name = season_name.split("/")[-1] if season_name and "/" in season_name else season_name

    # --- Build per-tournament stats from careerHistory (accurate data from FotMob) ---
    tourney = {}  # leagueId -> {league, matches, goals, assists, minutes}
    for level, sn in [("senior", season_name), ("national team", nt_season_name)]:
        for entry in career_items.get(level, {}).get("seasonEntries", []):
            if entry.get("seasonName") != sn:
                continue
            for ts in entry.get("tournamentStats", []):
                if ts.get("isFriendly"):
                    continue
                lid = ts.get("leagueId") or ts.get("tournamentId")
                tourney[lid] = {
                    "league": ts.get("leagueName", "Unknown"),
                    "matches": _int(ts.get("appearances")),
                    "goals": _int(ts.get("goals")),
                    "assists": _int(ts.get("assists")),
                    "minutes": 0,
                }

    # --- Add minutes from recentMatches (only for tournaments in current season) ---
    current_tids = set(tourney.keys())
    # Also include statSeasons tournament IDs for matching
    if stat_seasons:
        for t in stat_seasons[0].get("tournaments", []):
            current_tids.add(t["tournamentId"])
    min_by_lid = defaultdict(int)
    for m in matches:
        lid = m.get("leagueId")
        if lid in current_tids:
            min_by_lid[lid] += m.get("minutesPlayed", 0) or 0
    for lid, t in tourney.items():
        t["minutes"] = min_by_lid.get(lid, 0)

    per_tournament = sorted(tourney.values(), key=lambda x: x["matches"], reverse=True)
    season_total = {
        "league": "Total",
        "matches": sum(t["matches"] for t in tourney.values()),
        "goals": sum(t["goals"] for t in tourney.values()),
        "assists": sum(t["assists"] for t in tourney.values()),
        "minutes": sum(t["minutes"] for t in tourney.values()),
    }

    # --- Career totals ---
    total_apps, total_goals, total_assists = 0, 0, 0
    for data in career_items.values():
        for e in data.get("teamEntries", []):
            total_apps += _int(e.get("appearances"))
            total_goals += _int(e.get("goals"))
            total_assists += _int(e.get("assists"))
    career_totals = [
        {"label": "Appearances", "value": str(total_apps)},
        {"label": "Goals", "value": str(total_goals)},
        {"label": "Assists", "value": str(total_assists)},
    ]
    return per_tournament, season_total, career_totals


@app.route("/player/<int:player_id>")
def fm_player(player_id):
    ctx = _ctx()
    player = get_player_info(player_id)
    if not player:
        return "Player not found", 404
    # Redirect to coach page if isCoach
    if player.get("isCoach"):
        return redirect(url_for("fm_coach", coach_id=player_id))
    position_description = player.get("positionDescription")
    primary_position = (
        position_description.get("primaryPosition")
        if isinstance(position_description, dict) else None
    )
    if not isinstance(primary_position, dict):
        primary_position = {}
    position_label = primary_position.get("label")
    position_key = primary_position.get("key")
    if not isinstance(position_key, str) or not position_key.strip():
        extra_positions = position_description.get("positions") if isinstance(
            position_description, dict
        ) else None
        if isinstance(extra_positions, list):
            ordered_positions = sorted(
                (position for position in extra_positions if isinstance(position, dict)),
                key=lambda position: position.get("isMainPosition") is not True,
            )
            for position in ordered_positions:
                details = position.get("strPos")
                if not isinstance(details, dict):
                    details = position.get("strPosShort")
                if not isinstance(details, dict):
                    continue
                detail_key = details.get("key")
                detail_label = details.get("label")
                if isinstance(detail_key, str) and detail_key.strip():
                    position_key = detail_key
                    if isinstance(detail_label, str) and detail_label.strip():
                        position_label = detail_label
                    break
    if not isinstance(position_label, str) or not position_label.strip():
        position_label = "Unknown position"
    if not isinstance(position_key, str) or not position_key.strip():
        position_key = position_label
    career_history = player.get("careerHistory")
    career = career_history.get("careerItems", {}) if isinstance(career_history, dict) else {}
    if not isinstance(career, dict):
        career = {}
    trophies = player.get("trophies", {}) if player else {}
    player_info_list = _parse_player_info(player) if player else []
    season_stats, season_total, career_totals = _aggregate_season_stats(player)

    def group_career_teams(level):
        career_level = career.get(level)
        if not isinstance(career_level, dict):
            return []
        season_entries = career_level.get("seasonEntries")
        if not isinstance(season_entries, list):
            return []
        team_entries = career_level.get("teamEntries")
        if not isinstance(team_entries, list):
            team_entries = []

        from collections import OrderedDict
        teams = OrderedDict()
        for season in season_entries:
            if not isinstance(season, dict):
                continue
            team_id = season.get("teamId")
            has_team_id = (
                isinstance(team_id, int) and not isinstance(team_id, bool) and team_id > 0
            )
            team_name = season.get("team") or season.get("teamName") or ""
            if has_team_id:
                group_key = ("id", team_id)
            elif isinstance(team_name, str) and team_name.strip():
                group_key = ("name", team_name.strip().casefold())
            else:
                group_key = ("unknown", len(teams))

            if group_key not in teams:
                if has_team_id:
                    team_entry = next(
                        (entry for entry in team_entries
                         if isinstance(entry, dict) and entry.get("teamId") == team_id),
                        {},
                    )
                else:
                    team_entry = next(
                        (entry for entry in team_entries
                         if isinstance(entry, dict)
                         and (entry.get("team") or entry.get("teamName")) == team_name),
                        {},
                    )
                teams[group_key] = {
                    "teamId": team_id if has_team_id else None,
                    "teamKey": len(teams),
                    "team": team_name,
                    "appearances": team_entry.get("appearances", "0"),
                    "goals": team_entry.get("goals", "0"),
                    "assists": team_entry.get("assists", "0"),
                    "startDate": team_entry.get("startDate", ""),
                    "endDate": team_entry.get("endDate"),
                    "seasons": [],
                }
            teams[group_key]["seasons"].append(season)
        return list(teams.values())

    club_by_team = group_career_teams("senior")
    nt_by_team = group_career_teams("national team")
    wiki_individual = None
    doc = get_player_honours(player.get('id'))
    birth_date = player.get('birthDate')
    birth_date = birth_date.get('utcTime') if isinstance(birth_date, dict) else None
    birth_date = birth_date[:10] if isinstance(birth_date, str) else None
    scheduled = schedule_individual_refresh(player.get('id'), player.get('name', ''), doc, birth_date)
    is_active = is_individual_refresh_active(player.get('id'))
    if doc:
        raw_indiv = doc.get('honours', {}).get('individual', [])
        sanitized = []
        for a in raw_indiv:
            trophy = a.get('trophy', '')
            if not is_disqualified_individual_award(trophy):
                copied = dict(a)
                copied['trophy'] = normalize_trophy_name(trophy)
                sanitized.append(copied)
        wiki_individual = sort_individual_awards(sanitized)
    honours_loading = bool((scheduled or is_active) and not wiki_individual)
    honours_refreshing = bool((scheduled or is_active) and bool(wiki_individual))
    return render_template("player.html", player=player, career=career,
                           position_key=position_key.casefold(), position_label=position_label,
                           trophies=trophies, wiki_individual=wiki_individual,
                           honours_loading=honours_loading,
                           honours_refreshing=honours_refreshing,
                           player_info_list=player_info_list,
                           season_stats=season_stats, season_total=season_total,
                           career_totals=career_totals, club_by_team=club_by_team,
                           nt_by_team=nt_by_team, **ctx)


@app.route("/player/<int:player_id>/honours-data")
def player_honours_data(player_id):
    if is_individual_refresh_active(player_id):
        wait_for_individual_refresh(player_id, timeout=1.5)

    doc = get_player_honours(player_id)
    is_active = is_individual_refresh_active(player_id)

    raw_indiv = doc.get('honours', {}).get('individual', []) if doc else []
    sanitized = []
    for a in raw_indiv:
        trophy = a.get('trophy', '')
        if not is_disqualified_individual_award(trophy):
            copied = dict(a)
            copied['trophy'] = normalize_trophy_name(trophy)
            sanitized.append(copied)
    wiki_individual = sort_individual_awards(sanitized)

    html = render_template(
        "_player_individual_awards.html",
        wiki_individual=wiki_individual,
        honours_loading=is_active,
    )
    return jsonify({
        "loading": is_active,
        "count": len(wiki_individual),
        "html": html,
    })


def _parse_trophy_list(info):
    """Parse trophyList, chỉ lấy winner."""
    raw = info.get("history", {}).get("trophyList", []) if info else []
    result = []
    total = 0

    def scalar(value):
        if isinstance(value, list):
            return value[0] if len(value) == 1 else None
        return value

    for t in raw:
        if not isinstance(t, dict):
            logger.warning("Skipping invalid FotMob trophy entry: %r", t)
            continue
        name = scalar(t.get("name"))
        count = scalar(t.get("won"))
        if not isinstance(name, str) or not name.strip():
            logger.warning("Skipping FotMob trophy with invalid name: %r", name)
            continue
        if isinstance(count, bool) or not (
            isinstance(count, int) and count >= 0
            or isinstance(count, str) and count.isascii() and count.isdigit()
        ):
            logger.warning("Skipping FotMob trophy %s with invalid win count: %r", name, count)
            continue
        won = int(count)
        if won == 0:
            continue
        seasons_value = t.get("seasonsWon", t.get("season_won", ""))
        if isinstance(seasons_value, str):
            seasons_value = [seasons_value]
        if not isinstance(seasons_value, list) or not all(isinstance(s, str) for s in seasons_value):
            logger.warning("FotMob trophy %s has invalid seasons: %r", name, seasons_value)
            seasons_value = []
        seasons = [s.strip() for value in seasons_value for s in value.split(",") if s.strip()]
        league_id = scalar(t.get("leagueId", t.get("tournamentTemplateId", "")))
        area = scalar(t.get("area", ""))
        result.append({
            "name": name,
            "league_id": league_id if league_id is not None else "",
            "area": area if area is not None else "",
            "won": won,
            "seasons_won": seasons,
        })
        total += won
    return result, total


def _group_coach_history(raw):
    """Gộp coach history theo tên, đảo ngược từ mới → cũ."""
    from collections import OrderedDict
    grouped = OrderedDict()
    for entry in reversed(raw):
        cid = entry["id"]
        if cid not in grouped:
            grouped[cid] = {
                "id": cid, "name": entry["name"],
                "seasons": [], "win": 0, "draw": 0, "loss": 0,
            }
        g = grouped[cid]
        g["seasons"].append(entry["season"])
        g["win"] += entry.get("win", 0)
        g["draw"] += entry.get("draw", 0)
        g["loss"] += entry.get("loss", 0)
    result = []
    for g in grouped.values():
        total = g["win"] + g["draw"] + g["loss"]
        g["total"] = total
        g["ppg"] = round((g["win"] * 3 + g["draw"]) / total, 2) if total else 0
        g["win_pct"] = round(g["win"] / total * 100) if total else 0
        g["period"] = g["seasons"][-1] + " → " + g["seasons"][0] if len(g["seasons"]) > 1 else g["seasons"][0]
        result.append(g)
    return result


@app.route("/team/<int:team_id>")
def fm_team(team_id):
    ctx = _ctx()
    info = get_team_info(team_id)
    details = info.get("details", {}) if info else {}
    squad = info.get("squad", {}).get("squad", []) if info else []
    coach = None
    for g in squad:
        if g.get("title") == "coach" and g.get("members"):
            coach = g["members"][0]
            break
    venue = info.get("overview", {}).get("venue") if info else None
    raw_history = info.get("overview", {}).get("coachHistory", []) if info else []
    coach_history = _group_coach_history(raw_history)
    top_players = info.get("overview", {}).get("topPlayers", {}) if info else {}
    trophy_list, total_trophies = _parse_trophy_list(info)
    # League position
    league_pos = None
    league_name_pos = ""
    league_id_pos = ""
    table_data = info.get("overview", {}).get("table", []) if info else []
    if table_data:
        league_name_pos = table_data[0]["data"]["leagueName"]
        league_id_pos = table_data[0]["data"]["leagueId"]
        for t in table_data[0]["data"]["table"]["all"]:
            if t["id"] == team_id:
                league_pos = t
                break
    # Squad stats
    squad_size = 0
    total_age = 0
    total_value = 0
    for g in squad:
        if g.get("title") == "coach":
            continue
        for m in g.get("members", []):
            squad_size += 1
            total_age += m.get("age", 0) or 0
            total_value += m.get("transferValue", 0) or 0
    avg_age = round(total_age / squad_size, 1) if squad_size else 0
    team_value = round(total_value / 1_000_000, 1)
    # Next & last match
    next_match = info.get("overview", {}).get("nextMatch") if info else None
    last_match = info.get("overview", {}).get("lastMatch") if info else None
    return render_template("team.html", details=details, squad=squad,
                           coach=coach, venue=venue, coach_history=coach_history,
                           trophy_list=trophy_list, total_trophies=total_trophies,
                           top_players=top_players, league_pos=league_pos,
                           league_name_pos=league_name_pos, league_id_pos=league_id_pos,
                           next_match=next_match, last_match=last_match,
                           squad_size=squad_size, avg_age=avg_age, team_value=team_value, **ctx)


def _parse_coach_career_stats(player):
    """Parse coaching career: merge careerItems.coach với coachStats."""
    cs = player.get("coachStats", {})
    ci = player.get("careerHistory", {}).get("careerItems", {}).get("coach", {}).get("teamEntries", [])

    # Build stats lookup from coachStats
    stats_map = {}
    for entry in cs.get("historicalCareerEntries", []):
        key = (entry["teamId"], entry.get("startDate", {}).get("utcTime", "")[:4] if entry.get("startDate") else "")
        stats_map[key] = entry
    active = cs.get("activeCareerEntry", {})
    if active:
        stats_map[(active.get("teamId"), "")] = active

    entries = []
    for item in ci:
        tid = item["teamId"]
        start = item.get("startDate", "")[:4] if item.get("startDate") else "?"
        end = item.get("endDate", "")[:4] if item.get("endDate") else "Now"
        # Match with stats
        matched = stats_map.get((tid, start)) or stats_map.get((tid, ""))
        if matched:
            total = matched.get("matches", 0)
            entries.append({
                "teamId": tid, "teamName": item["team"],
                "start": start, "end": end,
                "matches": total, "wins": matched.get("wins", 0),
                "draws": matched.get("draws", 0), "losses": matched.get("losses", 0),
                "win_pct": round(matched.get("winPercentage", 0), 1),
                "ppg": round(matched.get("pointsPerGame", 0), 2),
                "is_assistant": False,
            })
        else:
            entries.append({
                "teamId": tid, "teamName": item["team"],
                "start": start, "end": end,
                "matches": 0, "wins": 0, "draws": 0, "losses": 0,
                "win_pct": 0, "ppg": 0, "is_assistant": True,
            })

    # Totals (head coach only)
    hc = [e for e in entries if not e["is_assistant"]]
    total_m = sum(e["matches"] for e in hc)
    total_w = sum(e["wins"] for e in hc)
    totals = {
        "matches": total_m, "wins": total_w,
        "draws": sum(e["draws"] for e in hc),
        "losses": sum(e["losses"] for e in hc),
        "win_pct": round(total_w / total_m * 100, 1) if total_m else 0,
        "teams": len(set(e["teamId"] for e in hc)),
    }
    return entries, totals


def _parse_coach_trophies(player):
    """Parse coachTrophies thành flat list."""
    trophies = player.get("trophies", {}).get("coachTrophies", [])
    result = []
    total = 0
    for team_group in trophies:
        for t in team_group.get("tournaments", []):
            if not t.get("seasonsWon"):
                continue
            won = len(t["seasonsWon"])
            result.append({
                "league": t["leagueName"],
                "league_id": t.get("leagueId", ""),
                "team": team_group["teamName"],
                "team_id": team_group["teamId"],
                "won": won,
                "seasons": t["seasonsWon"],
            })
            total += won
    return result, total


@app.route("/coach/<int:coach_id>")
def fm_coach(coach_id):
    ctx = _ctx()
    player = get_player_info(coach_id)
    if not player:
        return "Coach not found", 404
    info_list = _parse_player_info(player)
    career_entries, career_totals = _parse_coach_career_stats(player)
    trophies, total_trophies = _parse_coach_trophies(player)
    # Player career (only if has senior/national team with appearances)
    player_career = {}
    all_career = player.get("careerHistory", {}).get("careerItems", {})
    for level in ["senior", "national team"]:
        data = all_career.get(level, {})
        team_entries = data.get("teamEntries", [])
        has_apps = any(e.get("appearances") for e in team_entries)
        if has_apps:
            player_career[level] = data
    return render_template("coach.html", player=player, info_list=info_list,
                           career_entries=career_entries, career_totals=career_totals,
                           trophies=trophies, total_trophies=total_trophies,
                           player_career=player_career, **ctx)


# ============================================================
# ADMIN — HONOURS MANAGER
# ============================================================

CAT_LABELS = {v: k for k, v in CATEGORY_MAP.items()}
CAT_ICONS = {
    'club_domestic_league': 'fa-ranking-star',
    'club_domestic_cup': 'fa-trophy',
    'club_continental': 'fa-earth-europe',
    'club_world': 'fa-globe',
    'intl_senior': 'fa-flag',
    'intl_youth': 'fa-child',
    'individual': 'fa-medal',
    'orders': 'fa-award',
}
ALL_CATS = {v: k for k, v in CATEGORY_MAP.items()}


@app.route('/admin/honours')
@admin_required
def fm_admin_honours():
    ctx = _ctx()
    docs = list(honours_coll.find({}, {'_id': 0}).sort('name', 1))
    for d in docs:
        d['total'] = sum(
            e.get('count', 0) for entries in d.get('honours', {}).values() for e in entries
        )
    return render_template('admin_honours.html', players=docs,
                           seed_msg=request.args.get('seed_msg'),
                           seed_ok=request.args.get('seed_ok') == '1', **ctx)


@app.route('/admin/honours/seed', methods=['POST'])
@admin_required
def fm_admin_seed():
    try:
        fid = int(request.form['fotmob_id'])
    except (KeyError, ValueError):
        abort(400, description="Invalid FotMob player ID")
    name = request.form['player_name']
    wiki = request.form['wiki_page']
    force = 'force' in request.form
    result = seed_from_wikipedia(fid, name, wiki, force=force)
    if result is None:
        return redirect(url_for('fm_admin_honours', seed_msg='Skipped (verified hoặc fetch fail)', seed_ok='0'))
    total = sum(e['count'] for entries in result.values() for e in entries)
    return redirect(url_for('fm_admin_honours', seed_msg=f'✅ {name}: {total} danh hiệu', seed_ok='1'))


@app.route('/admin/honours/<int:fotmob_id>')
@admin_required
def fm_admin_detail(fotmob_id):
    ctx = _ctx()
    doc = get_player_honours(fotmob_id)
    if not doc:
        return 'Player not found', 404
    honours = doc.get('honours', {})
    summary = {}
    for cat, entries in honours.items():
        summary[cat] = sum(e.get('count', 0) for e in entries)
    summary['total'] = sum(summary.values())
    return render_template('admin_detail.html', player=doc, honours=honours,
                           summary=summary, cat_labels=CAT_LABELS, cat_icons=CAT_ICONS,
                           all_cats=ALL_CATS,
                           msg=request.args.get('msg'),
                           msg_ok=request.args.get('msg_ok') == '1', **ctx)


@app.route('/admin/honours/<int:fotmob_id>/delete', methods=['POST'])
@admin_required
def fm_admin_delete(fotmob_id):
    honours_coll.delete_one({'fotmob_id': fotmob_id})
    return redirect(url_for('fm_admin_honours', seed_msg=f'🗑 Đã xóa player #{fotmob_id}', seed_ok='1'))


@app.route('/admin/honours/<int:fotmob_id>/toggle-verified', methods=['POST'])
@admin_required
def fm_admin_toggle_verified(fotmob_id):
    doc = get_player_honours(fotmob_id)
    if doc:
        set_verified(fotmob_id, not doc.get('verified', False))
    referer = request.referrer or url_for('fm_admin_honours')
    return redirect(referer)


@app.route('/admin/honours/<int:fotmob_id>/update/<category>', methods=['POST'])
@admin_required
def fm_admin_update_category(fotmob_id, category):
    if category not in CAT_LABELS:
        abort(404)
    doc = get_player_honours(fotmob_id)
    if not doc:
        return 'Not found', 404

    trophies = request.form.getlist('trophy')
    contexts = request.form.getlist('context')
    years_list = request.form.getlist('years')
    counts = request.form.getlist('count')

    entries = []
    for trophy, context, years_str, count in zip(trophies, contexts, years_list, counts):
        trophy = trophy.strip()
        if not trophy:
            continue
        years = [y.strip() for y in years_str.split(',') if y.strip()]
        try:
            count_value = int(count) if count else len(years)
        except ValueError:
            abort(400, description="Invalid honours count")
        if count_value < 0:
            abort(400, description="Invalid honours count")
        entry = {'trophy': trophy, 'years': years, 'count': count_value}
        context = context.strip()
        if context:
            if category.startswith('intl'):
                entry['team'] = context
            else:
                entry['club'] = context
        entries.append(entry)

    honours = doc.get('honours', {})
    if entries:
        honours[category] = entries
    else:
        honours.pop(category, None)

    from datetime import datetime, timezone
    honours_coll.update_one(
        {'fotmob_id': fotmob_id},
        {'$set': {'honours': honours, 'updated_at': datetime.now(timezone.utc)}},
    )
    return redirect(url_for('fm_admin_detail', fotmob_id=fotmob_id,
                            msg=f'✅ Đã lưu {CAT_LABELS.get(category, category)}', msg_ok='1'))


@app.route('/admin/honours/<int:fotmob_id>/add-category', methods=['POST'])
@admin_required
def fm_admin_add_category(fotmob_id):
    doc = get_player_honours(fotmob_id)
    if not doc:
        return 'Not found', 404
    cat = request.form['category']
    if cat not in ALL_CATS:
        abort(400, description="Invalid honours category")
    honours = doc.get('honours', {})
    if cat not in honours:
        honours[cat] = []
        from datetime import datetime, timezone
        honours_coll.update_one(
            {'fotmob_id': fotmob_id},
            {'$set': {'honours': honours, 'updated_at': datetime.now(timezone.utc)}},
        )
    return redirect(url_for('fm_admin_detail', fotmob_id=fotmob_id))


if __name__ == "__main__":
    ensure_indexes()
    app.run(debug=False, host="127.0.0.1", port=5001)
