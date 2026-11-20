import unittest
from copy import deepcopy
from unittest.mock import patch

from requests.exceptions import Timeout

import club_stats
import fotmob


def player(pid, team, value, minutes=90, matches=1, count=1):
    return {
        "ParticiantId": pid, "ParticipantName": f"Player {pid}", "TeamId": team,
        "TeamName": f"Team {team}", "StatValue": value, "SubStatValue": 0,
        "MinutesPlayed": minutes, "MatchesPlayed": matches, "StatValueCount": count,
    }


def page(cid, season, dates, stats=True):
    return {
        "details": {"id": cid, "selectedSeason": season},
        "allAvailableSeasons": [season],
        "fixtures": {"allMatches": [
            {"id": str(cid * 100 + i), "home": {"id": "10"}, "away": {"id": "90"},
             "status": {"utcTime": date, "finished": True}}
            for i, date in enumerate(dates)
        ]},
        "stats": {
            "seasonStatLinks": [{"Name": season, "TemplateId": cid, "TournamentId": cid * 10}],
            "players": [{"name": stat} for stat in (
                "goals", "goal_assist", "mins_played", "rating",
                "expected_goals", "expected_assists",
            )] if stats else [],
        },
    }


def match_data():
    def participant(pid, team, minutes, **values):
        return {
            "id": pid, "name": f"Player {pid}", "teamId": team, "teamName": f"Team {team}",
            "stats": [{"stats": {
                key: {"key": key, "stat": {"value": value}}
                for key, value in {"minutes_played": minutes, **values}.items()
            }}],
        }

    return {
        "general": {
            "matchId": "24700", "parentLeagueId": 247, "finished": True,
            "homeTeam": {"id": 10}, "awayTeam": {"id": 90},
        },
        "header": {"teams": [{"id": 10, "score": 2}, {"id": 90, "score": 1}]},
        "content": {
            "playerStats": {
                "1": participant(1, 10, 75, goals=1, assists=1, rating_title=8.2,
                                 expected_goals=0.75, expected_assists=0.4),
                "2": participant(2, 10, 90, rating_title=6.5),
                "3": participant(3, 90, 90, goals=0, assists=0, rating_title=6),
                "4": participant(4, 10, 15, goals=1, assists=0),
                "5": participant(5, 10, 0, goals=0, assists=0),
            },
            "lineup": {
                "homeTeam": {"starters": [{"id": 1}, {"id": 2}], "subs": [
                    {"id": 4, "performance": {"substitutionEvents": [{"type": "subIn"}]}},
                    {"id": 5},
                ]},
                "awayTeam": {"starters": [{"id": 3}], "subs": []},
            },
            "matchFacts": {"events": {"events": [
                {"type": "Goal", "playerId": 1, "goalDescriptionKey": "penalty"},
                {"type": "Goal", "playerId": 4, "assistPlayerId": 1},
                {"type": "Goal", "playerId": 2, "ownGoal": True},
                {"type": "Goal", "playerId": 1, "isPenaltyShootoutEvent": True},
            ]}},
        },
    }


