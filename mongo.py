import os
import logging
import pymongo
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

logger = logging.getLogger(__name__)


def _mongo_uri():
    uri = os.getenv("MONGO_URI")
    if uri:
        return uri

    legacy_user = os.getenv("username")
    legacy_password = os.getenv("password")
    if (
        not os.getenv("MONGO_HOST")
        and legacy_user
        and legacy_password
    ):
        logger.warning(
            "Using legacy Atlas configuration; migrate to MONGO_URI. "
            "Set MONGO_HOST explicitly to use a local MongoDB."
        )
        return (
            f"mongodb+srv://{quote_plus(legacy_user)}:{quote_plus(legacy_password)}"
            "@cluster0.wbx8bpm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        )

    host = os.getenv("MONGO_HOST", "localhost")
    port = os.getenv("MONGO_PORT", "27017")
    username = os.getenv("MONGO_USER")
    password = os.getenv("MONGO_PASS")
    if bool(username) != bool(password):
        raise RuntimeError("MONGO_USER and MONGO_PASS must be configured together")

    if username and password:
        credentials = f"{quote_plus(username)}:{quote_plus(password)}@"
        return f"mongodb://{credentials}{host}:{port}/?authSource=admin"
    return f"mongodb://{host}:{port}/"


myclient = pymongo.MongoClient(
    _mongo_uri(),
    # Connection Pooling
    maxPoolSize=50,
    minPoolSize=5,
    maxConnecting=5,
    maxIdleTimeMS=60000,
    waitQueueTimeoutMS=5000,

    # Connection timeout
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=20000,

    # Monitoring
    heartbeatFrequencyMS=10000,

    # Timezone
    tz_aware=True,
)
my_db = myclient[os.getenv("MONGO_DB_NAME", "football")]
