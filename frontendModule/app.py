# uiModule/app.py

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

MAPPING_API_URL = "http://localhost:5003/processed-events"
API_BASE_URL = "http://localhost:5001"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/authorize')
def authorize():
    try:
        # Redirect to the backend's Google Calendar authorization
        return redirect(f"{API_BASE_URL}/login")
    except Exception as error:
        logging.error(f"Authorization Error: {error}")
        return "Authorization Failed", 500

@app.route('/callback')
def callback():
    try:
        # After successful authorization, redirect to the form page
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
            response = requests.get(MAPPING_API_URL, params=params)
            logging.debug(f"Mapping Module Response: {response.status_code} - {response.text}")

            if response.status_code == 200:
                events = response.json()  # Directly parse the list of events
                logging.debug(f"Parsed events: {events}")
                return render_template('events.html', events=events)
            else:
                return f"Error fetching events: {response.text}", response.status_code

        except Exception as error:
            logging.error(f"Submission Error: {error}")
            return "Submission Failed", 500

    return render_template('calendar_form.html')

@app.route('/hotspots')
def hotspots():
    hotspots_data = []
    return render_template('hotspots.html', hotspots=hotspots_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
