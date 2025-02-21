import logging
import sys

from flask import Flask, redirect, request

from get_calendar_events import get_events, process_events
from utils import GoogleCalendarClient, establish_rabbitmq_connection, validate_date

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler(filename='calendar.log', mode='w'),
        logging.StreamHandler(stream=sys.stdout)
    ]
)

app = Flask(__name__)
gc_client = GoogleCalendarClient()


@app.route("/login")
# Login to calendar
def login():
    try:
        gc_client.login_to_calendar()
        return redirect("/")
    except Exception as error:
        logging.error(f"Login Error: {error}")
        return "Login Failed", 500


@app.route("/", methods=["GET"])
# Returns the list of events from authorized user calendar
def events():
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # Validate input parameters - "YYYY-MM-DD"
    validate_date(date_from)
    validate_date(date_to)

    # Login to calendar if necessary
    try:
        if not gc_client.creds or not gc_client.creds.valid:
            login()
        service = gc_client.get_calendar_service()

        # Load events in given date range
        try:
            logging.info('Load events from calendar')
            events = get_events(service, date_from, date_to)
        except Exception as e:
            logging.debug(f"Error while fetching events {e}")
    except Exception as e:
        logging.debug(f'Service error {e}')

    # Connect to RabbitMQ
    channel = establish_rabbitmq_connection()

    # Create exchange if not exists
    channel.exchange_declare(exchange='calendar_events', exchange_type='topic', passive=True)

    # Process events
    return process_events(events, channel)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
