import requests
import re
import sys
import json
import logging

from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'FootballWeb/1.0 (dungpham; test)'}
WIKI_API = 'https://en.wikipedia.org/w/api.php'
INDIVIDUAL_AWARDS_VERSION = 4
logger = logging.getLogger(__name__)

DISQUALIFIED_INDIVIDUAL_RE = re.compile(
    r'\b(?:'
    r'nominee|nominees|nomination|nominations|nominated'
    r'|shortlist|shortlists|shortlisted'
    r'|candidate|candidates'
    r'|runner.?up|runners.?up|finalist|finalists'
    r'|second place|third place|fourth place|podium'
    r')\b',
    re.IGNORECASE,
)


def is_disqualified_individual_award(name: str) -> bool:
    """Kiểm tra tên giải cá nhân có phải là đề cử, á quân hay hạng phụ không phải danh hiệu."""
    if not name or not isinstance(name, str):
        return True
    return bool(DISQUALIFIED_INDIVIDUAL_RE.search(name))


LEAGUE_POTY_EXCLUDE_RE = re.compile(
    r'\b(?:club|playmaker|young|fans|month|week|round|team'
    r'|manchester|liverpool|chelsea|arsenal|tottenham|city|united'
    r'|madrid|barcelona|bayern|juventus|milan|inter|roma|psg|dortmund'
    r'|brighton|everton|newcastle|aston villa)\b',
    re.IGNORECASE,
)

LEAGUE_POTY_EXPLICIT = {
    'premier league player of the season',
    "pfa players' player of the year",
    'pfa player of the year',
    "football writers' association footballer of the year",
    'fwa footballer of the year',
    'la liga best player',
    'la liga player of the season',
    'trofeo alfredo di stéfano',
    'serie a footballer of the year',
    'serie a most valuable player',
    'serie a best player',
    'serie a player of the season',
    'bundesliga player of the season',
    'german footballer of the year',
    'footballer of the year in germany',
    'ligue 1 player of the year',
    'unfp ligue 1 player of the year',
    'eredivisie player of the year',
    'dutch footballer of the year',
    'primeira liga player of the year',
    'liga portugal player of the season',
    'mls most valuable player',
    'saudi pro league player of the season',
}

LEAGUE_POTY_PATTERN = re.compile(
    r'^(?:premier league|la liga|serie a|bundesliga|ligue 1|eredivisie|primeira liga|liga portugal|mls|saudi pro league)\b.+(?:player of the (?:season|year)|footballer of the year|most valuable player|mvp|best player)',
    re.IGNORECASE,
)

BALLON_DOR_RE = re.compile(r'ballon\s*d[\'’]or', re.IGNORECASE)
FIFA_THE_BEST_RE = re.compile(r'the\s+best\s+fifa|fifa\s+world\s+player', re.IGNORECASE)
GERD_MULLER_RE = re.compile(
    r'gerd\s+m[üu]ller\s+trophy|ballon\s*d[\'’]or\s+striker\s+of\s+the\s+year',
    re.IGNORECASE,
)


def normalize_trophy_name(name: str) -> str:
    """Chuẩn hóa tên giải thưởng, loại bỏ các chú thích phụ (ví dụ Gerd Müller Trophy)."""
    if not name or not isinstance(name, str):
        return name
    if GERD_MULLER_RE.search(name):
        return 'Gerd Müller Trophy'
    return name


def is_league_poty_award(name: str) -> bool:
    """Xác định danh hiệu có phải là Cầu thủ xuất sắc nhất giải VĐQG hay không."""
    if not name or not isinstance(name, str) or is_disqualified_individual_award(name):
        return False
    nl = name.lower().strip()
    if LEAGUE_POTY_EXCLUDE_RE.search(nl):
        return False
    if nl in LEAGUE_POTY_EXPLICIT:
        return True
    return bool(LEAGUE_POTY_PATTERN.search(nl))


def is_ballon_dor_award(name: str) -> bool:
    if not name or not isinstance(name, str) or is_disqualified_individual_award(name):
        return False
    if GERD_MULLER_RE.search(name):
        return False
    return bool(BALLON_DOR_RE.search(name))


