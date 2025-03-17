# uiModule/app.py
import json
import logging
import sys
import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify

from mappingModule.event_matcher import redis_client, match_event_to_disasters

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(stream=sys.stdout)]
)

app = Flask(__name__, template_folder='templates')

API_BASE_URL = "http://localhost:5001"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/authorize')
def authorize():
    try:
        return redirect(f"{API_BASE_URL}/login")
    except Exception as error:
        logging.error(f"Authorization Error: {error}")
        return "Authorization Failed", 500

@app.route('/callback')
def callback():
    try:
        return redirect(url_for('calendar_form'))
    except Exception as error:
        logging.error(f"Callback Error: {error}")
        return "Callback Failed", 500

@app.route("/add_test_disaster", methods=["POST"])
def add_test_disaster():
    try:
        test_disasters = [
            {
                "id": "simulated_earthquake",
                "title": "Simulated Earthquake in LA",
                "coordinates": [-118.2437, 34.0522],  # Los Angeles
                "category": "Earthquake",
                "date": "2025-03-17"
            }
        ]
        redis_client.set("disaster_events", json.dumps(test_disasters), ex=3600)
        return jsonify({"status": "Success", "message": "Test disasters added."}), 200
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

def get_user_events(date_from, date_to):
    try:
        # Fetch user events from API
        response = requests.get(f"{API_BASE_URL}/", params={"date_from": date_from, "date_to": date_to})
        logging.debug(f"Backend Response: {response.status_code} - {response.text}")

        if response.status_code == 200:
            events = response.json()
            logging.debug(f"Events fetched: {events}")

            matched_events = []
            for event in events.get('events', []):
                matched_disasters = match_event_to_disasters(event)
                matched_events.append({
                    "event": event,
                    "matched_disasters": matched_disasters['disasters'] if matched_disasters['alert'] else []
                })

            return render_template('events.html', events=matched_events)

        return f"Error fetching events: {response.text}", response.status_code

    except Exception as error:
        logging.error(f"Submission Error: {error}")
        return "Submission Failed", 500


@app.route('/calendar', methods=['GET', 'POST'])
def calendar_view():
    if request.method == 'POST':
        date_from = request.form['date_from']
        date_to = request.form['date_to']
        try:
            return get_user_events(date_from, date_to)
        except Exception as e:
            logging.error(f"Calendar Error: {e}")
            return "Error loading calendar", 500
    return render_template('calendar_form.html')



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
