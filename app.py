import os
import random
import string
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory
from datetime import datetime
from handle_data import *
from mongo import *

load_dotenv()

API_HOST = os.getenv("x-rapidapi-host")
API_KEY = os.getenv("x-rapidapi-key")

secret = ''.join(random.choices(string.ascii_letters + string.digits, k=20))

headers = {
    'x-rapidapi-host': API_HOST,
    'x-rapidapi-key': API_KEY
    }

d_league = {
    "epl":"39",
    "laliga":"140",
    "seriea":"135",
    "bundes":"78",
    "ligue1":"61",
    "euro_cup":"4",
    "worldcup":"1"
}
id_name = {
    "39":"Premier League",
    "140":"La Liga",
    "135":"Serie A",
    "78":"Bundesliga",
    "61":"Ligue 1",
    "4":"Euro Championship",
    "1": "World Cup"
}

app = Flask(__name__)
app.secret_key = secret

def json_process(query):
    try:
        res = requests.request("GET", "https://"+API_HOST+query, headers=headers)
        res.raise_for_status()  # Raise an HTTPError for bad responses
        d_json = res.json()
        return d_json
    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        return None
    except ValueError as e:
        print(f"JSON decoding failed: {e}")
        return None

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

def get_season_name(json_data):
    d_data = json_data["parameters"]
    n_season = d_data["season"]
    id = d_data["league"]
    name_league = id_name[id]
    season_league = str(n_season) + "-" +str(int(n_season)+1)
    logo = url_for('static',filename="league_logo/"+str(id)+'.png')
    return name_league, season_league, logo

def get_team_info(team_id):
    query = f"/teams?id={team_id}"
    json_data = json_process(query)
    return json_data

def get_player_info(player_id, n_season):
    query = f"/players?id={player_id}&season={n_season}"
    json_data = json_process(query)
    return json_data

def get_player_trophies(player_id):
    query = f"/trophies?player={player_id}"
    json_data = json_process(query)
    return json_data

def get_coach_trophies(coach_id):
    query = f"/trophies?coach={coach_id}"
    json_data = json_process(query)
    return json_data

def get_squads(team_id):
    query = f"/players/squads?team={team_id}"
    json_data = json_process(query)
    return json_data

def get_coachs(team_id):
    query = f"/coachs?team={team_id}"
    json_data = json_process(query)
    return json_data

def get_transfer(player_id):
    query = f"/transfers?player={player_id}"
    json_data = json_process(query)
    return json_data

def is_euro_wc(str_league):
    if "euro" in str_league:
        return "eu"
    elif "worldcup" in str_league:
        return "wc"
    else:
        pass

def get_this_season(summer_cup=None):
    currentYear = datetime.now().year
    currentMonth = datetime.now().month
    # check thang hien tai
    # print("summer_cup",summer_cup)
    if currentMonth <= 8:
        if currentMonth in [6,7] and summer_cup == "eu":
            data = {"season":str(currentYear)}
        elif currentMonth in [6,7] and summer_cup == "wc":
            data = {"season":str(currentYear)}
        else:
            data = {"season":str(currentYear-1)}
            currentYear = currentYear -1
    else:
        data = {"season":str(currentYear)}
    # check co data trong mongo voi current_season
    check_data = get_data_mongo("current_season",{})
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
        print("Update current season")
        update_in_mongo("current_season",{"season":str(currentYear-1)},data)
        my_coll = my_db["current_season"]
        n_this_season = my_coll.find_one()["season"]
    return n_this_season


# ========================================================
# =============== ROUTE ==================================
# Site standing of league
@app.route("/standing/<n_season>/<s_league>",methods=["GET","POST"])
def standing_league(n_season, s_league):
    this_season = str(get_this_season())
    my_query = {"parameters": {"league":d_league[s_league],"season":str(n_season)}}
    d_result = get_data_mongo("standing",my_query)
    # check data in mongo
    if d_result is not None:
        dic_data = d_result
        list_data = handle_data_standing(dic_data,n_season)
        if this_season == n_season:
            print("get from api standing")
            dic_data_new = get_data_standing(n_season,s_league)
            update_in_mongo("standing",dic_data,dic_data_new)
            list_data = handle_data_standing(dic_data,n_season)
        else:
            dic_data = d_result
            list_data = handle_data_standing(dic_data,n_season)
    #get data from api-football
    else:
        dic_data = get_data_standing(n_season,s_league)
        save_in_mongo("standing",dic_data)
        list_data = handle_data_standing(dic_data,n_season)
    league_season = get_season_name(dic_data)
    list_data = html_replace(list_data)
    s_league_session = session.get("s_league",None)
    n_season_session = session.get("n_season",None)
    return render_template("standing.html",listitem=list_data,n_season=n_season_session,s_league=s_league_session,
            league=league_season[0],season=league_season[1], logo_image=league_season[2]
    )

