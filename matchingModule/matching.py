import math

import requests
import logging
from datetime import datetime, timedelta
import redis
import json
from rx import from_iterable, operators as op
from dotenv import load_dotenv
from calendarModule.utils import establish_rabbitmq_connection, setup_rabbitmq
from flask import request, jsonify
from typing import List, Dict, Any, Optional, Tuple

from config import Config

# Set up logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

load_dotenv()

# Main URL for disaster API
EONET_EVENTS_API_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"

def calculate_date_range(events):
    logging.info(f"Received {len(events)} events for date range calculation: {events}")
    # Get the list of start times from events, sort them, then extend the range by 10 days before and after.
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
                # Note: Check coordinate order: disaster geo coordinates provided as [longitude, latitude]
                event_lat = geometry.get("coordinates")[1]
                event_lng = geometry.get("coordinates")[0]
                distance = haversine(coords["lat"], coords["lng"], event_lat, event_lng)
                logging.debug(f"Distance from event to disaster {disaster.get('id')}: {distance:.2f} km")
                if distance <= Config.DISTANCE:
                    return True
            return False
        except Exception as e:
            logging.error(f"Error calculating proximity: {e}")
            return False

    location = event.get("coordinates")
    if not location:
        logging.warning(f"Event '{event['id']}' is missing coordinates, skipping.")
        return []

    central_coords = calculate_central_coords(location)
    matched = from_iterable(disasters) \
        .pipe(
            op.filter(lambda disaster: is_disaster_near(central_coords, disaster)),
            op.to_list()
        ).run()
    logging.debug(f"Event {event.get('id')} matched disasters: {matched}")
    return matched

def haversine(lat1, lon1, lat2, lon2):
    # Radius of Earth in kilometers
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def process_events(events, date_from, date_to):
    logging.info(f"Processing {len(events)} events.")
    # Fetch disasters once for all events
    disasters = fetch_disasters_bulk(date_from, date_to)
    return from_iterable(events) \
        .pipe(
            op.map(lambda event: {
                **event,
                "matched_disasters": filter_disasters_for_event(event, disasters)
            }),
            op.filter(lambda event: len(event["matched_disasters"]) > 0),
            op.map(lambda event: {
                "id": event.get("id", "unknown"),
                "location": event.get("location", event.get("coordinates", {})),
                "summary": event.get("summary", ""),
                "matched_disasters": event["matched_disasters"]
            }),
            op.to_list()
        ).run()

def store_matched_events_in_redis(matched_results):
    try:
        r = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB, decode_responses=True)
        r.delete("matched_events")
        logging.info("Storing matched events in Redis...")
        for event in matched_results:
            # Log each event being stored with full details
            event_json = json.dumps(event, ensure_ascii=False, indent=2)
            logging.debug(f"Storing event:\n{event_json}")
            r.rpush("matched_events", json.dumps(event, ensure_ascii=False))
        logging.info(f"Stored {len(matched_results)} matched events in Redis.")
    except Exception as ex:
        logging.error(f"Error storing matched events in Redis: {ex}")

def update_hotspots_data(matched_results):
    """
    Update the hotspots data in Redis with the latest matched events.
    This function stores both the full event data and a simplified version for the map.
    
    Args:
        matched_results (list): List of matched events with their associated disasters
    """
    try:
        r = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB, decode_responses=True)
        
        # Store full event data
        r.delete("matched_events")
        logging.info("Storing matched events in Redis...")
        for event in matched_results:
            event_json = json.dumps(event, ensure_ascii=False, indent=2)
            logging.debug(f"Storing event:\n{event_json}")
            r.rpush("matched_events", json.dumps(event, ensure_ascii=False))
            
        # Store simplified version for map display
        r.delete("hotspots")
        for event in matched_results:
            hotspot = {
                "id": event["id"],
                "location": event["location"],
                "summary": event["summary"],
                "disaster_count": len(event["matched_disasters"]),
                "disaster_types": list(set(d.get("type", "Unknown") for d in event["matched_disasters"]))
            }
            r.rpush("hotspots", json.dumps(hotspot, ensure_ascii=False))
            
        logging.info(f"Successfully updated hotspots data with {len(matched_results)} events")
    except Exception as ex:
        logging.error(f"Error updating hotspots data in Redis: {ex}")
        raise

def consume_and_match_events():
    channel = establish_rabbitmq_connection()
    setup_rabbitmq(channel, exchange="calendar_events", queue_name="calendar_queue", routing_key="default")

    def callback(ch, method, properties, body):
        try:
            logging.info("Received message from RabbitMQ!")
            raw_data = json.loads(body.decode("utf-8"))
            logging.info(f"Raw message received: {raw_data}")

            # Normalize events (whether a single event or a batch)
            events = raw_data if isinstance(raw_data, list) else [raw_data]
            logging.info(f"Normalized events list: {events}")

            # Calculate date range for query based on events' start times
            date_from, date_to = calculate_date_range(events)
            logging.info(f"Calculated disaster query date range: {date_from} to {date_to}")

            # Process events for matching disasters
            matched_results = process_events(events, date_from, date_to)
            logging.info(f"Matched disaster results: {matched_results}")

            # Uncomment the following line if you wish to store the matched events in Redis
            store_matched_events_in_redis(matched_results)
        except Exception as e:
            logging.error(f"Error processing RabbitMQ message: {e}")

    channel.basic_consume(queue="calendar_queue", on_message_callback=callback, auto_ack=True)
    channel.start_consuming()


if __name__ == "__main__":
    logging.info("Starting Matching Module...")
    consume_and_match_events()