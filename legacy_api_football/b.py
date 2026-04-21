import http.client

conn = http.client.HTTPSConnection("v3.football.api-sports.io")

headers = {
    'x-apisports-key': "bb06910dd83d28059d99aa19cf518b43"
    }

conn.request("GET", "/coachs?search=Zidane", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))