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


# Create connection to Google Calendar and Calendar Service object
class GoogleCalendarClient:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        self.creds = None

    # Login to calendar
    def login_to_calendar(self):
        """Handles user authentication and saves credentials."""
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
        self.creds = flow.run_local_server(port=8090)

    # Create calendar service object
    def get_calendar_service(self):
        return build('calendar', 'v3', credentials=self.creds)


# Create connection to RabbitMQ
def establish_rabbitmq_connection():
    load_dotenv()
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv("RABBITMQ_HOST"),
                                                                   port=os.getenv("RABBITMQ_PORT")))
    return connection.channel()



# Send message to rabbitMQ topic
def publish_message_to_rabbitmq_topic(channel, exchange, routing_key, message):
    logging.info(f"Pushing event {message} to RabbitMQ topic")
    channel.basic_publish(exchange=exchange, routing_key=routing_key, body=message,
                          properties=pika.BasicProperties(delivery_mode=1))


# Validate that date is formatted as YYYY-MM-DD
def validate_date(date_text):
    try:
        date.fromisoformat(date_text)
    except ValueError:
        return ValueError("Incorrect data format, should be YYYY-MM-DD"), 400
