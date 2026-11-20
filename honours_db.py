"""
Honours DB Module
Quản lý danh hiệu cầu thủ với MongoDB.
- Seed data từ Wikipedia
- FotMob player_id làm key chính
- verified flag để bảo vệ data đã review
"""

import logging
import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from requests.exceptions import RequestException

from mongo import my_db
from wiki_honours import (
    get_honours_wikitext, get_wiki_birth_date, parse_honours, classify_honours, search_wiki_page,
    INDIVIDUAL_AWARDS_VERSION, is_disqualified_individual_award, sort_individual_awards,
    normalize_trophy_name,
)

# Collections
trophy_defs = my_db['trophy_definitions']
player_honours = my_db['player_honours']
individual_refresh = my_db['individual_award_refresh']
logger = logging.getLogger(__name__)
_refresh_slots = threading.BoundedSemaphore(2)
_active_refreshes = {}
_active_refreshes_lock = threading.Lock()

# ============================================================
# TROPHY DEFINITIONS
# ============================================================

CATEGORY_MAP = {
    'Club - Domestic League': 'club_domestic_league',
    'Club - Domestic Cup': 'club_domestic_cup',
    'Club - Continental': 'club_continental',
    'Club - World': 'club_world',
    'International - Senior': 'intl_senior',
    'International - Youth': 'intl_youth',
    'Individual Awards': 'individual',
    'Orders & Decorations': 'orders',
}


def ensure_indexes():
    """Tạo indexes cho collections."""
    trophy_defs.create_index('name', unique=True)
    player_honours.create_index('fotmob_id', unique=True)
    player_honours.create_index('name')


def upsert_trophy_def(name, category, **kwargs):
    """Thêm/cập nhật định nghĩa danh hiệu."""
    trophy_defs.update_one(
        {'name': name},
        {'$set': {
            'name': name,
            'category': category,
            **kwargs,
            'updated_at': datetime.now(timezone.utc),
        }, '$setOnInsert': {'created_at': datetime.now(timezone.utc)}},
        upsert=True,
    )


# ============================================================
# PLAYER HONOURS CRUD
# ============================================================

def get_player_honours(fotmob_id):
    """Lấy danh hiệu player từ DB."""
    return player_honours.find_one({'fotmob_id': fotmob_id}, {'_id': 0})


def save_player_honours(fotmob_id, name, honours_data, source='manual', verified=False):
    """
    Lưu danh hiệu player.
    honours_data format:
    {
        "club_domestic_league": [{"trophy": "La Liga", "club": "Barcelona", "years": ["2008-09"], "count": 1}],
        "individual": [{"trophy": "Ballon d'Or", "years": ["2009"], "count": 1}],
        ...
    }
    """
    now = datetime.now(timezone.utc)
    player_honours.update_one(
        {'fotmob_id': fotmob_id},
        {'$set': {
            'fotmob_id': fotmob_id,
            'name': name,
            'honours': honours_data,
            'source': source,
            'verified': verified,
            'updated_at': now,
        }, '$setOnInsert': {'created_at': now}},
        upsert=True,
    )


def set_verified(fotmob_id, verified=True):
    """Đánh dấu verified cho player."""
    player_honours.update_one(
        {'fotmob_id': fotmob_id},
        {'$set': {'verified': verified, 'updated_at': datetime.now(timezone.utc)}},
    )


# ============================================================
# WIKIPEDIA SEED / AUTO-UPDATE
# ============================================================

def _classified_to_db_format(classified):
    """Chuyển output classify_honours() sang format DB."""
    result = {}
    for display_cat, trophies in classified.items():
        db_cat = CATEGORY_MAP.get(display_cat)
        if not db_cat:
            continue
        entries = []
        for t in trophies:
            entry = {
                'trophy': t['trophy'],
                'years': t.get('years', []),
                'count': t.get('count', 0),
            }
            if t.get('club'):
                entry['club'] = t['club']
            if t.get('team'):
                entry['team'] = t['team']
            entries.append(entry)
            # Upsert trophy definition
            upsert_trophy_def(t['trophy'], db_cat)
        if entries:
            result[db_cat] = entries
    return result


