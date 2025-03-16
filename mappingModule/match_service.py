from flask import Flask, request, jsonify
from event_matcher import match_event_to_disasters

app = Flask(__name__)

@app.route('/match_event', methods=['POST'])
def match_event():
    try:
        user_event = request.get_json()
        result = match_event_to_disasters(user_event)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5003, debug=True)