# Site standing of cup
@app.route("/standing_cup/<n_season>/<s_league>",methods=["GET","POST"])
def standing_cup(n_season, s_league):
    this_season = str(get_this_season(is_euro_wc(s_league)))
    my_query = {"parameters": {"league":d_league[s_league],"season":str(n_season)}}
    d_result = get_data_mongo("standing",my_query)
    # check data in mongo
    if d_result is not None:
        dic_data = d_result
        try:
            list_data = handle_data_cup_standing(dic_data,n_season,s_league)
        except Exception as e:
            return redirect(request.referrer)
        if this_season == n_season:
            print("get from api cup standing")
            dic_data_new = get_data_standing(n_season,s_league)
            update_in_mongo("standing",dic_data,dic_data_new)
            list_data = handle_data_cup_standing(dic_data,n_season,s_league)
        else:
            dic_data = d_result
            list_data = handle_data_cup_standing(dic_data,n_season,s_league)
    #get data from api-football
    else:
        dic_data = get_data_standing(n_season,s_league)
        save_in_mongo("standing",dic_data)
        list_data = handle_data_cup_standing(dic_data,n_season,s_league)
    league_season = get_season_name(dic_data)
    # print(list_data)
    
    s_league_session = session.get("s_league",None)
    n_season_session = session.get("n_season",None)
    return render_template("standing-cup.html",tables=list_data[0],third_place_table=list_data[1],n_season=n_season_session,s_league=s_league_session,
            league=league_season[0],season=league_season[1], logo_image=league_season[2]
    )


# Site team of league
@app.route("/teams/<team_id>/<n_season>",methods=["GET","POST"])
def team_infomation(team_id,n_season):
    this_season = get_this_season()
    team_query = {"parameters": {"id":str(team_id)}}
    squad_query = {"parameters": {"team":str(team_id)}}
    coach_query = {"parameters": {"team":str(team_id)}}
    team_result = get_data_mongo("teams",team_query)
    squad_result = get_data_mongo("squads",squad_query)
    coach_result = get_data_mongo("coachs",coach_query)
    
    #get data from api-football
    if team_result is None or squad_result is None or coach_result is None:
        team_data = get_team_info(team_id)
        list_team_data = handle_data_team_info(team_data)
        save_in_mongo("teams",team_data)
        squad_data = get_squads(team_id)
        list_squad_data = handle_data_squad(squad_data,n_season)
        save_in_mongo("squads",squad_data)
        coach_data = handle_multi_coach(get_coachs(team_id))
        
        save_in_mongo("coachs",coach_data)
        list_coach_data = handle_coach_for_team(coach_data,team_id)
    # check data in mongo
    else:
        list_team_data = handle_data_team_info(team_result)
        list_squad_data = handle_data_squad(squad_result,n_season)
        list_coach_data = handle_coach_for_team(coach_result,team_id)

    list_team_data = html_replace(list_team_data)
    list_squad_data = html_replace(list_squad_data)

    s_league = session.get("s_league",None)
    n_season = session.get("n_season",None)
    return render_template("team_info.html",listitem = list_team_data, list_squad=list_squad_data,
                           list_coach=list_coach_data, n_season=n_season, s_league=s_league)

