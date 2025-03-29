import json
import logging
from functools import reduce
from geopy.distance import geodesic
from redis import Redis
from mappingModule.geo_utils import get_coordinates_from_location
from typing import NamedTuple, Tuple
import pika

logging.basicConfig(level=logging.INFO)


def pipe(value, *funcs):
    return reduce(lambda v, f: f(v), funcs, value)


REDIS_HOST = "localhost"
redis_client = Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)


class DisasterEvent(NamedTuple):
    id: str
    title: str
    coordinates: tuple
    category: str
    date: str


def dict_to_disaster(d: dict) -> DisasterEvent:
    return DisasterEvent(
        id=d.get("id"),
        title=d.get("title"),
        coordinates=tuple(d.get("coordinates")) if d.get("coordinates") else None,
        category=d.get("category"),
        date=d.get("date")
    )


def extract_coordinates(d: dict) -> dict:
    if not d.get("coordinates") and d.get("geometry") and isinstance(d["geometry"], list) and len(d["geometry"]) > 0:
        first_geom = d["geometry"][0]
        if first_geom.get("coordinates"):
            d["coordinates"] = first_geom["coordinates"]
    return d


def filter_with_coordinates(disasters: list) -> list:
    return list(filter(lambda d: d.get("coordinates"), disasters))


def get_immutable_disasters(client=redis_client) -> Tuple[DisasterEvent, ...]:
    def load_key(key):
        return client.get(key) or "[]"

    data_real = load_key("disaster_events")
    data_test = load_key("test_disaster_events")
    disasters_list = json.loads(data_real) + json.loads(data_test)
    processed = pipe(
        disasters_list,
        lambda lst: map(extract_coordinates, lst),
        list,
        filter_with_coordinates
    )
    logging.info(f"Processed {len(processed)} disaster events from Redis (combined real and test)")
    return tuple(dict_to_disaster(d) for d in processed)


def store_disasters(disasters, client=redis_client):
    if disasters:
        client.set("disaster_events", json.dumps(disasters), ex=3600)
        logging.info(f"Stored {len(disasters)} disaster events in Redis")
    return disasters


def geocode_location(event):
    location = event.get('location', '').strip()
    return get_coordinates_from_location(location)


def calculate_distance(event_coords, disaster: DisasterEvent):
    return geodesic(
        (event_coords[0], event_coords[1]),
        (disaster.coordinates[1], disaster.coordinates[0])
    ).km


def publish_matched_event(result, rabbitmq_host="localhost", exchange="disaster_updates", routing_key="update"):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
        message = json.dumps(result, ensure_ascii=False)
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logging.info(f"Published matched event to exchange '{exchange}' with routing key '{routing_key}'")
        connection.close()
    except Exception as e:
        logging.error("Failed to publish matched event: %s", e)


def match_event_to_disasters(user_event, distance_threshold=500):
    logging.info(f"Starting disaster matching for event: {user_event.get('summary', 'Unknown')}")
    disasters = get_immutable_disasters()
    logging.info(f"Loaded {len(disasters)} disaster events from Redis.")

    event_location = user_event.get("location", "").strip()
    event_coords = get_coordinates_from_location(event_location)
    if not event_coords:
        logging.warning(f"Skipping event {user_event.get('summary', 'Unknown')} - Missing or invalid coordinates.")
        return {"alert": False}

    matched = list(
        filter(
            lambda tup: tup[1] < distance_threshold,
            map(lambda d: (d, calculate_distance(event_coords, d)), disasters)
        )
    )

    if matched:
        result = {
            "alert": True,
            "event": user_event,
            "disasters": list(map(lambda tup: tup[0]._asdict(), matched)),
            "distances_km": list(map(lambda tup: tup[1], matched))
        }
        publish_matched_event(result)
        return result
    logging.info("No matched disasters found for event.")
    return {"alert": False}
