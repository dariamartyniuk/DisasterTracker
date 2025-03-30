import json
import logging
import os
import os.path
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from rx import from_iterable, operators as op

from utils import publish_message_to_rabbitmq_topic

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
    return service.events().list(
        calendarId=calendar_id,
        timeMin=datetime.strptime(date_from, "%Y-%m-%d").astimezone(timezone.utc).isoformat(),
        timeMax=datetime.strptime(date_to, "%Y-%m-%d").astimezone(timezone.utc).isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()


# Connect to Geocoding API, send location and get geo data
def geocoding_api_connect(location: str, base_url="https://maps.googleapis.com/maps/api/geocode/json"):
    load_dotenv()
    return requests.get(base_url, params={"address": location, "key": os.getenv('GEOCODING_API_KEY')}).json()


# Filter message fields, leave only necessary
def form_message(event):
    return {'id': event.get('id'), 'location': event.get('location'), 'summary': event.get('summary'),
            'email': event.get('creator')['email'],
            'start': event.get('start'), 'end': event.get('end'),
            'coordinates': event.get('coordinates').get('results')[0].get('geometry').get('bounds')}


# Events processing pipe
# 1. Events without location cannot be matched with geo data, filter it out
# 2. Match events with location to geo data
# 3. Filter out events with location unknown to Geocoding
# 4. Filter out unnecessary fields
# 5. Convert event to json, preserve encoding
# 6. Publish event to RabbitMQ topic
def process_events(events, channel):
    return from_iterable(events['items']) \
        .pipe(
            # Filter events with valid locations
            op.filter(lambda x: x.get('location') is not None),
            # Add coordinates using the geocoding API
            op.map(lambda x: {**x, 'coordinates': geocoding_api_connect(x['location'])}),
            # Filter events with valid geocoding results
            op.filter(lambda x: x['coordinates'].get('status') == 'OK'),
            # Convert events to message format
            op.map(lambda x: form_message(x)),
            # Collect all processed events into a batch (list)
            op.to_list(),
            # Publish the batch of events to RabbitMQ as a single message
            op.do_action(lambda batch: logging.info(f"Publishing batch of events to RabbitMQ: {batch}")),  # Added logging
            op.do_action(lambda batch: publish_message_to_rabbitmq_topic(
                channel=channel,
                exchange='calendar_events',
                routing_key='default',
                message=json.dumps(batch, ensure_ascii=False)
            )),
            # Return the batch for debugging/testing
            op.to_list()
        ) \
        .run()