# producer.py

import pika
import json

RABBITMQ_HOST = "localhost"
EVENT_QUEUE = "calendar_events"

sample_event = {
    "summary": "Vacation in Indonesia",
    "location": "Jakarta, Indonesia",
    "start": "2025-04-01T10:00:00Z"
}

connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
channel = connection.channel()

channel.queue_declare(queue=EVENT_QUEUE, durable=True)
channel.basic_publish(
    exchange='',
    routing_key=EVENT_QUEUE,
    body=json.dumps(sample_event),
    properties=pika.BasicProperties(delivery_mode=2)
)

print(" [x] Sent test event.")
connection.close()
