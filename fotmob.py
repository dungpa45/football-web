"""
FotMob Skills Module
Lấy dữ liệu từ FotMob thông qua scraping __NEXT_DATA__ và data.fotmob.com API.
"""

import requests
from requests.exceptions import Timeout
import json
import logging
import re
from copy import deepcopy
from bs4 import BeautifulSoup
from cache import get_cached, set_cached, TTL_CURRENT_SEASON, TTL_PAST_SEASON, TTL_PLAYER, TTL_TEAM

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

BASE_URL = "https://www.fotmob.com"
DATA_URL = "https://data.fotmob.com"
logger = logging.getLogger(__name__)

# 5 giải hàng đầu châu Âu - FotMob league IDs
LEAGUES = {
    "epl": {"id": 47, "name": "Premier League", "slug": "premier-league"},
    "laliga": {"id": 87, "name": "La Liga", "slug": "la-liga"},
    "seriea": {"id": 55, "name": "Serie A", "slug": "serie-a"},
    "bundes": {"id": 54, "name": "Bundesliga", "slug": "bundesliga"},
    "ligue1": {"id": 53, "name": "Ligue 1", "slug": "ligue-1"},
}


# ============================================================
# =============== HELPER =====================================
# ============================================================

def _fetch_page(url):
    """Fetch page và parse __NEXT_DATA__ JSON."""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    script = soup.find("script", attrs={"id": "__NEXT_DATA__"})
    if not script:
        raise requests.RequestException("FotMob page is missing __NEXT_DATA__")
    return json.loads(script.text)["props"]["pageProps"]


def _fetch_json(url):
    """Fetch JSON trực tiếp từ data.fotmob.com."""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


# ============================================================
# =============== LEAGUE DATA ================================
# ============================================================

def _league_cache_key(league_key, season=None):
    return f"league:v2:{league_key}:{season or 'current'}"


def _season_ttl(season, league_data):
    seasons = league_data.get("allAvailableSeasons", []) if isinstance(league_data, dict) else []
    current = seasons[0] if isinstance(seasons, list) and seasons else None
    if (isinstance(season, str) and isinstance(current, str)
            and re.fullmatch(r"\d{4}/\d{4}", season)
            and re.fullmatch(r"\d{4}/\d{4}", current)
            and season < current):
        return TTL_PAST_SEASON
    return TTL_CURRENT_SEASON


def _stat_ttl(league_key, season):
    league_data = get_cached(_league_cache_key(league_key))
    return _season_ttl(season, league_data)


def get_league_page(league_key, season=None):
    """
    Lấy toàn bộ data trang league (standings, stats overview, seasons...).
    league_key: 'epl', 'laliga', 'seriea', 'bundes', 'ligue1'
    season: '2024/2025' hoặc None (mặc định mùa hiện tại)
    Returns: dict pageProps
    """
    cache_key = _league_cache_key(league_key, season)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    league = LEAGUES[league_key]
    url = f"{BASE_URL}/leagues/{league['id']}/overview/{league['slug']}"
    if season:
        url += f"?season={season}"
    data = _fetch_page(url)
    if data:
        set_cached(cache_key, data, _season_ttl(season, data))
    return data


def get_available_seasons(league_key):
    """Lấy danh sách các mùa giải có sẵn."""
    data = get_league_page(league_key)
    return data.get("allAvailableSeasons", []) if data else []


# ============================================================
# =============== STANDINGS ==================================
# ============================================================

def get_standings(league_key, season=None):
    """
    Lấy bảng xếp hạng.
    Returns: (table, legend)
        table: list of team dicts
        legend: list of {title, color, indices}
    """
    data = get_league_page(league_key, season)
    if not data:
        return [], []
    table_data = data.get("table", [])
    if not table_data:
        return [], []
    d = table_data[0]["data"]
    return d["table"]["all"], d.get("legend", [])


