"""
FotMob Web App - Modern Glassmorphism UI
Chạy: python app_fotmob.py
"""
from flask import Flask, render_template, request, redirect, url_for
from fotmob import (
    LEAGUES, get_standings, get_top_scorers, get_top_assists, get_top_goals_assists,
    get_available_seasons, get_player_info,
    get_team_info, get_team_squad, get_team_coach, get_team_venue,
    get_team_coach_history, get_tm_trophies,
)
from honours_db import (
    ensure_indexes, get_player_honours, save_player_honours,
    set_verified, seed_from_wikipedia, get_honours_summary,
    auto_seed, player_honours as honours_coll, CATEGORY_MAP,
)

app = Flask(__name__)

DEFAULT_SEASONS = ["2025/2026", "2024/2025", "2023/2024", "2022/2023", "2021/2022", "2020/2021", "2019/2020", "2018/2019", "2017/2018", "2016/2017" ]


def _ctx(league_key=None, season=None):
    """Context chung cho mọi template."""
    league_key = league_key or request.args.get("league", "epl")
    season = season or request.args.get("season")
    league = LEAGUES.get(league_key, LEAGUES["epl"])
    return {
        "leagues": LEAGUES,
        "current_league": league_key,
        "current_season": season or DEFAULT_SEASONS[0],
        "league_name": league["name"],
        "league_id": league["id"],
        "seasons": DEFAULT_SEASONS,
    }


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def fm_home():
    return render_template("home.html", leagues=LEAGUES, seasons=DEFAULT_SEASONS)


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
    return result


def _aggregate_season_stats(player):
    """Tổng hợp stats current season per tournament + career totals."""
    if not player:
        return [], {}, []

    import re as _re
    from collections import defaultdict

    career_items = player.get("careerHistory", {}).get("careerItems", {})
    stat_seasons = player.get("statSeasons", [])
    matches = player.get("recentMatches", [])

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
    career = player.get("careerHistory", {}).get("careerItems", {}) if player else {}
    trophies = player.get("trophies", {}) if player else {}
    player_info_list = _parse_player_info(player) if player else []
    season_stats, season_total, career_totals = _aggregate_season_stats(player)
    # Group seasonEntries by team for club career dropdown
    club_by_team = []
    if career:
        from collections import OrderedDict
        teams = OrderedDict()
        for s in career.get("senior", {}).get("seasonEntries", []):
            tid = s.get("teamId")
            if tid not in teams:
                te = next((e for e in career.get("senior", {}).get("teamEntries", []) if e.get("teamId") == tid), {})
                teams[tid] = {
                    "teamId": tid, "team": s.get("team", ""),
                    "appearances": te.get("appearances", "0"), "goals": te.get("goals", "0"),
                    "assists": te.get("assists", "0"),
                    "startDate": te.get("startDate", ""), "endDate": te.get("endDate"),
                    "seasons": [],
                }
            teams[tid]["seasons"].append(s)
        club_by_team = list(teams.values())
    # Same for national team
    nt_by_team = []
    if career:
        teams = OrderedDict()
        for s in career.get("national team", {}).get("seasonEntries", []):
            tid = s.get("teamId")
            if tid not in teams:
                te = next((e for e in career.get("national team", {}).get("teamEntries", []) if e.get("teamId") == tid), {})
                teams[tid] = {
                    "teamId": tid, "team": s.get("team", ""),
                    "appearances": te.get("appearances", "0"), "goals": te.get("goals", "0"),
                    "assists": te.get("assists", "0"),
                    "startDate": te.get("startDate", ""), "endDate": te.get("endDate"),
                    "seasons": [],
                }
            teams[tid]["seasons"].append(s)
        nt_by_team = list(teams.values())
    # Wiki honours (individual awards) - auto seed if not in DB
    wiki_individual = None
    try:
        doc = auto_seed(player.get('id'), player.get('name', ''))
        if doc:
            wiki_individual = doc.get('honours', {}).get('individual', [])
    except Exception:
        pass
    return render_template("player.html", player=player, career=career,
                           trophies=trophies, wiki_individual=wiki_individual,
                           player_info_list=player_info_list,
                           season_stats=season_stats, season_total=season_total,
                           career_totals=career_totals, club_by_team=club_by_team,
                           nt_by_team=nt_by_team, **ctx)


def _parse_trophy_list(info):
    """Parse trophyList, chỉ lấy winner."""
    raw = info.get("history", {}).get("trophyList", []) if info else []
    result = []
    total = 0
    for t in raw:
        won = int(t.get("won", ["0"])[0])
        if won == 0:
            continue
        seasons_str = t.get("season_won", [""])[0]
        seasons = [s.strip() for s in seasons_str.split(",") if s.strip()]
        result.append({
            "name": t["name"][0],
            "league_id": t.get("tournamentTemplateId", [""])[0],
            "area": t.get("area", [""])[0],
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
def fm_admin_seed():
    fid = int(request.form['fotmob_id'])
    name = request.form['player_name']
    wiki = request.form['wiki_page']
    force = 'force' in request.form
    result = seed_from_wikipedia(fid, name, wiki, force=force)
    if result is None:
        return redirect(url_for('fm_admin_honours', seed_msg='Skipped (verified hoặc fetch fail)', seed_ok='0'))
    total = sum(e['count'] for entries in result.values() for e in entries)
    return redirect(url_for('fm_admin_honours', seed_msg=f'✅ {name}: {total} danh hiệu', seed_ok='1'))


@app.route('/admin/honours/<int:fotmob_id>')
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
def fm_admin_delete(fotmob_id):
    honours_coll.delete_one({'fotmob_id': fotmob_id})
    return redirect(url_for('fm_admin_honours', seed_msg=f'🗑 Đã xóa player #{fotmob_id}', seed_ok='1'))


@app.route('/admin/honours/<int:fotmob_id>/toggle-verified', methods=['POST'])
def fm_admin_toggle_verified(fotmob_id):
    doc = get_player_honours(fotmob_id)
    if doc:
        set_verified(fotmob_id, not doc.get('verified', False))
    referer = request.referrer or url_for('fm_admin_honours')
    return redirect(referer)


@app.route('/admin/honours/<int:fotmob_id>/update/<category>', methods=['POST'])
def fm_admin_update_category(fotmob_id, category):
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
        entry = {'trophy': trophy, 'years': years, 'count': int(count) if count else len(years)}
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
def fm_admin_add_category(fotmob_id):
    doc = get_player_honours(fotmob_id)
    if not doc:
        return 'Not found', 404
    cat = request.form['category']
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
    app.run(debug=True, host="0.0.0.0", port=5001)