def seed_from_wikipedia(fotmob_id, player_name, wiki_page, force=False):
    """
    Seed danh hiệu từ Wikipedia vào DB.
    - Nếu player đã verified và force=False → skip
    - Returns: dict honours hoặc None nếu skip/fail
    """
    existing = get_player_honours(fotmob_id)
    if existing and existing.get('verified') and not force:
        return None  # Đã verified, không overwrite

    wikitext = get_honours_wikitext(wiki_page)
    if not wikitext:
        return None

    raw = parse_honours(wikitext)
    classified = classify_honours(raw)
    db_data = _classified_to_db_format(classified)

    save_player_honours(
        fotmob_id=fotmob_id,
        name=player_name,
        honours_data=db_data,
        source=f'wikipedia:{wiki_page}',
        verified=False,
    )
    return db_data


def auto_seed(fotmob_id, player_name):
    """Auto-seed từ Wikipedia nếu chưa có trong DB. Trả về doc hoặc None."""
    doc = get_player_honours(fotmob_id)
    if doc:
        return doc
    wiki_page = search_wiki_page(player_name)
    if not wiki_page:
        # Lưu empty doc để không gọi lại Wikipedia mỗi lần
        save_player_honours(fotmob_id, player_name, {}, source='wikipedia:not_found')
        return get_player_honours(fotmob_id)
    result = seed_from_wikipedia(fotmob_id, player_name, wiki_page)
    if result is None:
        save_player_honours(fotmob_id, player_name, {}, source='wikipedia:no_honours')
        return get_player_honours(fotmob_id)
    return get_player_honours(fotmob_id)


def _merge_individual_awards(existing, incoming):
    clean_existing = []
    for item in existing:
        if is_disqualified_individual_award(item.get('trophy', '')):
            continue
        copied = deepcopy(item)
        copied['trophy'] = normalize_trophy_name(copied['trophy'])
        clean_existing.append(copied)
    merged = clean_existing
    by_name = {' '.join(item['trophy'].casefold().split()): item for item in merged}
    for award in incoming:
        if is_disqualified_individual_award(award.get('trophy', '')):
            continue
        norm_trophy = normalize_trophy_name(award['trophy'])
        key = ' '.join(norm_trophy.casefold().split())
        if key not in by_name:
            item = {
                'trophy': norm_trophy,
                'years': list(award.get('years', [])),
                'count': award.get('count', 0),
            }
            merged.append(item)
            by_name[key] = item
            continue
        item = by_name[key]
        years = list(item.get('years', []))
        for year in award.get('years', []):
            if year not in years:
                years.append(year)
        if years != item.get('years', []):
            item['years'] = years
            item['count'] = max(item.get('count', 0), award.get('count', 0), len(years))
    return merged


