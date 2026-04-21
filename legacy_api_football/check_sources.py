"""
Diagnostic script - kiểm tra kết nối tới các nguồn data.
Chạy: python check_sources.py
"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TM_HEADERS = {
    **HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.transfermarkt.com/",
}

tests = [
    ("FotMob Page (EPL)", "https://www.fotmob.com/leagues/47/overview/premier-league", HEADERS),
    ("FotMob Data API (goals)", "https://data.fotmob.com/stats/47/season/27110/goals.json", HEADERS),
    ("FotMob Player (Haaland)", "https://www.fotmob.com/players/737066/overview", HEADERS),
    ("FotMob Team (Man City)", "https://www.fotmob.com/teams/8456/squad", HEADERS),
    ("FotMob Image (player)", "https://images.fotmob.com/image_resources/playerimages/737066.png", HEADERS),
    ("FotMob Image (team)", "https://images.fotmob.com/image_resources/logo/teamlogo/8456.png", HEADERS),
    ("FotMob Image (league dark)", "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/47.png", HEADERS),
    ("FotMob Image (flag)", "https://images.fotmob.com/image_resources/logo/teamlogo/nor.png", HEADERS),
    ("Transfermarkt Search", "https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query=Erling+Haaland", TM_HEADERS),
    ("Transfermarkt Trophies", "https://www.transfermarkt.com/erling-haaland/erfolge/spieler/418560", TM_HEADERS),
]

# Load TM cookies if available
tm_cookies = {}
try:
    import json as _json
    with open("tm_cookies.json") as f:
        tm_cookies = {c["name"]: c["value"] for c in _json.load(f)}
except Exception:
    pass

print("=" * 60)
print("  DATA SOURCE DIAGNOSTIC")
print("=" * 60)

for name, url, headers in tests:
    try:
        cookies = tm_cookies if 'transfermarkt' in url else {}
        r = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        status = r.status_code
        ok = "✅" if status == 200 else "❌"
        print(f"  {ok} {name:35s} {status}  ({len(r.content)} bytes)")
    except Exception as e:
        print(f"  ❌ {name:35s} ERROR: {e}")

print("=" * 60)
print("\nNếu Transfermarkt bị ❌ 403/405 → server đang bị block.")
print("Thử chạy từ máy local hoặc dùng VPN.\n")
