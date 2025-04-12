import logging
import sys
import requests
from flask import Flask, render_template, request, redirect, url_for

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(stream=sys.stdout)]
)

app = Flask(__name__, template_folder='templates')

# Base URL for the calendar module, which updates and returns updated events.
API_BASE_URL = "http://localhost:5001"
# URL of the mapping module, which returns the matched events from Redis.
MAPPING_API_URL = "http://localhost:5003/processed-events"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/authorize')
def authorize():
    try:
        # Redirect to the calendar module's Google Calendar authorization if needed.
        return redirect(f"{API_BASE_URL}/login")
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

            calendar_response = requests.get(API_BASE_URL, params=params)
            logging.debug(f"Calendar Module Response: {calendar_response.status_code} - {calendar_response.text}")
            raw_events = calendar_response.json()

            mapping_response = requests.get(MAPPING_API_URL, params=params)
            logging.debug(f"Mapping Module Response: {mapping_response.status_code} - {mapping_response.text}")
            processed_events = mapping_response.json()

            # Merge raw event date info into processed events by matching IDs
            # (This assumes that raw_events contains an "items" list and that each event's "id" matches the processed events' "id")
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

@app.route('/hotspots')
def hotspots():
    hotspots_data = []  # Add your hotspots data here if needed.
    return render_template('hotspots.html', hotspots=hotspots_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