# Site coach info
@app.route("/coachs/<coach_id>/<team_id>",methods=["GET","POST"])
def coach_infomation(coach_id,team_id):
    coach_query = {"parameters": {"team":str(team_id)}}
    trophies_query = {"parameters": {"coach":str(coach_id)}}
    d_coach_mongo = get_data_mongo("coachs",coach_query)
    d_trophies_mongo = get_data_mongo("trophies",trophies_query)
    
    # Get data from api
    if d_coach_mongo is None:
        d_data = get_coachs(team_id)
        save_in_mongo("coachs",d_data)
        l_data_coach = handle_data_coach(d_data)
        career_data = d_data["response"][0]
    else:
        l_data_coach = handle_data_coach(d_coach_mongo)
        career_data = d_coach_mongo["response"][0]
    
    # Get career start date
    career = career_data["career"]
    first_job = min(career, key=lambda x: x["start"])
    career_start = first_job["start"]
    
    # Get trophies data
    if d_trophies_mongo is None:
        d_trophies_data = get_coach_trophies(coach_id)
        trophies, num_trophies = handle_data_coach_trophies(d_trophies_data, career_start)
        save_in_mongo("trophies",d_trophies_data)
    else:
        trophies, num_trophies = handle_data_coach_trophies(d_trophies_mongo, career_start)
    
    # Separate trophies into coach and player sections
    coach_trophies = [t for t in trophies if t["is_coach"]]
    player_trophies = [t for t in trophies if not t["is_coach"]]
    num_coach_trophies = len(coach_trophies)
    num_player_trophies = len(player_trophies)
    
    # Calculate additional statistics
    last_job = max(career, key=lambda x: x["end"] if x["end"] else "9999")
    start_year = int(career_start.split("-")[0])
    end_year = int(last_job["end"].split("-")[0]) if last_job["end"] else datetime.now().year
    career_years = end_year - start_year
    
    # Count teams managed
    teams_managed = len(set(job["team"]["id"] for job in career))
    
    s_league = session.get("s_league",None)
    n_season = session.get("n_season",None)
    # Pass n_season to handle_data_coach for correct team links
    l_info_coach = html_replace(l_data_coach[0])
    l_career_coach = html_replace(handle_data_coach(d_coach_mongo, n_season)[1])
    return render_template("coach_info.html",
                         listinfo=l_info_coach, 
                         listcareer=l_career_coach,
                         coach_trophies=coach_trophies,
                         player_trophies=player_trophies,
                         no_trophies=num_trophies,
                         num_coach_trophies=num_coach_trophies,
                         num_player_trophies=num_player_trophies,
                         career_years=career_years,
                         teams_managed=teams_managed,
                         n_season=n_season, 
                         s_league=s_league)
# Site player info's of league
@app.route("/players/<player_id>/<n_season>",methods=["GET","POST"])
def player_infomation(n_season,player_id):
    player_query = {"parameters": {"id":str(player_id),"season":str(n_season)}}
    trophies_query = {"parameters": {"player":str(player_id)}}
    transfer_query = {"parameters": {"player":str(player_id)}}
    d_player_mongo = get_data_mongo("players",player_query)
    d_trophies_mongo = get_data_mongo("trophies",trophies_query)
    d_transfer_mongo = get_data_mongo("transfers",trophies_query)
    # get data from api-football
    if d_player_mongo is None or d_trophies_mongo is None or d_transfer_mongo is None:
        # infomation
        dic_data = get_player_info(player_id,n_season)
        player_info = handle_data_player_info(dic_data)
        save_in_mongo("players",dic_data)
        # trophies
        d_trophies_data = get_player_trophies(player_id)
        trophies, num_trophies = handle_data_trophies(d_trophies_data)
        save_in_mongo("trophies",d_trophies_data)
        # transfers
        d_transfer_data = get_transfer(player_id)
        career_history = handle_data_transfer(d_transfer_data, n_season)
        save_in_mongo("transfers",d_transfer_data)
    # check data in mongo
    else:
        player_info = handle_data_player_info(d_player_mongo)
        trophies, num_trophies = handle_data_trophies(d_trophies_mongo)
        career_history = handle_data_transfer(d_transfer_mongo, n_season)

    # Calculate total transfer fee
    total_transfer_fee = 0
    for move in career_history:
        fee = move.get("fee", "")
        fee_style = fee.replace(",", "").replace("€", "").replace("$", "").replace("M", "").replace("m", "").replace("Loan", "0").replace(" ", "")
        # Remove currency symbols and commas, try to convert to int
        if isinstance(fee, str) and isinstance(float(fee_style), float):
            try:
                total_transfer_fee += float(fee_style)
            except Exception:
                pass
    # Format as currency (Euro)
    total_transfer_fee_formatted = f"€{total_transfer_fee:,}" if total_transfer_fee else "-"

    s_league = session.get("s_league",None)
    n_season = session.get("n_season",None)
    return render_template("player_info.html",n_season=n_season,s_league=s_league,
                           player_info=player_info, trophies=trophies, 
                           no_trophies=num_trophies, career_history=career_history,
                           total_transfer_fee=total_transfer_fee_formatted
                           )

