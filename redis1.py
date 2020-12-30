import json
import http.client
import redis

host="18.141.168.235"
password = "QY7vI9mVEFJV1tKF"
redis_server = redis.Redis(host=host, port=6379, db=0, password=password)
all_keys = redis_server.keys()
all_keys = [key.decode("utf-8") for key in all_keys]
print(all_keys)

def get_val(key):
    for key in all_keys:
        val= redis_server.hgetall(key)
        return val

league_id = "39"
season = "2011"
s_key = season+"_"+league_id

# def get_data():
#     conn = http.client.HTTPSConnection("v3.football.api-sports.io")

#     headers = {
#         "x-rapidapi-host": "v3.football.api-sports.io",
#         "x-rapidapi-key": "19f9bf9793df4f07694b4f8f2d32ef2c"
#         }

#     league_id = "135"
#     season = "2011"
#     # query = "/leagues?id={}".format(league_id)
#     query = "/standings?league={}&season={}".format(league_id,season)
#     # query = "/leagues?country=germany"
#     conn.request("GET", query, headers=headers)

#     res = conn.getresponse()
#     data = res.read()
#     json_data = json.loads(data.decode("utf-8"))
#     print(json_data,type(json_data))
#     return json_data

# d_value = get_data()
# d_value = {"get": "leagues", 
#             "parameters": {"country": "germany"},
#             "errors": [], 
#             "results": 12, 
#             "paging": {"current": 1, "total": 1}, 
#             "response": {"league": {"id": 78, "name": "Bundesliga 1", "type": "League", "logo": "https://media.api-sports.io/football/leagues/78.png"}}
# }
d_value = {'get': 'standings', 'parameters': {'league': '135', 'season': '2011'}, 'errors': [], 'results': 1, 'paging': {'current': 1, 'total': 1}, 'response': [{'league': {'id': 135, 'name': 'Serie A', 'country': 'Italy', 'logo': 'https://media.api-sports.io/football/leagues/135.png', 'flag': 'https://media.api-sports.io/flags/it.svg', 'season': 2011, 'standings': [[{'rank': 1, 'team': {'id': 496, 'name': 'Juventus', 'logo': 'https://media.api-sports.io/football/teams/496.png'}, 'points': 84, 'goalsDiff': 48, 'group': 'Serie A', 'form': 'WWDWW', 'status': None, 'description': 'UEFA Champions League', 'all': {'played': 38, 'win': 23, 'draw': 15, 'lose': 0, 'goals': {'for': 68, 'against': 20}}, 'home': {'played': 19, 'win': 13, 'draw': 6, 'lose': 0, 'goals': {'for': 40, 'against': 12}}, 'away': {'played': 19, 'win': 10, 'draw': 9, 'lose': 0, 'goals': {'for': 28, 'against': 8}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 2, 'team': {'id': 489, 'name': 'AC Milan', 'logo': 'https://media.api-sports.io/football/teams/489.png'}, 'points': 80, 'goalsDiff': 41, 'group': 'Serie A', 'form': 'WLWWW', 'status': None, 'description': 'UEFA Champions League', 'all': {'played': 38, 'win': 24, 'draw': 8, 'lose': 6, 'goals': {'for': 74, 'against': 33}}, 'home': {'played': 19, 'win': 12, 'draw': 5, 'lose': 2, 'goals': {'for': 36, 'against': 11}}, 'away': {'played': 19, 'win': 12, 'draw': 3, 'lose': 4, 'goals': {'for': 38, 'against': 22}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 3, 'team': {'id': 494, 'name': 'Udinese', 'logo': 'https://media.api-sports.io/football/teams/494.png'}, 'points': 64, 'goalsDiff': 17, 'group': 'Serie A', 'form': 'WWWWL', 'status': None, 'description': 'UEFA Champions League Qualifiers', 'all': {'played': 38, 'win': 18, 'draw': 10, 'lose': 10, 'goals': {'for': 52, 'against': 35}}, 'home': {'played': 19, 'win': 13, 'draw': 4, 'lose': 2, 'goals': {'for': 33, 'against': 13}}, 'away': {'played': 19, 'win': 5, 'draw': 6, 'lose': 8, 'goals': {'for': 19, 'against': 22}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 4, 'team': {'id': 487, 'name': 'Lazio', 'logo': 'https://media.api-sports.io/football/teams/487.png'}, 'points': 62, 'goalsDiff': 9, 'group': 'Serie A', 'form': 'WWDLL', 'status': None, 'description': 'UEFA Europa League', 'all': {'played': 38, 'win': 18, 'draw': 8, 'lose': 12, 'goals': {'for': 56, 'against': 47}}, 'home': {'played': 19, 'win': 10, 'draw': 6, 'lose': 3, 'goals': {'for': 28, 'against': 16}}, 'away': {'played': 19, 'win': 8, 'draw': 2, 'lose': 9, 'goals': {'for': 28, 'against': 31}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 5, 'team': {'id': 492, 'name': 'Napoli', 'logo': 'https://media.api-sports.io/football/teams/492.png'}, 'points': 61, 'goalsDiff': 20, 'group': 'Serie A', 'form': 'WLWDW', 'status': None, 'description': 'UEFA Europa League', 'all': {'played': 38, 'win': 16, 'draw': 13, 'lose': 9, 'goals': {'for': 66, 'against': 46}}, 'home': {'played': 19, 'win': 10, 'draw': 6, 'lose': 3, 'goals': {'for': 39, 'against': 22}}, 'away': {'played': 19, 'win': 6, 'draw': 7, 'lose': 6, 'goals': {'for': 27, 'against': 24}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 6, 'team': {'id': 505, 'name': 'Inter', 'logo': 'https://media.api-sports.io/football/teams/505.png'}, 'points': 58, 'goalsDiff': 3, 'group': 'Serie A', 'form': 'LWLWW', 'status': None, 'description': None, 'all': {'played': 38, 'win': 17, 'draw': 7, 'lose': 14, 'goals': {'for': 58, 'against': 55}}, 'home': {'played': 19, 'win': 10, 'draw': 4, 'lose': 5, 'goals': {'for': 36, 'against': 27}}, 'away': {'played': 19, 'win': 7, 'draw': 3, 'lose': 9, 'goals': {'for': 22, 'against': 28}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 7, 'team': {'id': 497, 'name': 'AS Roma', 'logo': 'https://media.api-sports.io/football/teams/497.png'}, 'points': 56, 'goalsDiff': 6, 'group': 'Serie A', 'form': 'WDDDL', 'status': None, 'description': None, 'all': {'played': 38, 'win': 16, 'draw': 8, 'lose': 14, 'goals': {'for': 60, 'against': 54}}, 'home': {'played': 19, 'win': 10, 'draw': 5, 'lose': 4, 'goals': {'for': 39, 'against': 22}}, 'away': {'played': 19, 'win': 6, 'draw': 3, 'lose': 10, 'goals': {'for': 21, 'against': 32}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 8, 'team': {'id': 523, 'name': 'Parma', 'logo': 'https://media.api-sports.io/football/teams/523.png'}, 'points': 56, 'goalsDiff': 1, 'group': 'Serie A', 'form': 'WWWWW', 'status': None, 'description': None, 'all': {'played': 38, 'win': 15, 'draw': 11, 'lose': 12, 'goals': {'for': 54, 'against': 53}}, 'home': {'played': 19, 'win': 10, 'draw': 5, 'lose': 4, 'goals': {'for': 34, 'against': 20}}, 'away': {'played': 19, 'win': 5, 'draw': 6, 'lose': 8, 'goals': {'for': 20, 'against': 33}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 9, 'team': {'id': 500, 'name': 'Bologna', 'logo': 'https://media.api-sports.io/football/teams/500.png'}, 'points': 51, 'goalsDiff': -2, 'group': 'Serie A', 'form': 'LWWWD', 'status': None, 'description': None, 'all': {'played': 38, 'win': 13, 'draw': 12, 'lose': 13, 'goals': {'for': 41, 'against': 43}}, 'home': {'played': 19, 'win': 8, 'draw': 4, 'lose': 7, 'goals': {'for': 23, 'against': 24}}, 'away': {'played': 19, 'win': 5, 'draw': 8, 'lose': 6, 'goals': {'for': 18, 'against': 19}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 10, 'team': {'id': 491, 'name': 'Chievo', 'logo': 'https://media.api-sports.io/football/teams/491.png'}, 'points': 49, 'goalsDiff': -10, 'group': 'Serie A', 'form': 'WDDDL', 'status': None, 'description': None, 'all': {'played': 38, 'win': 12, 'draw': 13, 'lose': 13, 'goals': {'for': 35, 'against': 45}}, 'home': {'played': 19, 'win': 8, 'draw': 6, 'lose': 5, 'goals': {'for': 16, 'against': 15}}, 'away': {'played': 19, 'win': 4, 'draw': 7, 'lose': 8, 'goals': {'for': 19, 'against': 30}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 11, 'team': {'id': 1580, 'name': 'Catania', 'logo': 'https://media.api-sports.io/football/teams/1580.png'}, 'points': 48, 'goalsDiff': -5, 'group': 'Serie A', 'form': 'LDLDL', 'status': None, 'description': None, 'all': {'played': 38, 'win': 11, 'draw': 15, 'lose': 12, 'goals': {'for': 47, 'against': 52}}, 'home': {'played': 19, 'win': 9, 'draw': 5, 'lose': 5, 'goals': {'for': 24, 'against': 15}}, 'away': {'played': 19, 'win': 2, 'draw': 10, 'lose': 7, 'goals': {'for': 23, 'against': 37}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 12, 'team': {'id': 499, 'name': 'Atalanta', 'logo': 'https://media.api-sports.io/football/teams/499.png'}, 'points': 46, 'goalsDiff': -2, 'group': 'Serie A', 'form': 'LLLWW', 'status': None, 'description': None, 'all': {'played': 38, 'win': 13, 'draw': 13, 'lose': 12, 'goals': {'for': 41, 'against': 43}}, 'home': {'played': 19, 'win': 9, 'draw': 6, 'lose': 4, 'goals': {'for': 23, 'against': 15}}, 'away': {'played': 19, 'win': 4, 'draw': 7, 'lose': 8, 'goals': {'for': 18, 'against': 28}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 13, 'team': {'id': 502, 'name': 'Fiorentina', 'logo': 'https://media.api-sports.io/football/teams/502.png'}, 'points': 46, 'goalsDiff': -6, 'group': 'Serie A', 'form': 'DWDLW', 'status': None, 'description': None, 'all': {'played': 38, 'win': 11, 'draw': 13, 'lose': 14, 'goals': {'for': 37, 'against': 43}}, 'home': {'played': 19, 'win': 7, 'draw': 7, 'lose': 5, 'goals': {'for': 24, 'against': 22}}, 'away': {'played': 19, 'win': 4, 'draw': 6, 'lose': 9, 'goals': {'for': 13, 'against': 21}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 14, 'team': {'id': 1583, 'name': 'Robur Siena', 'logo': 'https://media.api-sports.io/football/teams/1583.png'}, 'points': 44, 'goalsDiff': 0, 'group': 'Serie A', 'form': 'LLDLD', 'status': None, 'description': None, 'all': {'played': 38, 'win': 11, 'draw': 11, 'lose': 16, 'goals': {'for': 45, 'against': 45}}, 'home': {'played': 19, 'win': 8, 'draw': 4, 'lose': 7, 'goals': {'for': 27, 'against': 19}}, 'away': {'played': 19, 'win': 3, 'draw': 7, 'lose': 9, 'goals': {'for': 18, 'against': 26}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 15, 'team': {'id': 490, 'name': 'Cagliari', 'logo': 'https://media.api-sports.io/football/teams/490.png'}, 'points': 43, 'goalsDiff': -9, 'group': 'Serie A', 'form': 'DLLDW', 'status': None, 'description': None, 'all': {'played': 38, 'win': 10, 'draw': 13, 'lose': 15, 'goals': {'for': 37, 'against': 46}}, 'home': {'played': 19, 'win': 7, 'draw': 8, 'lose': 4, 'goals': {'for': 23, 'against': 16}}, 'away': {'played': 19, 'win': 3, 'draw': 5, 'lose': 11, 'goals': {'for': 14, 'against': 30}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 16, 'team': {'id': 522, 'name': 'Palermo', 'logo': 'https://media.api-sports.io/football/teams/522.png'}, 'points': 43, 'goalsDiff': -10, 'group': 'Serie A', 'form': 'LDLDL', 'status': None, 'description': None, 'all': {'played': 38, 'win': 11, 'draw': 10, 'lose': 17, 'goals': {'for': 52, 'against': 62}}, 'home': {'played': 19, 'win': 10, 'draw': 3, 'lose': 6, 'goals': {'for': 38, 'against': 30}}, 'away': {'played': 19, 'win': 1, 'draw': 7, 'lose': 11, 'goals': {'for': 14, 'against': 32}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 17, 'team': {'id': 495, 'name': 'Genoa', 'logo': 'https://media.api-sports.io/football/teams/495.png'}, 'points': 42, 'goalsDiff': -19, 'group': 'Serie A', 'form': 'WLWLL', 'status': None, 'description': None, 'all': {'played': 38, 'win': 11, 'draw': 9, 'lose': 18, 'goals': {'for': 50, 'against': 69}}, 'home': {'played': 19, 'win': 9, 'draw': 6, 'lose': 4, 'goals': {'for': 29, 'against': 24}}, 'away': {'played': 19, 'win': 2, 'draw': 3, 'lose': 14, 'goals': {'for': 21, 'against': 45}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 18, 'team': {'id': 867, 'name': 'Lecce', 'logo': 'https://media.api-sports.io/football/teams/867.png'}, 'points': 36, 'goalsDiff': -16, 'group': 'Serie A', 'form': 'LLDLL', 'status': None, 'description': 'Relegation', 'all': {'played': 38, 'win': 8, 'draw': 12, 'lose': 18, 'goals': {'for': 40, 'against': 56}}, 'home': {'played': 19, 'win': 3, 'draw': 6, 'lose': 10, 'goals': {'for': 22, 'against': 29}}, 'away': {'played': 19, 'win': 5, 'draw': 6, 'lose': 8, 'goals': {'for': 18, 'against': 27}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 19, 'team': {'id': 513, 'name': 'Novara', 'logo': 'https://media.api-sports.io/football/teams/513.png'}, 'points': 32, 'goalsDiff': -30, 'group': 'Serie A', 'form': 'LWDLW', 'status': None, 'description': 'Relegation', 'all': {'played': 38, 'win': 7, 'draw': 11, 'lose': 20, 'goals': {'for': 35, 'against': 65}}, 'home': {'played': 19, 'win': 5, 'draw': 8, 'lose': 6, 'goals': {'for': 20, 'against': 27}}, 'away': {'played': 19, 'win': 2, 'draw': 3, 'lose': 14, 'goals': {'for': 15, 'against': 38}}, 'update': '2018-02-15T00:00:00+00:00'}, {'rank': 20, 'team': {'id': 509, 'name': 'Cesena', 'logo': 'https://media.api-sports.io/football/teams/509.png'}, 'points': 22, 'goalsDiff': -36, 'group': 'Serie A', 'form': 'LLLLL', 'status': None, 'description': 'Relegation', 'all': {'played': 38, 'win': 4, 'draw': 10, 'lose': 24, 'goals': {'for': 24, 'against': 60}}, 'home': {'played': 19, 'win': 2, 'draw': 7, 'lose': 10, 'goals': {'for': 15, 'against': 24}}, 'away': {'played': 19, 'win': 2, 'draw': 3, 'lose': 14, 'goals': {'for': 9, 'against': 36}}, 'update': '2018-02-15T00:00:00+00:00'}]]}}]}


def save_in_redis(keyy,d_value):
    print(type(d_value))
    # valuee = json.dumps(d_value,indent=2).encode("utf-8")
    valuee = json.dumps(d_value)
    valuee = {"value":valuee}
    with redis_server.pipeline() as pipe:
        # for h_id, item in d_value.items():
        # pipe.hmset(h_id, item)
        pipe.hmset(keyy, valuee)
        pipe.execute()
    redis_server.bgsave()

save_in_redis(s_key,d_value)

for key in all_keys:
    val = get_val(key)
    # print(key,"===> value: ",val)

def get_value_redis(str_key):
    d_b_value = redis_server.hgetall(str_key)
    d_value = {k.decode("utf-8"):v.decode("utf-8") for k,v in d_b_value.items()}
    return d_value

json_data = get_value_redis(s_key)
# print(json_data,type(json_data))
json_data = json.loads(json_data["value"])
print(json_data)
# d_data = json_data["response"][0]
# l_standings = d_data["league"]["standings"]
# print(l_standings)