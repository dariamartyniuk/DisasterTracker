# consumer.py

import pika
import json
import logging
from event_matcher import match_event_to_disasters

RABBITMQ_HOST = "localhost"
EVENT_QUEUE = "calendar_events"         # Queue name where calendar events are published
RESULT_QUEUE = "disaster_matches"       # Optional: you can publish match results here

def callback(ch, method, properties, body):
    try:
        user_event = json.loads(body)
        logging.info(f"Received event: {user_event}")

        result = match_event_to_disasters(user_event)
        logging.info(f"Match result: {result}")

        # Optional: Publish result to another queue (e.g. for notification module)
        publish_result(result)

    except Exception as e:
        logging.error(f"Error processing message: {e}")

def publish_result(result):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=RESULT_QUEUE, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=RESULT_QUEUE,
            body=json.dumps(result),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
    except Exception as e:
        logging.error(f"Failed to publish result: {e}")

def start_consumer():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=EVENT_QUEUE, durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=EVENT_QUEUE, on_message_callback=callback, auto_ack=True)

    logging.info(f" [*] Waiting for messages in '{EVENT_QUEUE}' queue. To exit press CTRL+C")
    channel.start_consuming()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_consumer()