# Site topscorers of league
@app.route("/topscorers/<n_season>/<s_league>",methods=["GET","POST"]) 
def topscorers(n_season, s_league):
    this_season = str(get_this_season(is_euro_wc(s_league)))
    my_query = {"parameters": {"season":str(n_season),"league":d_league[s_league]}}
    d_result = get_data_mongo("topscorers",my_query)

    #get data from api-football
    if d_result is None:
        dic_data = get_top_score(n_season,s_league)
        save_in_mongo("topscorers",dic_data)
        list_data = handle_data_top_score(dic_data,n_season)
    # check data in mongo
    else:
        if this_season == n_season:
            print("get from score api")
            dic_data = get_top_score(n_season,s_league)
            update_in_mongo("topscorers",d_result,dic_data)
            list_data = handle_data_top_score(dic_data,n_season)
        else:
            dic_data = d_result
            list_data = handle_data_top_score(d_result,n_season)
    
    league_season = get_season_name(dic_data)
    print(n_season,type(n_season),s_league,type(s_league))
    list_data = html_replace(list_data)
    
    s_league_session = session.get("s_league",None)
    n_season_session = session.get("n_season",None)
    if "cup" in s_league:
        return render_template("topscore-cup.html",listitem=list_data,n_season=n_season_session,s_league=s_league_session,
                league=league_season[0],season=league_season[1], logo_image=league_season[2]
        )
    else:
        return render_template("topscore.html",listitem=list_data,n_season=n_season_session,s_league=s_league_session,
                league=league_season[0],season=league_season[1], logo_image=league_season[2]
        )

# Site topassists of league
@app.route("/topassists/<n_season>/<s_league>",methods=["GET","POST"]) 
def topassists(n_season, s_league):
    this_season = str(get_this_season(is_euro_wc(s_league)))
    my_query = {"parameters": {"season":str(n_season),"league":d_league[s_league]}}
    d_result = get_data_mongo("topassists",my_query)

    #get data from api-football
    if d_result is None:
        dic_data = get_top_assist(n_season,s_league)
        save_in_mongo("topassists",dic_data)
        list_data = handle_data_top_assist(dic_data,n_season)
    # check data in mongo
    else:
        if this_season == n_season:
            print("get from assist api")
            dic_data = get_top_assist(n_season,s_league)
            update_in_mongo("topscorers",d_result,dic_data)
            list_data = handle_data_top_assist(dic_data,n_season)
        else:
            dic_data = d_result
            list_data = handle_data_top_assist(d_result,n_season)
    
    league_season = get_season_name(dic_data)
    list_data = html_replace(list_data)
    
    s_league_session = session.get("s_league",None)
    n_season_session = session.get("n_season",None)
    if "cup" in s_league:
        return render_template("topassist-cup.html",listitem=list_data,n_season=n_season_session,s_league=s_league_session,
                league=league_season[0],season=league_season[1], logo_image=league_season[2]
        )
    else:
        return render_template("topassist.html",listitem=list_data,n_season=n_season_session,s_league=s_league_session,
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
        # print("================")
        print(n_season,s_league)
        # Store value in session
        session['s_league'] = s_league
        session['n_season'] = n_season
        # League select
        if request.form.get("league-type") == "Standings":
            return redirect(url_for('standing_league',n_season=n_season,s_league=s_league))
        elif request.form.get("league-type") == "TopScore":
            return redirect(url_for('topscorers',n_season=n_season,s_league=s_league))
        elif request.form.get("league-type") == "TopAssist":
            return redirect(url_for('topassists',n_season=n_season,s_league=s_league))
        # Cup select
        elif request.form.get("cup") == "Standings":
            return redirect(url_for('standing_cup',n_season=n_season,s_league=s_league))
        elif request.form.get("cup") == "TopScore":
            return redirect(url_for('topscorers',n_season=n_season,s_league=s_league))
        elif request.form.get("cup") == "TopAssist":
            return redirect(url_for('topassists',n_season=n_season,s_league=s_league))
        else:
            print(request.form.get("league"))
if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0")