import os
import pymongo
from dotenv import load_dotenv
from urllib.parse import quote_plus
load_dotenv()

USERMONGO = os.getenv("username")
PASSMONGO = quote_plus(os.getenv("password"))

# myclient = pymongo.MongoClient(f"mongodb://{USERMONGO}:{PASSMONGO}@mongodb:27017/")
myclient = pymongo.MongoClient(f"mongodb+srv://{USERMONGO}:{PASSMONGO}@cluster0.wbx8bpm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

my_db = myclient['football']

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