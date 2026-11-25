import os
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pymongo import MongoClient

import honours_db
import wiki_honours


class IndividualAwardClassificationTests(unittest.TestCase):
    def test_season_playmaker_and_club_awards_keep_names_years_and_counts(self):
        names = [
            'Premier League Player of the Season',
            'Premier League Playmaker of the Season',
            'Manchester City Player of the Season',
            'Liverpool Players\' Player of the Season',
            'Manchester United Players\' Player of the Year',
            'Tottenham Hotspur Player of the Year',
            'Brighton & Hove Albion Player of the Year',
            'AS Roma Player of the Season',
        ]
        text = "'''Individual'''\n" + '\n'.join(
            f'* [[{name}]]: 2023, 2024' for name in names
        )
        result = wiki_honours.classify_honours(wiki_honours.parse_honours(text))
        self.assertEqual(result['Individual Awards'], [
            {'trophy': name, 'years': ['2023', '2024'], 'count': 2} for name in names
        ])

    def test_season_awards_do_not_include_monthly_teams_or_runner_up(self):
        text = """'''Individual'''
* [[Premier League Player of the Month]]: 2024
* [[Liverpool Player of the Month]]: 2024
* [[PFA Team of the Year]]: 2024
* [[Manchester City Player of the Season]] runner-up: 2024
* [[Premier League Playmaker of the Season]]: 2024
"""
        result = wiki_honours.classify_honours(wiki_honours.parse_honours(text))
        self.assertEqual(result['Individual Awards'], [
            {'trophy': 'Premier League Playmaker of the Season', 'years': ['2024'], 'count': 1},
        ])

    def test_disqualified_awards_such_as_nominees_are_excluded(self):
        text = """'''Individual'''
* [[Ballon d'Or]] nominee: 2021, 2022
* [[Ballon d'Or]] nomination: 2023
* [[The Best FIFA Men's Player]] nominee: 2022
* Ballon d'Or candidate: 2020
* [[Ballon d'Or]] shortlisted: 2019
* [[Ballon d'Or]]: 2024
* [[Premier League Player of the Season]] nominee: 2023
* [[Premier League Player of the Season]]: 2024
"""
        result = wiki_honours.classify_honours(wiki_honours.parse_honours(text))
        self.assertEqual(result['Individual Awards'], [
            {'trophy': "Ballon d'Or", 'years': ['2024'], 'count': 1},
            {'trophy': 'Premier League Player of the Season', 'years': ['2024'], 'count': 1},
        ])

    def test_gerd_muller_trophy_normalization_and_ballon_exclusion(self):
        text = """'''Individual'''
* [[Gerd Müller Trophy]] (Ballon d'Or Striker of the Year): 2021, 2022
* [[Ballon d'Or]]: 2020
"""
        parsed = wiki_honours.parse_honours(text)
        classified = wiki_honours.classify_honours(parsed)
        awards = classified['Individual Awards']
        self.assertEqual(len(awards), 2)
        self.assertEqual(awards[0]['trophy'], 'Gerd Müller Trophy')
        self.assertEqual(awards[0]['years'], ['2021', '2022'])
        self.assertEqual(awards[0]['count'], 2)
        self.assertEqual(awards[1]['trophy'], "Ballon d'Or")

        # Ensure Gerd Müller variants do not trigger Ballon d'Or
        self.assertFalse(wiki_honours.is_ballon_dor_award("Gerd Müller Trophy (Ballon d'Or Striker of the Year)"))
        self.assertFalse(wiki_honours.is_ballon_dor_award("Gerd Müller Trophy"))
        self.assertFalse(wiki_honours.is_ballon_dor_award("Ballon d'Or Striker of the Year"))
        self.assertTrue(wiki_honours.is_ballon_dor_award("Ballon d'Or"))

    def test_major_award_recognition_and_sorting(self):
        self.assertTrue(wiki_honours.is_ballon_dor_award("Ballon d'Or"))
        self.assertTrue(wiki_honours.is_ballon_dor_award("Ballon d’Or"))
        self.assertTrue(wiki_honours.is_ballon_dor_award("FIFA Ballon d'Or"))
        self.assertFalse(wiki_honours.is_ballon_dor_award("Ballon d'Or nominee"))

        self.assertTrue(wiki_honours.is_fifa_the_best_award("The Best FIFA Men's Player"))
        self.assertTrue(wiki_honours.is_fifa_the_best_award("FIFA World Player of the Year"))
        self.assertFalse(wiki_honours.is_fifa_the_best_award("The Best FIFA Men's Player nominee"))

        self.assertTrue(wiki_honours.is_league_poty_award("Premier League Player of the Season"))
        self.assertTrue(wiki_honours.is_league_poty_award("PFA Players' Player of the Year"))
        self.assertTrue(wiki_honours.is_league_poty_award("Football Writers' Association Footballer of the Year"))
        self.assertTrue(wiki_honours.is_league_poty_award("La Liga Best Player"))
        self.assertTrue(wiki_honours.is_league_poty_award("Serie A Footballer of the Year"))
        self.assertTrue(wiki_honours.is_league_poty_award("Bundesliga Player of the Season"))
        self.assertTrue(wiki_honours.is_league_poty_award("Ligue 1 Player of the Year"))

        self.assertFalse(wiki_honours.is_league_poty_award("Premier League Playmaker of the Season"))
        self.assertFalse(wiki_honours.is_league_poty_award("Manchester City Player of the Year"))
        self.assertFalse(wiki_honours.is_league_poty_award("Liverpool Players' Player of the Season"))
        self.assertFalse(wiki_honours.is_league_poty_award("Premier League Player of the Season nominee"))

        awards = [
            {'trophy': 'Manchester City Player of the Year', 'count': 1},
            {'trophy': 'Premier League Playmaker of the Season', 'count': 1},
            {'trophy': 'Ballon d’Or', 'count': 1},
            {'trophy': 'Premier League Player of the Season', 'count': 2},
            {'trophy': "The Best FIFA Men's Player", 'count': 1},
        ]
        sorted_awards = wiki_honours.sort_individual_awards(awards)
        self.assertEqual(
            [a['trophy'] for a in sorted_awards],
            [
                'Ballon d’Or',
                "The Best FIFA Men's Player",
                'Premier League Player of the Season',
                'Premier League Playmaker of the Season',
                'Manchester City Player of the Year',
            ]
        )

    def test_national_player_of_the_year_awards_are_kept(self):
        names = [
            'Danish Football Player of the Year',
            'Danish Football Player of the Year by TV2 and DBU',
            'Footballer of the Year (Germany)',
            'Footballer of the Year in Germany',
            'Guldbollen',
            'Gullballen',
            'Kniksen of the Year',
            'Portuguese Golden Ball',
            'Czech Golden Ball',
            'Hungarian Golden Ball',
            'Idol Nacije',
            'Belgian Golden Shoe',
            'Swedish Footballer of the Year',
            "PFA Scotland Players' Player of the Year",
        ]
        text = "'''Individual'''\n" + '\n'.join(f'* [[{name}]]: 2020' for name in names)
        result = wiki_honours.classify_honours(wiki_honours.parse_honours(text))
        self.assertEqual(
            [award['trophy'] for award in result['Individual Awards']],
            names,
        )

        excluded = """'''Individual'''
* [[Danish Talent of the Year]]: 2011
* [[Kniksen's honour award]]: 2020
* [[Premier League Player of the Year by Northwest Football Awards]]: 2019
"""
        excluded_result = wiki_honours.classify_honours(wiki_honours.parse_honours(excluded))
        self.assertNotIn('Individual Awards', excluded_result)


