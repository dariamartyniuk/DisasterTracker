import logging
import sys
import requests
from flask import Flask, redirect, request, jsonify

from get_calendar_events import get_events
from mappingModule.event_matcher import get_hotspots, match_event_to_disasters, redis_client
from google.oauth2.credentials import Credentials
from get_calendar_events import get_events, process_events
from utils import GoogleCalendarClient, establish_rabbitmq_connection, setup_rabbitmq, validate_date

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(stream=sys.stdout)]
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

        if not isinstance(events, dict):
            logging.error(f"Unexpected `events` type: {type(events)}. Expected dict.")
            return jsonify({"status": "Error", "message": "Invalid response from Google Calendar API"}), 500

        items = events.get('items', [])
        if not isinstance(items, list):
            logging.error(f"Unexpected `items` type: {type(items)}. Expected list.")
            items = []

        matched_events = [
            {
                **event,
                "disaster_alert": match_event_to_disasters({
                    "id": event.get("id"),
                    "coordinates": event.get("coordinates"),
                    "summary": event.get("summary"),
                    "start": event.get("start"),
                    "end": event.get("end")
                }) if event.get("coordinates") else {"alert": False}  # Skip events without coordinates
            }
            for event in items if isinstance(event, dict)
        ]

        return jsonify({"status": "Success", "events": matched_events})

    except Exception as e:
        logging.error(f"Service error: {e}", exc_info=True)
        return jsonify({"status": "Error", "message": "Internal Server Error"}), 500

@app.route("/hotspots", methods=["GET"])
def hotspots():
    try:
        hotspot_data = get_hotspots()
        return jsonify({"status": "Success", "hotspots": hotspot_data})
    except Exception as e:
        logging.error(f"Error fetching hotspots: {e}", exc_info=True)
        return jsonify({"status": "Error", "message": "Internal Server Error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)
