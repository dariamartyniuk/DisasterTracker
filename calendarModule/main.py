# Updated main.py
import json
import logging
import sys
import requests
from flask import Flask, redirect, request, jsonify

from get_calendar_events import get_events
from mappingModule.event_matcher import get_hotspots, match_event_to_disasters, redis_client
from utils import GoogleCalendarClient, establish_rabbitmq_connection, setup_rabbitmq, validate_date

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(stream=sys.stdout)]
)

app = Flask(__name__)
gc_client = GoogleCalendarClient()



@app.route("/login")
def login():
    try:
        logging.info("Redirecting user for Google Calendar authentication")
        gc_client.login_to_calendar()
        return redirect("http://localhost:5005/calendar")
    except Exception as error:
        logging.error(f"Login Error: {error}")
        return "Login Failed", 500

@app.route("/", methods=["GET"])
def events():
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    if not date_from or not date_to:
        logging.error("Missing required parameters: date_from and date_to")
        return jsonify({"status": "Error", "message": "Missing required parameters: date_from and date_to"}), 400

    try:
        validate_date(date_from)
        validate_date(date_to)

        # Fetch user calendar events
        service = gc_client.get_calendar_service()
        events = get_events(service, date_from, date_to)

        if not isinstance(events, dict):
            logging.error(f"Unexpected `events` type: {type(events)}. Expected dict.")
            return jsonify({"status": "Error", "message": "Invalid response from Google Calendar API"}), 500

        items = events.get('items', [])
        if not isinstance(items, list):
            logging.error(f"Unexpected `items` type: {type(items)}. Expected list.")
            items = []

        matched_events = [
            {
                **event,
                "disaster_alert": match_event_to_disasters({
                    "id": event.get("id"),
                    "coordinates": event.get("coordinates"),
                    "summary": event.get("summary"),
                    "start": event.get("start"),
                    "end": event.get("end")
                }) if event.get("coordinates") else {"alert": False}  # Skip events without coordinates
            }
            for event in items if isinstance(event, dict)
        ]

        return jsonify({"status": "Success", "events": matched_events})

    except Exception as e:
        logging.error(f"Service error: {e}", exc_info=True)
        return jsonify({"status": "Error", "message": "Internal Server Error"}), 500

@app.route("/hotspots", methods=["GET"])
def hotspots():
    try:
        hotspot_data = get_hotspots()
        return jsonify({"status": "Success", "hotspots": hotspot_data})
    except Exception as e:
        logging.error(f"Error fetching hotspots: {e}", exc_info=True)
        return jsonify({"status": "Error", "message": "Internal Server Error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)
