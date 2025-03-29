import json
import logging
import pika
import time
from mappingModule.event_matcher import match_event_to_disasters

logging.basicConfig(level=logging.INFO)
RABBITMQ_HOST = "localhost"

def publish_processed_events(data):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.exchange_declare(exchange="disaster_updates", exchange_type="topic", durable=True)
        message = json.dumps(data, ensure_ascii=False)
        channel.basic_publish(
            exchange="disaster_updates",
            routing_key="update",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logging.info("Published processed (matched) events.")
        connection.close()
    except Exception as e:
        logging.error("Error publishing processed events: %s", e)

def mapping_callback(ch, method, properties, body):
    try:
        raw_data = json.loads(body)
        events = raw_data.get("events", [])
        processed_events = []
        for event in events:
            result = match_event_to_disasters(event)  # Якщо alert True, повертає результат
            if result.get("alert"):
                processed_events.append(result)
        if processed_events:
            publish_processed_events({"processed": processed_events})
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logging.error("Error in mapping callback: %s", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def start_mapping_consumer():
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            channel.exchange_declare(exchange="calendar_events", exchange_type="topic", durable=True)
            channel.queue_declare(queue="calendar_events_queue", durable=True)
            channel.queue_bind(queue="calendar_events_queue", exchange="calendar_events", routing_key="calendar")
            channel.basic_consume(queue="calendar_events_queue", on_message_callback=mapping_callback)
            logging.info("Started mapping consumer on 'calendar_events_queue'")
            channel.start_consuming()
        except Exception as e:
            logging.error("Mapping consumer error: %s", e)
            time.sleep(5)

if __name__ == "__main__":
    start_mapping_consumer()
