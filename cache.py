"""
Cache layer - MongoDB with in-memory fallback.
Mỗi entry: {_id: cache_key, data: ..., expires_at: datetime}
"""
import os
import time as _time

try:
    import pymongo
    _HAS_MONGO = True
except ImportError:
    _HAS_MONGO = False

from datetime import datetime, timedelta, timezone

_client = None
_db = None
_mem_cache = {}  # fallback: {key: (data, expires_ts)}

# TTL defaults (seconds)
TTL_STANDINGS = 2 * 3600       # 2h
TTL_TOP_STATS = 2 * 3600      # 2h
TTL_PLAYER = 24 * 3600        # 24h
TTL_TEAM = 24 * 3600          # 24h
TTL_LEAGUE_PAGE = 2 * 3600    # 2h


_mongo_available = None  # None = chưa check, True/False


def _get_db():
    global _client, _db, _mongo_available
    if _mongo_available is False:
        return None
    if _db is not None:
        return _db
    if not _HAS_MONGO:
        _mongo_available = False
        return None
    try:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        _client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=1000)
        _client.admin.command('ping')
        _db = _client["fotmob_cache"]
        _db["cache"].create_index("expires_at", expireAfterSeconds=0)
        _mongo_available = True
        return _db
    except Exception:
        _mongo_available = False
        return None


def get_cached(key):
    # Try MongoDB
    try:
        db = _get_db()
        if db:
            doc = db["cache"].find_one({"_id": key})
            if doc and doc.get("expires_at", datetime.min.replace(tzinfo=timezone.utc)) > datetime.now(timezone.utc):
                return doc["data"]
    except Exception:
        pass
    # Fallback: in-memory
    entry = _mem_cache.get(key)
    if entry:
        data, expires_ts = entry
        if expires_ts > _time.time():
            return data
        else:
            del _mem_cache[key]
    return None


def set_cached(key, data, ttl=3600):
    # Try MongoDB
    try:
        db = _get_db()
        if db:
            db["cache"].replace_one(
                {"_id": key},
                {
                    "_id": key,
                    "data": data,
                    "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl),
                },
                upsert=True,
            )
            return
    except Exception:
        pass
    # Fallback: in-memory
    _mem_cache[key] = (data, _time.time() + ttl)
