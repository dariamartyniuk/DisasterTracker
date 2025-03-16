import logging
import os
import sys
from datetime import date

import pika
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler(filename='utils.log', mode='w'),
        logging.StreamHandler(stream=sys.stdout)
    ]
)


# Create connection to Google Calendar∂ and Calendar Service object
class GoogleCalendarClient:
    def __init__(self):
        # Use a restricted scope to limit access
        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']
        self.creds = None

    def login_to_calendar(self):
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
        self.creds = flow.run_local_server(port=0, open_browser=False)


    # Create calendar service object
    def get_calendar_service(self):
        return build('calendar', 'v3', credentials=self.creds)


# Create connection to RabbitMQ
def establish_rabbitmq_connection():
    load_dotenv()
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv("RABBITMQ_HOST"),
                                                                   port=os.getenv("RABBITMQ_PORT")))
    return connection.channel()

def setup_rabbitmq(channel, exchange, queue_name, routing_key):
    # Declare an exchange (if it doesn't exist)
    channel.exchange_declare(exchange=exchange, exchange_type='direct', durable=True)
    # Declare a queue
    channel.queue_declare(queue=queue_name, durable=True)
    # Bind the queue to the exchange with a routing key
    channel.queue_bind(exchange=exchange, queue=queue_name, routing_key=routing_key)
    logging.info(f"Exchange '{exchange}' and queue '{queue_name}' are ready!")

# Send message to rabbitMQ topic
def publish_message_to_rabbitmq_topic(channel, exchange, routing_key, message):
    logging.info(f"Pushing event {message} to RabbitMQ topic")
    channel.basic_publish(exchange=exchange,
                          routing_key=routing_key,
                          body=message,
                          properties=pika.BasicProperties(delivery_mode=2))


# Validate that date is formatted as YYYY-MM-DD
def validate_date(date_text):
    if not date_text or not isinstance(date_text, str):
        raise ValueError("Invalid date format. Expected a string in YYYY-MM-DD format.")

    try:
        date.fromisoformat(date_text)
    except ValueError:
        raise ValueError("Incorrect date format, should be YYYY-MM-DD")

