import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from requests.exceptions import Timeout

import app as app_module
import fotmob


class FotmobStatsTests(unittest.TestCase):
    def test_all_league_tabs_join_full_ratings_without_changing_ranks_or_cache(self):
        leagues = {key: fotmob.LEAGUES[key] for key in ("epl", "bundes")}
        source = {
            key: [{"ParticiantId": 10, "StatValue": value},
                  {"ParticiantId": 20, "StatValue": 1}]
            for key, value in (("epl", 3), ("bundes", 5))
        }

        def ratings(key, season, limit):
            self.assertEqual(season, "2025/2026")
            self.assertIsNone(limit)
            return [
                *[{"ParticiantId": 100 + i, "StatValue": 9} for i in range(25)],
                {"ParticiantId": 10, "StatValue": 7.25 if key == "epl" else 8.5},
            ]

        for stat in ("goals", "goal_assist", "ga"):
            with self.subTest(stat=stat), patch.object(fotmob, "LEAGUES", leagues), patch.object(
                fotmob, "_fetch_stat", side_effect=lambda key, *args: source[key]
            ), patch.object(
                fotmob, "get_top_goals_assists", side_effect=lambda key, *args: source[key]
            ), patch.object(fotmob, "get_top_rating", side_effect=ratings) as get_ratings:
                result = (
                    fotmob.get_top_ga_all_leagues("2025/2026")
                    if stat == "ga" else fotmob.get_top_all_leagues(stat, "2025/2026")
                )
                self.assertEqual(get_ratings.call_count, 2)
                self.assertEqual([p["StatValue"] for p in result], [5, 3, 1, 1])
                self.assertEqual([p["Rating"] for p in result], [8.5, 7.25, None, None])
                self.assertTrue(all("Rating" not in p and "league_name" not in p
                                    for players in source.values() for p in players))

    def test_all_league_rating_failure_logs_and_recovers_without_losing_stats(self):
        for stat in ("goals", "goal_assist", "ga"):
            with self.subTest(stat=stat), patch.object(
                fotmob, "LEAGUES", {"epl": fotmob.LEAGUES["epl"]}
            ), patch.object(
                fotmob, "_fetch_stat", return_value=[{"ParticiantId": 10, "StatValue": 3}]
            ), patch.object(
                fotmob, "get_top_goals_assists",
                return_value=[{"ParticiantId": 10, "StatValue": 3}]
            ), patch.object(
                fotmob, "get_top_rating",
                side_effect=[Timeout("unavailable"), [{"ParticiantId": 10, "StatValue": 7.5}]]
            ):
                def fetch():
                    return (
                        fotmob.get_top_ga_all_leagues("2026/2027")
                        if stat == "ga" else fotmob.get_top_all_leagues(stat, "2026/2027")
                    )

                with self.assertLogs(fotmob.logger, level="WARNING"):
                    partial = fetch()
                self.assertEqual(partial[0]["StatValue"], 3)
                self.assertIsNone(partial[0]["Rating"])
                self.assertEqual(fetch()[0]["Rating"], 7.5)

    def test_missing_stats_are_not_reported_as_zero(self):
        player = {
            "ParticiantId": 10, "ParticipantName": "Player", "TeamId": 20,
            "TeamName": "Team", "Rank": 1, "StatValue": 2,
            "MatchesPlayed": 3, "MinutesPlayed": 90,
        }

        def fetch(url):
            if "_goals_and_goal_assist.json" in url:
                return {"TopLists": [{"StatList": [player.copy()]}]}
            if "/goal_assist.json" in url:
                raise Timeout("unavailable")
            if "/expected_goals.json" in url:
                return {"TopLists": []}
            value = 0 if "/goals.json" in url else 1.5
            return {"TopLists": [{"StatList": [{"ParticiantId": 10, "StatValue": value}]}]}

        with patch.object(fotmob, "_get_tournament_id", return_value=(1, 2)), patch.object(
            fotmob, "_fetch_json", side_effect=fetch
        ), patch.object(
            fotmob, "get_cached", return_value=None
        ):
            result = fotmob.get_top_goals_assists("epl", "2026/2027")
        self.assertEqual(result[0]["Goals"], 0)
        self.assertIsNone(result[0]["Assists"])
        self.assertIsNone(result[0]["xG"])
        self.assertEqual(result[0]["xA"], 1.5)

        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        with patch.object(app_module, "get_available_seasons", return_value=["2026/2027"]), patch.object(
            app_module, "get_top_goals_assists", return_value=result
        ):
            response = client.get("/topga")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            BeautifulSoup(response.data, "html.parser").select_one(".stat-bold").get_text(strip=True),
            "2",
        )
        self.assertNotIn("— = data unavailable".encode(), response.data)

        result[0]["league_id"] = 47
        result[0]["league_name"] = "Premier League"
        with patch.object(app_module, "get_available_seasons", return_value=["2026/2027"]), patch.object(
            app_module, "get_top_ga_all_leagues", return_value=result
        ):
            response = client.get("/all/topga")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            BeautifulSoup(response.data, "html.parser").select_one(".stat-bold").get_text(strip=True),
            "2",
        )
        self.assertNotIn("— = data unavailable".encode(), response.data)

    def test_ga_breakdown_is_hidden_when_incomplete_but_preserves_real_zero(self):
        base = {
            "ParticiantId": 10, "ParticipantName": "Player", "TeamId": 20,
            "TeamName": "Team", "Rank": 1, "StatValue": 9,
            "MatchesPlayed": 3, "MinutesPlayed": 270, "SubStatValue": 0,
            "league_id": 47, "league_name": "Premier League", "Rating": None,
            "xG": None, "xA": None,
        }
        players = [
            {**base, "Goals": 9, "Assists": None},
            {**base, "Goals": None, "Assists": 9},
            {**base, "Goals": 9, "Assists": 0},
            {**base, "Goals": 0, "Assists": 9},
            {**base, "Goals": 7, "Assists": 2},
            base.copy(),
        ]
        totals = {
            "players": players, "included_competitions": [],
            "unavailable_competitions": [],
        }
        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        with patch.object(app_module, "get_available_seasons", return_value=["2026/2027"]), patch.object(
            app_module, "get_top_goals_assists", return_value=players
        ), patch.object(
            app_module, "get_top_ga_all_leagues", return_value=players
        ), patch.object(app_module, "get_top_club_stats", return_value=totals):
            for url in ("/topga", "/all/topga?scope=league", "/all/topga?scope=all"):
                with self.subTest(url=url):
                    response = client.get(url)
                    self.assertEqual(response.status_code, 200)
                    page = BeautifulSoup(response.data, "html.parser")
                    self.assertEqual(
                        [cell.get_text(" ", strip=True) for cell in page.select("td.stat-bold")],
                        ["9", "9", "9 (9+0)", "9 (0+9)", "9 (7+2)", "9"],
                    )

    def test_league_and_stat_ttls_follow_provider_season(self):
        stored = {}
        ttls = {}
        metadata = {
            "allAvailableSeasons": ["2026/2027", "2025/2026"],
            "stats": {"seasonStatLinks": [
                {"Name": "2026/2027", "TournamentId": 1, "TemplateId": 2},
                {"Name": "2025/2026", "TournamentId": 3, "TemplateId": 2},
            ]},
        }

        def save(key, value, ttl):
            stored[key] = value
            ttls[key] = ttl

        response = {"TopLists": [{"StatList": [{"ParticiantId": 10, "StatValue": 2}]}]}
        with patch.object(fotmob, "get_cached", side_effect=stored.get), patch.object(
            fotmob, "set_cached", side_effect=save
        ), patch.object(fotmob, "_fetch_page", return_value=metadata), patch.object(
            fotmob, "_fetch_json", return_value=response
        ):
            fotmob.get_league_page("epl")
            for season in ("2026/2027", "2025/2026"):
                fotmob.get_league_page("epl", season)
                fotmob.get_top_scorers("epl", season)
                fotmob.get_top_assists("epl", season)

        self.assertEqual(ttls["league:v2:epl:current"], 900)
        for season, ttl in (("2026/2027", 900), ("2025/2026", 86400)):
            self.assertEqual(ttls[f"league:v2:epl:{season}"], ttl)
            self.assertEqual(ttls[f"stat:v2:epl:goals:{season}:20"], ttl)
            self.assertEqual(ttls[f"stat:v2:epl:goal_assist:{season}:20"], ttl)
        self.assertEqual(fotmob._season_ttl("2025/2026", {}), 900)
        self.assertEqual(fotmob._season_ttl("2027/2028", metadata), 900)

    def test_goals_assists_cache_reuses_full_result_without_sharing_mutations(self):
        metadata = {"allAvailableSeasons": ["2026/2027", "2025/2026"]}
        stored = {fotmob._league_cache_key("epl"): metadata}
        ttls = {}

        def save(key, value, ttl):
            stored[key] = value
            ttls[key] = ttl

        players = [{"ParticiantId": 10, "StatValue": 2}, {"ParticiantId": 20, "StatValue": 1}]

        def fetch(url):
            if "_goals_and_goal_assist.json" in url:
                return {"TopLists": [{"StatList": [player.copy() for player in players]}]}
            return {"TopLists": [{"StatList": [{"ParticiantId": 10, "StatValue": 1}]}]}

        with patch.object(fotmob, "get_cached", side_effect=stored.get), patch.object(
            fotmob, "set_cached", side_effect=save
        ), patch.object(fotmob, "_get_tournament_id", return_value=(1, 2)), patch.object(
            fotmob, "_fetch_json", side_effect=fetch
        ) as fetch_json:
            first = fotmob.get_top_goals_assists("epl", "2025/2026", limit=1)
            first[0]["league_name"] = "modified"
            second = fotmob.get_top_goals_assists("epl", "2025/2026", limit=2)
            self.assertEqual(fetch_json.call_count, 5)

        self.assertEqual(len(second), 2)
        self.assertNotIn("league_name", second[0])
        self.assertEqual(ttls["stat:v2:epl:goals_assists:2025/2026"], 86400)

    def test_goals_assists_failure_is_not_cached_and_can_recover(self):
        stored = {fotmob._league_cache_key("epl"): {"allAvailableSeasons": ["2026/2027"]}}
        attempts = 0

        def save(key, value, ttl):
            stored[key] = value

        def fetch(url):
            nonlocal attempts
            if "/goal_assist.json" in url:
                attempts += 1
                if attempts == 1:
                    raise Timeout("unavailable")
            return {"TopLists": [{"StatList": [{"ParticiantId": 10, "StatValue": 2}]}]}

        with patch.object(fotmob, "get_cached", side_effect=stored.get), patch.object(
            fotmob, "set_cached", side_effect=save
        ) as set_cached, patch.object(fotmob, "_get_tournament_id", return_value=(1, 2)), patch.object(
            fotmob, "_fetch_json", side_effect=fetch
        ) as fetch_json:
            partial = fotmob.get_top_goals_assists("epl", "2026/2027")
            self.assertIsNone(partial[0]["Assists"])
            set_cached.assert_not_called()
            recovered = fotmob.get_top_goals_assists("epl", "2026/2027")
            self.assertEqual(recovered[0]["Assists"], 2)
            set_cached.assert_called_once()
            self.assertEqual(set_cached.call_args.args[2], 900)
            fotmob.get_top_goals_assists("epl", "2026/2027")
            self.assertEqual(fetch_json.call_count, 10)
            self.assertEqual(attempts, 2)

