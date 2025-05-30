from tabulate import tabulate
import requests, os

def down_images(type, id):
    id = str(id)
    # Create directory if it doesn't exist
    directory = f'./images/{type}'
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        
    link = f'https://media.api-sports.io/football/{type}/{id}.png'
    img_data = requests.get(link,stream=True).content
    with open(f'./images/{type}/{id}.png', 'wb') as handler:
        handler.write(img_data)
        print("done",id)

def check_file(type, id):
    path = f"./images/{type}/{id}.png"
    isFile = os.path.isfile(path)
    return isFile

def check_n_down_images(s_type, id):
    b_file = check_file(s_type,id)
    if b_file is False:
        down_images(s_type,id)

def handle_data_standing(json_data,n_season):
    d_data = json_data["response"][0]
    l_standings = d_data["league"]["standings"]
    l_mess = []
    for team in l_standings[0]:
        logo = team['team']['logo']
        team_id = team['team']['id']
        check_n_down_images("teams",team_id)
        rank = team['rank']
        name = f'<img style="width: 28px; height: 28px; min-width: 28px; min-height: 28px; object-fit: contain;" align="left" src="/images/teams/{team_id}.png">'+\
                f'<a href="/teams/{team_id}/{n_season}">' + team['team']["name"] + "</a>"
        point = '<b>'+str(team["points"])+'</b>'
        description = team["description"]
        match = team["all"]["played"]
        win = team["all"]["win"]
        draw = team["all"]["draw"]
        lose = team["all"]["lose"]
        goals = team["all"]["goals"]["for"]
        against = team["all"]["goals"]["against"]
        goalsDiff = team["goalsDiff"]
        list_team = [rank,name,match,win,draw,lose,goals,against,goalsDiff,point,description]
        l_mess.append(list_team)
    
    list_headers = ["No","Team","Match","Win","Draw","Lose","Goals","Against","Difference","Points","Detail"]
    message = tabulate(l_mess,headers=list_headers,tablefmt='html', colalign=("center" for i in list_headers))
    return message

# Handle data cup standing
def handle_data_cup_standing(json_data,n_season,s_league):
    standings = json_data['response'][0]['league']['standings']
    # Create HTML tables using tabulate, organizing them in pairs for side-by-side display
    tables = []
    headers = ["Rank", "Team", "Points", "Played", "Win", "Draw", "Lose", "Goals", "Against", "Diff"]
    len_group = len(standings)
    if len_group%2 == 1:
        len_group = len_group -1
    for i in range(0, len_group, 2):
        table_pair = []
        for j in range(2):
            if i + j < len(standings):
                group = standings[i + j]
                rows = []
                for team in group:
                    team_id = team["team"]["id"]
                    check_n_down_images("teams",team_id)
                    img_name = f'<img style="width: 28px; height: 28px; min-width: 28px; min-height: 28px; object-fit: contain;" align="left" src="/images/teams/{team_id}.png">'+\
                        f'<a href="/teams/{team_id}/{n_season}">' + team['team']["name"] + "</a>"
                    if team['group'] == "Ranking of third-placed teams":
                        continue
                    else:
                        rows.append([
                            team['rank'],
                            img_name,
                            team['points'],
                            team['all']['played'],
                            team['all']['win'],
                            team['all']['draw'],
                            team['all']['lose'],
                            team['all']['goals']['for'],
                            team['all']['goals']['against'],
                            team['goalsDiff']
                        ])
                table = tabulate(rows, headers, tablefmt='unsafehtml', colalign=("left" for i in headers))
                table_pair.append(table)
            else:
                table_pair.append(None)
        tables.append(table_pair)
    if "euro" in s_league:
        third_place_rows = []
        third_headers = ["Rank", "Team", "Points", "Played", "Win", "Draw", "Lose", "Goals", "Against", "Diff",""]
        for l_table in standings:
            for team in l_table:
                if team['group'] == "Ranking of third-placed teams":
                    team_id = team["team"]["id"]
                    img_name = f'<img style="width: 28px; height: 28px; min-width: 28px; min-height: 28px; object-fit: contain;" align="left" src="/images/teams/{team_id}.png">'+\
                                    f'<a href="/teams/{team_id}/{n_season}">' + team['team']["name"] + "</a>"
                    if team["description"]:
                        des = team["description"][:9]
                    else:
                        des = ""
                    third_place_rows.append([
                        team["rank"],
                        img_name,
                        team['points'],
                        team['all']['played'],
                        team['all']['win'],
                        team['all']['draw'],
                        team['all']['lose'],
                        team['all']['goals']['for'],
                        team['all']['goals']['against'],
                        team['goalsDiff'],
                        des
                    ])
                else:
                    continue
        third_place_table = tabulate(third_place_rows, third_headers, tablefmt='unsafehtml', colalign=("left" for i in third_headers))
    else:
        third_place_table = []
    return tables, third_place_table
    