# ============================================================
# =============== TOP SCORERS / ASSISTS ======================
# ============================================================

def _get_season_stat_links(league_key, season=None):
    """Lấy seasonStatLinks để tìm TournamentId cho mùa giải."""
    data = get_league_page(league_key, season)
    if not data:
        return [], {}
    stats = data.get("stats", {})
    return stats.get("seasonStatLinks", []), stats


def _get_tournament_id(league_key, season_name=None):
    """Tìm TournamentId cho 1 mùa giải cụ thể."""
    links, stats = _get_season_stat_links(league_key)
    if not season_name:
        # Lấy mùa hiện tại (đầu tiên trong list)
        if links:
            return links[0]["TournamentId"], links[0]["TemplateId"]
        return None, None
    for link in links:
        if link["Name"] == season_name:
            return link["TournamentId"], link["TemplateId"]
    return None, None


def _fetch_stat(league_key, stat_type, season=None, limit=20):
    """
    Lấy full danh sách stat từ data.fotmob.com.
    stat_type: 'goals', 'goal_assist', 'goals_assists', 'rating', ...
    Returns: list of player dicts
    """
    cache_key = f"stat:v2:{league_key}:{stat_type}:{season or 'current'}:{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    league = LEAGUES[league_key]
    tournament_id, template_id = _get_tournament_id(league_key, season)
    if not tournament_id:
        return []
    url = f"{DATA_URL}/stats/{template_id}/season/{tournament_id}/{stat_type}.json"
    data = _fetch_json(url)
    top_lists = data.get("TopLists", [])
    if not top_lists:
        return []
    players = top_lists[0].get("StatList", [])
    result = players[:limit] if limit else players
    if result:
        set_cached(cache_key, result, _stat_ttl(league_key, season))
    return result


def get_top_scorers(league_key, season=None, limit=20):
    """
    Lấy danh sách top ghi bàn.
    Returns: list of dict với fields:
        ParticipantName, ParticiantId, TeamId, TeamName, StatValue (goals),
        SubStatValue, MinutesPlayed, MatchesPlayed, Rank, ParticipantCountryCode
    """
    return _fetch_stat(league_key, "goals", season, limit)


def get_top_assists(league_key, season=None, limit=20):
    """
    Lấy danh sách top kiến tạo.
    Returns: list of dict (cùng format với top scorers)
    """
    return _fetch_stat(league_key, "goal_assist", season, limit)


def get_top_goals_assists(league_key, season=None, limit=20):
    """Lấy danh sách top Goals + Assists, kèm xG và xA."""
    cache_key = f"stat:v2:{league_key}:goals_assists:{season or 'current'}"
    cached = get_cached(cache_key)
    if cached is not None:
        return deepcopy(cached[:limit] if limit else cached)

    tournament_id, template_id = _get_tournament_id(league_key, season)
    if not tournament_id:
        return []
    base = f"{DATA_URL}/stats/{template_id}/season/{tournament_id}"

    # Fetch G+A
    data = _fetch_json(f"{base}/_goals_and_goal_assist.json")
    top_lists = data.get("TopLists", [])
    if not top_lists:
        return []
    players = top_lists[0].get("StatList", [])

    # Fetch goals, assists, xG, xA lookups
    goals_map, assists_map, xg_map, xa_map = {}, {}, {}, {}
    complete = True
    for stat_type, target in [("goals", goals_map), ("goal_assist", assists_map),
                               ("expected_goals", xg_map), ("expected_assists", xa_map)]:
        try:
            d = _fetch_json(f"{base}/{stat_type}.json")
            top_lists = d.get("TopLists") or []
            stat_list = top_lists[0].get("StatList", []) if top_lists else []
            for p in stat_list:
                target[p["ParticiantId"]] = p["StatValue"]
        except (requests.RequestException, json.JSONDecodeError) as exc:
            logger.warning("Could not fetch FotMob %s stats: %s", stat_type, exc)
            complete = False

    # Merge
    for p in players:
        pid = p["ParticiantId"]
        goals = goals_map.get(pid)
        assists = assists_map.get(pid)
        p["Goals"] = int(goals) if goals is not None else None
        p["Assists"] = int(assists) if assists is not None else None
        p["xG"] = xg_map.get(pid)
        p["xA"] = xa_map.get(pid)

    if players and complete:
        set_cached(cache_key, players, _stat_ttl(league_key, season))
    return deepcopy(players[:limit] if limit else players)


