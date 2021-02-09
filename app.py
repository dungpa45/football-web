import http.client
import os
import json
import redis
import datetime

from flask import Flask, render_template, request, redirect, url_for
from tabulate import tabulate
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("host")
PASSWORD = os.getenv("password")
API_HOST = os.getenv("x-rapidapi-host")
API_KEY = os.getenv("x-rapidapi-key")
redis_server = redis.Redis(host=HOST, port=6379, db=0, password=PASSWORD)
all_keys = redis_server.keys()

conn = http.client.HTTPSConnection("v3.football.api-sports.io")
headers = {
    'x-rapidapi-host': API_HOST,
    'x-rapidapi-key': API_KEY
    }

d_league = {
    "epl":"39",
    "laliga":"140",
    "seriea":"135",
    "bundes":"78",
    "ligue1":"61"
}

app = Flask(__name__)

def get_all_key_redis():
    all_keys = redis_server.keys()
    all_keys = [key.decode("utf-8") for key in all_keys]
    # print(all_keys)
    return all_keys

def get_value_redis(str_key):
    d_b_value = redis_server.hgetall(str_key)
    d_value = {k.decode("utf-8"):v.decode("utf-8") for k,v in d_b_value.items()}
    return d_value

def save_in_redis(keyy,d_value):
    print(type(d_value))
    # valuee = json.dumps(d_value,indent=2).encode("utf-8")
    valuee = json.dumps(d_value)
    valuee = {"value":valuee}
    time = datetime.datetime.now()
    this_year = time.year
    that_year = this_year - 1
    try:
        with redis_server.pipeline() as pipe:
            # save key in redis
            pipe.hmset(keyy, valuee)
            # expire key
            print("keyy",keyy)
            if str(this_year) in keyy or str(that_year) in keyy:
                pipe.expire(keyy,86400)
            pipe.execute()
        redis_server.bgsave()
    except Exception as e:
        print(e)
    print("save done")

def get_data_redis(s_key):
    json_data = get_value_redis(s_key)
    # print(json_data,type(json_data))
    json_data = json.loads(json_data["value"])
    # print(l_standings)
    return json_data

def get_data_standing(season,league_value): 
    league_id = d_league[league_value]
    print(league_id)
    # season = "2019"
    query = f"/standings?league={league_id}&season={season}"
    conn.request("GET", query, headers=headers)
    print(query)
    res = conn.getresponse()
    data = res.read()
    json_data = json.loads(data.decode("utf-8"))
    # print(json_data)
    return json_data

def get_top_score(season,league_value):
    # print("####################",league_value)
    league_id = d_league[league_value]
    query = f"/players/topscorers?season={season}&league={league_id}"
    conn.request("GET", query, headers=headers)
    res = conn.getresponse()
    data = res.read()
    json_data = json.loads(data.decode("utf-8"))
    return json_data

def get_team_info(team_id):
    query = f"/teams?id={team_id}"
    conn.request("GET", query, headers=headers)
    res = conn.getresponse()
    data = res.read()
    json_data = json.loads(data.decode("utf-8"))
    return json_data

def get_name_season_league(json_data):
    d_data = json_data["response"][0]
    name_league = d_data["league"]["name"]
    season_league = d_data["league"]["season"]
    season_league = str(season_league) + "-" +str(season_league+1)
    logo = d_data["league"]["logo"]
    return name_league, season_league, logo

def get_season_name(json_data):
    d_data = json_data["response"][0]["statistics"][0]
    n_season = d_data["league"]["season"]
    name_league = d_data["league"]["name"]
    id = d_data["league"]["id"]
    season_league = str(n_season) + "-" +str(n_season+1)
    logo = url_for('static',filename="league_logo/"+str(id)+'.png')
    print("LOGO",logo)
    return name_league, season_league, logo

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

