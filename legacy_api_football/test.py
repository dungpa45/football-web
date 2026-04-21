import requests
from bs4 import BeautifulSoup
import json

LEAGUES = {
    "Premier League": 47,
    "ESP-La Liga": 87,
    "FRA-Ligue 1": 53,
    "GER-Bundesliga": 54,
    "ITA-Serie A": 55,
}

URL = "https://www.fotmob.com/leagues/47/table/premier-league?season=2024-2025"
# HEADERS = {"User-Agent": "Mozilla/5.0"}

resp = requests.get(URL)
soup = BeautifulSoup(resp.text, "html.parser")

# Extract embedded JSON from <script id="__NEXT_DATA__">
data = json.loads(soup.find("script", attrs={"id": "__NEXT_DATA__"}).text)
table = data["props"]["pageProps"]["overview"]["table"][0]["data"]["table"]["all"]
d_stats=data["props"]["pageProps"]['stats']


def get_tournament_id(data, league_name, season_year):
    """
    Returns the TournamentId for a given season name from the data.
    """
    for season in data.get("seasonStatLinks", []):
        if season.get("League") == league_name and season.get("Name") == season_year:
            return season.get("TournamentId")
    return None

ss_id = get_tournament_id(d_stats, "Premier League", "2024/2025")
print(ss_id)
# Parse into DataFrame
rows = []
# print(len(table))
for entry in table:
    team = entry["name"]
    # print(team)
    pos = entry["idx"]
    
    row = {
        "Position": pos,
        "Team": team,
        "Played": entry["played"],
        "Won": entry["wins"],
        "Drawn": entry["draws"],
        "Lost": entry["losses"],
        "GA": entry["scoresStr"],
        "GD": entry["goalConDiff"],
        "Points": entry["pts"],
    }
    rows.append(row)




# import json
# import requests
# import pandas as pd
# from bs4 import BeautifulSoup

# url = "https://www.fotmob.com/leagues/47/table/premier-league?season=2024-2025"
# r = requests.get(url)
# html_doc = r.text
# soup = BeautifulSoup(html_doc, "html.parser")

# data = json.loads(soup.find("script", attrs={"id": "__NEXT_DATA__"}).text)
# # print(data["props"]["pageProps"])
# d = data["props"]["pageProps"]["overview"]["table"][0]["data"]["table"]["all"]
# print(d)
# df = pd.DataFrame(d)
# df = pd.concat([df, df.pop("all").apply(pd.Series)], axis=1)

# print(df)