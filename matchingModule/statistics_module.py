# hotspots.py

import logging
import sys
import requests
import redis
import json
from datetime import datetime, timedelta
from config import Config

# Logging setup: output logs to console
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(stream=sys.stdout)]
)

def fetch_disasters_bulk(date_from: str, date_to: str):
    """
    Loads natural disasters from the EONET API for a given date range.
    """
    try:
        response = requests.get(Config.EONET_EVENTS_API_URL, params={"start": date_from, "end": date_to})
        response.raise_for_status()
        disasters = response.json().get("events", [])
        logging.info(f"Retrieved {len(disasters)} events for the range {date_from} - {date_to}")
        return disasters
    except Exception as e:
        logging.error(f"Error loading events from API: {e}")
        return []

def store_disasters_in_redis(disasters):
    """
    Stores the retrieved natural disasters in Redis under the key 'disasters'.
    Deletes previous data before saving.
    """
    try:
        r = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB, decode_responses=True)
        r.delete(Config.REDIS_DISASTERS_KEY)
        logging.info("Saving event data to Redis...")
        for disaster in disasters:
            # Convert dictionary to JSON string
            disaster_json = json.dumps(disaster, ensure_ascii=False)
            logging.debug(f"Saving record:\n{disaster_json}")
            r.rpush(Config.REDIS_DISASTERS_KEY, disaster_json)
        logging.info(f"{len(disasters)} events saved to Redis.")
    except Exception as e:
        logging.error(f"Error saving data to Redis: {e}")

def get_disasters_from_redis():
    """
    Reads natural disaster data from Redis and returns a list of dictionaries.
    """
    try:
        r = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB, decode_responses=True)
        data = r.lrange(Config.REDIS_DISASTERS_KEY, 0, -1)
        disasters = [json.loads(item) for item in data]
        logging.info(f"Read {len(disasters)} events from Redis.")
        return disasters
    except Exception as e:
        logging.error(f"Error reading data from Redis: {e}")
        return []