def is_fifa_the_best_award(name: str) -> bool:
    if not name or not isinstance(name, str) or is_disqualified_individual_award(name):
        return False
    return bool(FIFA_THE_BEST_RE.search(name))


def is_major_individual_award(name: str) -> bool:
    return is_ballon_dor_award(name) or is_fifa_the_best_award(name) or is_league_poty_award(name)


def individual_award_rank(award: dict) -> int:
    trophy = award.get('trophy', '') if isinstance(award, dict) else str(award)
    if is_ballon_dor_award(trophy):
        return 0
    if is_fifa_the_best_award(trophy):
        return 1
    if is_league_poty_award(trophy):
        return 2
    al = trophy.lower().strip()
    if 'world cup' in al and 'golden' in al:
        return 3
    if 'golden shoe' in al or 'champions league' in al or 'copa am' in al or ('euro' in al and 'golden' in al):
        return 4
    if any(k in al for k in ['gerd müller', 'gerd muller', 'striker of the year', 'pichichi', 'capocannoniere', 'golden boot', 'top scorer', 'top goalscorer']):
        return 5
    if 'playmaker' in al:
        return 6
    if any(k in al for k in ['golden boy', 'kopa', 'young player']):
        return 7
    if any(k in al for k in ['player of the year', 'player of the season', 'footballer of the year', 'mvp']):
        return 8
    return 9


def sort_individual_awards(awards: list[dict]) -> list[dict]:
    """Sắp xếp giải cá nhân đưa các giải lớn (Ballon d'Or, FIFA The Best, League POTY) lên đầu."""
    return sorted(awards, key=individual_award_rank)

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


def search_wiki_pages(player_name: str) -> list[str]:
    """Liệt kê các trang Wikipedia ứng viên cho tên cầu thủ (direct match trước, rồi search)."""
    candidates = []
    try:
        slug = player_name.replace(' ', '_')
        params = {'action': 'query', 'titles': slug, 'format': 'json'}
        r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=5)
        pages = r.json().get('query', {}).get('pages', {})
        if '-1' not in pages:
            candidates.append(slug)

        params = {'action': 'query', 'list': 'search', 'srsearch': f'{player_name} footballer',
                  'format': 'json', 'srlimit': 5}
        r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=5)
        for result in r.json().get('query', {}).get('search', []):
            candidate = result['title'].replace(' ', '_')
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("Wikipedia page lookup failed for %s: %s", player_name, exc)
        return candidates


def search_wiki_page(player_name: str) -> str | None:
    """Tìm Wikipedia page từ tên cầu thủ (trang đầu tiên có mục honours)."""
    try:
        for slug in search_wiki_pages(player_name):
            if get_honours_wikitext(slug):
                return slug
        return None
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("Wikipedia honours lookup failed for %s: %s", player_name, exc)
        return None


def get_honours_wikitext(player_page: str) -> str | None:
    params = {'action': 'parse', 'page': player_page, 'prop': 'sections', 'format': 'json'}
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=8)
    r.raise_for_status()
    sections = r.json()['parse']['sections']

    honours_idx = None
    for s in sections:
        if s['line'].lower() in ('honours', 'career honours', 'honors'):
            honours_idx = s['index']
            break

    if not honours_idx:
        return None

    params = {'action': 'parse', 'page': player_page, 'prop': 'wikitext', 'section': honours_idx, 'format': 'json'}
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=8)
    r.raise_for_status()
    return r.json()['parse']['wikitext']['*']


