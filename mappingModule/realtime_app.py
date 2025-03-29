# realtime_app.py
import json
import logging
import time
import pika
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

logging.basicConfig(level=logging.INFO)

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('realtime.html')

@app.route('/disasters', methods=['GET'])
def get_disasters():
    """
    REST API для отримання поточних катастроф з Redis (fallback).
    """
    import redis
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    data = r.get("disaster_events") or "[]"
    events = json.loads(data)
    return jsonify({
        "status": "success",
        "source": "EONET",
        "total": len(events),
        "events": events
    })

def rabbitmq_callback(ch, method, properties, body):
    logging.info("Received message from RabbitMQ: %s", body)
    try:
        data = json.loads(body)
        socketio.emit("update", data, broadcast=True)
    except Exception as e:
        logging.error("Error processing RabbitMQ message: %s", e)

def start_rabbitmq_consumer():
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
            channel = connection.channel()
            channel.exchange_declare(exchange="disaster_updates", exchange_type="topic", durable=True)
            channel.queue_declare(queue="disaster_alerts", durable=True)
            channel.queue_bind(queue="disaster_alerts", exchange="disaster_updates", routing_key="update")
            channel.basic_consume(queue="disaster_alerts", on_message_callback=rabbitmq_callback, auto_ack=True)
            logging.info("Started consuming from RabbitMQ queue 'disaster_alerts'")
            channel.start_consuming()
        except Exception as e:
            logging.error("RabbitMQ consumer error: %s", e)
            time.sleep(5)

if __name__ == "__main__":
    socketio.start_background_task(start_rabbitmq_consumer)
    socketio.run(app, host="0.0.0.0", port=5008, debug=True, allow_unsafe_werkzeug=True)
