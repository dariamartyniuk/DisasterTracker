from collections import Counter

from geopy.distance import geodesic
from redis import Redis
from mappingModule.geo_utils import get_coordinates_from_location
import requests
import logging
import json

REDIS_HOST = "localhost"
redis_client = Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

def get_stored_disasters():
    """Retrieve disaster events from Redis."""
    data = redis_client.get("disaster_events")
    return json.loads(data) if data else []

def store_disasters(disasters):
    """Store disaster events in Redis."""
    if disasters:
        redis_client.set("disaster_events", json.dumps(disasters), ex=3600)
        print(f"Stored {len(disasters)} disaster events in Redis")

def geocode_location(event):
    """Get coordinates from location or fallback."""
    location_name = event.get('location', '').strip()
    return get_coordinates_from_location(location_name) if location_name else get_coordinates_from_location(location_name)

def build_disaster(event):
    """Build disaster data structure."""
    coordinates = geocode_location(event)
    if coordinates:
        return {
            "id": event['id'],
            "title": event['title'],
            "coordinates": coordinates,  # [latitude, longitude]
            "category": event['categories'][0]['title'],
            "date": event['geometry'][0]['date']
        }
    return None

def fetch_disaster_events():
    """Fetch disaster events from EONET API and store in Redis."""

    url = "https://eonet.gsfc.nasa.gov/api/v3/events"

    try:
        logging.info(f"Fetching disasters from: {url} ")
        response = requests.get(url, timeout=1000)
        response.raise_for_status()

        raw_data = response.json()
        events = raw_data.get('events', [])

        if not events:
            logging.warning("No disaster events found in API response.")
            return []

        logging.info(f"Found {len(events)} disaster events.")

        disaster_list = [
            {
                "id": event['id'],
                "title": event['title'],
                "coordinates": geo['coordinates'],  # [longitude, latitude]
                "category": event['categories'][0]['title'],
                "date": geo['date']
            }
            for event in events if event.get('geometry')
            for geo in event['geometry']
        ]

        redis_client.set("disaster_events", json.dumps(disaster_list), ex=3600)
        logging.info(f"Stored {len(disaster_list)} disasters in Redis.")

        return disaster_list

    except requests.exceptions.RequestException as e:
        logging.error(f"API Request Failed: {e}")
        return []

    except Exception as e:
        logging.error(f"Unexpected Error: {e}", exc_info=True)
        return []


def get_hotspots(threshold=3):
    """Identifies high-risk locations based on disaster event frequency."""
    disasters = get_stored_disasters()

    if not disasters:
        return {"status": "Success", "hotspots": []}

    location_counts = Counter(
        (d["coordinates"][1], d["coordinates"][0]) for d in disasters if "coordinates" in d and d["coordinates"]
    )

    hotspots = [
        {"location": coords, "occurrences": count}
        for coords, count in location_counts.items() if count >= threshold
    ]

    hotspots.sort(key=lambda x: x["occurrences"], reverse=True)

    return {"status": "Success", "hotspots": hotspots}


def match_event_to_disasters(user_event):
    disasters = get_stored_disasters()
    event_location = user_event.get("location")

    # Geocode the location to get coordinates
    event_coordinates = get_coordinates_from_location(event_location)

    if not event_coordinates:
        logging.warning(f"Skipping event {user_event.get('summary', 'Unknown')} - Missing or invalid coordinates.")
        return {"alert": False}

    matched_disasters = list(filter(
        lambda disaster: geodesic(
            (event_coordinates[0], event_coordinates[1]),
            (disaster["coordinates"][1], disaster["coordinates"][0])
        ).km < 500000,
        disasters
    ))

    if matched_disasters:
        return {
            "alert": True,
            "event": user_event,
            "disasters": matched_disasters,
            "distances_km": list(map(
                lambda disaster: geodesic(
                    (event_coordinates[0], event_coordinates[1]),
                    (disaster["coordinates"][1], disaster["coordinates"][0])
                ).km, matched_disasters))
        }

    return {"alert": False}
