import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
import sys
import os

# Add the parent directory to the Python path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from frontendModule.app import (
    app,
    group_disasters_by_zone,
    update_hotspots_data
)


class TestFrontendModule(unittest.TestCase):
    def setUp(self):
        """Set up test client and sample data"""
        self.app = app.test_client()
        self.app.testing = True

        # Sample disaster data
        self.sample_disasters = [
            {
                "id": "disaster1",
                "title": "Test Disaster 1",
                "description": "Test Description 1",
                "categories": [{"name": "Test Category"}],
                "geometry": [{
                    "coordinates": [-74.0060, 40.7128],
                    "date": "2024-03-20T10:00:00Z"
                }],
                "status": "active"
            },
            {
                "id": "disaster2",
                "title": "Test Disaster 2",
                "description": "Test Description 2",
                "categories": [{"name": "Test Category"}],
                "geometry": [{
                    "coordinates": [-74.0060, 40.7128],  # Same coordinates as disaster1
                    "date": "2024-03-20T11:00:00Z"
                }],
                "status": "active"
            },
            {
                "id": "disaster3",
                "title": "Test Disaster 3",
                "description": "Test Description 3",
                "categories": [{"name": "Test Category"}],
                "geometry": [{
                    "coordinates": [-118.2437, 34.0522],  # Different coordinates
                    "date": "2024-03-20T12:00:00Z"
                }],
                "status": "active"
            }
        ]

    def test_index_route(self):
        """Test the index route returns 200 and renders index.html"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        # Check for content that should be in the rendered template
        self.assertIn(b'Disaster Tracker', response.data)

    @patch('requests.get')
    def test_authorize_route(self, mock_get):
        """Test the authorize route redirects to calendar login"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        response = self.app.get('/authorize')
        self.assertEqual(response.status_code, 302)  # Redirect status code
        self.assertIn('/login', response.location)

    def test_callback_route(self):
        """Test the callback route redirects to calendar form"""
        response = self.app.get('/callback')
        self.assertEqual(response.status_code, 302)  # Redirect status code
        self.assertIn('/calendar', response.location)

    def test_calendar_form_get(self):
        """Test the calendar form route returns the form on GET"""
        response = self.app.get('/calendar')
        self.assertEqual(response.status_code, 200)
        # Check for content that should be in the rendered template
        self.assertIn(b'Select Date Range', response.data)
        self.assertIn(b'Start Date', response.data)
        self.assertIn(b'End Date', response.data)
        self.assertIn(b'Submit', response.data)

    @patch('requests.get')
    def test_calendar_form_post_success(self, mock_get):
        """Test successful calendar form submission"""
        # Mock calendar API response
        calendar_response = MagicMock()
        calendar_response.json.return_value = {
            "items": [
                {
                    "id": "event1",
                    "start": {"dateTime": "2024-03-20T10:00:00Z"},
                    "end": {"dateTime": "2024-03-20T11:00:00Z"}
                }
            ]
        }

        # Mock mapping API response
        mapping_response = MagicMock()
        mapping_response.json.return_value = [
            {
                "id": "event1",
                "matched_disasters": self.sample_disasters[:1]
            }
        ]

        mock_get.side_effect = [calendar_response, mapping_response]

        response = self.app.post('/calendar', data={
            'date_from': '2024-03-20',
            'date_to': '2024-03-21'
        })

        self.assertEqual(response.status_code, 200)
        # Check for content that should be in the rendered template
        self.assertIn(b'Events', response.data)

    def test_calendar_form_post_missing_dates(self):
        """Test calendar form submission with missing dates"""
        response = self.app.post('/calendar', data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Missing date range', response.data)

    def test_group_disasters_by_zone(self):
        """Test grouping disasters by geographical zone"""
        grouped = group_disasters_by_zone(self.sample_disasters)

        # Should have 2 groups (2 disasters at same location, 1 at different)
        self.assertEqual(len(grouped), 2)

        # First group should have 2 disasters (same coordinates)
        self.assertEqual(grouped[0]['count'], 2)
        self.assertEqual(len(grouped[0]['disasters']), 2)

        # Second group should have 1 disaster
        self.assertEqual(grouped[1]['count'], 1)
        self.assertEqual(len(grouped[1]['disasters']), 1)

    def test_group_disasters_by_zone_invalid_data(self):
        """Test grouping disasters with invalid data"""
        invalid_disasters = [
            {
                "id": "invalid1",
                "geometry": []  # Missing coordinates
            }
        ]
        grouped = group_disasters_by_zone(invalid_disasters)
        self.assertEqual(len(grouped), 0)

    @patch('frontendModule.app.fetch_disasters_bulk')
    @patch('frontendModule.app.store_disasters_in_redis')
    def test_update_hotspots_data(self, mock_store, mock_fetch):
        """Test updating hotspots data"""
        mock_fetch.return_value = self.sample_disasters

        disasters = update_hotspots_data()

        self.assertEqual(disasters, self.sample_disasters)
        mock_fetch.assert_called_once()
        mock_store.assert_called_once_with(self.sample_disasters)

    @patch('frontendModule.app.get_disasters_from_redis')
    def test_hotspots_route(self, mock_get_disasters):
        """Test the hotspots route"""
        mock_get_disasters.return_value = self.sample_disasters

        response = self.app.get('/hotspots')

        self.assertEqual(response.status_code, 200)
        # Check for content that should be in the rendered template
        self.assertIn(b'Hotspots', response.data)
        mock_get_disasters.assert_called_once()


if __name__ == '__main__':
    unittest.main()