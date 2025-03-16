import json
import redis
from geopy.distance import geodesic

redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

def get_stored_disasters():
    return json.loads(redis_client.get("disaster_events") or "[]")

def calculate_distance(event_location, disaster_location):
    return geodesic(
        (event_location[0], event_location[1]),
        (disaster_location[1], disaster_location[0])
    ).km

def match_event_to_disasters(user_event):
    disasters = get_stored_disasters()
    event_location = user_event.get("coordinates")  # [lat, lon]

    nearby_disasters = list(filter(
        lambda disaster: calculate_distance(event_location, disaster["coordinates"]) < 50,
        disasters
    ))

    return {
        "alert": bool(nearby_disasters),
        "event": user_event,
        "disasters": nearby_disasters,
        "distances_km": [calculate_distance(event_location, d["coordinates"]) for d in nearby_disasters]
    }
