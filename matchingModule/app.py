import os
import json
import logging
from flask import Flask, request, jsonify
import redis
from matching import process_events, calculate_date_range

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Flask(__name__)

def clear_processed_events():
    """
    Clears only the processed events from Redis (key 'matched_events').
    Note: We are not flushing the entire DB so the raw events remain intact.
    """
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.delete("matched_events")
        logging.info("Redis: Processed events (matched_events) key cleared.")
    except Exception as e:
        logging.error("Error clearing processed events from Redis: " + str(e))

def get_raw_events():
    """
    Reads raw events stored in Redis under the key 'raw_events'.
    These events are expected to be stored as JSON strings.
    """
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        raw_data = r.lrange("raw_events", 0, -1)
        events = [json.loads(item) for item in raw_data]
        # Log a summary of raw events (make sure the "start" field is still present)
        for event in events:
            if "start" not in event:
                logging.error(f"Raw event with id {event.get('id', 'UNKNOWN')} is missing 'start' field!")
            else:
                logging.debug(f"Raw event {event['id']} has start time {event['start']}")
        return events
    except Exception as e:
        logging.error("Error reading raw events from Redis: " + str(e))
        return []

def store_processed_events(processed_events):
    """
    Stores processed events in Redis under the key 'matched_events'.
    Previous data under that key is removed.
    """
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.delete("matched_events")
        logging.info("Cleared 'matched_events' key in Redis.")
        for event in processed_events:
            event_json = json.dumps(event, ensure_ascii=False)
            logging.debug("Storing processed event: " + event_json)
            r.rpush("matched_events", event_json)
        logging.info(f"Stored {len(processed_events)} processed events in Redis.")
    except Exception as e:
        logging.error("Error storing processed events in Redis: " + str(e))

@app.route('/update-processed-events', methods=['POST'])
def update_processed_events():
    """
    Endpoint that performs the following steps:
      1. Deletes only the processed events (so raw events remain).
      2. Retrieves raw events from Redis (raw events must contain a valid "start" field).
      3. Calculates a date range based on these events.
      4. Processes the events (i.e. matches disasters using matching.py logic).
      5. Stores the processed events back to Redis.
    """
    try:
        # Remove only the processed events—not all data
        clear_processed_events()

        raw_events = get_raw_events()
        if not raw_events:
            return jsonify({"message": "No raw events found"}), 404

        # For safety, log one raw event sample so we can inspect the structure
        logging.debug(f"Sample raw event: {raw_events[0]}")

        # Calculate the disaster query date range based on event start times.
        # This will fail if any event is missing the "start" field.
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
    Endpoint returns the processed events (matched_events) from Redis.
    Other modules (e.g., UI) may call this endpoint to retrieve processed event data.
    """
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        events_data = r.lrange("matched_events", 0, -1)
        processed_events = [json.loads(item) for item in events_data]
        logging.debug("Processed events retrieved from Redis: " + str(processed_events))
        return jsonify(processed_events)
    except Exception as e:
        logging.error("Error fetching processed events: " + str(e))
        return jsonify({"message": "Error fetching processed events"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5003, debug=True)
