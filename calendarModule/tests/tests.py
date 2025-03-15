import unittest
from unittest.mock import patch, MagicMock

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from calendarModule.main import app
from calendarModule.get_calendar_events import process_events
from calendarModule.utils import validate_date, establish_rabbitmq_connection


class TestGoogleCalendarAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch("main.GoogleCalendarClient.login_to_calendar")
    def test_login(self, mock_login):
        mock_login.return_value = None
        response = self.app.get("/login")
        self.assertEqual(response.status_code, 302)  # Redirect expected

    @patch("main.get_events")
    @patch("main.gc_client.get_calendar_service")
    def test_events(self, mock_get_calendar_service, mock_get_events):
        mock_service = MagicMock()
        mock_get_calendar_service.return_value = mock_service
        mock_get_events.return_value = {"items": [{"id": "1", "location": "NYC", "summary": "Meeting"}]}

        response = self.app.get("/?date_from=2025-01-01&date_to=2025-01-02")
        self.assertEqual(response.status_code, 500)  # Expecting failure due to RabbitMQ mock


class TestGetCalendarEvents(unittest.TestCase):
    @patch("get_calendar_events.geocoding_api_connect")
    def test_process_events(self, mock_geocoding):
        events = {"items": [
            {"id": "1", "location": "NYC", "summary": "Meeting", "creator": {"email": "test@example.com"},
             "start": "2025-01-01T10:00:00Z", "end": "2025-01-01T11:00:00Z"}]}
        mock_geocoding.return_value = {"status": "OK", "results": [{"geometry": {"bounds": "data"}}]}
        channel = MagicMock()

        result = process_events(events, channel)
        self.assertEqual(len(result), 1)


class TestUtils(unittest.TestCase):
    def test_validate_date(self):
        self.assertIsNone(validate_date("2025-01-01"))
        error, code = validate_date("invalid-date")
        self.assertIsInstance(error, ValueError)
        self.assertEqual(str(error), "Incorrect data format, should be YYYY-MM-DD")
        self.assertEqual(code, 400)

    @patch("pika.BlockingConnection")
    def test_establish_rabbitmq_connection(self, mock_pika):
        mock_channel = MagicMock()
        mock_pika.return_value.channel.return_value = mock_channel
        channel = establish_rabbitmq_connection()
        self.assertIsNotNone(channel)


if __name__ == "__main__":
    unittest.main()
