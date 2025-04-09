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

            # First, call the calendar module (API_BASE_URL)
            # This endpoint should update or fetch the latest calendar events.
            response = requests.get(API_BASE_URL, params=params)
            events = response.json()['processed_events']
            logging.info(events)
            logging.debug(f"Calendar Module Response: {response.status_code} - {response.text}")



            if response.status_code == 200:
                # Next, query the mapping module for matched events that were saved in Redis.
                map_response = requests.get(MAPPING_API_URL, params=params)
                # logging.debug(f"Mapping Module Response: {map_response.status_code} - {map_response.text}")
                #
                # if map_response.status_code == 200:
                #     events = map_response.json()  # List of processed matched events.
                #     logging.debug(f"Parsed events: {events}")
                return render_template('events.html', events=events)
                # else:
                #     return f"Error fetching matched events: {map_response.text}", map_response.status_code

            else:
                return f"Error updating calendar events: {events.text}", events.status_code

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
