import pymongo, os
from dotenv import load_dotenv

load_dotenv()

USERMONGO = os.getenv("username")
PASSMONGO = os.getenv("password")

# myclient = pymongo.MongoClient(f"mongodb://{USERMONGO}:{PASSMONGO}@mongodb:27017/")
myclient = pymongo.MongoClient(f"mongodb://{USERMONGO}:{PASSMONGO}@localhost:27017/")
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