import json
import logging
import os
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
        logging.StreamHandler(stream=sys.stdout)
    ]
)

load_dotenv()


def get_events(service, date_from, date_to, calendar_id='primary'):
    try:
        logging.info(f"Запит подій для календаря {calendar_id} з {date_from} до {date_to}")
        time_min = datetime.strptime(date_from, "%Y-%m-%d").astimezone(timezone.utc).isoformat()
        time_max = datetime.strptime(date_to, "%Y-%m-%d").astimezone(timezone.utc).isoformat()
        logging.debug(f"timeMin: {time_min}, timeMax: {time_max}")

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        logging.info("Події успішно отримані з Google Calendar.")
        return events_result
    except Exception as e:
        logging.error(f"Помилка отримання подій з календаря: {e}")
        return {}


def geocoding_api_connect(location: str, base_url="https://maps.googleapis.com/maps/api/geocode/json"):
    try:
        logging.info(f"Запит геокодування для локації: {location}")
        response = requests.get(base_url, params={"address": location, "key": os.getenv('GEOCODING_API_KEY')})
        data = response.json()
        logging.debug(f"Результат геокодування: {data}")
        return data
    except Exception as e:
        logging.error(f"Помилка геокодування: {e}")
        return {}


def form_message(event):
    try:
        message = {
            'id': event.get('id'),
            'location': event.get('location'),
            'summary': event.get('summary'),
            'email': event.get('creator')['email'] if event.get('creator') else "N/A",
            'start': event.get('start'),
            'end': event.get('end'),
            'coordinates': event.get('coordinates').get('results')[0].get('geometry').get('bounds')
        }
        logging.debug(f"Сформовано повідомлення: {message}")
        return message
    except Exception as e:
        logging.error(f"Помилка формування повідомлення для події {event.get('id')}: {e}")
        return {}


def process_events(events, channel):
    try:
        logging.info("Розпочато обробку подій...")
        return from_iterable(events['items']) \
            .pipe(
                op.filter(lambda x: x.get('location') is not None),
                op.map(lambda x: {**x, 'coordinates': geocoding_api_connect(x['location'])}),
                op.filter(lambda x: x['coordinates'].get('status') == 'OK'),
                op.map(lambda x: form_message(x)),
                op.to_list(),
                op.do_action(lambda batch: logging.info(f"Публікація обробленої партії подій в RabbitMQ: {batch}")),
                op.do_action(lambda batch: publish_message_to_rabbitmq_topic(
                    channel=channel,
                    exchange='calendar_events',
                    routing_key='default',
                    message=json.dumps(batch, ensure_ascii=False)
                ))
            ) \
            .run()
    except Exception as e:
        logging.error(f"Помилка обробки подій: {e}")
        return []
