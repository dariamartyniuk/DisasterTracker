import json
import logging
import pika
import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify
import redis


import json
from pyrsistent import pvector

def get_immutable_alerts(client, key="latest_matched_events"):
    data = client.get(key)
    if data:
        alerts = json.loads(data)
        if not isinstance(alerts, list):
            alerts = [alerts]
        return pvector(alerts)
    return pvector()


logging.basicConfig(level=logging.INFO)
app = Flask(__name__, template_folder='templates')
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
API_BASE_URL = "http://localhost:5001"

def get_user_events(date_from, date_to):
    try:
        response = requests.get(f"{API_BASE_URL}/", params={"date_from": date_from, "date_to": date_to})
        logging.debug(f"Backend Response: {response.status_code} - {response.text}")
        if response.status_code != 200:
            return f"Error fetching events: {response.text}", response.status_code
        data = response.json()
        all_events = data.get("events", [])
        logging.debug(f"Fetched {len(all_events)} events from backend.")
        alerts = get_immutable_alerts(r, "latest_matched_events")
        alerts_by_event = {}
        for alert in alerts:
            evt = alert.get("event", {})
            event_id = evt.get("id")
            if event_id:
                alerts_by_event[event_id] = alert.get("disasters", [])
        events_with_matches = []
        for ev in all_events:
            ev_id = ev.get("id")
            if ev_id in alerts_by_event:
                ev["disaster_alert"] = True
                ev["matched_disasters"] = alerts_by_event[ev_id]
            else:
                ev["disaster_alert"] = False
                ev["matched_disasters"] = []
            events_with_matches.append(ev)
        return render_template("calendar_form.html", events=events_with_matches)
    except Exception as error:
        logging.error(f"Submission Error: {error}", exc_info=True)
        return "Submission Failed", 500

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/authorize")
def authorize():
    return redirect(f"{API_BASE_URL}/login")

@app.route("/callback")
def callback():
    return redirect(url_for("calendar_form"))

@app.route("/calendar", methods=["GET", "POST"])
def calendar_form():
    if request.method == "POST":
        date_from = request.form["date_from"]
        date_to = request.form["date_to"]
        return get_user_events(date_from, date_to)
    return render_template("calendar_form.html", events=[])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)