class IndividualMergeTests(unittest.TestCase):
    def test_merge_preserves_manual_awards_and_adds_only_new_years(self):
        existing = [
            {'trophy': 'Ballon d’Or', 'years': ['2024'], 'count': 1, 'note': 'reviewed'},
            {'trophy': 'Manual award', 'years': ['2023'], 'count': 1},
        ]
        incoming = [
            {'trophy': 'ballon d’or', 'years': ['2024', '2025'], 'count': 2},
            {'trophy': 'Golden Boot', 'years': ['2026'], 'count': 1},
        ]
        merged = honours_db._merge_individual_awards(existing, incoming)
        self.assertEqual(merged[0]['years'], ['2024', '2025'])
        self.assertEqual(merged[0]['count'], 2)
        self.assertEqual(merged[0]['note'], 'reviewed')
        self.assertEqual(merged[1], existing[1])
        self.assertEqual(merged[2]['trophy'], 'Golden Boot')
        self.assertEqual(existing[0]['years'], ['2024'])

    def test_merge_purges_disqualified_nominees(self):
        existing = [
            {'trophy': "Ballon d'Or nominee", 'years': ['2023'], 'count': 1},
            {'trophy': "Ballon d'Or", 'years': ['2024'], 'count': 1},
        ]
        incoming = [
            {'trophy': "Ballon d'Or nominee", 'years': ['2023', '2025'], 'count': 2},
            {'trophy': "The Best FIFA Men's Player", 'years': ['2024'], 'count': 1},
        ]
        merged = honours_db._merge_individual_awards(existing, incoming)
        trophies = [item['trophy'] for item in merged]
        self.assertNotIn("Ballon d'Or nominee", trophies)
        self.assertEqual(trophies, ["Ballon d'Or", "The Best FIFA Men's Player"])

    def test_merge_normalizes_gerd_muller_trophy_and_combines_years(self):
        existing = [
            {'trophy': "Gerd Müller Trophy (Ballon d'Or Striker of the Year)", 'years': ['2021'], 'count': 1},
        ]
        incoming = [
            {'trophy': 'Gerd Müller Trophy', 'years': ['2021', '2022'], 'count': 2},
        ]
        merged = honours_db._merge_individual_awards(existing, incoming)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['trophy'], 'Gerd Müller Trophy')
        self.assertEqual(merged[0]['years'], ['2021', '2022'])
        self.assertEqual(merged[0]['count'], 2)

    def test_verified_profile_is_not_scheduled(self):
        with patch.object(honours_db.threading, 'Thread') as thread:
            honours_db.schedule_individual_refresh(10, 'Player', {'verified': True})
        thread.assert_not_called()

    def test_active_refresh_tracking_and_wait(self):
        self.assertFalse(honours_db.is_individual_refresh_active(999))
        self.assertTrue(honours_db.wait_for_individual_refresh(999, timeout=0.01))

        # Test tracking when scheduled
        with patch.object(honours_db.threading, 'Thread') as mock_thread:
            started = honours_db.schedule_individual_refresh(888, 'Player', None)
            self.assertTrue(started)
            self.assertTrue(honours_db.is_individual_refresh_active(888))
            # Clean up manually
            with honours_db._active_refreshes_lock:
                ev = honours_db._active_refreshes.pop(888, None)
                if ev:
                    ev.set()
        self.assertFalse(honours_db.is_individual_refresh_active(888))