def _refresh_individual_awards(fotmob_id, player_name, birth_date=None):
    now = datetime.now(timezone.utc)
    season = now.year if now.month >= 8 else now.year - 1
    token = uuid4().hex
    try:
        try:
            claim = individual_refresh.find_one_and_update(
                {
                    '_id': fotmob_id,
                    '$and': [
                        {'$or': [
                            {'completed_season': {'$ne': season}},
                            {'awards_version': {'$ne': INDIVIDUAL_AWARDS_VERSION}},
                        ]},
                        {'$or': [
                            {'next_attempt_at': {'$exists': False}},
                            {'next_attempt_at': {'$lte': now}},
                        ]},
                    ],
                },
                {'$set': {'lease_token': token, 'next_attempt_at': now + timedelta(minutes=5)}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            return
        if not claim:
            return

        doc = get_player_honours(fotmob_id)
        if doc and doc.get('verified'):
            return
        source = (doc.get('source') or '') if doc else ''
        wiki_page = source.removeprefix('wikipedia:') if source.startswith('wikipedia:') else ''
        if wiki_page in ('not_found', 'no_honours'):
            wiki_page = ''
        if not wiki_page:
            wiki_page = search_wiki_page(player_name) if birth_date else None
            if wiki_page and get_wiki_birth_date(wiki_page) != birth_date:
                logger.warning("Wikipedia birth date does not match player %s", fotmob_id)
                wiki_page = None
        wikitext = get_honours_wikitext(wiki_page) if wiki_page else None
        if not wikitext:
            logger.warning("Wikipedia honours unavailable for player %s", fotmob_id)
            individual_refresh.update_one(
                {'_id': fotmob_id, 'lease_token': token},
                {'$set': {'next_attempt_at': datetime.now(timezone.utc) + timedelta(days=1)},
                 '$unset': {'lease_token': ''}},
            )
            return

        awards = classify_honours(parse_honours(wikitext)).get('Individual Awards', [])
        doc = get_player_honours(fotmob_id)
        if doc and doc.get('verified'):
            return
        honours = deepcopy(doc.get('honours', {})) if doc else {}
        existing = honours.get('individual', [])
        merged = _merge_individual_awards(existing, awards)
        if merged != existing:
            honours['individual'] = merged
            updated_at = datetime.now(timezone.utc)
            if doc:
                result = player_honours.update_one(
                    {
                        'fotmob_id': fotmob_id,
                        'verified': {'$ne': True},
                        'updated_at': doc.get('updated_at'),
                        'honours': doc.get('honours'),
                    },
                    {'$set': {'honours': honours, 'updated_at': updated_at}},
                )
                if not result.matched_count:
                    logger.info("Player %s changed during awards refresh; retrying later", fotmob_id)
                    return
            else:
                player_honours.insert_one({
                    'fotmob_id': fotmob_id, 'name': player_name, 'honours': honours,
                    'source': f'wikipedia:{wiki_page}', 'verified': False,
                    'created_at': updated_at, 'updated_at': updated_at,
                })
        individual_refresh.update_one(
            {'_id': fotmob_id, 'lease_token': token},
            {'$set': {'completed_season': season, 'awards_version': INDIVIDUAL_AWARDS_VERSION,
                      'last_success_at': datetime.now(timezone.utc)},
             '$unset': {'lease_token': '', 'next_attempt_at': ''}},
        )
    except (RequestException, ValueError, KeyError, TypeError, PyMongoError):
        logger.exception("Could not refresh individual awards for player %s", fotmob_id)


def is_individual_refresh_active(fotmob_id):
    with _active_refreshes_lock:
        return fotmob_id in _active_refreshes


def wait_for_individual_refresh(fotmob_id, timeout=2.0):
    with _active_refreshes_lock:
        ev = _active_refreshes.get(fotmob_id)
    if ev:
        return ev.wait(timeout=timeout)
    return True


def schedule_individual_refresh(fotmob_id, player_name, doc, birth_date=None):
    if doc and doc.get('verified'):
        return False
    with _active_refreshes_lock:
        if fotmob_id in _active_refreshes:
            return True
    if not _refresh_slots.acquire(blocking=False):
        logger.warning("Awards refresh busy for player %s; retrying on a later visit", fotmob_id)
        return False

    event = threading.Event()
    with _active_refreshes_lock:
        _active_refreshes[fotmob_id] = event

    def run():
        try:
            _refresh_individual_awards(fotmob_id, player_name, birth_date)
        finally:
            _refresh_slots.release()
            with _active_refreshes_lock:
                ev = _active_refreshes.pop(fotmob_id, None)
                if ev:
                    ev.set()

    try:
        threading.Thread(target=run, daemon=True).start()
        return True
    except RuntimeError:
        _refresh_slots.release()
        with _active_refreshes_lock:
            ev = _active_refreshes.pop(fotmob_id, None)
            if ev:
                ev.set()
        logger.exception("Could not start individual awards refresh for player %s", fotmob_id)
        return False


def get_honours_summary(fotmob_id):
    """Lấy tóm tắt danh hiệu cho hiển thị nhanh."""
    doc = get_player_honours(fotmob_id)
    if not doc:
        return None

    honours = doc.get('honours', {})
    summary = {}
    total = 0
    for cat, entries in honours.items():
        cat_total = sum(e.get('count', 0) for e in entries)
        if cat_total:
            summary[cat] = cat_total
            total += cat_total
    summary['total'] = total
    return summary


# ============================================================
# CLI
# ============================================================

if __name__ == '__main__':
    import sys

    ensure_indexes()

    if len(sys.argv) < 4:
        print("Usage: python honours_db.py <fotmob_id> <player_name> <wiki_page> [--force]")
        print("Example: python honours_db.py 194165 'Lionel Messi' Lionel_Messi")
        sys.exit(1)

    fid = int(sys.argv[1])
    pname = sys.argv[2]
    wiki = sys.argv[3]
    force = '--force' in sys.argv

    print(f"Seeding {pname} (FotMob #{fid}) from Wikipedia: {wiki}")
    result = seed_from_wikipedia(fid, pname, wiki, force=force)

    if result is None:
        print("Skipped (already verified or Wikipedia fetch failed)")
    else:
        total = sum(e['count'] for entries in result.values() for e in entries)
        print(f"✅ Saved {total} honours in {len(result)} categories")
        for cat, entries in result.items():
            cat_total = sum(e['count'] for e in entries)
            print(f"  {cat}: {cat_total}")
