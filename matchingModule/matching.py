import json
import logging

import redis
import requests
import math
from datetime import datetime, timedelta
from rx import from_iterable, operators as op
from dotenv import load_dotenv
from calendarModule.utils import establish_rabbitmq_connection, setup_rabbitmq

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()

# Main url for disaster api
EONET_EVENTS_API_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"

# Pipe for calculating disaster query date range based on event times - 10 days before first event, 10 days after last
def calculate_date_range(events):
    logging.info(f"Received {len(events)} events for date range calculation: {events}")
    return from_iterable(events) \
        .pipe(
            op.map(lambda event: datetime.fromisoformat(event["start"]["dateTime"].split("+")[0])),
            op.to_iterable(),
            op.map(lambda dates: sorted(dates)),
            op.map(lambda sorted_dates: (
                (sorted_dates[0] - timedelta(days=10)).date().isoformat(),
                (sorted_dates[-1] + timedelta(days=10)).date().isoformat()
            )),
            op.to_list()
        ).run()[0]

# Get disasters in bulk for a given date range
def fetch_disasters_bulk(date_from: str, date_to: str):
    try:
        response = requests.get(EONET_EVENTS_API_URL, params={"start": date_from, "end": date_to})
        response.raise_for_status()
        disasters = response.json().get("events", [])
        logging.info(f"Fetched {len(disasters)} disasters for the date range {date_from} to {date_to}")
        return disasters
    except Exception as e:
        logging.error(f"Error fetching bulk disasters: {e}")
        return []

# Match disasters to the event using proximity
def filter_disasters_for_event(event, disasters):
    def calculate_central_coords(location):
        bounds = location["northeast"], location["southwest"]
        return {
            "lat": (bounds[0]["lat"] + bounds[1]["lat"]) / 2,
            "lng": (bounds[0]["lng"] + bounds[1]["lng"]) / 2,
        }

    def is_disaster_near(coords, disaster):
        try:
            for geometry in disaster.get("geometry", []):
                event_lat, event_lng = geometry.get("coordinates")[1], geometry.get("coordinates")[0]
                distance = haversine(coords["lat"], coords["lng"], event_lat, event_lng)
                # 200 km threshold, could be changed for more precised check
                return distance <= 200
        except Exception as e:
            logging.error(f"Error calculating proximity: {e}")
        return False

    location = event.get("coordinates")
    # Validate events coordinates
    if not location:
        logging.warning(f"Event '{event['id']}' is missing coordinates, skipping.")
        return []

    central_coords = calculate_central_coords(location)
    return from_iterable(disasters) \
        .pipe(
            op.filter(lambda disaster: is_disaster_near(central_coords, disaster)),
            op.to_list()
        ).run()

# Calculate distance using Haversine formula (kudos to chatGPT for this function!)
def haversine(lat1, lon1, lat2, lon2):
    # Radius of Earth in kilometers
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Main pipe to match disasters
def process_events(events, date_from, date_to):
    logging.info(f"Processing {len(events)} events.")
    disasters = fetch_disasters_bulk(date_from, date_to)
    return from_iterable(events) \
        .pipe(
            op.map(lambda event: {**event, "matched_disasters": filter_disasters_for_event(event, disasters)}),
            # Only return events that have at least one matched disaster
            op.filter(lambda event: len(event["matched_disasters"]) > 0),
            op.to_list()
        ).run()

def store_matched_events_in_redis(matched_results):
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.delete("matched_events")
        for event in matched_results:
            r.rpush("matched_events", json.dumps(event))
        logging.info(f"Stored {matched_results} matched events in Redis.")
    except Exception as ex:
        logging.error(f"Error storing matched events in Redis: {ex}")

def consume_and_match_events():
    channel = establish_rabbitmq_connection()
    setup_rabbitmq(channel, exchange="calendar_events", queue_name="calendar_queue", routing_key="default")

    def callback(ch, method, properties, body):
        try:
            raw_data = json.loads(body.decode("utf-8"))
            logging.info(f"Raw message received: {raw_data}")
            events = raw_data if isinstance(raw_data, list) else [raw_data]
            logging.info(f"Normalized events list: {events}")

            date_from, date_to = calculate_date_range(events)
            logging.info(f"Calculated disaster query date range: {date_from} to {date_to}")

            matched_results = process_events(events, date_from, date_to)
            logging.info(f"Matched disaster results: {matched_results}")

            store_matched_events_in_redis(matched_results)

        except Exception as e:
            logging.error(f"Error processing RabbitMQ message: {e}")

    channel.basic_consume(queue="calendar_queue", on_message_callback=callback, auto_ack=True)
    channel.start_consuming()


if __name__ == "__main__":
    logging.info("Starting Matching Module...")
    consume_and_match_events()