class ClubStatsTests(unittest.TestCase):
    def setUp(self):
        self.stored = {}
        self.ttls = {}
        for name, replacement in (
            ("get_cached", self.stored.get),
            ("set_cached", self.save),
        ):
            mock = patch.object(club_stats, name, side_effect=replacement)
            mock.start()
            self.addCleanup(mock.stop)

    def save(self, key, value, ttl):
        self.stored[key] = value
        self.ttls[key] = ttl

    def test_totals_include_cup_only_players_and_transfers_before_ranking(self):
        league_a = fotmob.LEAGUES["epl"]
        league_b = fotmob.LEAGUES["bundes"]
        pages = {
            47: page(47, "2026/2027", ["2026-08-15"]),
            54: page(54, "2026/2027", ["2026-08-15"]),
            132: page(132, "2026/2027", ["2026-09-15"]),
        }
        pages[54]["fixtures"]["allMatches"][0]["home"]["id"] = "20"
        data = {
            47: {
                "goals": [*[player(pid, 10, 25 - pid) for pid in range(10, 21)],
                          player(1, 10, 1, 270, 3), player(3, 10, 2)],
                "goal_assist": [player(1, 10, 2)],
                "mins_played": [player(1, 10, 270, 270, 3), player(3, 10, 90)],
                "rating": [player(1, 10, 7, 270, 3, 3)],
                "expected_goals": [player(1, 10, 1.2)],
                "expected_assists": [player(1, 10, 0.4)],
            },
            54: {
                "goals": [player(3, 20, 3)],
                "goal_assist": [],
                "mins_played": [player(3, 20, 90)],
                "rating": [],
                "expected_goals": [player(3, 20, 2.2)],
                "expected_assists": [],
            },
            132: {
                "goals": [player(1, 10, 30), player(3, 10, 1), player(4, 10, 8),
                          player(999, 90, 100)],
                "goal_assist": [player(4, 10, 1)],
                "mins_played": [player(1, 10, 90), player(3, 10, 90), player(4, 10, 90)],
                "rating": [player(1, 10, 9)],
                "expected_goals": [player(1, 10, 2.3)],
                "expected_assists": [player(1, 10, 0.2)],
            },
        }
        original = deepcopy(data)
        with patch.object(fotmob, "LEAGUES", {"epl": league_a, "bundes": league_b}), patch.object(
            fotmob, "get_standings", side_effect=lambda key, season: (
                [{"id": 10 if key == "epl" else 20}], []
            )
        ) as standings, patch.object(
            fotmob, "get_league_page", return_value={"allAvailableSeasons": ["2026/2027"]}
        ), patch.object(
            club_stats, "CUPS", ((132, "FA Cup", "season"),)
        ), patch.object(
            club_stats, "_season_pages",
            side_effect=lambda cid, kind, season: iter([pages[cid]]),
        ), patch.object(
            club_stats, "_stat_rows", side_effect=lambda link, stat, ttl: data[link["TemplateId"]][stat]
        ) as fetch:
            goals = club_stats.get_top_club_stats("goals", "2026/2027")
            calls = fetch.call_count
            assists = club_stats.get_top_club_stats("assists", "2026/2027")
            ga = club_stats.get_top_club_stats("ga", "2026/2027")
            self.assertEqual(fetch.call_count, calls)
            self.assertEqual(standings.call_args_list[0].args, ("epl", "2026/2027"))
            self.assertEqual(standings.call_args_list[1].args, ("bundes", "2026/2027"))

        self.assertEqual(goals["players"][0]["ParticiantId"], 1)
        winner = goals["players"][0]
        self.assertEqual((winner["Goals"], winner["Assists"], winner["StatValue"]), (31, 2, 31))
        self.assertEqual((winner["MinutesPlayed"], winner["MatchesPlayed"]), (360, 4))
        self.assertEqual(winner["Rating"], 7.5)
        self.assertEqual((winner["xG"], winner["xA"]), (3.5, 0.6))
        self.assertEqual(assists["players"][0]["StatValue"], 2)
        self.assertEqual(ga["players"][0]["StatValue"], 33)
        transfer = next(p for p in goals["players"] if p["ParticiantId"] == 3)
        self.assertEqual((transfer["Goals"], transfer["MatchesPlayed"]), (6, 3))
        self.assertIn(4, [p["ParticiantId"] for p in goals["players"]])
        self.assertNotIn(999, [p["ParticiantId"] for p in goals["players"]])
        self.assertEqual(goals["included_competitions"], ["Premier League", "Bundesliga", "FA Cup"])
        self.assertEqual(goals["unavailable_competitions"], [])
        self.assertEqual(data, original)
        goals["players"][0]["Goals"] = -1
        self.assertEqual(self.stored["all-club:v2:2026/2027"]["players"][0]["Goals"], 31)
        self.assertEqual(self.ttls["all-club:v2:2026/2027"], 900)

    def test_missing_optional_datasets_do_not_become_partial_minute_or_expected_totals(self):
        stats = {stat: {} for stat in (
            "goals", "goal_assist", "mins_played", "rating", "expected_goals", "expected_assists"
        )}
        stats["goals"][(1, 10)] = player(1, 10, 2)
        stats["mins_played"][(1, 10)] = player(1, 10, 90)
        stats["mins_played"][(2, 20)] = player(2, 20, 90)
        snapshots = [{"stats": stats, "teams": {10, 20}}]
        missing = {**stats, "goals": {(1, 10): player(1, 10, 1)},
                   "mins_played": None, "expected_goals": None, "expected_assists": None}
        snapshots.append({"stats": missing, "teams": {10}})
        result = {p["ParticiantId"]: p for p in club_stats._aggregate(
            snapshots, {10: {}, 20: {}}
        )}
        self.assertEqual(result[1]["Goals"], 3)
        for field in ("MinutesPlayed", "MatchesPlayed", "xG", "xA", "Rating"):
            self.assertIsNone(result[1][field])
        self.assertEqual(result[2]["MinutesPlayed"], 90)
        self.assertEqual(result[2]["xG"], 0)

    def test_supercup_without_match_feed_remains_explicitly_unavailable(self):
        with patch.object(
            club_stats, "_season_pages", return_value=iter([
                page(207, "2026/2027", ["2026-08-15"], stats=False)
            ])
        ), patch.object(
            club_stats, "_match_snapshot", side_effect=Timeout("unavailable")
        ), patch.object(club_stats, "_stat_rows") as fetch, self.assertLogs(
            club_stats.logger, level="WARNING"
        ):
            snapshots, warnings, complete = club_stats._load_competition(
                (207, "French Super Cup", "supercup"), "2026/2027", {10}, 900
            )
        self.assertEqual(snapshots, [])
        self.assertIn("French Super Cup", warnings[0])
        self.assertFalse(complete)
        fetch.assert_not_called()

    def test_supercup_match_fallback_is_cached_deduplicated_and_aggregated(self):
        cup = page(247, "2025/2026", ["2026-08-15"], stats=False)
        cup["fixtures"]["allMatches"] *= 2
        data = match_data()
        original = deepcopy(data)
        with patch.object(
            club_stats, "_season_pages", side_effect=lambda *args: iter([cup])
        ), patch.object(
            fotmob, "_fetch_json", return_value=data
        ) as fetch, patch.object(club_stats, "_stat_rows") as competition_feed:
            for _ in range(2):
                snapshots, warnings, complete = club_stats._load_competition(
                    (247, "Community Shield", "supercup"), "2026/2027", {10}, 900
                )
                self.assertEqual(len(snapshots), 1)
                self.assertEqual(warnings, [])
                self.assertTrue(complete)
            fetch.assert_called_once_with(
                "https://www.fotmob.com/api/data/matchDetails?matchId=24700"
            )
            competition_feed.assert_not_called()
        result = {p["ParticiantId"]: p for p in club_stats._aggregate(snapshots, {10: {}})}
        self.assertEqual(set(result), {1, 2, 4})
        self.assertEqual((result[1]["Goals"], result[1]["Assists"]), (1, 1))
        self.assertEqual((result[1]["MinutesPlayed"], result[1]["MatchesPlayed"]), (75, 1))
        self.assertEqual(result[1]["SubStatValue"], 1)
        self.assertEqual(result[1]["Rating"], 8.2)
        self.assertEqual((result[1]["xG"], result[1]["xA"]), (0.8, 0.4))
        self.assertEqual(result[2]["Goals"], 0)
        self.assertEqual(result[4]["Goals"], 1)
        self.assertIsNone(result[4]["Rating"])
        self.assertIsNone(result[4]["xG"])
        self.assertEqual(self.ttls["club-match:v1:24700"], 900)
        self.assertEqual(data, original)

    def test_match_fallback_does_not_duplicate_available_competition_totals(self):
        with patch.object(
            club_stats, "_season_pages",
            return_value=iter([page(247, "2025/2026", ["2026-08-15"])]),
        ), patch.object(
            club_stats, "_stat_rows", return_value=[player(1, 10, 1)]
        ), patch.object(club_stats, "_match_snapshot") as match_feed:
            snapshots, warnings, complete = club_stats._load_competition(
                (247, "Community Shield", "supercup"), "2026/2027", {10}, 900
            )
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(warnings, [])
        self.assertTrue(complete)
        match_feed.assert_not_called()

    def test_stoppage_time_substitute_with_zero_rounded_minutes_still_has_an_appearance(self):
        data = match_data()
        data["content"]["playerStats"]["4"]["stats"][0]["stats"]["minutes_played"]["stat"]["value"] = 0
        match = page(247, "2025/2026", ["2026-08-15"])["fixtures"]["allMatches"][0]
        stats = club_stats._match_stats(data, match, 247, {10})
        self.assertEqual(stats["mins_played"][(4, 10)]["MatchesPlayed"], 1)
        self.assertEqual(stats["mins_played"][(4, 10)]["MinutesPlayed"], 0)
        self.assertNotIn((5, 10), stats["mins_played"])

    def test_incomplete_match_is_not_cached_and_can_recover(self):
        match = page(247, "2025/2026", ["2026-08-15"])["fixtures"]["allMatches"][0]
        incomplete = match_data()
        incomplete["content"]["playerStats"]["4"]["stats"] = []
        with patch.object(
            fotmob, "_fetch_json", side_effect=[incomplete, match_data()]
        ) as fetch:
            with self.assertRaisesRegex(fotmob.requests.RequestException, "incomplete"):
                club_stats._match_snapshot(match, 247, "Community Shield", {10}, 86400)
            self.assertNotIn("club-match:v1:24700", self.stored)
            recovered = club_stats._match_snapshot(match, 247, "Community Shield", {10}, 86400)
            self.assertEqual(recovered["stats"]["goals"][(4, 10)]["StatValue"], 1)
            self.assertEqual(fetch.call_count, 2)
        self.assertEqual(self.ttls["club-match:v1:24700"], 86400)

    def test_wrong_match_and_incomplete_scoring_data_are_rejected(self):
        match = page(247, "2025/2026", ["2026-08-15"])["fixtures"]["allMatches"][0]
        for error in ("wrong_match", "wrong_competition", "missing_events", "wrong_goals"):
            data = match_data()
            if error == "wrong_match":
                data["general"]["matchId"] = "999"
            elif error == "wrong_competition":
                data["general"]["parentLeagueId"] = 47
            elif error == "missing_events":
                data["content"]["matchFacts"]["events"]["events"] = []
            else:
                data["content"]["playerStats"]["1"]["stats"][0]["stats"]["goals"]["stat"]["value"] = 2
            with self.subTest(error=error), self.assertRaises(fotmob.requests.RequestException):
                club_stats._match_stats(data, match, 247, {10})

    def test_transient_competition_failure_is_visible_and_not_cached(self):
        with patch.object(
            fotmob, "get_standings", return_value=([{"id": 10}], [])
        ), patch.object(
            fotmob, "get_league_page", return_value={"allAvailableSeasons": ["2026/2027"]}
        ), patch.object(
            club_stats, "_load_competition", return_value=([], ["upstream unavailable"], False)
        ):
            result = club_stats.get_top_club_stats("ga", "2026/2027")
        self.assertIn("upstream unavailable", result["unavailable_competitions"])
        self.assertNotIn("all-club:v2:2026/2027", self.stored)

    def test_failed_required_and_optional_feeds_have_explicit_coverage(self):
        for failed in ("goals", "rating"):
            def rows(link, stat, ttl):
                if stat == failed:
                    raise Timeout("unavailable")
                return [player(1, 10, 2)]

            with self.subTest(failed=failed), patch.object(
                club_stats, "_season_pages",
                return_value=iter([page(132, "2026/2027", ["2026-09-15"])]),
            ), patch.object(
                club_stats, "_stat_rows", side_effect=rows
            ), self.assertLogs(club_stats.logger, level="WARNING"):
                snapshots, warnings, complete = club_stats._load_competition(
                    (132, "FA Cup", "season"), "2026/2027", {10}, 900
                )
            self.assertFalse(complete)
            self.assertIn(f"FA Cup: {failed} temporarily unavailable", warnings)
            self.assertEqual(len(snapshots), 0 if failed == "goals" else 1)
            if snapshots:
                self.assertIsNone(snapshots[0]["stats"]["rating"])

    def test_cup_without_played_eligible_clubs_does_not_count_or_fetch_stats(self):
        future = page(132, "2026/2027", ["2027-01-15"], stats=False)
        future["fixtures"]["allMatches"][0]["status"]["finished"] = False
        with patch.object(
            club_stats, "_season_pages", return_value=iter([future])
        ), patch.object(club_stats, "_stat_rows") as fetch:
            result = club_stats._load_competition(
                (132, "FA Cup", "season"), "2026/2027", {10}, 900
            )
        self.assertEqual(result, ([], [], True))
        fetch.assert_not_called()

    def test_stat_failure_can_retry_and_empty_list_is_cached(self):
        link = {"TemplateId": 132, "TournamentId": 123}
        with patch.object(
            fotmob, "_fetch_json",
            side_effect=[Timeout("unavailable"), {"TopLists": [{"StatList": []}]}],
        ) as fetch:
            with self.assertRaises(Timeout):
                club_stats._stat_rows(link, "goals", 86400)
            self.assertEqual(club_stats._stat_rows(link, "goals", 86400), [])
            self.assertEqual(club_stats._stat_rows(link, "goals", 86400), [])
            self.assertEqual(fetch.call_count, 2)
        self.assertEqual(self.ttls["club-stat:v1:132:123:goals"], 86400)

    def test_wrong_season_and_missing_membership_cannot_fall_back_to_current(self):
        current = page(132, "2026/2027", ["2026-08-15"])
        current["allAvailableSeasons"].append("2025/2026")
        with patch.object(club_stats, "_competition_page", return_value=current):
            with self.assertRaisesRegex(fotmob.requests.RequestException, "did not return"):
                list(club_stats._season_pages(132, "season", "2025/2026"))
        with patch.object(fotmob, "get_standings", return_value=([], [])):
            with self.assertRaisesRegex(fotmob.requests.RequestException, "Cannot determine"):
                club_stats.get_top_club_stats("goals", "2025/2026")

    def test_supercup_and_calendar_editions_are_assigned_by_fixture_date(self):
        current = page(8924, "2025/2026", ["2026-08-22"])
        prior = page(8924, "2024/2025", ["2025-08-22"])
        current["allAvailableSeasons"].append("2024/2025")
        with patch.object(
            club_stats, "_competition_page",
            side_effect=lambda cid, season=None: prior if season == "2024/2025" else current,
        ):
            selected = list(club_stats._season_pages(8924, "supercup", "2025/2026"))
        self.assertEqual(selected, [prior])
        world_cup = page(78, "2025", ["2025-06-14", "2025-07-13"])
        with patch.object(club_stats, "_competition_page", return_value=world_cup):
            self.assertEqual(list(club_stats._season_pages(78, "calendar", "2024/2025")), [world_cup])
            self.assertEqual(list(club_stats._season_pages(78, "calendar", "2025/2026")), [])
