import os
import pymongo
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

USERMONGO = os.getenv("username")
PASSMONGO = quote_plus(os.getenv("password") or "")

myclient = pymongo.MongoClient(
    f"mongodb+srv://{USERMONGO}:{PASSMONGO}@cluster0.wbx8bpm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)

my_db = myclient['football']