# Api will response some data have multiple results
def handle_multi_coach(res):
    # Filter the response
    l_one_coach = [
        coach for coach in res['response'] if any(job['end'] is None for job in coach['career'])
    ]
    res['results'] = 1
    res['response'] = l_one_coach
    return res

# get data coach for team info
def handle_coach_for_team(json_data, team_id):
    d_data = json_data["response"][0]
    coach_id = d_data["id"]
    check_n_down_images("coachs",coach_id)
    name = d_data["name"]
    photo_name = f'<img style="width: 90px; height: 90px; object-fit: cover; border-radius: 50%; margin-right: 15px; vertical-align: middle;" src="/images/coachs/{coach_id}.png" loading="lazy">'+\
                f'<a style="vertical-align: middle; font-size: 1.1em; font-weight: 500;" href="/coachs/{coach_id}/{team_id}"> <br> {name} </a>'
    html_coach = f'<div class="team-details" style="grid-column: 2"><table class="w3-table"><tr><td style="width: 120px; font-weight: bold;">Coach</td><td>{photo_name}</td></tr></table></div>'
    return html_coach

# xu ly data coach
def handle_data_coach(json_data, n_season=None):
    d_data = json_data["response"][0]
    coach_id = d_data["id"]
    check_n_down_images("coachs",coach_id)
    name = d_data["name"]
    full_name = d_data["firstname"]+" "+d_data["lastname"]
    image = f'<img style="width: 100px; height: auto; max-width: 100px; max-height: auto;" align="left" src="/images/coachs/{coach_id}.png">'
    n_age = d_data["age"]
    nation = d_data["nationality"]
    birth = d_data["birth"]["date"]
    place_ = d_data["birth"]["place"] or ""
    birth_place = place_ +" - "+ d_data["birth"]["country"]
    height = d_data["height"]
    weight = d_data["weight"]
    team = d_data["team"]["name"]
    l_career = d_data["career"]
    mess_career = []
        
    l_mess = [
        ["",image],
        ["Full Name",full_name],
        ["Nationality",nation],["Age",n_age],["Birth",birth],
        ["Birth place",birth_place],["Height",height],
        ["Weight",weight],["Team",team]
    ]
    for team in l_career:
        team_id = team["team"]["id"]
        check_n_down_images("teams",team_id)
        start = team["start"]
        end = team["end"]
        if not end:
            end = "Now"
        # Use n_season if provided, else fallback to old link
        if n_season:
            team_link = f'/teams/{team_id}/{n_season}'
        else:
            team_link = f'/teams/{team_id}'
        image_name = f'<img style="width: 38px; height: 38px; min-width: 38px; min-height: 38px; object-fit: contain;" align="left" src="/images/teams/{team_id}.png">'+\
                f'<a href="{team_link}">' + team["team"]["name"] + "</a>"
        time_coach = start+" - "+end
        l_team = [image_name, time_coach]
        mess_career.append(l_team)
    message = tabulate(l_mess,tablefmt='html')
    message2 = tabulate(mess_career,tablefmt='html')
    return message, message2

