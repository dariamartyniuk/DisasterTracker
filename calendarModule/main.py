
import logging
import sys
import requests
from flask import Flask, redirect, request, jsonify

from get_calendar_events import get_events
from utils import GoogleCalendarClient, establish_rabbitmq_connection, setup_rabbitmq, validate_date

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(stream=sys.stdout)]
)

app = Flask(__name__)
gc_client = GoogleCalendarClient()

MATCHING_API_URL = "http://localhost:5003/match_event"

@app.route("/login")
def login():
    try:
        logging.info("Redirecting user for Google Calendar authentication")
        gc_client.login_to_calendar()
        return redirect("http://localhost:5005/callback")
    except Exception as error:
        logging.error(f"Login Error: {error}")
        return "Login Failed", 500

@app.route("/", methods=["GET"])
def events():
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    if not date_from or not date_to:
        return jsonify({"status": "Error", "message": "Missing required parameters: date_from and date_to"}), 400

    # Validate input parameters
    try:
        validate_date(date_from)
        validate_date(date_to)
    except ValueError as e:
        return jsonify({"status": "Error", "message": str(e)}), 400


    except Exception as e:
        logging.error(f"Service error: {e}")
        return {"status": "Error", "message": "Internal Server Error"}, 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)
