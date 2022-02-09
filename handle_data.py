from tabulate import tabulate


def handle_data_standing(json_data):
    d_data = json_data["response"][0]
    l_standings = d_data["league"]["standings"]
    l_mess = []
    for team in l_standings[0]:
        # print(team)
        logo = team['team']['logo']
        team_id = team['team']['id']
        rank = team['rank']
        name = f'<img align="left" width="28" height="28" src="{logo}">'+\
                f'<a href="/teams/{team_id}">' + team['team']["name"] + "</a>"
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
    # print(message,type(message))
    return message

# xu ly data ve thong tin chi tiet 1 team
def handle_data_team_info(json_data):
    d_data = json_data["response"][0]
    team_name = d_data["team"]["name"]
    country = d_data["team"]["country"]
    founded = d_data["team"]["founded"]
    logo = d_data["team"]["logo"]
    logo = f'<img align="left" max-width="100px" height="auto" src="{logo}">'
    stadium = d_data["venue"]["name"]
    address = d_data["venue"]["address"]
    city = d_data["venue"]["city"]
    capacity = d_data["venue"]["capacity"]
    surface = d_data["venue"]["surface"]
    image = d_data["venue"]["image"]
    image = f'<img align="left" max-width="100px" height="auto" src="{image}">'
    l_mess = []
    # l_items = [team_name,country,founded,logo,stadium,address,city,capacity,surface,image]
    # l_mess.append(l_items)
    l_mess = [
        ["",logo],
        ["Team Name",team_name],["Country",country],
        ["Founded",founded],["Stadium",stadium],
        ["Address",address],["City",city],
        ["Capacity",capacity],["Surface",surface],
        ["",image]
        ]
    message = tabulate(l_mess,tablefmt='html')
    return message

# Xu ly data top score
def handle_data_top_score(json_data,this_season):
    d_data = json_data["response"]
    rank = 1
    this_season
    l_mess = []
    for data in d_data:
        photo = data["player"]["photo"]
        team_id = data["statistics"][0]['team']['id']
        logo = data["statistics"][0]["team"]["logo"]
        club = f'<img align="left" width="28" height="28" src="{logo}">' + data["statistics"][0]["team"]["name"]
        name = f'<img align="left" width="38" height="38" src="{photo}">' + data["player"]["name"]
        club = f'<img align="left" width="28" height="28" src="{logo}">'+\
                f'<a href="/teams/{team_id}">' + data["statistics"][0]['team']["name"] + "</a>"
        # age = data["player"]["age"]
        date = data["player"]["birth"]["date"]
        date = int(date.split("-")[0])
        age = int(this_season) - date
        nationality = data["player"]["nationality"]
        appearences = data["statistics"][0]["games"]["appearences"]
        rating = data["statistics"][0]["games"]["rating"]
        goals = data["statistics"][0]["goals"]["total"]
        assists = data["statistics"][0]["goals"]["assists"]
        goals = '<b>'+str(goals)+'</b>'
        list_topscore = [rank,name,age,club,nationality,goals,assists,appearences,rating]
        rank+=1
        l_mess.append(list_topscore)
    list_headers = ["Rank","Name","Age","Club","Country","Goals","Assists","App","Rating"]
    message = tabulate(l_mess, headers=list_headers,tablefmt='html', colalign=("left" for i in list_headers))
    return message