def get_top_rating(league_key, season=None, limit=20):
    """Lấy danh sách top FotMob rating."""
    return _fetch_stat(league_key, "rating", season, limit)


# ============================================================
# =============== PLAYER INFO ================================
# ============================================================

def get_player_info(player_id):
    """
    Lấy thông tin chi tiết cầu thủ.
    Returns: dict với keys:
        id, name, birthDate, primaryTeam, positionDescription,
        playerInformation, trophies, careerHistory, statSeasons,
        firstSeasonStats, marketValues, ...
    """
    cache_key = f"player:{player_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    url = f"{BASE_URL}/players/{player_id}/overview"
    data = _fetch_page(url)
    if not data:
        return None
    result = data.get("data")
    if result:
        set_cached(cache_key, result, TTL_PLAYER)
    return result


def get_player_career(player_id):
    """Lấy lịch sử sự nghiệp cầu thủ."""
    info = get_player_info(player_id)
    if not info:
        return None
    return info.get("careerHistory", {}).get("careerItems", {})


def get_player_trophies(player_id):
    """Lấy danh hiệu cầu thủ."""
    info = get_player_info(player_id)
    if not info:
        return None
    return info.get("trophies", {})


def get_player_season_stats(player_id):
    """Lấy thống kê mùa giải hiện tại."""
    info = get_player_info(player_id)
    if not info:
        return None
    return info.get("firstSeasonStats")


# ============================================================
# =============== TEAM INFO ==================================
# ============================================================

def get_team_info(team_id):
    """
    Lấy thông tin đội bóng (details, squad, coach, venue...).
    Returns: dict với keys:
        details, overview, squad, stats, table, transfers, ...
    """
    cache_key = f"team:{team_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    url = f"{BASE_URL}/teams/{team_id}/squad"
    data = _fetch_page(url)
    if not data:
        return None
    fallback = data.get("fallback", {})
    result = None
    for key, val in fallback.items():
        if key.startswith("team-"):
            result = val
            break
    if result:
        set_cached(cache_key, result, TTL_TEAM)
    return result


def get_team_details(team_id):
    """Lấy thông tin cơ bản đội (tên, quốc gia, ...)."""
    info = get_team_info(team_id)
    if not info:
        return None
    return info.get("details")


def get_team_squad(team_id):
    """
    Lấy danh sách cầu thủ theo vị trí.
    Returns: list of groups, mỗi group có title (coach/keepers/defenders/midfielders/attackers)
             và members (list of player dicts)
    """
    info = get_team_info(team_id)
    if not info:
        return None
    return info.get("squad", {}).get("squad", [])


def get_team_coach(team_id):
    """Lấy thông tin HLV hiện tại."""
    squad = get_team_squad(team_id)
    if not squad:
        return None
    for group in squad:
        if group.get("title") == "coach":
            members = group.get("members", [])
            return members[0] if members else None
    return None


def get_team_venue(team_id):
    """Lấy thông tin sân vận động."""
    info = get_team_info(team_id)
    if not info:
        return None
    return info.get("overview", {}).get("venue")


def get_team_coach_history(team_id):
    """Lấy lịch sử HLV của đội."""
    info = get_team_info(team_id)
    if not info:
        return None
    return info.get("overview", {}).get("coachHistory", [])


# ============================================================
# =============== IMAGE URLS =================================
# ============================================================

