import json
import logging
from flask import Flask, jsonify
import redis

from matching import process_events, calculate_date_range

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Flask(__name__)

def get_raw_events():
    """
    Reads raw events from Redis under key 'raw_events'.
    These events are expected to be JSON strings.
    """
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        raw_data = r.lrange("raw_events", 0, -1)
        events = [json.loads(item) for item in raw_data]
        logging.debug("Retrieved raw events: " + str(events))
        return events
    except Exception as e:
        logging.error("Error retrieving raw events from Redis: " + str(e))
        return []

def store_processed_events(processed_events):
    """
    Stores the processed (matched) events in Redis under the key 'matched_events'.
    """
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.delete("matched_events")
        for event in processed_events:
            r.rpush("matched_events", json.dumps(event))
        logging.info(f"Stored {len(processed_events)} matched events in Redis.")
    except Exception as e:
        logging.error("Error storing processed events in Redis: " + str(e))

@app.route('/update-processed-events', methods=['POST'])
def update_processed_events():
    """
    This endpoint triggers the processing of raw events.
    It reads raw events, calculates the date range, processes them,
    and stores the resulting processed events in Redis.
    """
    try:
        raw_events = get_raw_events()
        if not raw_events:
            return jsonify({"message": "No raw events available"}), 404

        date_from, date_to = calculate_date_range(raw_events)
        logging.info(f"Calculated date range: {date_from} to {date_to}")

        processed = process_events(raw_events, date_from, date_to)
        logging.info("Processed events: " + str(processed))

        store_processed_events(processed)

        return jsonify({
            "message": "Processed events updated successfully",
            "processed_events": processed
        })
    except Exception as e:
        logging.error("Error updating processed events: " + str(e))
        return jsonify({"message": "Error processing events"}), 500

@app.route('/processed-events', methods=['GET'])
def get_processed_events():
    """
    This endpoint retrieves the processed events from Redis.
    Other modules (e.g., UI) can call this endpoint to get the enriched events.
    """
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        events_data = r.lrange("matched_events", 0, -1)
        processed_events = [json.loads(item) for item in events_data]
        return jsonify(processed_events)
    except Exception as e:
        logging.error("Error fetching processed events: " + str(e))
        return jsonify({"message": "Error fetching processed events"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5003, debug=True)
