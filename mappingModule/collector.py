import logging
import requests
import pika
import json
import schedule
import time

logging.basicConfig(level=logging.INFO)
RABBITMQ_HOST = "localhost"
EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"

def publish_raw_events(data):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.exchange_declare(exchange="raw_updates", exchange_type="topic", durable=True)
        message = json.dumps(data, ensure_ascii=False)
        channel.basic_publish(
            exchange="raw_updates",
            routing_key="raw",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logging.info("Published raw events to RabbitMQ")
        connection.close()
    except Exception as e:
        logging.error("Error publishing raw events: %s", e)

def fetch_and_publish():
    try:
        logging.info("Fetching EONET events...")
        response = requests.get(EONET_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        events = data.get("events", [])
        logging.info(f"Fetched {len(events)} events from EONET")
        if events:
            publish_raw_events({"source": "EONET", "events": events})
    except Exception as e:
        logging.error("Error fetching EONET events: %s", e)

if __name__ == "__main__":
    schedule.every(5).minutes.do(fetch_and_publish)
    logging.info("Starting collector service...")
    fetch_and_publish()
    while True:
        schedule.run_pending()
        time.sleep(1)
