import json

from flask import Flask, request, jsonify
import logging
from event_matcher import match_event_to_disasters, redis_client

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

@app.route("/")
def home():
    return "Event Matching Service is running!", 200

@app.route("/match_event", methods=["POST"])
def match_event():
    try:
        event_data = request.json
        if not event_data:
            return jsonify({"status": "Error", "message": "Invalid input"}), 400

        result = match_event_to_disasters(event_data)
        return jsonify(result)

    except Exception as e:
        logging.error(f"Error in matching event: {e}")
        return jsonify({"status": "Error", "message": "Internal Server Error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=True)  # Specify port 5003 explicitly
