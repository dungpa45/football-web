import os
import requests
import pymongo
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from dotenv import load_dotenv
from datetime import datetime
from handle_data import *

load_dotenv()

API_HOST = os.getenv("x-rapidapi-host")
API_KEY = os.getenv("x-rapidapi-key")
USERMONGO = os.getenv("username")
PASSMONGO = os.getenv("password")

myclient = pymongo.MongoClient(f"mongodb://{USERMONGO}:{PASSMONGO}@mongodb:27017/")
# myclient = pymongo.MongoClient(f"mongodb://{USERMONGO}:{PASSMONGO}@localhost:27017/")
my_db = myclient['football']

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

def save_in_mongo(coll_name,data):
    my_coll = my_db[coll_name]
    my_coll.insert_one(data)

def update_in_mongo(coll_name,old_data,new_data):
    mycol = my_db[coll_name]
    newdata = {"$set": new_data}
    mycol.update_one(old_data, newdata)

def get_data_mongo(coll_name,query):
    mycol = my_db[coll_name]
    mydoc = mycol.find(query)
    for data in mydoc:
        return data

def json_process(query):
    res = requests.request("GET", "https://"+API_HOST+query, headers=headers)
    d_json = res.json()
    return d_json

def html_replace(data):
    data_html = data.replace('&lt;','<').replace('&gt;','>').replace('&quot;','"').replace('<table>','').replace('</table>','')
    return data_html

def get_data_standing(season,league_value): 
    league_id = d_league[league_value]
    query = f"/standings?league={league_id}&season={season}"
    json_data = json_process(query)
    return json_data

def get_top_score(season,league_value):
    league_id = d_league[league_value]
    query = f"/players/topscorers?season={season}&league={league_id}"
    json_data = json_process(query)
    return json_data

def get_top_assist(season,league_value):
    league_id = d_league[league_value]
    query = f"/players/topassists?season={season}&league={league_id}"
    json_data = json_process(query)
    return json_data

def get_name_season_league(json_data):
    d_data = json_data["response"][0]
    name_league = d_data["league"]["name"]
    id = d_data["league"]["id"]
    season_league = d_data["league"]["season"]
    season_league = str(season_league) + "-" +str(season_league+1)
    # logo = d_data["league"]["logo"]
    logo = url_for('static',filename="league_logo/"+str(id)+'.png')
    return name_league, season_league, logo

def get_season_name(json_data):
    d_data = json_data["response"][0]["statistics"][0]
    n_season = d_data["league"]["season"]
    name_league = d_data["league"]["name"]
    id = d_data["league"]["id"]
    season_league = str(n_season) + "-" +str(n_season+1)
    logo = url_for('static',filename="league_logo/"+str(id)+'.png')
    # print("LOGO",logo)
    return name_league, season_league, logo

def get_team_info(team_id):
    query = f"/teams?id={team_id}"
    json_data = json_process(query)
    return json_data

def get_player_info(player_id, n_season):
    query = f"/players?id={player_id}&season={n_season}"
    json_data = json_process(query)
    return json_data

def get_player_tropies(player_id):
    query = f"/trophies?player={player_id}"
    json_data = json_process(query)
    return json_data

def get_squads(team_id):
    query = f"/players/squads?team={team_id}"
    json_data = json_process(query)
    return json_data

def get_this_season():
    currentYear = datetime.now().year
    currentMonth = datetime.now().month
    # check thang hien tai
    if currentMonth <= 8:
        data = {"season":str(currentYear-1)}
        currentYear = currentYear -1
    else:
        data = {"season":str(currentYear)}
    # check co data trong mongo voi current_season
    check_data = get_data_mongo("current_season",{"season":str(currentYear)})
    if check_data is None:
        save_in_mongo("current_season",data)
        # try:
        #     print("data",data)
        #     update_in_mongo("current_season",{"season":str(currentYear-1)},data)
        # except:
        #     print("data",data)
        #     save_in_mongo("current_season",data)
        n_this_season = currentYear
    else:
        update_in_mongo("current_season",{"season":str(currentYear-1)},data)
        my_coll = my_db["current_season"]
        n_this_season = my_coll.find_one()["season"]
    return n_this_season

# =============== ROUTE ==================================
# Site standing of league
@app.route("/standing/<n_season>/<s_league>",methods=["GET","POST"])
def standing_(n_season, s_league):
    this_season = str(get_this_season())
    print("this season",type(this_season))
    print("n_season",type(n_season))
    my_query = {"parameters": {"league":d_league[s_league],"season":str(n_season)}}
    d_result = get_data_mongo("standing",my_query)
    # check data in mongo
    if d_result is not None:
        dic_data = d_result
        list_data = handle_data_standing(dic_data,s_league,n_season)
        if this_season == n_season:
            print("vao day nao")
            dic_data = get_data_standing(n_season,s_league)
            save_in_mongo("standing",dic_data)
            list_data = handle_data_standing(dic_data,s_league,n_season)
        else:
            dic_data = d_result
            list_data = handle_data_standing(dic_data,s_league,n_season)
    #get data from api-football
    else:
        dic_data = get_data_standing(n_season,s_league)
        save_in_mongo("standing",dic_data)
        list_data = handle_data_standing(dic_data,s_league,n_season)
    league_season = get_name_season_league(dic_data)
    # print(list_data)
    list_data = html_replace(list_data)
    return render_template("standing.html",listitem=list_data, n_season=n_season,s_league=s_league,
            league=league_season[0],season=league_season[1], logo_image=league_season[2])

