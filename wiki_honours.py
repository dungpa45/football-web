import requests
import re
import sys
import json

HEADERS = {'User-Agent': 'FootballWeb/1.0 (dungpham; test)'}
WIKI_API = 'https://en.wikipedia.org/w/api.php'

# Các đội tuyển quốc gia phổ biến
NATIONAL_TEAMS = {
    'argentina', 'brazil', 'france', 'germany', 'spain', 'portugal',
    'england', 'italy', 'netherlands', 'belgium', 'croatia', 'uruguay',
    'colombia', 'chile', 'mexico', 'japan', 'south korea', 'australia',
    'united states', 'canada', 'morocco', 'senegal', 'nigeria', 'cameroon',
    'egypt', 'algeria', 'tunisia', 'ghana', 'ivory coast', 'wales',
    'scotland', 'ireland', 'poland', 'czech republic', 'sweden', 'denmark',
    'norway', 'switzerland', 'austria', 'turkey', 'greece', 'romania',
    'hungary', 'serbia', 'ukraine', 'russia', 'paraguay', 'peru',
    'ecuador', 'venezuela', 'bolivia', 'costa rica', 'panama', 'honduras',
    'jamaica', 'trinidad and tobago', 'china', 'india', 'iran', 'iraq',
    'saudi arabia', 'qatar', 'uae', 'thailand', 'vietnam', 'indonesia',
}


def search_wiki_page(player_name: str) -> str | None:
    """Tìm Wikipedia page từ tên cầu thủ."""
    try:
        # 1) Thử direct page match trước
        slug = player_name.replace(' ', '_')
        params = {'action': 'query', 'titles': slug, 'format': 'json'}
        r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=5)
        pages = r.json().get('query', {}).get('pages', {})
        if '-1' not in pages:
            if get_honours_wikitext(slug):
                return slug

        # 2) Fallback: search và chọn page đầu tiên có honours
        params = {'action': 'query', 'list': 'search', 'srsearch': f'{player_name} footballer',
                  'format': 'json', 'srlimit': 5}
        r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=5)
        for result in r.json().get('query', {}).get('search', []):
            slug = result['title'].replace(' ', '_')
            if get_honours_wikitext(slug):
                return slug
        return None
    except Exception:
        return None


def get_honours_wikitext(player_page: str) -> str | None:
    params = {'action': 'parse', 'page': player_page, 'prop': 'sections', 'format': 'json'}
    r = requests.get(WIKI_API, params=params, headers=HEADERS)
    sections = r.json()['parse']['sections']

    honours_idx = None
    for s in sections:
        if s['line'].lower() in ('honours', 'career honours', 'honors'):
            honours_idx = s['index']
            break

    if not honours_idx:
        return None

    params = {'action': 'parse', 'page': player_page, 'prop': 'wikitext', 'section': honours_idx, 'format': 'json'}
    return requests.get(WIKI_API, params=params, headers=HEADERS).json()['parse']['wikitext']['*']


def clean_wikitext(wikitext: str) -> str:
    text = re.sub(r'<ref\s+name="[^"]*"\s*/>', '', wikitext)
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
    text = re.sub(r'\{\{refn\|[^}]*\}\}', '', text)
    text = re.sub(r'\{\{For\|[^}]*\}\}', '', text)
    text = re.sub(r"'''", '', text)
    text = re.sub(r'\{\{columns-list\|[^}]*\}\}', '', text)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    return text


