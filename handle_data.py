from tabulate import tabulate
import requests, os

def down_images(type, id):
    id = str(id)
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

def handle_data_standing(json_data,s_league,n_season):
    d_data = json_data["response"][0]
    l_standings = d_data["league"]["standings"]
    l_mess = []
    for team in l_standings[0]:
        logo = team['team']['logo']
        team_id = team['team']['id']
        check_n_down_images("teams",team_id)
        rank = team['rank']
        name = f'<img align="left" width="28" height="28" src="/images/teams/{team_id}.png">'+\
                f'<a href="/teams/{team_id}/{n_season}/{s_league}">' + team['team']["name"] + "</a>"
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

# xu ly data ve thong tin chi tiet 1 team
def handle_data_team_info(json_data):
    d_data = json_data["response"][0]
    team_id = d_data["team"]["id"]
    check_n_down_images("teams",team_id)
    team_name = d_data["team"]["name"]
    country = d_data["team"]["country"]
    founded = d_data["team"]["founded"]
    logo = d_data["team"]["logo"]
    logo = f'<img align="left" max-width="100px" height="auto" src="/images/teams/{team_id}.png">'
    stadium = d_data["venue"]["name"]
    venue_id = d_data["venue"]["id"]
    check_n_down_images("venues",venue_id)
    address = d_data["venue"]["address"]
    city = d_data["venue"]["city"]
    capacity = d_data["venue"]["capacity"]
    surface = d_data["venue"]["surface"]
    image = d_data["venue"]["image"]
    image = f'<img align="left" max-width="100px" height="auto" src="/images/venues/{venue_id}.png">'
    l_mess = []
    # l_items = [team_name,country,founded,logo,stadium,address,city,capacity,surface,image]
    # l_mess.append(l_items)
    l_mess = [
        ["",logo],
        ["Team Name",team_name],["Country",country],
        ["Founded",founded],["Stadium",stadium],
        ["Address",address],["City",city],
        ["Capacity",capacity],["Surface",surface],
        ["",image],['<b align="center"> Current Squad</b>']
        ]
    message = tabulate(l_mess,tablefmt='html')
    return message

def handle_data_squad(json_data,s_league,n_season):
    d_data = json_data["response"][0]
    l_mess = []
    for data in d_data["players"]:
        player_id = data["id"]
        check_n_down_images("players",player_id)
        name_player = f'<img align="left" width="38" height="38" src="/images/players/{player_id}.png" loading="lazy">' +\
                f'<a href="/players/{player_id}/{n_season}/{s_league}">' + data["name"] + "</a>"
        age = data["age"]
        no = data["number"]
        position = data["position"]
        l_row = [name_player,age,position,no]
        l_mess.append(l_row)
    list_headers = ["Name","Age","Position","No"]
    message = tabulate(l_mess, headers=list_headers, tablefmt='html', colalign=("left" for i in list_headers))
    return message

def handle_data_player_info(json_data):
    # Player data
    d_data = json_data["response"][0]["player"]
    d_stat = json_data["response"][0]["statistics"][0]
    season = json_data["parameters"]["season"]
    this_season = season + " - " + str(int(season)+1)
    player_id = d_data["id"]
    name_player = d_data["name"]
    full_name = d_data["firstname"] + " " + d_data["lastname"]
    image = d_data["photo"]
    image = f'<img align="left" max-width="100px" height="auto" src="/images/players/{player_id}.png">'
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
    l_mess = [
        ["",image],
        ["Full Name",full_name],["Position",position],
        ["Nationality",nation],["Age",age],["Birth",birth],
        ["Birth place",birth_place],["Height",height],
        ["Weight",weight],["Current team",team],
        ["This season stats",this_season],
        ["Appearences / Lineups", appear],
        ["Goals / Assists", goals_assist],
        ["Rating", rating]
        ]
    message = tabulate(l_mess,tablefmt='html')
    return message

# Xu ly data trophy
def handle_data_trophies(json_trophy_data):
    l_data = json_trophy_data["response"]
    no = 1
    l_mess = []
    for trophy in l_data:
        league = trophy["league"]
        country = trophy["country"]
        s_season = " ("+trophy["season"]+")"
        place = trophy["place"]
        if place == "Winner":
            trophy = str(no)+" - "+league+s_season
            if "UEFA Champions League" in league:
                trophy = f'<div id="c1">{trophy}</div>'
            elif "FIFA World Cup" in league:
                trophy = f'<div id="wc">{trophy}</div>'
            elif "UEFA Europa League" in league:
                trophy = f'<div id="c2">{trophy}</div>'
            l_cup = [trophy, country]
        else:
            continue
        no+=1
        l_mess.append(l_cup)
    no_trophies = no -1
    message = tabulate(l_mess, tablefmt='html')
    return message, no_trophies

# Xu ly data top score
def handle_data_top_score(json_data,this_season,this_league):
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

        name = f'<img align="left" width="38" height="38" src="/images/players/{player_id}.png" loading="lazy">' +\
                f'<a href="/players/{player_id}/{this_season}/{this_league}">' + data["player"]["name"] + "</a>"
        club = f'<img align="left" width="28" height="28" src="/images/teams/{team_id}.png" loading="lazy">'+\
                f'<a href="/teams/{team_id}/{this_season}/{this_league}">' + data["statistics"][0]['team']["name"] + "</a>"
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
def handle_data_top_assist(json_data,this_season,this_league):
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

        name = f'<img align="left" width="38" height="38" src="/images/players/{player_id}.png" loading="lazy">' +\
                f'<a href="/players/{player_id}/{this_season}/{this_league}">' + data["player"]["name"] + "</a>"
        club = f'<img align="left" width="28" height="28" src="/images/teams/{team_id}.png" loading="lazy">'+\
                f'<a href="/teams/{team_id}/{this_season}/{this_league}">' + data["statistics"][0]['team']["name"] + "</a>"
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
