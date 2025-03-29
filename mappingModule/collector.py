# collector.py
import logging
import requests
import schedule
import time
import redis
import json
import pika

logging.basicConfig(level=logging.INFO)

r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"

def publish_update(data):
    """
    Публікує дані у RabbitMQ на exchange "disaster_updates" з routing key "update".
    """
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
        channel = connection.channel()
        channel.exchange_declare(exchange="disaster_updates", exchange_type="topic", durable=True)
        message = json.dumps(data, ensure_ascii=False)
        channel.basic_publish(
            exchange="disaster_updates",
            routing_key="update",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logging.info("Published update to RabbitMQ.")
        connection.close()
    except Exception as e:
        logging.error("Failed to publish update: %s", e)

def fetch_eonet_events():
    """
    Завантажує події з EONET API, зберігає їх у Redis і публікує оновлення в RabbitMQ.
    """
    try:
        logging.info("Fetching EONET disasters...")
        response = requests.get(EONET_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        events = data.get("events", [])
        logging.info(f"Fetched {len(events)} EONET events.")

        r.set("disaster_events", json.dumps(events))
        logging.info("EONET events stored in Redis.")

        if events:
            update_data = {"source": "EONET", "events": events}
            publish_update(update_data)
    except Exception as e:
        logging.error("Failed to fetch EONET events: %s", e)

def poll_disasters():
    fetch_eonet_events()

if __name__ == "__main__":
    schedule.every(1).minutes.do(poll_disasters)
    logging.info("Starting disaster collector service...")
    poll_disasters()

    while True:
        schedule.run_pending()
        time.sleep(1)