def handle_data_coach_trophies(json_trophy_data, career_start=None):
    l_data = json_trophy_data["response"]
    trophies = []
    no = 1
    # Convert career start to year if provided
    career_start_year = None
    if career_start:
        try:
            career_start_year = int(career_start.split("-")[0])
        except (ValueError, AttributeError):
            pass

    for trophy in l_data:
        league = trophy["league"]
        country = trophy["country"]
        season = trophy["season"]
        place = trophy["place"]
        if place == "Winner":
            # Determine if trophy was won as coach or player
            is_coach = False
            role = "Player"
            if career_start_year:
                try:
                    trophy_year = int(season.split("/")[0])
                    is_coach = trophy_year >= career_start_year
                    role = "Coach" if is_coach else "Player"
                except (ValueError, AttributeError):
                    pass

            text = f"{no} - {league} ({season})"
            highlight = False
            css_class = ""
            if "UEFA Champions League" in league:
                highlight = True
                css_class = "highlight-champions"
            elif "FIFA World Cup" in league:
                highlight = True
                css_class = "highlight-worldcup"
            elif "UEFA Europa League" in league:
                highlight = True
                css_class = "highlight-europa"
            elif "UEFA European Championship" in league or "Euro Championship" in league:
                highlight = True
                css_class = "highlight-euro"
            trophies.append({
                "text": text,
                "country": country,
                "highlight": highlight,
                "class": css_class,
                "is_coach": is_coach,
                "role": role
            })
            no += 1
    return trophies, no-1

# xu ly data ve thong tin chi tiet 1 team
def handle_data_team_info(json_data):
    d_data = json_data["response"][0]
    team_id = d_data["team"]["id"]
    check_n_down_images("teams",team_id)
    team_name = d_data["team"]["name"]
    country = d_data["team"]["country"]
    founded = d_data["team"]["founded"]
    stadium = d_data["venue"]["name"]
    venue_id = d_data["venue"]["id"]
    check_n_down_images("venues",venue_id)
    address = d_data["venue"]["address"]
    city = d_data["venue"]["city"]
    capacity = d_data["venue"]["capacity"]
    surface = d_data["venue"]["surface"]

    # Left: logo + team name
    logo_html = f'''<div class="team-logo">
        <img src="/images/teams/{team_id}.png">
        <div class="team-name-under-logo">{team_name}</div>
    </div>'''

    # Right: stadium image + stadium name
    stadium_html = f'''<div class="stadium-image">
        <img src="/images/venues/{venue_id}.png">
        <div class="stadium-name-under-image">{stadium}</div>
    </div>'''

    # Center: details table (excluding team name and stadium)
    details_html = f'''
    <div class="team-details">
        <table class="w3-table">
            <tr><td>Country</td><td><span style="font-weight: 500;">{country}</span></td></tr>
            <tr><td>Founded</td><td>{founded}</td></tr>
            <tr><td>Address</td><td>{address}</td></tr>
            <tr><td>City</td><td>{city}</td></tr>
            <tr><td>Capacity</td><td>{capacity:,}</td></tr>
            <tr><td>Surface</td><td>{surface}</td></tr>
        </table>
    </div>'''

    # Combine all sections for grid columns
    message = logo_html + details_html + stadium_html
    return message

def handle_data_squad(json_data,n_season):
    d_data = json_data["response"][0]
    l_mess = []
    for idx, data in enumerate(d_data["players"], 1):
        player_id = data["id"]
        check_n_down_images("players",player_id)
        name_player = f'<img style="width: 45px; height: 45px; object-fit: cover; vertical-align: middle; margin-right: 10px;" src="/images/players/{player_id}.png" loading="lazy">' +\
                f'<a style="vertical-align: middle; font-weight: 500;" href="/players/{player_id}/{n_season}">' + data["name"] + "</a>"
        age = data["age"]
        no = data["number"] or "-"
        position = data["position"]
        l_row = [idx, name_player, age, position, no]
        l_mess.append(l_row)
    list_headers = ["No", "Name","Age","Position","No"]
    message = tabulate(l_mess, headers=list_headers, tablefmt='html', colalign=("left" for i in list_headers))
    return message

