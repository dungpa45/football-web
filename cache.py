"""MongoDB cache with an in-memory fallback."""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from pymongo.errors import PyMongoError

from mongo import my_db, myclient

logger = logging.getLogger(__name__)

TTL_CURRENT_SEASON = 15 * 60
TTL_PAST_SEASON = 24 * 3600
TTL_PLAYER = 24 * 3600
TTL_TEAM = 24 * 3600
MONGO_RETRY_SECONDS = 30

_db = None
_retry_after = 0.0
_db_lock = threading.Lock()
_mem_cache = {}
_mem_lock = threading.Lock()


def _mark_unavailable():
    global _db, _retry_after
    with _db_lock:
        _db = None
        _retry_after = time.monotonic() + MONGO_RETRY_SECONDS


def _get_db():
    global _db, _retry_after
    with _db_lock:
        if _db is not None:
            return _db
        if time.monotonic() < _retry_after:
            return None
        try:
            myclient.admin.command("ping")
            my_db["cache"].create_index("expires_at", expireAfterSeconds=0)
        except PyMongoError as exc:
            logger.warning("MongoDB cache unavailable; using in-memory cache: %s", exc)
            _retry_after = time.monotonic() + MONGO_RETRY_SECONDS
            return None
        _db = my_db
        _retry_after = 0.0
        return _db


def _cache_in_memory(key, data, expires_ts):
    with _mem_lock:
        _mem_cache[key] = (data, expires_ts)


def get_cached(key):
    with _mem_lock:
        entry = _mem_cache.get(key)
        if entry:
            data, expires_ts = entry
            if expires_ts > time.time():
                return data
            _mem_cache.pop(key, None)

    db = _get_db()
    if db is not None:
        try:
            doc = db["cache"].find_one({"_id": key})
            if doc:
                expires_at = doc.get("expires_at", datetime.min.replace(tzinfo=timezone.utc))
                now = datetime.now(timezone.utc)
                if expires_at > now:
                    data = doc["data"]
                    expires_ts = time.time() + (expires_at - now).total_seconds()
                    _cache_in_memory(key, data, expires_ts)
                    return data
        except PyMongoError as exc:
            logger.warning("Could not read MongoDB cache entry %s: %s", key, exc)
            _mark_unavailable()
    return None


def set_cached(key, data, ttl=3600):
    db = _get_db()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    if db is not None:
        try:
            db["cache"].replace_one(
                {"_id": key},
                {
                    "_id": key,
                    "data": data,
                    "expires_at": expires_at,
                },
                upsert=True,
            )
            remaining_ttl = max((expires_at - datetime.now(timezone.utc)).total_seconds(), 0)
            _cache_in_memory(key, data, time.time() + remaining_ttl)
            return
        except PyMongoError as exc:
            logger.warning("Could not write MongoDB cache entry %s: %s", key, exc)
            _mark_unavailable()
    _cache_in_memory(key, data, time.time() + ttl)
