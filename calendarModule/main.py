import logging
import sys
from flask import Flask, redirect, request, jsonify

from get_calendar_events import get_events, process_events
from utils import GoogleCalendarClient, establish_rabbitmq_connection, setup_rabbitmq, validate_date

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(stream=sys.stdout)
    ]
)

app = Flask(__name__)
gc_client = GoogleCalendarClient()

@app.route("/login")
def login():
    try:
        logging.info("Redirecting user for Google Calendar authentication")
        gc_client.login_to_calendar()
        return redirect("http://localhost:5002/callback")
    except Exception as error:
        logging.error(f"Login Error: {error}")
        return "Login Failed", 500

@app.route("/", methods=["GET"])
def events():
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    validate_date(date_from)
    validate_date(date_to)

    try:
        if not gc_client.creds or not gc_client.creds.valid:
            login()
        service = gc_client.get_calendar_service()

        logging.info('Load events from calendar')
        events = get_events(service, date_from, date_to)

        # Process events and return the response
        channel = establish_rabbitmq_connection()
        setup_rabbitmq(channel, "calendar_events", "calendar_queue", "default")

        channel.exchange_declare(exchange='calendar_events', exchange_type='topic', passive=True)

        return process_events(events, channel)

    except Exception as e:
        logging.error(f"Service error: {e}")
        return {"status": "Error", "message": "Internal Server Error"}, 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)
