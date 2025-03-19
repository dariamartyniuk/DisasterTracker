import logging
import os
import sys

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, request, jsonify
from google.oauth2.credentials import Credentials
from get_calendar_events import get_events, process_events
from utils import GoogleCalendarClient, establish_rabbitmq_connection, setup_rabbitmq, validate_date

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler(filename='calendar.log', mode='w'),
        logging.StreamHandler(stream=sys.stdout)
    ]
)

load_dotenv()
app = Flask(__name__)
gc_client = GoogleCalendarClient()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:5001/callback"


@app.route("/login")
def login():
    try:
        google_auth_url = (
            "https://accounts.google.com/o/oauth2/auth"
            "?response_type=code"
            f"&client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            "&scope=https://www.googleapis.com/auth/calendar.readonly"
            "&access_type=offline"
            "&prompt=consent"
        )
        return redirect(google_auth_url)
    except Exception as error:
        logging.error(f"Login Error: {error}")
        return "Login Failed", 500


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Authorization failed"}), 400

    # Exchange code for token
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    response = requests.post(token_url, data=data)
    token_data = response.json()

    if "access_token" not in token_data:
        return jsonify({"error": "Login Failed"}), 400

    gc_client.creds = Credentials(token_data.get('access_token'))
    return redirect("http://localhost:5002/callback")


@app.route("/", methods=["GET"])
# Returns the list of events from authorized user calendar
def events():
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    if not date_from or not date_to:
        logging.error("Missing required parameters: date_from and date_to")
        return jsonify({"status": "Error", "message": "Missing required parameters: date_from and date_to"}), 400

    # Validate input parameters - "YYYY-MM-DD"
    validate_date(date_from)
    validate_date(date_to)

    # Login to calendar if necessary
    try:
        if not gc_client.creds or not gc_client.creds.valid:
            login()
        service = gc_client.get_calendar_service()

        logging.info('Load events from calendar')
        events = get_events(service, date_from, date_to)

        # Process events via rabbitMQ
        channel = establish_rabbitmq_connection()
        setup_rabbitmq(channel, "calendar_events", "calendar_queue", "default")
        # Create exchange if not exists
        channel.exchange_declare(exchange='calendar_events', exchange_type='topic', passive=True)

        # return processed events
        return process_events(events, channel)

    except Exception as e:
        logging.error(f"Service error: {e}")
        return {"status": "Error", "message": "Internal Server Error"}, 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)