def parse_honours(wikitext: str) -> dict:
    text = clean_wikitext(wikitext)
    result = {}
    current_group = None

    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('=='):
            continue

        if not line.startswith('*'):
            group_name = re.sub(r'\[|\]', '', line).strip()
            if group_name:
                current_group = group_name
                result[current_group] = []
            continue

        if not current_group:
            continue

        # Bỏ qua runner-up / finalist / đội hình tiêu biểu / giải tháng
        if re.search(
            r'runner.?up|runners.?up|finalist|second place'
            r'|team of the|xi\b|dream team'
            r'|world.?11|men.s.?11|women.s.?11|fifpro.+11|best.+11'
            r'|of the month|of the week|of the round'
            r'|all.?time|century|hall of fame',
            line, re.IGNORECASE
        ):
            continue

        line = line.lstrip('* ')
        
        # Xử lý dòng có [[File:...]] ở đầu (Orders/Decorations)
        if line.startswith('[[File:') or line.startswith('[[Image:'):
            all_links = re.findall(r'\[\[([^|\]]*\|)?([^\]]*)\]\]', line)
            real_links = [b for _, b in all_links if not b.startswith('File') and not b.startswith('Image') and not re.match(r'\d+px$', b)]
            if real_links:
                trophy_name = real_links[0]
                year_match = re.findall(r'\((?:\d{1,2}\s+\w+\s+)?(\d{4})\)', line)
                result[current_group].append({
                    'trophy': trophy_name,
                    'years': year_match,
                    'count': len(year_match) if year_match else 1
                })
            continue

        parts = line.split(':', 1)
        trophy_name = re.sub(r'\[\[([^|\]]*\|)?([^\]]*)\]\]', r'\2', parts[0]).strip()
        trophy_name = re.sub(r"''|''", '', trophy_name).strip()

        # Bỏ qua entries là file/image - lấy tên thật từ link tiếp theo
        if trophy_name.startswith('File') or trophy_name.startswith('Image'):
            all_links = re.findall(r'\[\[([^|\]]*\|)?([^\]]*)\]\]', line)
            real_links = [(a, b) for a, b in all_links if not b.startswith('File') and not b.startswith('Image')]
            if real_links:
                trophy_name = real_links[0][1]
                # Tìm năm từ dấu ngoặc (ngày tháng năm)
                year_match = re.findall(r'\((\d{1,2}\s+\w+\s+)?(\d{4})\)', line)
                if year_match:
                    years = [m[1] for m in year_match]
                    seen = set()
                    years = [y for y in years if not (y in seen or seen.add(y))]
                    result[current_group].append({
                        'trophy': trophy_name,
                        'years': years,
                        'count': len(years)
                    })
                    continue
            else:
                continue

        years = []
        if len(parts) > 1:
            # Loại bỏ wikilinks trước, chỉ giữ display text
            year_text = re.sub(r'\[\[([^|\]]*\|)?([^\]]*)\]\]', r'\2', parts[1])
            years = re.findall(r'\d{4}(?:[–−-]\d{2,4})?', year_text)
            # Deduplicate giữ thứ tự
            seen = set()
            years = [y for y in years if not (y in seen or seen.add(y))]

        result[current_group].append({
            'trophy': trophy_name,
            'years': years,
            'count': len(years) if years else 1
        })

    return result


