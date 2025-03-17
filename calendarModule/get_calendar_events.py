import json
import logging
import os
import os.path
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from calendarModule.utils import publish_message_to_rabbitmq_topic

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler(filename='calendar.log', mode='w'),
        logging.StreamHandler(stream=sys.stdout)
    ]
)


# Retrieve events using the Google Calendar API.
def get_events(service, date_from, date_to, calendar_id='primary'):
    if service is None:
        logging.error("Google Calendar service is None. Cannot fetch events")
        return {}

    try:
        logging.info(f"Fetching events from {date_from} to {date_to}")

        events_response = service.events().list(
            calendarId=calendar_id,
            timeMin=datetime.strptime(date_from, "%Y-%m-%d").astimezone(timezone.utc).isoformat(),
            timeMax=datetime.strptime(date_to, "%Y-%m-%d").astimezone(timezone.utc).isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        logging.debug(f"Raw API Response: {events_response}")

        if not isinstance(events_response, dict):
            logging.error("Unexpected response format. Expected a dictionary but received something else")
            return {}

        # Ensure 'items' exists and is a list
        items = events_response.get('items', [])
        if not isinstance(items, list):
            logging.error("The items field is not a list. Possible API structure change")
            return {}

        logging.info(f"Retrieved {len(items)} events from Google Calendar")

        # Debug each event structure
        for event in items:
            if not isinstance(event, dict):
                logging.error(f"Unexpected event format: {event}")
                continue

        return events_response  # ✅ FIX: Return the full dictionary instead of just `items`

    except Exception as e:
        logging.error(f"Google Calendar API request failed: {e}", exc_info=True)
        return {}







# Connect to Geocoding API, send location and get geo data
def geocoding_api_connect(location: str, base_url="https://maps.googleapis.com/maps/api/geocode/json"):
    load_dotenv()
    return requests.get(base_url, params={"address": location, "key": os.getenv('GEOCODING_API_KEY')}).json()


# Filter message fields, leave only necessary
import logging






# Events processing pipe
# 1. Events without location cannot be matched with geo data, filter it out
# 2. Match events with location to geo data
# 3. Filter out events with location unknown to Geocoding
# 4. Filter out unnecessary fields
# 5. Convert event to json, preserve encoding
# 6. Publish event to RabbitMQ topic
import json
import logging
from rx import from_iterable, operators as op

import logging
import json
from rx import from_iterable
import rx.operators as op

def process_events(events, channel):
    try:
        # Ensure `events` is a dictionary, not a list or None
        if not isinstance(events, dict):
            logging.error(f"Invalid events format: Expected a dictionary but got {type(events)}. Fixing...")
            events = {"items": []}  # Default to empty dictionary with `items`

        # Debugging raw event data
        logging.debug(f"Raw event data received: {json.dumps(events, indent=2)}")

        # Ensure 'items' exists and is a list
        items = events.get("items", [])
        if not isinstance(items, list):
            logging.error(f"Unexpected 'items' format: Expected a list but got {type(items)}. Fixing...")
            items = []

        return from_iterable(items) \
            .pipe(
                # Ensure item is a dictionary and has 'location'
                op.filter(lambda x: isinstance(x, dict) and 'location' in x),

                # Add geocoding coordinates
                op.map(lambda x: {**x, 'coordinates': safe_geocode(x['location'])}),

                # Ensure geocoding was successful
                op.filter(lambda x: x['coordinates'].get('status') == 'OK'),

                # Transform into a message format
                op.map(lambda x: form_message(x)),

                # Publish to RabbitMQ safely
                op.do_action(lambda x: safe_publish(channel, x)),

                # Collect processed events into a list
                op.to_list()
            ) \
            .run()

    except Exception as e:
        logging.error(f"Error processing events: {e}", exc_info=True)
        return []

# --- Helper Functions ---

def safe_geocode(location):
    """Safely calls geocoding API, preventing errors."""
    try:
        return geocoding_api_connect(location)
    except Exception as e:
        logging.error(f"Geocoding failed for location '{location}': {e}")
        return {"status": "ERROR"}

def safe_publish(channel, message):
    """Safely publishes to RabbitMQ, preventing errors."""
    try:
        if channel is None:
            raise ValueError("RabbitMQ channel is not initialized.")
        publish_message_to_rabbitmq_topic(
            channel=channel,
            exchange='calendar_events',
            routing_key='default',
            message=json.dumps(message, ensure_ascii=False)
        )
    except Exception as e:
        logging.error(f"Failed to publish message to RabbitMQ: {e}")


def form_message(event):
    """Extracts relevant event data and avoids list indexing errors."""
    try:

        return {
            'id': event.get('id'),
            'summary': event.get('summary', 'No Title'),
            'description': event.get('description', ''),
            'start': event.get('start', {}).get('dateTime', event.get('start', {}).get('date')),
            'end': event.get('end', {}).get('dateTime', event.get('end', {}).get('date')),
            'organizer': event.get('organizer', {}).get('email', 'Unknown'),
            'attendees': [att.get('email', 'Unknown') for att in event.get('attendees', [])] if isinstance(event.get('attendees'), list) else [],
            'htmlLink': event.get('htmlLink', ''),
        }
    except Exception as e:
        logging.error(f"Error processing event: {event}. Exception: {e}")
        return None  # Skip problematic event