def handle_data_top_score(json_data,this_season):
    d_data = json_data["response"]
    rank = 1
    this_season
    l_mess = []
    for data in d_data:
        photo = data["player"]["photo"]
        logo = data["statistics"][0]["team"]["logo"]
        club = f'<img align="left" width="28" height="28" src="{logo}">' + data["statistics"][0]["team"]["name"]
        name = f'<img align="left" width="38" height="38" src="{photo}">' + data["player"]["name"] 
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

@app.route("/standing/<n_season>/<s_league>",methods=["GET","POST"])
def standing_(n_season, s_league):
    str_key = n_season+"_"+s_league
    print("==>",str_key)
    list_keys = get_all_key_redis()
    #check data in redis
    if str_key in list_keys:
        dic_data = get_data_redis(str_key)
        list_data = handle_data_standing(dic_data)
    #get data from api-football
    else:
        dic_data = get_data_standing(n_season,s_league)
        save_in_redis(str_key,dic_data)
        list_data = handle_data_standing(dic_data)
    # list_data = get_data_standing(n_season,s_league)
    league_season = get_name_season_league(dic_data)
    list_data = list_data.replace('&lt;','<')
    list_data = list_data.replace('&gt;','>')
    list_data = list_data.replace('&quot;','"')
    list_data = list_data.replace('<table>','<table id="myTableLeague" class="w3-table-all w3-medium sortable">')
    return render_template("standing.html",listitem=list_data, n_season=n_season,s_league=s_league,
            league=league_season[0],season=league_season[1], logo_image=league_season[2])

@app.route("/teams/<team_id>",methods=["GET","POST"])
def team_infomation(team_id):
    str_key = "Team_"+team_id
    list_keys = get_all_key_redis()
    #check data in redis
    if str_key in list_keys:
        dic_data = get_data_redis(str_key)
        list_data = handle_data_team_info(dic_data)
    #get data from api-football
    else:
        dic_data = get_team_info(team_id)
        save_in_redis(str_key,dic_data)
        list_data = handle_data_team_info(dic_data)
    list_data = list_data.replace('&lt;','<')
    list_data = list_data.replace('&gt;','>')
    list_data = list_data.replace('&quot;','"')
    list_data = list_data.replace('<table>','<table id="myTable" class="w3-table-all w3-medium">')
    return render_template("team_info.html",listitem=list_data)

@app.route("/topscorers/<n_season>/<s_league>",methods=["GET","POST"]) 
def topscorers(n_season, s_league):
    str_key = "TopScore-"+n_season+"_"+s_league
    print("==>",str_key)
    list_keys = get_all_key_redis()
    #check data in redis
    if str_key in list_keys:
        dic_data = get_data_redis(str_key)
        list_data = handle_data_top_score(dic_data,n_season)
    #get data from api-football
    else:
        dic_data = get_top_score(n_season,s_league)
        save_in_redis(str_key,dic_data)
        list_data = handle_data_top_score(dic_data,n_season)
    
    league_season = get_season_name(dic_data)
    print(n_season,type(n_season),s_league,type(s_league))
    list_data = list_data.replace('&lt;','<')
    list_data = list_data.replace('&gt;','>')
    list_data = list_data.replace('&quot;','"')
    list_data = list_data.replace('<table>','<table id="TopScoreTable" class="w3-table-all w3-medium sortable">')
    return render_template("topscore.html",listitem=list_data,n_season=n_season,s_league=s_league,
            league=league_season[0],season=league_season[1], logo_image=league_season[2]
    )

@app.route("/",methods=["GET","POST"])
def main():
    if request.method == "GET":
        return render_template("home.html")
    elif request.method == "POST":
        n_season = request.form.get("season")
        s_league = request.form.get("league")
        if request.form.get("action") == "Standings":
            return redirect(url_for('standing_',n_season=n_season,s_league=s_league))
        elif request.form.get("action") == "TopScore":
            return redirect(url_for('topscorers',n_season=n_season,s_league=s_league))

if __name__ == "__main__":
    app.run(debug=True)