def handle_data_player_info(json_data):
    # Player data
    d_data = json_data["response"][0]["player"]
    d_stat = json_data["response"][0]["statistics"][0]
    season = json_data["parameters"]["season"]
    this_season = season + " - " + str(int(season)+1)
    player_id = d_data["id"]
    full_name = d_data["firstname"] + " " + d_data["lastname"]
    image = f'<img style="width: 100px; height: auto; max-width: 100px; max-height: auto;" align="left" src="/images/players/{player_id}.png">'
    age = d_data["age"]
    nation = d_data["nationality"]
    birth = d_data["birth"]["date"]
    place_ = d_data["birth"]["place"] or ""
    birth_place = place_ +" - "+ d_data["birth"]["country"]
    height = d_data["height"]
    weight = d_data["weight"]
    team = d_stat["team"]["name"]
    appear = str(d_stat["games"]["appearences"]) +"/"+ str(d_stat["games"]["lineups"])
    position = d_stat["games"]["position"]
    rating = d_stat["games"]["rating"]
    goals_assist = str(d_stat["goals"]["total"]) + "/" + str(d_stat["goals"]["assists"])
    player_info = [
        ("Image", image),
        ("Full Name", full_name),
        ("Position", position),
        ("Nationality", nation),
        ("Age", age),
        ("Birth", birth),
        ("Birth place", birth_place),
        ("Height", height),
        ("Weight", weight),
        ("Team", team),
        ("Season stats", this_season),
        ("Appearences / Lineups", appear),
        ("Goals / Assists", goals_assist),
        ("Rating", rating)
    ]
    return player_info

# Xu ly data trophy
def handle_data_trophies(json_trophy_data):
    l_data = json_trophy_data["response"]
    trophies = []
    no = 1
    for trophy in l_data:
        league = trophy["league"]
        country = trophy["country"]
        s_season = " ("+trophy["season"]+")"
        place = trophy["place"]
        if place == "Winner":
            text = f"{no} - {league}{s_season}"
            highlight = False
            css_class = ""
            if "UEFA Champions League" in league:
                highlight = True
                css_class = "highlight-champions"
            elif "FIFA World Cup" in league:
                highlight = True
                css_class = "highlight-worldcup"
            elif "UEFA Europa League" in league:
                highlight = True
                css_class = "highlight-europa"
            elif "UEFA European Championship" in league or "Euro Championship" in league:
                highlight = True
                css_class = "highlight-euro"
            trophies.append({
                "text": text,
                "country": country,
                "highlight": highlight,
                "class": css_class
            })
            no += 1
    return trophies, no-1

# Xu ly data transfer
def handle_data_transfer(json_trans_data, n_season):
    if json_trans_data["results"] == 0:
        return []
    l_data = json_trans_data["response"][0]["transfers"]
    transfers = []
    for tr in l_data:
        date = tr["date"]
        fee = tr.get("fee") or tr["type"]  # Prefer fee, fallback to type
        team_out_id = tr["teams"]["out"]["id"]
        team_in_id = tr["teams"]["in"]["id"]
        team_out_name = tr["teams"]["out"]["name"]
        team_in_name = tr["teams"]["in"]["name"]
        check_n_down_images("teams",team_out_id)
        check_n_down_images("teams",team_in_id)
        team_out_image = f'<img style="width: 28px; height: 28px; min-width: 28px; min-height: 28px; object-fit: contain;" align="left" src="/images/teams/{team_out_id}.png" loading="lazy">'+\
                f'<a href="/teams/{team_out_id}/{n_season}">' + team_out_name + "</a>"
        team_in_image = f'<img style="width: 28px; height: 28px; min-width: 28px; min-height: 28px; object-fit: contain;" align="left" src="/images/teams/{team_in_id}.png" loading="lazy">'+\
                f'<a href="/teams/{team_in_id}/{n_season}">' + team_in_name + "</a>"
        transfers.append({
            "date": date,
            "fee": fee,
            "from": team_out_image,
            "to": team_in_image
        })
    return transfers

