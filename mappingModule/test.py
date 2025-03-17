import redis
import json
import logging

from mappingModule.event_matcher import get_stored_disasters

# Connect to Redis
REDIS_HOST = "localhost"
redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

test_disasters = [
    {
        "id": "test_event_2",
        "title": "Test Earthquake",
        "coordinates": [50.4501, 30.5236],
        "category": "Earthquake",
        "date": "2025-03-17"
    }
]
redis_client.set("disaster_events", json.dumps(test_disasters))

stored_disasters = get_stored_disasters()
print(stored_disasters)

