import datetime
import logging
import sys
from functools import reduce

import requests
import redis
from flask import Flask, render_template, request, redirect, url_for, jsonify

from config import Config
from matchingModule.statistics_module import get_disasters_from_redis, fetch_disasters_bulk, store_disasters_in_redis

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(stream=sys.stdout)]
)

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/authorize')
def authorize():
    try:
        # Redirect to the calendar module's Google Calendar authorization if needed.
        return redirect(f"{Config.CALENDAR_API_BASE_URL}/login")
    except Exception as error:
        logging.error(f"Authorization Error: {error}")
        return "Authorization Failed", 500

@app.route('/callback')
def callback():
    try:
        # After successful authorization, redirect to the form page.
        return redirect(url_for('calendar_form'))
    except Exception as error:
        logging.error(f"Callback Error: {error}")
        return "Callback Failed", 500

@app.route('/calendar', methods=['GET', 'POST'])
def calendar_form():
    if request.method == 'POST':
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')

        if not date_from or not date_to:
            return "Missing date range", 400

        try:
            params = {"date_from": date_from, "date_to": date_to}

            calendar_response = requests.get(Config.CALENDAR_API_BASE_URL, params=params)
            logging.debug(f"Calendar Module Response: {calendar_response.status_code} - {calendar_response.text}")
            raw_events = calendar_response.json()

            mapping_response = requests.get(Config.MAPPING_API_URL, params=params)
            logging.debug(f"Mapping Module Response: {mapping_response.status_code} - {mapping_response.text}")
            processed_events = mapping_response.json()

            # Merge raw event date info into processed events by matching IDs
            raw_items = {event['id']: event for event in raw_events.get('items', [])}
            merged_events = []
            for processed in processed_events:
                raw = raw_items.get(processed['id'], {})
                # Add start/end if available
                processed['start'] = raw.get('start')
                processed['end'] = raw.get('end')
                merged_events.append(processed)

            logging.debug(f"Merged events: {merged_events}")
            return render_template('events.html', events=merged_events)
        except Exception as error:
            logging.error(f"Submission Error: {error}")
            return "Submission Failed", 500

    return render_template('calendar_form.html')

def group_disasters_by_zone(disasters, precision=1):
    """
    Groups disasters by geographical zone by rounding their coordinates to a given precision.
    Returns a sorted list of groups (hotspots) in descending order of event count.
    """
    def round_key(disaster):
        try:
            coords = disaster["geometry"][0]["coordinates"]
            lon, lat = coords[0], coords[1]
            return (round(lat, precision), round(lon, precision))
        except Exception as e:
            logging.error(f"Error obtaining rounded key for disaster {disaster.get('id')}: {e}")
            return None

    def add_to_group(accumulator, disaster):
        key = round_key(disaster)
        if key is None:
            return accumulator
        group = accumulator.get(key, {"coordinates": key, "count": 0, "disasters": []})
        new_group = {
            "coordinates": key,
            "count": group["count"] + 1,
            "disasters": group["disasters"] + [disaster]
        }
        new_accumulator = {**accumulator, key: new_group}
        return new_accumulator

    grouped = reduce(add_to_group, disasters, {})
    sorted_groups = sorted(grouped.values(), key=lambda x: x["count"], reverse=True)
    return sorted_groups

@app.route('/hotspots')
def hotspots():
    """
    Render the hotspots page by reading disaster data from Redis,
    grouping them by geographic zones.
    """
    update_hotspots_data()
    disasters = get_disasters_from_redis()
    logging.info(f"Retrieved {len(disasters)} disasters from Redis.")
    hotspots_data = group_disasters_by_zone(disasters)
    logging.debug(f"Calculated hotspots: {hotspots_data}")
    return render_template("hotspots.html", hotspots=hotspots_data)

def update_hotspots_data():
    """
    Update disaster data by fetching from the external API for a date range
    (today - 5 days to today + 5 days) and store the data in Redis.
    Returns the fetched disasters.
    """
    today = datetime.datetime.utcnow().date()
    date_from = (today - datetime.timedelta(days=40)).isoformat()
    date_to = (today + datetime.timedelta(days=40)).isoformat()
    disasters = fetch_disasters_bulk(date_from, date_to)
    store_disasters_in_redis(disasters)
    return disasters

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.FRONTEND_SERVICE_PORT, debug=True)