def classify_honours(honours: dict) -> dict:
    classified = {
        'Club - Domestic League': [],
        'Club - Domestic Cup': [],
        'Club - Continental': [],
        'Club - World': [],
        'International - Senior': [],
        'International - Youth': [],
        'Individual Awards': [],
        'Orders & Decorations': [],
    }

    DOMESTIC_LEAGUES = {
        'la liga', 'ligue 1', 'premier league', 'serie a', 'bundesliga',
        'eredivisie', 'primeira liga', 'liga portugal', 'süper lig',
        'scottish premiership', 'mls cup', "supporters' shield",
        'saudi pro league',
    }
    DOMESTIC_CUPS = {
        'copa del rey', 'supercopa de españa', 'trophée des champions',
        'fa cup', 'efl cup', 'league cup', 'carabao cup', 'community shield',
        'fa community shield', 'football league cup',
        'coppa italia', 'supercoppa italiana', 'dfb-pokal', 'dfl-supercup',
        'knvb cup', 'johan cruyff shield', 'taça de portugal',
        'coupe de france', 'coupe de la ligue',
        'supertaça cândido de oliveira',
    }
    INTL_TROPHIES = {
        'fifa world cup', 'copa américa', 'uefa european championship',
        'africa cup of nations', 'finalissima', 'concacaf gold cup',
        'afc asian cup', 'fifa confederations cup', 'uefa nations league',
        'olympic games', 'fifa world youth championship',
        'fifa u-20 world cup', 'fifa u-17 world cup',
    }
    CONTINENTAL = {
        'uefa champions league', 'uefa europa league', 'uefa super cup',
        'uefa conference league', 'copa libertadores', 'copa sudamericana',
        'recopa sudamericana', 'afc champions league', 'leagues cup',
        'caf champions league',
    }
    CLUB_WORLD = {'fifa club world cup', 'intercontinental cup'}

    # Giải cá nhân chính thống — chỉ giữ những giải này
    PRESTIGIOUS_INDIVIDUAL = {
        # Giải toàn cầu
        "ballon d'or", "fifa ballon d'or",
        "fifa world player of the year", "the best fifa men's player",
        "european golden shoe",
        "fifa puskás award",
        # Giải World Cup
        "fifa world cup golden ball", 
        "fifa world cup golden boot",
        "fifa world cup young player award",
        "fifa u-20 world cup golden ball", "fifa u-20 world cup golden boot",
        "fifa club world cup golden ball",
        # Giải châu Âu
        "uefa men's player of the year award",
        "uefa club footballer of the year",
        "uefa champions league top scorer",
        "uefa european championship golden boot",
        "uefa nations league finals golden boot",
        # Giải châu lục khác
        "copa américa golden ball", "copa américa golden boot",
        "africa cup of nations golden ball", "africa cup of nations golden boot",
        "afc asian cup most valuable player",
        "concacaf gold cup golden ball",
        # Giải quốc gia - player of the year / season
        "premier league player of the season",
        "premier league golden boot",
        "pfa players' player of the year", "pfa young player of the year",
        "football writers' association footballer of the year",
        "la liga best player",
        "pichichi trophy",
        "serie a footballer of the year",
        "serie a most valuable player",
        "capocannoniere",
        "ligue 1 player of the year",
        "ligue 1 top goalscorer",
        "bundesliga player of the season",
        "bundesliga top scorer",
        "mls most valuable player",
        "mls golden boot",
        "saudi pro league golden boot",
        "eredivisie golden boot",
        # Giải cầu thủ quốc gia
        "argentine footballer of the year",
        "brazilian footballer of the year",
        "french player of the year",
        "african footballer of the year",
        "asian footballer of the year",
        "concacaf player of the year",
        "oceania footballer of the year",
        # Giải trẻ
        "golden boy", "kopa trophy",
        # Franche football
        "yashin trophy", "gerd müller trophy"
        # Laureus
        "laureus world sportsman of the year",
    }
    # Pattern phụ để match các biến thể
    PRESTIGIOUS_PATTERNS = [
        r"ballon d.or",
        r"the best fifa men's player",
        r"fifa world player",
        r"golden shoe",
        r"world cup golden ball", r"world cup golden boot", r"world cup young player",
        r"club world cup golden ball",
        r"uefa.+player of the year",
        r"uefa club footballer",
        r"champions league top scorer",
        r"champions league player of the season",
        r"european championship golden boot",
        r"european championship player of the tournament",
        r"nations league.+golden boot",
        r"nations league.+player of the tournament",
        r"copa am.rica golden",
        r"africa cup.+golden",
        r"^premier league player of the season",
        r"^premier league golden boot",
        r"^pfa players",
        r"^pfa young player",
        r"^football writers.+footballer",
        r"^la liga best player",
        r"^serie a footballer of the year",
        r"^serie a most valuable player",
        r"^ligue 1 player of the year",
        r"^ligue 1 top goalscorer",
        r"^bundesliga player of the season",
        r"^bundesliga top scorer",
        r"^mls most valuable player",
        r"^mls golden boot",
        r"^saudi pro league golden boot",
        r"^eredivisie golden boot",
        r"pichichi",
        r"capocannoniere",
        r"^golden boy$",
        r"^kopa trophy$",
        r"^yashin trophy$",
        r"^gerd müller trophy$",
        r"^laureus",
        r"pusk.s award",
        r"footballer of the year$",
        r"^.{2,20} player of the year$",
    ]

    def _is_prestigious_individual(name):
        nl = name.lower().strip()
        # Loại bỏ phần trước / nếu có (vd: "FIFA World Player of the Year/FIFA Ballon d'Or/The Best")
        for part in nl.split('/'):
            part = part.strip()
            if part in PRESTIGIOUS_INDIVIDUAL:
                return True
        for pat in PRESTIGIOUS_PATTERNS:
            if re.search(pat, nl, re.IGNORECASE):
                return True
        return False

    for group, trophies in honours.items():
        gl = group.lower().strip()

        for t in trophies:
            name_lower = t['trophy'].lower()

            if gl == 'individual':
                if _is_prestigious_individual(t['trophy']):
                    classified['Individual Awards'].append(t)
                continue
            elif gl == 'orders':
                classified['Orders & Decorations'].append(t)
            elif 'u20' in gl or 'u23' in gl or 'u21' in gl or 'u19' in gl or 'u17' in gl or 'youth' in gl or 'olympic' in gl:
                classified['International - Youth'].append({**t, 'team': group})
            elif any(nat in gl for nat in NATIONAL_TEAMS) or gl in NATIONAL_TEAMS:
                classified['International - Senior'].append({**t, 'team': group})
            elif name_lower in INTL_TROPHIES or any(it in name_lower for it in INTL_TROPHIES):
                classified['International - Senior'].append({**t, 'team': group})
            elif name_lower in CONTINENTAL:
                classified['Club - Continental'].append({**t, 'club': group})
            elif name_lower in CLUB_WORLD:
                classified['Club - World'].append({**t, 'club': group})
            elif name_lower in DOMESTIC_CUPS:
                classified['Club - Domestic Cup'].append({**t, 'club': group})
            elif name_lower in DOMESTIC_LEAGUES:
                classified['Club - Domestic League'].append({**t, 'club': group})
            elif 'league' in name_lower and 'champions' not in name_lower and 'cup' not in name_lower:
                classified['Club - Domestic League'].append({**t, 'club': group})
            else:
                classified['Club - Domestic Cup'].append({**t, 'club': group})

    return {k: v for k, v in classified.items() if v}


def print_honours(classified: dict):
    for category, trophies in classified.items():
        print(f"\n{'='*60}")
        print(f"  📋 {category}")
        print(f"{'='*60}")
        for t in trophies:
            extra = t.get('club') or t.get('team') or ''
            extra_str = f" [{extra}]" if extra else ''
            years_str = ', '.join(t['years']) if t['years'] else ''
            print(f"  🏆 {t['trophy']}{extra_str} × {t['count']}")
            if years_str:
                print(f"     └─ {years_str}")


if __name__ == '__main__':
    player = sys.argv[1] if len(sys.argv) > 1 else 'Lionel_Messi'

    print(f"\n🔍 Fetching honours for: {player.replace('_', ' ')}\n")
    wikitext = get_honours_wikitext(player)

    if not wikitext:
        print("❌ Không tìm thấy phần Honours!")
        exit(1)

    honours = parse_honours(wikitext)
    classified = classify_honours(honours)
    print_honours(classified)

    # Tổng kết
    total = sum(t['count'] for trophies in classified.values() for t in trophies)
    print(f"\n{'='*60}")
    print(f"  📊 TỔNG CỘNG: {total} danh hiệu")
    print(f"{'='*60}")
