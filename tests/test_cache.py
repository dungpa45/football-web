import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pymongo import MongoClient
from pymongo.errors import AutoReconnect

import cache


class DatabaseWithoutTruthValue:
    def __init__(self):
        self.collection = MagicMock()

    def __bool__(self):
        raise AssertionError("Database must not be evaluated as a boolean")

    def __getitem__(self, name):
        if name != "cache":
            raise KeyError(name)
        return self.collection


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.memory = patch.object(cache, "_mem_cache", {})
        self.memory.start()
        self.addCleanup(self.memory.stop)

    def test_mongodb_cache_write_populates_memory(self):
        database = DatabaseWithoutTruthValue()
        with patch.object(cache, "_get_db", return_value=database):
            cache.set_cached("stats", {"goals": 0})
            result = cache.get_cached("stats")
        database.collection.replace_one.assert_called_once()
        database.collection.find_one.assert_not_called()
        self.assertEqual(result, {"goals": 0})
        self.assertIn("stats", cache._mem_cache)

    def test_mongodb_cache_hit_is_cached_in_memory(self):
        database = DatabaseWithoutTruthValue()
        database.collection.find_one.return_value = {
            "data": {"goals": 3},
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        with patch.object(cache, "_get_db", return_value=database):
            self.assertEqual(cache.get_cached("stats"), {"goals": 3})
            self.assertEqual(cache.get_cached("stats"), {"goals": 3})
        database.collection.find_one.assert_called_once_with({"_id": "stats"})
        self.assertIn("stats", cache._mem_cache)

    def test_expired_memory_entry_is_reloaded_from_mongodb(self):
        database = DatabaseWithoutTruthValue()
        database.collection.find_one.return_value = {
            "data": {"goals": 4},
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        cache._mem_cache["stats"] = ({"goals": 1}, cache.time.time() - 1)
        with patch.object(cache, "_get_db", return_value=database):
            self.assertEqual(cache.get_cached("stats"), {"goals": 4})
        database.collection.find_one.assert_called_once_with({"_id": "stats"})
        self.assertEqual(cache._mem_cache["stats"][0], {"goals": 4})

    def test_reconnect_after_failed_initial_connection(self):
        database = DatabaseWithoutTruthValue()
        client = MagicMock()
        client.admin.command.side_effect = [AutoReconnect("offline"), {"ok": 1}]
        with patch.multiple(cache, my_db=database, myclient=client, _db=None, _retry_after=0.0):
            with patch.object(cache.time, "monotonic", return_value=100):
                self.assertIsNone(cache._get_db())
                self.assertIsNone(cache._get_db())
                client.admin.command.assert_called_once()
            with patch.object(cache.time, "monotonic", return_value=131):
                self.assertIs(cache._get_db(), database)
        self.assertEqual(client.admin.command.call_count, 2)
        database.collection.create_index.assert_called_once()

    def test_failed_write_falls_back_and_success_refreshes_memory(self):
        database = DatabaseWithoutTruthValue()
        database.collection.replace_one.side_effect = [AutoReconnect("offline"), None]
        with patch.object(cache, "_get_db", return_value=database), patch.object(cache, "_mark_unavailable"):
            cache.set_cached("stats", {"value": 1})
            self.assertEqual(cache.get_cached("stats"), {"value": 1})
            cache.set_cached("stats", {"value": 2})
        self.assertEqual(cache.get_cached("stats"), {"value": 2})


@unittest.skipUnless(os.getenv("MONGO_TEST_URI"), "MONGO_TEST_URI not set")
class MongoCacheIntegrationTests(unittest.TestCase):
    def test_cache_round_trip_and_expiration(self):
        client = MongoClient(os.environ["MONGO_TEST_URI"], tz_aware=True, serverSelectionTimeoutMS=3000)
        database_name = "football_web_test_" + uuid.uuid4().hex
        database = client[database_name]
        try:
            with patch.multiple(cache, myclient=client, my_db=database, _db=None, _retry_after=0.0, _mem_cache={}):
                cache.set_cached("integration", {"goals": 3}, ttl=60)
                self.assertEqual(cache.get_cached("integration"), {"goals": 3})
                self.assertEqual(database["cache"].count_documents({"_id": "integration"}), 1)
                cache.set_cached("expired", {"goals": 4}, ttl=-1)
                self.assertIsNone(cache.get_cached("expired"))
        finally:
            client.drop_database(database_name)
            client.close()