# Site team of league
@app.route("/teams/<team_id>/<n_season>/<s_league>",methods=["GET","POST"])
def team_infomation(team_id,s_league,n_season):
    this_season = get_this_season()
    team_query = {"parameters": {"id":str(team_id)}}
    squad_query = {"parameters": {"team":str(team_id)}}
    team_result = get_data_mongo("teams",team_query)
    squad_result = get_data_mongo("squads",squad_query)
    
    #get data from api-football
    if team_result is None or squad_result is None:
        team_data = get_team_info(team_id)
        list_team_data = handle_data_team_info(team_data)
        save_in_mongo("teams",team_data)
        squad_data = get_squads(team_id)
        list_squad_data = handle_data_squad(squad_data,s_league,n_season)
        save_in_mongo("squads",squad_data)
    # check data in mongo
    else:
        list_team_data = handle_data_team_info(team_result)
        list_squad_data = handle_data_squad(squad_result,s_league,n_season)

    list_team_data = html_replace(list_team_data)
    list_squad_data = html_replace(list_squad_data)
    return render_template("team_info.html",listitem = list_team_data, list_squad=list_squad_data,
                           n_season=n_season,s_league=s_league)

# Site player info's of league
@app.route("/players/<player_id>/<n_season>/<s_league>",methods=["GET","POST"])
def player_infomation(n_season,s_league,player_id):
    player_query = {"parameters": {"id":str(player_id),"season":str(n_season)}}
    trophies_query = {"parameters": {"player":str(player_id)}}
    d_player_mongo = get_data_mongo("players",player_query)
    d_trophies_mongo = get_data_mongo("trophies",trophies_query)
    # get data from api-football
    if d_player_mongo is None or d_trophies_mongo is None:
        dic_data = get_player_info(player_id,n_season)
        save_in_mongo("players",dic_data)
        d_trophies_data = get_player_tropies(player_id)
        print("data cup")
        list_data = handle_data_player_info(dic_data)
        list_trop_data = handle_data_trophies(d_trophies_data)
        save_in_mongo("trophies",d_trophies_data)
    # check data in mongo
    else:
        list_data = handle_data_player_info(d_player_mongo)
        list_trop_data = handle_data_trophies(d_trophies_mongo)

    list_data = html_replace(list_data)
    l_trop_data = html_replace(list_trop_data[0])
    num_trophies = list_trop_data[1]
    print(type(n_season),n_season)
    return render_template("player_info.html",listitem = list_data, list_trop = l_trop_data, no_trophies=num_trophies, 
                           n_season=n_season,s_league=s_league)

# Site topscorers of league
@app.route("/topscorers/<n_season>/<s_league>",methods=["GET","POST"]) 
def topscorers(n_season, s_league):
    this_season = str(get_this_season())
    my_query = {"parameters": {"season":str(n_season),"league":d_league[s_league]}}
    d_result = get_data_mongo("topscorers",my_query)

    #get data from api-football
    if d_result is None:
        print("None")
        dic_data = get_top_score(n_season,s_league)
        save_in_mongo("topscorers",dic_data)
        list_data = handle_data_top_score(dic_data,n_season,s_league)
    # check data in mongo
    else:
        if this_season == n_season:
            dic_data = get_top_score(n_season,s_league)
            save_in_mongo("topscorers",dic_data)
            list_data = handle_data_top_score(dic_data,n_season,s_league)
        else:
            dic_data = d_result
            list_data = handle_data_top_score(d_result,n_season,s_league)
    
    league_season = get_season_name(dic_data)
    print(n_season,type(n_season),s_league,type(s_league))
    list_data = html_replace(list_data)
    return render_template("topscore.html",listitem=list_data,n_season=n_season,s_league=s_league,
            league=league_season[0],season=league_season[1], logo_image=league_season[2]
    )

# Site topassists of league
@app.route("/topassists/<n_season>/<s_league>",methods=["GET","POST"]) 
def topassists(n_season, s_league):
    this_season = str(get_this_season())
    my_query = {"parameters": {"season":str(n_season),"league":d_league[s_league]}}
    d_result = get_data_mongo("topassists",my_query)

    #get data from api-football
    if d_result is None:
        print("None")
        dic_data = get_top_assist(n_season,s_league)
        save_in_mongo("topassists",dic_data)
        list_data = handle_data_top_assist(dic_data,n_season,s_league)
    # check data in mongo
    else:
        if this_season == n_season:
            dic_data = get_top_score(n_season,s_league)
            save_in_mongo("topscorers",dic_data)
            list_data = handle_data_top_score(dic_data,n_season,s_league)
        else:
            dic_data = d_result
            list_data = handle_data_top_assist(d_result,n_season,s_league)
    
    league_season = get_season_name(dic_data)
    print(n_season,type(n_season),s_league,type(s_league))
    list_data = html_replace(list_data)
    return render_template("topassist.html",listitem=list_data,n_season=n_season,s_league=s_league,
            league=league_season[0],season=league_season[1], logo_image=league_season[2]
    )

# Get image with path
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('images', filename)

# Site homepage
@app.route("/",methods=["GET","POST"])
def main():
    if request.method == "GET":
        return render_template("home.html")
    elif request.method == "POST":
        n_season = request.form.get("season")
        s_league = request.form.get("league")
        s_player = request.form.get("footballer")
        if request.form.get("action") == "Standings":
            return redirect(url_for('standing_',n_season=n_season,s_league=s_league))
        elif request.form.get("action") == "TopScore":
            return redirect(url_for('topscorers',n_season=n_season,s_league=s_league))
        elif request.form.get("action") == "TopAssist":
            return redirect(url_for('topassists',n_season=n_season,s_league=s_league))

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0")