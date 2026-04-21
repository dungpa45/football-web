"""
FotMob Skills Module
Lấy dữ liệu từ FotMob thông qua scraping __NEXT_DATA__ và data.fotmob.com API.
"""

import requests
import json
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

BASE_URL = "https://www.fotmob.com"
DATA_URL = "https://data.fotmob.com"

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
        return None
    return json.loads(script.text)["props"]["pageProps"]


def _fetch_json(url):
    """Fetch JSON trực tiếp từ data.fotmob.com."""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


# ============================================================
# =============== LEAGUE DATA ================================
# ============================================================

def get_league_page(league_key, season=None):
    """
    Lấy toàn bộ data trang league (standings, stats overview, seasons...).
    league_key: 'epl', 'laliga', 'seriea', 'bundes', 'ligue1'
    season: '2024/2025' hoặc None (mặc định mùa hiện tại)
    Returns: dict pageProps
    """
    league = LEAGUES[league_key]
    url = f"{BASE_URL}/leagues/{league['id']}/overview/{league['slug']}"
    if season:
        url += f"?season={season}"
    return _fetch_page(url)


def get_available_seasons(league_key):
    """Lấy danh sách các mùa giải có sẵn."""
    data = get_league_page(league_key)
    return data.get("allAvailableSeasons", [])


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
    return players[:limit] if limit else players


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
    league = LEAGUES[league_key]
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
    for stat_type, target in [("goals", goals_map), ("goal_assist", assists_map),
                               ("expected_goals", xg_map), ("expected_assists", xa_map)]:
        try:
            d = _fetch_json(f"{base}/{stat_type}.json")
            for p in d.get("TopLists", [{}])[0].get("StatList", []):
                target[p["ParticiantId"]] = p["StatValue"]
        except Exception:
            pass

    # Merge
    for p in players:
        pid = p["ParticiantId"]
        p["Goals"] = int(goals_map.get(pid, 0))
        p["Assists"] = int(assists_map.get(pid, 0))
        p["xG"] = xg_map.get(pid, 0)
        p["xA"] = xa_map.get(pid, 0)

    return players[:limit] if limit else players


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
    url = f"{BASE_URL}/players/{player_id}/overview"
    data = _fetch_page(url)
    if not data:
        return None
    return data.get("data")


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
    url = f"{BASE_URL}/teams/{team_id}/squad"
    data = _fetch_page(url)
    if not data:
        return None
    # Data nằm trong fallback
    fallback = data.get("fallback", {})
    for key, val in fallback.items():
        if key.startswith("team-"):
            return val
    return None


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


def get_country_flag_url(ccode):
    """URL cờ quốc gia (ccode phải viết thường)."""
    return f"https://images.fotmob.com/image_resources/logo/teamlogo/{ccode.lower()}.png"


# ============================================================
# =============== TRANSFERMARKT TROPHIES =====================
# ============================================================

_TM_BASE = "https://www.transfermarkt.com"
_TM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.transfermarkt.com/",
}


def _load_tm_cookies():
    """Load TM cookies từ file nếu có."""
    import os
    cookie_file = os.path.join(os.path.dirname(__file__), "tm_cookies.json")
    if not os.path.exists(cookie_file):
        return {}
    try:
        with open(cookie_file) as f:
            data = json.load(f)
        return {c["name"]: c["value"] for c in data}
    except Exception:
        return {}


def _tm_get(url):
    """GET request tới Transfermarkt với cookies fallback."""
    cookies = _load_tm_cookies()
    r = requests.get(url, headers=_TM_HEADERS, cookies=cookies, timeout=15)
    r.raise_for_status()
    return r

_INDIVIDUAL_KEYWORDS = [
    "best player", "golden boot", "golden ball", "golden glove",
    "footballer of the year", "player of the year", "player of the season",
    "top goal scorer", "top scorer", "top assist",
    "ballon d'or", "the best", "pfa", "mvp",
    "striker of the year", "goalkeeper of the year", "defender of the year",
    "young player", "best young", "golden boy",
    "tm-player", "rating", "puskas",
]

_PARTICIPATION_KEYWORDS = [
    "participant", "runner-up", "relegated",
]


def _classify_trophy(title):
    """Phân loại danh hiệu: individual / team / participation."""
    t = title.lower()
    for kw in _PARTICIPATION_KEYWORDS:
        if kw in t:
            return "participation"
    for kw in _INDIVIDUAL_KEYWORDS:
        if kw in t:
            return "individual"
    return "team"


def _search_tm_player(player_name):
    """Search Transfermarkt để lấy player slug + ID."""
    url = f"{_TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={player_name.replace(' ', '+')}"
    try:
        r = _tm_get(url)
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", class_="items")
    if not table:
        return None
    row = table.find("tr", class_=["odd", "even"])
    if not row:
        return None
    a = row.find("td", class_="hauptlink")
    if a:
        a = a.find("a")
    if not a:
        return None
    href = a["href"]  # /erling-haaland/profil/spieler/418560
    parts = href.split("/")
    return {"slug": parts[1], "id": parts[-1]}


def get_tm_trophies(player_name):
    """
    Scrape danh hiệu từ Transfermarkt, phân loại cá nhân / tập thể.
    Returns: {"individual": [...], "team": [...], "participation": [...]}
    Mỗi item: {"title": str, "entries": [{"season": str, "detail": str}]}
    """
    info = _search_tm_player(player_name)
    if not info:
        return None
    url = f"{_TM_BASE}/{info['slug']}/erfolge/spieler/{info['id']}"
    try:
        r = _tm_get(url)
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    main_col = soup.find("div", class_="large-8")
    if not main_col:
        return None

    result = {"individual": [], "team": [], "participation": []}
    for box in main_col.find_all("div", class_="box"):
        h2 = box.find("h2")
        if not h2:
            continue
        title = h2.get_text(strip=True)
        category = _classify_trophy(title)
        # Trophy image (first img in box, usually the cup/medal)
        first_img = box.find("img")
        trophy_img = first_img["src"] if first_img else ""
        entries = []
        table = box.find("table")
        if table:
            for row in table.find_all("tr"):
                tds = row.find_all("td")
                if not tds:
                    continue
                season = tds[0].get_text(strip=True)
                # TD[1] = team/league logo, TD[2] = team/league name
                team_img = ""
                team_name = ""
                if len(tds) > 1:
                    img = tds[1].find("img")
                    if img:
                        team_img = img.get("src", "")
                if len(tds) > 2:
                    team_name = tds[2].get_text(strip=True)
                entries.append({"season": season, "detail": team_name, "team_img": team_img})
        result[category].append({"title": title, "trophy_img": trophy_img, "entries": entries})
    return result