@unittest.skipUnless(os.getenv('MONGO_TEST_URI'), 'MONGO_TEST_URI not set')
class IndividualRefreshMongoTests(unittest.TestCase):
    def setUp(self):
        self.client = MongoClient(os.environ['MONGO_TEST_URI'], tz_aware=True, serverSelectionTimeoutMS=3000)
        self.database_name = 'football_refresh_test_' + uuid.uuid4().hex
        self.database = self.client[self.database_name]
        self.players = self.database['player_honours']
        self.players.create_index('fotmob_id', unique=True)
        self.refresh = self.database['individual_award_refresh']
        patcher = patch.multiple(honours_db, player_honours=self.players, individual_refresh=self.refresh)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.client.close)
        self.addCleanup(self.client.drop_database, self.database_name)
        self.now = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
        self.players.insert_one({
            'fotmob_id': 10, 'name': 'Player', 'source': 'wikipedia:Player',
            'verified': False, 'updated_at': self.now - timedelta(days=100),
            'honours': {
                'individual': [{'trophy': 'Award', 'years': ['2024'], 'count': 1}],
                'club_world': [{'trophy': 'Manual trophy', 'years': ['2023'], 'count': 1}],
            },
        })

    def test_refresh_once_per_season_and_preserves_existing_honours(self):
        awards = [{'trophy': 'Award', 'years': ['2024', '2025'], 'count': 2}]
        with patch.object(honours_db, 'datetime') as clock, patch.object(
            honours_db, 'get_honours_wikitext', return_value='honours'
        ) as fetch, patch.object(honours_db, 'parse_honours', return_value={}), patch.object(
            honours_db, 'classify_honours', return_value={'Individual Awards': awards}
        ):
            clock.now.return_value = self.now
            honours_db._refresh_individual_awards(10, 'Player')
            honours_db._refresh_individual_awards(10, 'Player')
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(self.refresh.find_one({'_id': 10})['completed_season'], 2025)
            clock.now.return_value = datetime(2026, 8, 1, tzinfo=timezone.utc)
            awards[0]['years'].append('2026')
            awards[0]['count'] = 3
            honours_db._refresh_individual_awards(10, 'Player')
            self.assertEqual(fetch.call_count, 2)

        doc = self.players.find_one({'fotmob_id': 10})
        self.assertEqual(doc['honours']['individual'][0]['years'], ['2024', '2025', '2026'])
        self.assertEqual(doc['honours']['club_world'][0]['trophy'], 'Manual trophy')
        self.assertEqual(self.refresh.find_one({'_id': 10})['completed_season'], 2026)

    def test_verification_during_fetch_prevents_write(self):
        def verify_during_fetch(page):
            self.players.update_one({'fotmob_id': 10}, {'$set': {'verified': True}})
            return 'honours'

        with patch.object(honours_db, 'get_honours_wikitext', side_effect=verify_during_fetch), patch.object(
            honours_db, 'parse_honours', return_value={}
        ), patch.object(
            honours_db, 'classify_honours',
            return_value={'Individual Awards': [{'trophy': 'New', 'years': ['2026'], 'count': 1}]},
        ):
            honours_db._refresh_individual_awards(10, 'Player')
        doc = self.players.find_one({'fotmob_id': 10})
        self.assertTrue(doc['verified'])
        self.assertEqual(len(doc['honours']['individual']), 1)
        self.assertNotIn('completed_season', self.refresh.find_one({'_id': 10}))

    def test_expanded_award_rules_refresh_an_already_checked_season_once(self):
        self.refresh.insert_one({'_id': 10, 'completed_season': 2026})
        text = """'''Individual'''
* [[Premier League Playmaker of the Season]]: 2024
* [[Manchester City Player of the Season]]: 2023, 2024
"""
        with patch.object(honours_db, 'datetime') as clock, patch.object(
            honours_db, 'get_honours_wikitext', return_value=text
        ) as fetch:
            clock.now.return_value = datetime(2026, 11, 17, tzinfo=timezone.utc)
            honours_db._refresh_individual_awards(10, 'Player')
            honours_db._refresh_individual_awards(10, 'Player')
            self.assertEqual(fetch.call_count, 1)

        doc = self.players.find_one({'fotmob_id': 10})
        self.assertEqual([award['trophy'] for award in doc['honours']['individual']], [
            'Award', 'Premier League Playmaker of the Season', 'Manchester City Player of the Season',
        ])
        self.assertEqual(doc['honours']['club_world'][0]['trophy'], 'Manual trophy')
        self.assertEqual(doc['honours']['individual'][2]['count'], 2)

    def test_edit_between_read_and_save_is_not_overwritten(self):
        collection = MagicMock(wraps=self.players)

        def edit_before_save(query, update):
            self.players.update_one(
                {'fotmob_id': 10},
                {'$set': {'honours.club_world.0.trophy': 'Edited trophy', 'updated_at': self.now}},
            )
            return self.players.update_one(query, update)

        collection.update_one.side_effect = edit_before_save
        with patch.object(honours_db, 'player_honours', collection), patch.object(
            honours_db, 'get_honours_wikitext', return_value='honours'
        ), patch.object(honours_db, 'parse_honours', return_value={}), patch.object(
            honours_db, 'classify_honours',
            return_value={'Individual Awards': [{'trophy': 'New', 'years': ['2026'], 'count': 1}]},
        ):
            honours_db._refresh_individual_awards(10, 'Player')
        doc = self.players.find_one({'fotmob_id': 10})
        self.assertEqual(doc['honours']['club_world'][0]['trophy'], 'Edited trophy')
        self.assertEqual(len(doc['honours']['individual']), 1)
        self.assertNotIn('completed_season', self.refresh.find_one({'_id': 10}))

    def test_new_player_is_created_when_awards_are_found(self):
        self.players.delete_one({'fotmob_id': 10})
        with patch.object(honours_db, 'search_wiki_pages', return_value=['Player']), patch.object(
            honours_db, 'get_wiki_birth_date', return_value='1993-07-28'
        ), patch.object(
            honours_db, 'get_honours_wikitext', return_value='honours'
        ), patch.object(honours_db, 'parse_honours', return_value={}), patch.object(
            honours_db, 'classify_honours',
            return_value={'Individual Awards': [{'trophy': 'New', 'years': ['2026'], 'count': 1}]},
        ):
            honours_db._refresh_individual_awards(10, 'Player', '1993-07-28')
        doc = self.players.find_one({'fotmob_id': 10})
        self.assertEqual(doc['source'], 'wikipedia:Player')
        self.assertFalse(doc['verified'])
        self.assertEqual(doc['honours']['individual'][0]['trophy'], 'New')

    def test_new_player_with_mismatched_birth_date_is_not_saved(self):
        self.players.delete_one({'fotmob_id': 10})
        with patch.object(honours_db, 'search_wiki_pages', return_value=['Wrong_Player']), patch.object(
            honours_db, 'get_wiki_birth_date', return_value='1992-01-01'
        ), patch.object(honours_db, 'get_honours_wikitext') as fetch:
            honours_db._refresh_individual_awards(10, 'Player', '1993-07-28')
        fetch.assert_not_called()
        self.assertIsNone(self.players.find_one({'fotmob_id': 10}))
        self.assertNotIn('completed_season', self.refresh.find_one({'_id': 10}))

    def test_next_candidate_is_used_when_first_birth_date_mismatches(self):
        self.players.delete_one({'fotmob_id': 10})
        with patch.object(
            honours_db, 'search_wiki_pages', return_value=['Wrong_Player', 'Right_Player']
        ), patch.object(
            honours_db, 'get_wiki_birth_date', side_effect=['1992-01-01', '1993-07-28']
        ), patch.object(
            honours_db, 'get_honours_wikitext', return_value='honours'
        ), patch.object(honours_db, 'parse_honours', return_value={}), patch.object(
            honours_db, 'classify_honours',
            return_value={'Individual Awards': [{'trophy': 'New', 'years': ['2026'], 'count': 1}]},
        ):
            honours_db._refresh_individual_awards(10, 'Player', '1993-07-28')
        doc = self.players.find_one({'fotmob_id': 10})
        self.assertEqual(doc['source'], 'wikipedia:Right_Player')
        self.assertEqual(doc['honours']['individual'][0]['trophy'], 'New')

    def test_two_workers_claim_only_one_refresh(self):
        started = threading.Event()
        release = threading.Event()

        def fetch(page):
            started.set()
            if not release.wait(5):
                raise TimeoutError('test did not release fetch')
            return 'honours'

        with patch.object(honours_db, 'get_honours_wikitext', side_effect=fetch) as wiki, patch.object(
            honours_db, 'parse_honours', return_value={}
        ), patch.object(honours_db, 'classify_honours', return_value={'Individual Awards': []}):
            with ThreadPoolExecutor(max_workers=2) as workers:
                first = workers.submit(honours_db._refresh_individual_awards, 10, 'Player')
                try:
                    self.assertTrue(started.wait(5))
                    second = workers.submit(honours_db._refresh_individual_awards, 10, 'Player')
                    second.result(timeout=5)
                finally:
                    release.set()
                first.result(timeout=5)
            self.assertEqual(wiki.call_count, 1)

    def test_missing_wikipedia_is_retried_on_later_visit(self):
        with patch.object(honours_db, 'datetime') as clock, patch.object(
            honours_db, 'get_honours_wikitext', side_effect=[None, 'honours']
        ) as fetch, patch.object(honours_db, 'parse_honours', return_value={}), patch.object(
            honours_db, 'classify_honours', return_value={'Individual Awards': []}
        ):
            clock.now.return_value = self.now
            honours_db._refresh_individual_awards(10, 'Player')
            honours_db._refresh_individual_awards(10, 'Player')
            self.assertEqual(fetch.call_count, 1)
            self.assertNotIn('completed_season', self.refresh.find_one({'_id': 10}))
            clock.now.return_value = self.now + timedelta(days=1, seconds=1)
            honours_db._refresh_individual_awards(10, 'Player')
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(self.refresh.find_one({'_id': 10})['completed_season'], 2026)
