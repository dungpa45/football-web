"""
Honours DB Module
Quản lý danh hiệu cầu thủ với MongoDB.
- Seed data từ Wikipedia
- FotMob player_id làm key chính
- verified flag để bảo vệ data đã review
"""

from datetime import datetime, timezone
from mongo import my_db
from wiki_honours import get_honours_wikitext, parse_honours, classify_honours, search_wiki_page

# Collections
trophy_defs = my_db['trophy_definitions']
player_honours = my_db['player_honours']

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