def get_player_image_url(player_id):
    """URL ảnh cầu thủ trên FotMob."""
    return f"https://images.fotmob.com/image_resources/playerimages/{player_id}.png"


def get_team_image_url(team_id):
    """URL logo đội bóng trên FotMob."""
    return f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"


def get_league_image_url(league_id):
    """URL logo giải đấu trên FotMob."""
    return f"https://images.fotmob.com/image_resources/logo/leaguelogo/{league_id}.png"


def _with_player_ratings(players, league_key, season):
    if not players:
        return []
    ratings = {}
    try:
        ratings = {
            p["ParticiantId"]: p["StatValue"]
            for p in get_top_rating(league_key, season, limit=None)
        }
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logger.warning("Could not fetch FotMob ratings for %s (%s): %s",
                       league_key, season or "current", exc)
    return [{**p, "Rating": ratings.get(p["ParticiantId"])} for p in players]


def get_top_all_leagues(stat_type="goals", season=None, limit_per_league=10):
    """
    Lấy top stats từ cả 5 giải, gộp lại và sort.
    stat_type: 'goals', 'goal_assist'
    Returns: sorted list of player dicts (thêm league_key, league_name)
    """
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_league(key):
        players = _fetch_stat(key, stat_type, season, limit_per_league)
        players = _with_player_ratings(players, key, season)
        for p in players:
            p["league_key"] = key
            p["league_name"] = LEAGUES[key]["name"]
            p["league_id"] = LEAGUES[key]["id"]
        return players

    all_players = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        results = ex.map(_fetch_league, LEAGUES.keys())
    for players in results:
        all_players.extend(players)
    all_players.sort(key=lambda x: x["StatValue"], reverse=True)
    return all_players


def get_top_ga_all_leagues(season=None, limit_per_league=10):
    """
    Lấy top G+A từ cả 5 giải, kèm xG và xA.
    Returns: sorted list
    """
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_league(key):
        players = get_top_goals_assists(key, season, limit_per_league)
        players = _with_player_ratings(players, key, season)
        for p in players:
            p["league_key"] = key
            p["league_name"] = LEAGUES[key]["name"]
            p["league_id"] = LEAGUES[key]["id"]
        return players

    all_players = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        results = ex.map(_fetch_league, LEAGUES.keys())
    for players in results:
        all_players.extend(players)
    all_players.sort(key=lambda x: x["StatValue"], reverse=True)
    return all_players


def get_top_rating_all_leagues(season=None):
    """
    Lấy top rating từ cả 5 giải, ghép thêm Goals/Assists, sort theo Rating giảm dần.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_league(key):
        players = _fetch_stat(key, "rating", season, limit=None)
        for p in players:
            p["Rating"] = p["StatValue"]
            p["Goals"] = None
            p["Assists"] = None
            p["league_key"] = key
            p["league_name"] = LEAGUES[key]["name"]
            p["league_id"] = LEAGUES[key]["id"]
        for stat, field in (("goals", "Goals"), ("goal_assist", "Assists")):
            try:
                values = {
                    r["ParticiantId"]: r["StatValue"]
                    for r in _fetch_stat(key, stat, season, limit=None)
                }
            except (Timeout, json.JSONDecodeError) as exc:
                logger.warning("%s/%s unavailable for %s: %s", key, stat, season or "current", exc)
                continue
            for p in players:
                if values.get(p["ParticiantId"]) is not None:
                    p[field] = values[p["ParticiantId"]]
        return players

    all_players = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        results = ex.map(_fetch_league, LEAGUES.keys())
    for players in results:
        all_players.extend(players)
    all_players.sort(key=lambda x: x["StatValue"], reverse=True)
    return all_players


def get_country_flag_url(ccode):
    """URL cờ quốc gia (ccode phải viết thường)."""
    return f"https://images.fotmob.com/image_resources/logo/teamlogo/{ccode.lower()}.png"

