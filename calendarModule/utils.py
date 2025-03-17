import logging
import os
import sys
from datetime import date

import pika
from flask import redirect
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(stream=sys.stdout)
    ]
)


# Create connection to Google Calendar∂ and Calendar Service object
class GoogleCalendarClient:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']
        self.creds = None

    def login_to_calendar(self):
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
        self.creds = flow.run_local_server(port=8090)

    def get_calendar_service(self):
        if not self.creds:
            logging.error("No credentials found. Please login first!")
            return None
        if not self.creds.valid:
            logging.error("Credentials are invalid or expired. Try re-authenticating!")
            return None

        logging.info("Successfully authenticated with Google Calendar API.")
        return build('calendar', 'v3', credentials=self.creds)


# Create connection to RabbitMQ
def establish_rabbitmq_connection():
    load_dotenv()
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv("RABBITMQ_HOST"),
                                                                   port=os.getenv("RABBITMQ_PORT")))
    return connection.channel()

def setup_rabbitmq(channel, exchange, queue_name, routing_key):
    channel.exchange_declare(exchange=exchange, exchange_type='direct', durable=True)
    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_bind(exchange=exchange, queue=queue_name, routing_key=routing_key)
    logging.info(f"Exchange '{exchange}' and queue '{queue_name}' are ready!")

def get_rabbitmq_channel():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()

        channel.exchange_declare(
            exchange='calendar_events',
            exchange_type='topic',
            durable=True
        )

        print("RabbitMQ connection established and exchange initialized.")
        return channel
    except Exception as e:
        print(f"Failed to connect to RabbitMQ: {e}")
        return None


# Send message to rabbitMQ topic
def publish_message_to_rabbitmq_topic(channel, exchange, routing_key, message):
    channel = get_rabbitmq_channel()
    if channel is None:
        raise ValueError("RabbitMQ channel is not initialized.")

    try:
        channel.exchange_declare(
            exchange=exchange,
            exchange_type='topic',
            durable=True
        )

        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2
            )
        )
        print(f"Successfully published message to {exchange} with routing key {routing_key}")

    except Exception as e:
        print(f"Failed to publish message: {e}")


# Validate that date is formatted as YYYY-MM-DD
def validate_date(date_text):
    if not date_text or not isinstance(date_text, str):
        raise ValueError("Invalid date format. Expected a string in YYYY-MM-DD format.")

    try:
        date.fromisoformat(date_text)
    except ValueError:
        raise ValueError("Incorrect date format, should be YYYY-MM-DD")

