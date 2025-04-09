import json
import logging
import os
import sys

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, request, jsonify
from google.oauth2.credentials import Credentials
from get_calendar_events import get_events, process_events
from utils import (
    GoogleCalendarClient,
    establish_rabbitmq_connection,
    setup_rabbitmq,
    validate_date
)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # Можна записувати в файл або виводити на консоль
        logging.StreamHandler(stream=sys.stdout)
    ]
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
        logging.debug("Початок процесу логіну через Google.")
        google_auth_url = (
            "https://accounts.google.com/o/oauth2/auth"
            "?response_type=code"
            f"&client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            "&scope=https://www.googleapis.com/auth/calendar.readonly"
            "&access_type=offline"
            "&prompt=consent"
        )
        logging.info(f"Redirecting to Google auth URL: {google_auth_url}")
        return redirect(google_auth_url)
    except Exception as error:
        logging.error(f"Login Error: {error}")
        return "Login Failed", 500


@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        logging.debug(f"Отримано код авторизації: {code}")
        if not code:
            logging.error("Код авторизації відсутній")
            return jsonify({"error": "Authorization failed"}), 400

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
        logging.debug(f"Token response data: {token_data}")

        if "access_token" not in token_data:
            logging.error("Отримання токену не вдалося")
            return jsonify({"error": "Login Failed"}), 400

        gc_client.creds = Credentials(token_data.get('access_token'))
        logging.info("Авторизація пройшла успішно. Зберігаємо об'єкт credentials.")
        return redirect("http://localhost:5002/callback")
    except Exception as e:
        logging.error(f"Callback error: {e}")
        return jsonify({"error": "Callback processing failed"}), 500


@app.route("/", methods=["GET"])
def events():
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        logging.debug(f"Отримано параметри: date_from={date_from}, date_to={date_to}")

        if not date_from or not date_to:
            logging.error("Відсутні обов'язкові параметри: date_from та date_to")
            return jsonify({"status": "Error", "message": "Missing required parameters: date_from and date_to"}), 400

        # Перевірка формату дат
        validate_date(date_from)
        validate_date(date_to)

        # Перевірка стану авторизації
        if not gc_client.creds or not gc_client.creds.valid:
            logging.info("Credentials не існують або недійсні, перенаправляємо на логін.")
            return redirect("/login")

        service = gc_client.get_calendar_service()
        logging.info("Отримано сервіс Google Calendar.")

        logging.info("Завантаження подій з календаря...")
        events = get_events(service, date_from, date_to)
        logging.debug(f"Отримано події: {events}")

        # Публікація подій у RabbitMQ
        channel = establish_rabbitmq_connection()
        setup_rabbitmq(channel, "calendar_events", "calendar_queue", "default")
        logging.info(
            "Підготовлено підписку на RabbitMQ: exchange=calendar_events, queue=calendar_queue, routing_key=default")

        # Обробка подій (можна, наприклад, публікувати їх у RabbitMQ, або проводити подальшу обробку)
        processed_events = process_events(events, channel)
        logging.info(f"Оброблені події: {processed_events}")

        return jsonify({"status": "Success", "processed_events": processed_events})

    except Exception as e:
        logging.error(f"Service error: {e}")
        return jsonify({"status": "Error", "message": "Internal Server Error"}), 500


if __name__ == "__main__":
    logging.info("Запуск Calendar Module на порті 5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
