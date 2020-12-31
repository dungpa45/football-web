from flask import Flask, render_template, request
import http.client
from tabulate import tabulate
from dotenv import load_dotenv
import os
import json
import redis

load_dotenv()

HOST =os.getenv("host")
PASSWORD =os.getenv("password")

redis_server = redis.Redis(host=HOST, port=6379, db=0, password=PASSWORD)
all_keys = redis_server.keys()

app = Flask(__name__)

def get_all_key_redis():
    all_keys = redis_server.keys()
    all_keys = [key.decode("utf-8") for key in all_keys]
    print(all_keys)
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
    try:
        with redis_server.pipeline() as pipe:
            # save key in redis
            pipe.hmset(keyy, valuee)
            # expire key
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

def get_data_api(season,league_value):
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': "19f9bf9793df4f07694b4f8f2d32ef2c"
        }
    d_league = {
        "epl":"39",
        "laliga":"140",
        "seriea":"135",
        "bundes":"78",
        "ligue1":"61"
    }
    league_id = d_league[league_value]
    print(league_id)
    # season = "2019"
    query = f"/standings?league={league_id}&season={season}"
    conn.request("GET", query, headers=headers)

    res = conn.getresponse()
    data = res.read()
    json_data = json.loads(data.decode("utf-8"))
    # print(json_data)
    return json_data

def handle_data_standing(json_data):
    d_data = json_data["response"][0]
    l_standings = d_data["league"]["standings"]
    l_mess = []
    for team in l_standings[0]:
        # print(team)
        logo = team['team']['logo']
        rank = team['rank']
        name = f'<img align="left" width="28" height="28" src="{logo}"></img>'+team['team']["name"]
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

@app.route("/",methods=["GET","POST"])
def main():
    if request.method == "GET":
        return render_template("home.html")
    elif request.method == "POST":
        n_season = request.form.get("season")
        s_league = request.form.get("league")
        str_key = n_season+"_"+s_league
        print("==>",str_key)
        list_keys = get_all_key_redis()
        #check data in redis
        if str_key in list_keys:
            dic_data = get_data_redis(str_key)
            list_data = handle_data_standing(dic_data)

        #get data from api-football
        else:
            dic_data = get_data_api(n_season,s_league)
            save_in_redis(str_key,dic_data)
            list_data = handle_data_standing(dic_data)
        # list_data = get_data_api(n_season,s_league)
        list_data = list_data.replace('&lt;','<')
        list_data = list_data.replace('&gt;','>')
        list_data = list_data.replace('&quot;','"')
        list_data = list_data.replace('<table>','<table id="myTable" class="w3-table-all w3-medium">')
        return render_template("standing.html",listitem=list_data)

# @app.route("/standing")
# def standing():
#     list_data = get_data_api()
#     list_data = list_data.replace('<table>','<table class="w3-table-all w3-small">')
#     # result = result.replace('</table>','<table class="w3-table-all w3-small">')
#     return render_template('standing.html',listitem=list_data)


if __name__ == "__main__":
    app.run(debug=True)