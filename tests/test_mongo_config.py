import os
import unittest
from unittest.mock import patch
from urllib.parse import quote_plus

from mongo import _mongo_uri


class MongoConfigTests(unittest.TestCase):
    def test_existing_atlas_credentials_remain_usable(self):
        with patch.dict(os.environ, {
            "username": "legacy user",
            "password": "special@password",
            "MONGO_USER": "local-user",
            "MONGO_PASS": "local-password",
        }, clear=True):
            with self.assertLogs("mongo", level="WARNING"):
                uri = _mongo_uri()
        self.assertIn(f"{quote_plus('legacy user')}:{quote_plus('special@password')}@", uri)
        self.assertTrue(uri.startswith("mongodb+srv://"))
        self.assertIn("cluster0.wbx8bpm.mongodb.net", uri)

    def test_explicit_mongo_host_overrides_legacy_credentials(self):
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "username": "legacy-user",
            "password": "legacy-password",
            "MONGO_HOST": "mongo",
            "MONGO_USER": "local-user",
            "MONGO_PASS": "local-password",
        }, clear=True):
            uri = _mongo_uri()
        self.assertEqual(uri, "mongodb://local-user:local-password@mongo:27017/?authSource=admin")

    def test_explicit_mongo_uri_takes_priority(self):
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "username": "legacy-user",
            "password": "legacy-password",
            "MONGO_HOST": "mongo",
            "MONGO_URI": "mongodb://example.test:27017/",
        }, clear=True):
            uri = _mongo_uri()
        self.assertEqual(uri, "mongodb://example.test:27017/")

    def test_production_uses_existing_atlas_credentials(self):
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "username": "legacy user",
            "password": "special@password",
            "MONGO_USER": "local-user",
            "MONGO_PASS": "local-password",
        }, clear=True):
            with self.assertLogs("mongo", level="WARNING"):
                uri = _mongo_uri()
        self.assertEqual(
            uri,
            f"mongodb+srv://{quote_plus('legacy user')}:{quote_plus('special@password')}"
            "@cluster0.wbx8bpm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",
        )


if __name__ == "__main__":
    unittest.main()