# Xu ly data top score
def handle_data_top_score(json_data,this_season):
    d_data = json_data["response"]
    if not d_data:
        l_mess =[" "]
        list_headers = ["No Data"]
        message = tabulate(l_mess, headers=list_headers,tablefmt='html', colalign=("left" for i in list_headers))
        return message
    rank = 1
    this_season
    l_mess = []
    for data in d_data:
        player_id = data["player"]["id"]
        check_n_down_images("players",player_id)
        
        team_id = data["statistics"][0]['team']['id']
        check_n_down_images("teams",team_id)

        name = f'<img style="width: 38px; height: 38px; min-width: 38px; min-height: 38px; object-fit: contain;" align="left" src="/images/players/{player_id}.png" loading="lazy">' +\
                f'<a href="/players/{player_id}/{this_season}">' + data["player"]["name"] + "</a>"
        club = f'<img style="width: 28px; height: 28px; min-width: 28px; min-height: 28px; object-fit: contain;" align="left" src="/images/teams/{team_id}.png" loading="lazy">'+\
                f'<a href="/teams/{team_id}/{this_season}">' + data["statistics"][0]['team']["name"] + "</a>"
        # age = data["player"]["age"]
        date = data["player"]["birth"]["date"]
        date = int(date.split("-")[0])
        age = int(this_season) - date
        nationality = data["player"]["nationality"]
        appearences = data["statistics"][0]["games"]["appearences"]
        rating = data["statistics"][0]["games"]["rating"]
        goals = data["statistics"][0]["goals"]["total"] or 0
        assists = data["statistics"][0]["goals"]["assists"] or 0
        ga = goals + assists
        goals = '<b>'+str(goals)+'</b>'
        list_topscore = [rank,name,age,club,nationality,goals,assists,ga,appearences,rating]
        rank+=1
        l_mess.append(list_topscore)
    list_headers = ["Rank","Name","Age","Club","Country","Goals","Assists","GA","App","Rating"]
    message = tabulate(l_mess, headers=list_headers,tablefmt='html', colalign=("left" for i in list_headers))
    return message

# Xu ly data top assist
def handle_data_top_assist(json_data,this_season):
    d_data = json_data["response"]
    if not d_data:
        l_mess =[" "]
        list_headers = ["No Data"]
        message = tabulate(l_mess, headers=list_headers,tablefmt='html')
        return message
    rank = 1
    this_season
    l_mess = []
    for data in d_data:
        player_id = data["player"]["id"]
        check_n_down_images("players",player_id)

        team_id = data["statistics"][0]['team']['id']
        check_n_down_images("teams",team_id)

        name = f'<img style="width: 38px; height: 38px; min-width: 38px; min-height: 38px; object-fit: contain;" align="left" src="/images/players/{player_id}.png" loading="lazy">' +\
                f'<a href="/players/{player_id}/{this_season}">' + data["player"]["name"] + "</a>"
        club = f'<img style="width: 28px; height: 28px; min-width: 28px; min-height: 28px; object-fit: contain;" align="left" src="/images/teams/{team_id}.png" loading="lazy">'+\
                f'<a href="/teams/{team_id}/{this_season}">' + data["statistics"][0]['team']["name"] + "</a>"
        # age = data["player"]["age"]
        date = data["player"]["birth"]["date"]
        date = int(date.split("-")[0])
        age = int(this_season) - date
        nationality = data["player"]["nationality"]
        appearences = data["statistics"][0]["games"]["appearences"]
        rating = data["statistics"][0]["games"]["rating"]
        goals = data["statistics"][0]["goals"]["total"] or 0
        assists = data["statistics"][0]["goals"]["assists"] or 0
        ga = goals + assists
        assists = '<b>'+str(assists)+'</b>'
        list_topassist = [rank,name,age,club,nationality,assists,goals,ga,appearences,rating]
        rank+=1
        l_mess.append(list_topassist)
    list_headers = ["Rank","Name","Age","Club","Country","Assists","Goals","GA","App","Rating"]
    message = tabulate(l_mess, headers=list_headers,tablefmt='html', colalign=("left" for i in list_headers))
    return message
