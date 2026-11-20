import base64
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from pymongo.errors import AutoReconnect
from requests.exceptions import Timeout

import app as app_module
import fotmob


class AppBehaviorTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True)
        app_module.ADMIN_USER = "test-admin"
        app_module.ADMIN_PASS = "test-password"
        self.client = app_module.app.test_client()
        seasons = patch.object(app_module, "get_available_seasons", return_value=["2026/2027", "2025/2026"])
        seasons.start()
        self.addCleanup(seasons.stop)

    def _admin_headers(self):
        credentials = base64.b64encode(b"test-admin:test-password").decode("ascii")
        return {"Authorization": f"Basic {credentials}"}

    def test_health_endpoint(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

    def test_all_league_tabs_render_rating_and_missing_data(self):
        player = {
            "ParticiantId": 10, "ParticipantName": "Player", "TeamId": 20,
            "TeamName": "Team", "league_id": 47, "league_name": "Premier League",
            "StatValue": 3, "SubStatValue": 0, "MinutesPlayed": 180,
            "MatchesPlayed": 2, "Goals": 2, "Assists": 1, "xG": 1.5, "xA": 0.5,
        }
        players = [{**player, "Rating": rating} for rating in (8.01, 8, 7.01, 7, 6.99, None)]
        for route, getter in (
            ("/all/topscorers", "get_top_all_leagues"),
            ("/all/topassists", "get_top_all_leagues"),
            ("/all/topga", "get_top_ga_all_leagues"),
        ):
            with self.subTest(route=route), patch.object(app_module, getter, return_value=players):
                response = self.client.get(route + "?season=2025%2F2026")
                self.assertEqual(response.status_code, 200)
                page = BeautifulSoup(response.data, "html.parser")
                headers = [th.get_text(strip=True) for th in page.select(".table-card th")]
                self.assertIn("Rating", headers)
                index = headers.index("Rating")
                rows = page.select(".table-card tbody tr")
                self.assertEqual(
                    [row.select("td")[index].get_text(strip=True) for row in rows],
                    ["8.01", "8.00", "7.01", "7.00", "6.99", "—"],
                )
                badges = page.select(".table-card .career-rating")
                self.assertEqual(
                    [badge.get("class") for badge in badges],
                    [["career-rating", "rating-high"],
                     ["career-rating", "rating-good"],
                     ["career-rating", "rating-good"],
                     ["career-rating"], ["career-rating"]],
                )
                self.assertNotIn("— = data unavailable", page.get_text())

    def test_all_club_scope_preserves_navigation_and_exposes_partial_coverage(self):
        totals = {
            "players": [{
                "ParticiantId": 10, "ParticipantName": "Player", "TeamId": 20,
                "TeamName": "Team", "league_id": 47, "league_name": "Premier League",
                "StatValue": 3, "SubStatValue": 0, "MinutesPlayed": None,
                "MatchesPlayed": None, "Goals": 2, "Assists": 1,
                "xG": None, "xA": None, "Rating": 8.25,
            }],
            "included_competitions": ["Premier League", "FA Cup"],
            "unavailable_competitions": ["UEFA Super Cup: player statistics unavailable"],
        }
        for route, stat in (("topscorers", "goals"), ("topassists", "assists"), ("topga", "ga")):
            with self.subTest(route=route), patch.object(
                app_module, "get_top_club_stats", return_value=totals
            ) as get_totals, patch.object(
                app_module, "get_top_all_leagues"
            ) as league_stats, patch.object(
                app_module, "get_top_ga_all_leagues"
            ) as league_ga:
                response = self.client.get(f"/all/{route}?scope=all&season=2025%2F2026")
                self.assertEqual(response.status_code, 200)
                get_totals.assert_called_once_with(stat, "2025/2026")
                league_stats.assert_not_called()
                league_ga.assert_not_called()
                page = BeautifulSoup(response.data, "html.parser")
                active = page.select_one('.page-header .competition-switch [aria-current="page"]')
                self.assertEqual(active.get_text(strip=True), "All club competitions")
                for link in page.select('.container a[href^="/all/"]'):
                    query = parse_qs(urlparse(link["href"]).query)
                    if "competition-switch" in link.parent.get("class", []):
                        self.assertEqual(query["scope"], [
                            "league" if link.get_text(strip=True) == "League only" else "all"
                        ])
                    else:
                        self.assertEqual(query["scope"], ["all"])
                    self.assertEqual(query["season"], ["2025/2026"])
                self.assertEqual(page.select_one('input[name="scope"]')["value"], "all")
                self.assertIn("Partial totals", page.select_one('[role="status"]').get_text())
                self.assertIn("UEFA Super Cup", page.select_one('[role="status"]').get_text())
                self.assertIn("FA Cup", page.select_one(".competition-coverage details").get_text())
                self.assertNotIn("None", page.select_one(".table-card tbody").get_text())

    def test_invalid_all_club_scope_is_rejected_before_fetching(self):
        with patch.object(app_module, "get_top_club_stats") as get_totals, patch.object(
            app_module, "get_available_seasons"
        ) as seasons:
            response = self.client.get("/all/topga?scope=invalid")
        self.assertEqual(response.status_code, 400)
        get_totals.assert_not_called()
        seasons.assert_not_called()

    def test_all_club_upstream_failure_uses_existing_error_response(self):
        with patch.object(app_module, "get_top_club_stats", side_effect=Timeout("unavailable")):
            response = self.client.get("/all/topscorers?scope=all")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"temporarily unavailable", response.data)

    def test_readiness_checks_mongodb(self):
        with patch.object(app_module, "my_db") as database:
            response = self.client.get("/readyz")
            self.assertEqual(response.status_code, 200)
            database.command.assert_called_once_with("ping")
            database.command.side_effect = AutoReconnect("unavailable")
            response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {"status": "unavailable"})

    def test_current_season_comes_from_provider(self):
        with patch.object(app_module, "get_available_seasons", return_value=["2028/2029", "2027/2028"]):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"2028/2029", response.data)

    def test_season_fallback_updates_across_year_boundary(self):
        with patch.object(app_module, "get_available_seasons", side_effect=Timeout("unavailable")):
            with patch.object(app_module, "datetime") as clock:
                clock.now.return_value.year = 2028
                clock.now.return_value.month = 7
                self.assertEqual(app_module._available_seasons("epl")[0], "2027/2028")
                clock.now.return_value.month = 8
                self.assertEqual(app_module._available_seasons("epl")[0], "2028/2029")

    def test_invalid_league_is_rejected_before_fetch(self):
        with patch.object(app_module, "get_standings") as get_standings:
            response = self.client.get("/standings?league=not-a-league")
        self.assertEqual(response.status_code, 404)
        get_standings.assert_not_called()

    def test_invalid_season_is_rejected_before_fetch(self):
        with patch.object(app_module, "get_standings") as get_standings:
            response = self.client.get("/standings?season=2024%2F2026")
        self.assertEqual(response.status_code, 400)
        get_standings.assert_not_called()

    def test_admin_post_without_csrf_token_is_rejected(self):
        with patch.object(app_module.honours_coll, "delete_one") as delete_one:
            response = self.client.post(
                "/admin/honours/42/delete",
                headers=self._admin_headers(),
            )
        self.assertEqual(response.status_code, 400)
        delete_one.assert_not_called()

    def test_admin_forms_render_csrf_token(self):
        cursor = type("Cursor", (), {"sort": lambda self, *args: []})()
        with patch.object(app_module.honours_coll, "find", return_value=cursor):
            response = self.client.get(
                "/admin/honours",
                headers=self._admin_headers(),
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="_csrf_token"', response.data)

    def test_admin_post_with_invalid_category_is_rejected(self):
        with self.client.session_transaction() as session:
            session["_csrf_token"] = "valid-token"
        with patch.object(app_module, "get_player_honours") as get_player_honours:
            response = self.client.post(
                "/admin/honours/42/update/not-a-category",
                data={"_csrf_token": "valid-token"},
                headers=self._admin_headers(),
            )
        self.assertEqual(response.status_code, 404)
        get_player_honours.assert_not_called()

    def test_admin_post_with_valid_csrf_token_reaches_route(self):
        with self.client.session_transaction() as session:
            session["_csrf_token"] = "valid-token"
        with patch.object(app_module.honours_coll, "delete_one") as delete_one:
            response = self.client.post(
                "/admin/honours/42/delete",
                data={"_csrf_token": "valid-token"},
                headers=self._admin_headers(),
            )
        self.assertEqual(response.status_code, 302)
        delete_one.assert_called_once_with({"fotmob_id": 42})

    def test_empty_stat_cache_entry_does_not_trigger_upstream_fetch(self):
        with patch.object(fotmob, "get_cached", return_value=[]), patch.object(
            fotmob, "_get_tournament_id"
        ) as get_tournament_id:
            result = fotmob._fetch_stat("epl", "goals")
        self.assertEqual(result, [])
        get_tournament_id.assert_not_called()

    def test_team_trophies_parse_current_and_legacy_fotmob_formats(self):
        info = {"history": {"trophyList": [
            {"name": "LaLiga", "leagueId": "87", "won": 36,
             "seasonsWon": "2023/2024, 2021/2022"},
            {"name": "Champions League", "leagueId": "42", "won": 0, "seasonsWon": ""},
            {"name": ["FA Cup"], "tournamentTemplateId": ["132"], "area": ["England"],
             "won": ["12"], "season_won": ["2022/2023, 2020/2021"]},
            {"name": "Cup", "leagueId": "-1", "won": "1", "seasonsWon": ""},
        ]}}
        trophies, total = app_module._parse_trophy_list(info)
        self.assertEqual(total, 49)
        self.assertEqual(trophies, [
            {"name": "LaLiga", "league_id": "87", "area": "", "won": 36,
             "seasons_won": ["2023/2024", "2021/2022"]},
            {"name": "FA Cup", "league_id": "132", "area": "England", "won": 12,
             "seasons_won": ["2022/2023", "2020/2021"]},
            {"name": "Cup", "league_id": "-1", "area": "", "won": 1,
             "seasons_won": []},
        ])

    def test_team_trophies_log_malformed_entries(self):
        info = {"history": {"trophyList": [
            {"name": "Invalid count", "won": "unknown"},
            {"name": "Missing count"},
            {"name": "Invalid seasons", "won": 2, "seasonsWon": 123},
            {"name": "Empty legacy fields", "won": [], "season_won": []},
        ]}}
        with self.assertLogs(app_module.logger, level="WARNING") as logs:
            trophies, total = app_module._parse_trophy_list(info)
        self.assertEqual(total, 2)
        self.assertEqual([t["name"] for t in trophies], ["Invalid seasons"])
        self.assertEqual(trophies[0]["seasons_won"], [])
        self.assertGreaterEqual(len(logs.output), 4)

    def test_team_route_renders_current_fotmob_trophies(self):
        info = {
            "details": {"id": 8633, "name": "Real Madrid", "country": "Spain",
                        "latestSeason": "2026/2027"},
            "history": {"trophyList": [
                {"name": "LaLiga", "leagueId": "87", "won": 36,
                 "seasonsWon": "2023/2024,2021/2022"},
                {"name": "Champions League", "leagueId": "42", "won": 15,
                 "seasonsWon": "2023/2024"},
                {"name": "Runner-up only", "won": 0, "seasonsWon": ""},
            ]},
        }
        with patch.object(app_module, "get_team_info", return_value=info):
            response = self.client.get("/team/8633")
        self.assertEqual(response.status_code, 200)
        page = BeautifulSoup(response.data, "html.parser")
        self.assertIn("51 titles", page.get_text())
        self.assertIn("2023/2024", page.get_text())
        self.assertIsNotNone(page.select_one('img[src*="/leaguelogo/dark/87.png"]'))
        self.assertNotIn("Runner-up only", page.get_text())

    def test_player_info_and_long_award_lists(self):
        player = {
            'id': 10, 'name': 'Player',
            'birthDate': {'utcTime': '1993-07-28T00:00:00.000Z'},
            'positionDescription': {'primaryPosition': {'key': 'forward', 'label': 'Forward'}},
            'playerInformation': [{'title': 'Height', 'value': {'fallback': '188 cm'}}],
            'trophies': {'playerTrophies': [
                {
                    'teamId': 20, 'teamName': 'Team',
                    'tournaments': [
                        {'leagueName': 'Trophy 1', 'seasonsWon': ['2024', '2025', '2026']},
                        {'leagueName': 'Trophy 2', 'seasonsWon': ['2025', '2026']},
                        *[{'leagueName': f'Trophy {n}', 'seasonsWon': ['2026']} for n in range(3, 6)],
                        {'leagueName': 'Not won', 'seasonsWon': []},
                        {'leagueName': 'Unavailable'},
                    ],
                },
                {'teamId': 21, 'teamName': 'Other team',
                 'tournaments': [{'leagueName': 'Other trophy', 'seasonsWon': ['2026']}]},
            ]},
        }
        award_names = [
            'Premier League Player of the Season', 'Premier League Playmaker of the Season',
            'Manchester City Player of the Year', 'Award 4', 'Award 5',
        ]
        doc = {'honours': {'individual': [
            {'trophy': name, 'years': ['2026'], 'count': 1} for name in award_names
        ]}}
        with patch.object(app_module, 'get_player_info', return_value=player), patch.object(
            app_module, 'get_player_honours', return_value=doc
        ), patch.object(app_module, 'schedule_individual_refresh') as schedule:
            response = self.client.get('/player/10')
        self.assertEqual(response.status_code, 200)
        schedule.assert_called_once_with(10, 'Player', doc, '1993-07-28')
        page = BeautifulSoup(response.data, 'html.parser')
        self.assertEqual(len(page.select('.player-info-grid .player-info-item')), 2)
        self.assertIn('1993-07-28', page.select_one('.player-info-grid').get_text())
        honours = page.select_one('details.honours-section')
        self.assertIsNotNone(honours)
        self.assertFalse(honours.has_attr('open'))
        self.assertEqual(honours.summary.get_text(' ', strip=True), 'Honours')
        self.assertEqual(len(honours.select('.honours-grid > section')), 2)
        self.assertFalse(honours.select('details'))
        self.assertEqual(len(page.select('.indiv-award')), 5)
        for award, name in zip(page.select('.indiv-award')[:3], award_names[:3]):
            self.assertIn(name, award.get_text())
            self.assertIn('indiv-poty', award['class'])
        self.assertEqual(len(page.select('.trophy-item')), 6)
        self.assertEqual(
            [item.get_text(strip=True) for item in page.select('.team-trophy-total')],
            ['8 titles', '1 title'],
        )
        self.assertEqual(page.select_one('.trophy-item .honour-count').get_text(strip=True), '3')
        self.assertEqual(page.select_one('.trophy-item .honour-count')['aria-label'], '3 titles')
        self.assertNotIn('3x', page.get_text())

    def test_player_page_handles_missing_position_key_and_description(self):
        players = [
            {
                'id': 248453, 'name': 'Paul Pogba',
                'positionDescription': {'primaryPosition': {'label': 'midfielder', 'key': None}},
            },
            {'id': 11, 'name': 'Player with no primary position', 'positionDescription': None},
            {'id': 12, 'name': 'Player with no position description'},
        ]
        for player in players:
            with self.subTest(player=player['id']), patch.object(
                app_module, 'get_player_info', return_value=player
            ), patch.object(
                app_module, 'get_player_honours', return_value=None
            ), patch.object(app_module, 'schedule_individual_refresh'):
                try:
                    response = self.client.get(f"/player/{player['id']}")
                except TypeError as exc:
                    self.fail(f"Player with incomplete position data should still render: {exc}")

            self.assertEqual(response.status_code, 200)
            page = BeautifulSoup(response.data, 'html.parser')
            badge = page.select_one('.player-position')
            self.assertIsNotNone(badge)
            if player['id'] == 248453:
                self.assertEqual(badge.get_text(strip=True), 'midfielder')
                self.assertIn('pos-mf', badge['class'])
            else:
                self.assertEqual(badge.get_text(strip=True), 'Unknown position')

    def test_retired_player_with_null_recent_matches_uses_detailed_position(self):
        player = {
            'id': 37459,
            'name': 'David Silva',
            'positionDescription': {
                'primaryPosition': {'label': 'midfielder', 'key': None},
                'positions': [{
                    'strPos': {
                        'label': 'Attacking Midfielder',
                        'key': 'centerattackingmidfielder',
                    },
                    'strPosShort': {'label': 'AM', 'key': 'centerattackingmidfielder_short'},
                }],
            },
            'statSeasons': [{
                'seasonName': '2022/2023',
                'tournaments': [{'tournamentId': 87}],
            }],
            'recentMatches': None,
            'careerHistory': {
                'careerItems': {
                    'senior': {
                        'seasonEntries': [{
                            'seasonName': '2022/2023',
                            'teamId': 20,
                            'team': 'Test FC',
                            'tournamentStats': [{
                                'leagueId': 87,
                                'leagueName': 'LaLiga',
                                'appearances': '1',
                                'goals': '0',
                                'assists': '0',
                            }],
                        }],
                        'teamEntries': [],
                    },
                    'national team': {'seasonEntries': [], 'teamEntries': []},
                },
            },
        }
        with patch.object(app_module, 'get_player_info', return_value=player), patch.object(
            app_module, 'get_player_honours', return_value=None
        ), patch.object(app_module, 'schedule_individual_refresh'):
            response = self.client.get('/player/37459')

        self.assertEqual(response.status_code, 200)
        page = BeautifulSoup(response.data, 'html.parser')
        badge = page.select_one('.player-position')
        self.assertEqual(badge.get_text(strip=True), 'Attacking Midfielder')
        self.assertIn('pos-mf', badge['class'])
        self.assertIn('LaLiga', page.get_text())

    def test_player_shows_clubs_without_fotmob_ids_as_plain_names(self):
        player = {
            'id': 18,
            'name': 'Player with clubs missing from FotMob',
            'positionDescription': {
                'primaryPosition': {'key': 'midfielder', 'label': 'Midfielder'},
            },
            'primaryTeam': {'teamId': 0, 'teamName': 'Unlisted Current Club'},
            'trophies': {
                'playerTrophies': [{
                    'teamName': 'Unlinked Trophy Club',
                    'tournaments': [{'leagueName': 'Cup', 'seasonsWon': ['2020']}],
                }],
            },
            'careerHistory': {
                'careerItems': {
                    'senior': {
                        'seasonEntries': [
                            {'seasonName': '2023/2024', 'teamId': 20, 'team': 'Known Club',
                             'tournamentStats': []},
                            {'seasonName': '2022/2023', 'teamId': None, 'team': 'Unlinked Club A',
                             'tournamentStats': []},
                            {'seasonName': '2021/2022', 'teamId': None, 'team': 'Unlinked Club B',
                             'tournamentStats': []},
                            {'seasonName': '2020/2021', 'teamId': -1, 'team': 'Unlinked Club C',
                             'tournamentStats': []},
                        ],
                        'teamEntries': [],
                    },
                    'national team': {'seasonEntries': [], 'teamEntries': []},
                },
            },
        }
        with patch.object(app_module, 'get_player_info', return_value=player), patch.object(
            app_module, 'get_player_honours', return_value=None
        ), patch.object(app_module, 'schedule_individual_refresh'):
            response = self.client.get('/player/18')

        self.assertEqual(response.status_code, 200)
        page = BeautifulSoup(response.data, 'html.parser')
        self.assertEqual(
            {link.get_text(strip=True): link['href'] for link in page.select('a.team-cell')},
            {'Known Club': '/team/20'},
        )
        self.assertEqual(
            {cell.get_text(strip=True) for cell in page.select('span.team-cell')},
            {'Unlinked Club A', 'Unlinked Club B', 'Unlinked Club C'},
        )
        self.assertEqual(
            [img['src'] for img in page.select('.career-team-row .team-cell img')],
            ['https://images.fotmob.com/image_resources/logo/teamlogo/20.png'],
        )
        self.assertIsNone(page.select_one('a.player-team-badge'))
        self.assertEqual(page.select_one('.player-team-badge').get_text(strip=True), 'Unlisted Current Club')
        self.assertIsNone(page.select_one('.player-team-badge img'))
        trophy_team = page.select_one('.player-trophy-team-name')
        self.assertEqual(trophy_team.select_one('span').get_text(strip=True), 'Unlinked Trophy Club')
        self.assertIsNone(trophy_team.select_one('img'))

    def test_honours_handles_only_individual_awards(self):
        player = {
            'id': 10, 'name': 'Player',
            'positionDescription': {'primaryPosition': {'key': 'forward', 'label': 'Forward'}},
        }
        doc = {'honours': {'individual': [{'trophy': 'Award', 'years': ['2026'], 'count': 1}]}}
        with patch.object(app_module, 'get_player_info', return_value=player), patch.object(
            app_module, 'get_player_honours', return_value=doc
        ), patch.object(app_module, 'schedule_individual_refresh'):
            response = self.client.get('/player/10')
        self.assertEqual(response.status_code, 200)
        page = BeautifulSoup(response.data, 'html.parser')
        self.assertEqual(len(page.select('.honours-grid > section')), 2)
        self.assertIn('No team trophies available', page.get_text())

    def test_honours_handles_only_team_trophies(self):
        player = {
            'id': 10, 'name': 'Player',
            'positionDescription': {'primaryPosition': {'key': 'forward', 'label': 'Forward'}},
            'trophies': {'playerTrophies': [{
                'teamId': 20, 'teamName': 'Team',
                'tournaments': [{'leagueName': 'Trophy', 'seasonsWon': ['2026']}],
            }]},
        }
        with patch.object(app_module, 'get_player_info', return_value=player), patch.object(
            app_module, 'get_player_honours', return_value=None
        ), patch.object(app_module, 'schedule_individual_refresh'):
            response = self.client.get('/player/10')
        self.assertEqual(response.status_code, 200)
        page = BeautifulSoup(response.data, 'html.parser')
        self.assertIn('No individual awards available', page.get_text())
        self.assertEqual(page.select_one('.team-trophy-total').get_text(strip=True), '1 title')
        self.assertEqual(page.select_one('.trophy-item .honour-count')['aria-label'], '1 title')

    def test_player_page_highlights_major_awards_and_omits_nominees(self):
        player = {
            'id': 7, 'name': 'Superstar',
            'positionDescription': {'primaryPosition': {'key': 'forward', 'label': 'Forward'}},
        }
        doc = {
            'honours': {
                'individual': [
                    {'trophy': 'Manchester City Player of the Year', 'years': ['2023'], 'count': 1},
                    {'trophy': "Ballon d'Or nominee", 'years': ['2022', '2023'], 'count': 2},
                    {'trophy': "Gerd Müller Trophy (Ballon d'Or Striker of the Year)", 'years': ['2021', '2022'], 'count': 2},
                    {'trophy': 'Ballon d’Or', 'years': ['2023'], 'count': 1},
                    {'trophy': 'Premier League Player of the Season', 'years': ['2023'], 'count': 1},
                    {'trophy': "The Best FIFA Men's Player", 'years': ['2023'], 'count': 1},
                    {'trophy': "The Best FIFA Men's Player nominee", 'years': ['2022'], 'count': 1},
                ]
            }
        }
        with patch.object(app_module, 'get_player_info', return_value=player), patch.object(
            app_module, 'get_player_honours', return_value=doc
        ), patch.object(app_module, 'schedule_individual_refresh'):
            response = self.client.get('/player/7')

        self.assertEqual(response.status_code, 200)
        page = BeautifulSoup(response.data, 'html.parser')
        awards = page.select('.indiv-award')
        # Nominees must NOT be rendered (only 5 real awards remain)
        self.assertEqual(len(awards), 5)
        self.assertNotIn('nominee', page.get_text().lower())

        # Major awards should be sorted to the top
        names = [a.select_one('.indiv-title-text').get_text(strip=True) for a in awards]
        self.assertEqual(
            names,
            [
                'Ballon d’Or',
                "The Best FIFA Men's Player",
                'Premier League Player of the Season',
                'Gerd Müller Trophy',
                'Manchester City Player of the Year',
            ]
        )

        # Check Ballon d'Or
        ballon_elem = awards[0]
        self.assertIn('indiv-ballon', ballon_elem['class'])
        self.assertIn('indiv-major', ballon_elem['class'])
        self.assertIsNotNone(ballon_elem.select_one('img[src*="ballon_dor.png"]'))
        self.assertIn("Ballon d'Or", ballon_elem.select_one('.indiv-badge').get_text())

        # Check FIFA The Best
        fifa_elem = awards[1]
        self.assertIn('indiv-fifabest', fifa_elem['class'])
        self.assertIn('indiv-major', fifa_elem['class'])
        self.assertIsNotNone(fifa_elem.select_one('img[src*="fifa_best.png"]'))
        self.assertIn('FIFA The Best', fifa_elem.select_one('.indiv-badge').get_text())

        # Check Domestic League Player of the Season
        pl_elem = awards[2]
        self.assertIn('indiv-league-poty', pl_elem['class'])
        self.assertIn('indiv-major', pl_elem['class'])
        self.assertIn('indiv-poty', pl_elem['class'])
        self.assertIn('👑', pl_elem.select_one('.indiv-icon').get_text())
        self.assertIn('League MVP', pl_elem.select_one('.indiv-badge').get_text())

        # Check Gerd Müller Trophy (normalized, topscorer tier, not misidentified as Ballon d'Or)
        gm_elem = awards[3]
        self.assertIn('indiv-topscorer', gm_elem['class'])
        self.assertNotIn('indiv-ballon', gm_elem['class'])
        self.assertNotIn('indiv-major', gm_elem['class'])
        self.assertIn('👟', gm_elem.select_one('.indiv-icon').get_text())

        # Check Club Player of the Year
        club_elem = awards[4]
        self.assertIn('indiv-poty', club_elem['class'])
        self.assertNotIn('indiv-major', club_elem['class'])
        self.assertNotIn('indiv-league-poty', club_elem['class'])
        self.assertIsNone(club_elem.select_one('.indiv-badge'))

    def test_player_info_without_birth_date_or_duplicate_born(self):
        self.assertEqual(app_module._parse_player_info({}), [])
        player = {
            'birthDate': {'utcTime': '1993-07-28T00:00:00.000Z'},
            'playerInformation': [{'title': 'Date of birth', 'value': {'fallback': '28 July 1993'}}],
        }
        self.assertEqual(len(app_module._parse_player_info(player)), 1)

    def test_player_honours_data_endpoint_returns_json_and_html(self):
        doc = {
            'honours': {
                'individual': [
                    {'trophy': "Ballon d'Or", 'years': ['2024'], 'count': 1},
                    {'trophy': 'Premier League Player of the Season', 'years': ['2024'], 'count': 1},
                ]
            }
        }
        with patch.object(app_module, 'get_player_honours', return_value=doc), patch.object(
            app_module, 'is_individual_refresh_active', return_value=False
        ):
            response = self.client.get('/player/10/honours-data')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data['loading'])
        self.assertEqual(data['count'], 2)
        self.assertIn('indiv-ballon', data['html'])
        self.assertIn("Ballon d'Or", data['html'])
        self.assertIn('Premier League Player of the Season', data['html'])

    def test_player_honours_data_endpoint_reports_loading_state_and_skeleton(self):
        with patch.object(app_module, 'get_player_honours', return_value=None), patch.object(
            app_module, 'is_individual_refresh_active', return_value=True
        ), patch.object(app_module, 'wait_for_individual_refresh'):
            response = self.client.get('/player/10/honours-data')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['loading'])
        self.assertEqual(data['count'], 0)
        self.assertIn('honours-loading-box', data['html'])
        self.assertIn('Fetching individual awards from Wikipedia', data['html'])

    def test_player_page_renders_loading_box_and_poll_script_when_loading(self):
        player = {
            'id': 15, 'name': 'NewStar',
            'positionDescription': {'primaryPosition': {'key': 'forward', 'label': 'Forward'}},
        }
        with patch.object(app_module, 'get_player_info', return_value=player), patch.object(
            app_module, 'get_player_honours', return_value=None
        ), patch.object(app_module, 'schedule_individual_refresh', return_value=True):
            response = self.client.get('/player/15')

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('honours-loading-box', html)
        self.assertIn('const playerId = 15;', html)
        self.assertIn("fetch('/player/' + playerId + '/honours-data')", html)


if __name__ == "__main__":
    unittest.main()
