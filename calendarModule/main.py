import json
import logging
import os
import sys

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, request, jsonify
from google.oauth2.credentials import Credentials

from calendarModule.utils import GoogleCalendarClient, validate_date, establish_rabbitmq_connection, setup_rabbitmq
from get_calendar_events import get_events, process_events
from config import Config

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # Can write to file or output to console
        logging.StreamHandler(stream=sys.stdout)
    ]
)

app = Flask(__name__)
gc_client = GoogleCalendarClient()


@app.route("/login")
def login():
    try:
        logging.debug("Starting login process through Google.")
        google_auth_url = (
            "https://accounts.google.com/o/oauth2/auth"
            "?response_type=code"
            f"&client_id={Config.GOOGLE_CLIENT_ID}"
            f"&redirect_uri={Config.GOOGLE_REDIRECT_URI}"
            "&scope=https://www.googleapis.com/auth/calendar.readonly"
            "&access_type=offline"
            "&prompt=consent"
        )
        logging.info(f"Redirecting to Google auth URL: {google_auth_url}")
        return redirect(google_auth_url)
    except Exception as error:
        logging.error(f"Login Error: {error}")
        return "Login Failed", 500


@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        logging.debug(f"Authorization code received: {code}")
        if not code:
            logging.error("Authorization code is missing")
            return jsonify({"error": "Authorization failed"}), 400

        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": Config.GOOGLE_CLIENT_ID,
            "client_secret": Config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": Config.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        response = requests.post(token_url, data=data)
        token_data = response.json()
        logging.debug(f"Token response data: {token_data}")

        if "access_token" not in token_data:
            logging.error("Failed to obtain token")
            return jsonify({"error": "Login Failed"}), 400

        gc_client.creds = Credentials(token_data.get('access_token'))
        logging.info("Authorization successful. Saving credentials object.")
        return redirect(f"{Config.FRONTEND_SERVICE_URL}/callback")
    except Exception as e:
        logging.error(f"Callback error: {e}")
        return jsonify({"error": "Callback processing failed"}), 500


@app.route("/", methods=["GET"])
def events():
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        logging.debug(f"Parameters received: date_from={date_from}, date_to={date_to}")

        if not date_from or not date_to:
            logging.error("Missing required parameters: date_from and date_to")
            return jsonify({"status": "Error", "message": "Missing required parameters: date_from and date_to"}), 400

        # Validate date format
        validate_date(date_from)
        validate_date(date_to)

        # Check authorization status
        if not gc_client.creds or not gc_client.creds.valid:
            logging.info("Credentials don't exist or are invalid, redirecting to login.")
            return redirect("/login")

        service = gc_client.get_calendar_service()
        logging.info("Google Calendar service obtained.")

        logging.info("Loading events from calendar...")
        events = get_events(service, date_from, date_to)
        logging.debug(f"Events received: {events}")

        # Publish events to RabbitMQ
        channel = establish_rabbitmq_connection()
        setup_rabbitmq(channel, Config.RABBITMQ_EXCHANGE, Config.RABBITMQ_QUEUE, Config.RABBITMQ_ROUTING_KEY)
        logging.info(
            f"RabbitMQ subscription prepared: exchange={Config.RABBITMQ_EXCHANGE}, queue={Config.RABBITMQ_QUEUE}, routing_key={Config.RABBITMQ_ROUTING_KEY}")

        # Process events (can publish to RabbitMQ or perform further processing)
        processed_events = process_events(events, channel)
        logging.info(f"Processed events: {processed_events}")

        return jsonify({"status": "Success", "processed_events": processed_events})

    except Exception as e:
        logging.error(f"Service error: {e}")
        return jsonify({"status": "Error", "message": "Internal Server Error"}), 500


if __name__ == "__main__":
    logging.info(f"Starting Calendar Module on port {Config.CALENDAR_SERVICE_PORT}")
    app.run(host='0.0.0.0', port=Config.CALENDAR_SERVICE_PORT, debug=True)
