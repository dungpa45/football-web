"""
Cache layer using local MongoDB.
Mỗi entry: {_id: cache_key, data: ..., expires_at: datetime}
"""
import os
import pymongo
from datetime import datetime, timedelta, timezone

_client = None
_db = None

# TTL defaults (seconds)
TTL_STANDINGS = 2 * 3600       # 2h
TTL_TOP_STATS = 2 * 3600      # 2h
TTL_PLAYER = 24 * 3600        # 24h
TTL_TEAM = 24 * 3600          # 24h
TTL_LEAGUE_PAGE = 2 * 3600    # 2h


def _get_db():
    global _client, _db
    if _db is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        _client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
        _db = _client["fotmob_cache"]
        _db["cache"].create_index("expires_at", expireAfterSeconds=0)
    return _db


def get_cached(key):
    try:
        db = _get_db()
        doc = db["cache"].find_one({"_id": key})
        if doc and doc.get("expires_at", datetime.min.replace(tzinfo=timezone.utc)) > datetime.now(timezone.utc):
            return doc["data"]
    except Exception:
        pass
    return None


def set_cached(key, data, ttl=3600):
    try:
        db = _get_db()
        db["cache"].replace_one(
            {"_id": key},
            {
                "_id": key,
                "data": data,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl),
            },
            upsert=True,
        )
    except Exception:
        pass