def get_wiki_birth_date(player_page: str) -> str | None:
    params = {'action': 'parse', 'page': player_page, 'prop': 'text', 'section': '0', 'format': 'json'}
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=8)
    r.raise_for_status()
    html = r.json()['parse']['text']['*']
    birth_date = BeautifulSoup(html, 'html.parser').select_one('.infobox .bday')
    return birth_date.get_text(strip=True) if birth_date else None


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

        # Bỏ qua runner-up / finalist / nominee / đội hình tiêu biểu / giải tháng
        if re.search(
            r'runner.?up|runners.?up|finalist|finalists|second place|third place|fourth place|podium'
            r'|nominee|nominees|nomination|nominations|nominated|shortlist|shortlists|shortlisted|candidate|candidates'
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
        trophy_name = normalize_trophy_name(trophy_name)
        if is_disqualified_individual_award(trophy_name):
            continue

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
        "premier league playmaker of the season", "most assists in the premier league",
        "premier league golden boot",
        "pfa players' player of the year", "pfa young player of the year",
        "football writers' association footballer of the year",
        "la liga best player",
        "la liga player of the season",
        "la liga top assist provider",
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
        # Giải cầu thủ châu lục
        "african footballer of the year",
        "asian footballer of the year",
        "concacaf player of the year",
        "oceania footballer of the year",
        "south american footballer of the year:"
        # Giải cầu thủ quốc gia
        "albanian footballer of the year",
        "argentine footballer of the year",
        "armenian footballer of the year",
        "austrian footballer of the year",
        "azerbaijani footballer of the year",
        "belarusian footballer of the year",
        "belgian golden shoe",
        "belgian professional footballer of the year",
        "brazilian footballer of the year",
        "bulgarian footballer of the year",
        "cnid footballer of the year",
        "croatian footballer of the year",
        "czech footballer of the year",
        "czech golden ball",
        "czechoslovak footballer of the year",
        "danish football player of the year",
        "danish football player of the year by tv2 and dbu",
        "dutch footballer of the year",
        "east german footballer of the year",
        "estonian footballer of the year",
        "faroese footballer of the year",
        "finnish footballer of the year",
        "france football french player of the year",
        "french player of the year",
        "georgian footballer of the year",
        "german footballer of the year",
        "germany national player of the year",
        "footballer of the year in germany",
        "greek footballer of the year",
        "guldbollen",
        "gullballen",
        "hungarian footballer of the year",
        "hungarian golden ball",
        "icelandic footballer of the year",
        "idol nacije",
        "israeli footballer of the year",
        "italian footballer of the year",
        "kazakhstani footballer of the year",
        "kniksen of the year",
        "latvian footballer of the year",
        "liechtensteiner footballer of the year",
        "lithuanian footballer of the year",
        "luxembourgish footballer of the year",
        "macedonian footballer of the year",
        "maltese player of the year",
        "moldovan footballer of the year",
        "montenegrin footballer of the year",
        "norwegian golden ball",
        "pfai players' player of the year",
        "pfa scotland players' player of the year",
        "polish footballer of the year",
        "portuguese golden ball",
        "romanian footballer of the year",
        "russian footballer of the year",
        "serbian footballer of the year",
        "sfwa footballer of the year",
        "slovak footballer of the year",
        "slovenian footballer of the year",
        "soviet footballer of the year",
        "spanish footballer of the year",
        "swedish footballer of the year",
        "swiss footballer of the year",
        "turkish footballer of the year",
        "ukrainian footballer of the year",
        "uzbekistan footballer of the year",
        "welsh footballer of the year",
        "yugoslav footballer of the year",
        # Giải trẻ
        "golden boy", "kopa trophy",
        # Franche football
        "yashin trophy", "gerd müller trophy",
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
        r"^la liga player of the season",
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
        r"gerd m[üu]ller trophy",
        r"striker of the year",
        r"^laureus",
        r"pusk.s award",
        r"footballer of the year(?: award)?(?:\s*(?:\([^)]*\)|in\s+.+))?$",
        r"^danish football player of the year\b",
        r"^(?:guldbollen|gullballen|norwegian golden ball)$",
        r"^kniksen of the year$",
        r"^(?:portuguese|czech|hungarian) golden ball$",
        r"^idol nacije$",
        r"^belgian golden shoe$",
        r"^.+ player of the (?:year|season)(?: award)?$",
    ]

    def _is_prestigious_individual(name):
        if is_disqualified_individual_award(name):
            return False
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
                norm_name = normalize_trophy_name(t['trophy'])
                if not is_disqualified_individual_award(norm_name) and _is_prestigious_individual(norm_name):
                    classified['Individual Awards'].append({**t, 'trophy': norm_name})
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
