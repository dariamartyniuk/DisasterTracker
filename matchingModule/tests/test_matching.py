import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
from matchingModule.matching import (
    calculate_date_range,
    fetch_disasters_bulk,
    filter_disasters_for_event,
    haversine,
    process_events,
    store_matched_events_in_redis,
    update_hotspots_data
)

class TestMatchingModule(unittest.TestCase):
    def setUp(self):
        # Sample test data
        self.sample_events = [
            {
                "id": "event1",
                "start": {"dateTime": "2024-03-20T10:00:00+00:00"},
                "location": {
                    "northeast": {"lat": 40.7128, "lng": -74.0060},
                    "southwest": {"lat": 40.7028, "lng": -73.9960}
                },
                "summary": "Test Event 1"
            },
            {
                "id": "event2",
                "start": {"dateTime": "2024-03-25T15:00:00+00:00"},
                "location": {
                    "northeast": {"lat": 34.0522, "lng": -118.2437},
                    "southwest": {"lat": 34.0422, "lng": -118.2337}
                },
                "summary": "Test Event 2"
            }
        ]

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
                    "coordinates": [-118.2437, 34.0522],
                    "date": "2024-03-25T15:00:00Z"
                }],
                "status": "active"
            }
        ]

    def test_calculate_date_range(self):
        """Test date range calculation with valid events"""
        date_from, date_to = calculate_date_range(self.sample_events)

        # Check if dates are in correct format (YYYY-MM-DD)
        self.assertTrue(isinstance(date_from, str))
        self.assertTrue(isinstance(date_to, str))
        self.assertEqual(len(date_from.split('-')), 3)
        self.assertEqual(len(date_to.split('-')), 3)

        # Check if date range includes buffer days
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        event_start = datetime.fromisoformat(self.sample_events[0]['start']['dateTime'].split('+')[0]).date()
        event_end = datetime.fromisoformat(self.sample_events[-1]['start']['dateTime'].split('+')[0]).date()

        self.assertTrue(start_date <= event_start)
        self.assertTrue(end_date >= event_end)

    @patch('requests.get')
    def test_fetch_disasters_bulk(self, mock_get):
        """Test fetching disasters from EONET API"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"events": self.sample_disasters}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        date_from = "2024-03-15"
        date_to = "2024-03-30"
        disasters = fetch_disasters_bulk(date_from, date_to)

        self.assertEqual(len(disasters), 2)
        self.assertEqual(disasters[0]['id'], 'disaster1')
        self.assertEqual(disasters[1]['id'], 'disaster2')

        # Verify API call
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('start', kwargs['params'])
        self.assertIn('end', kwargs['params'])

    @patch('requests.get')
    def test_fetch_disasters_bulk_error(self, mock_get):
        """Test error handling in fetch_disasters_bulk"""
        mock_get.side_effect = Exception("API Error")
        
        disasters = fetch_disasters_bulk("2024-03-15", "2024-03-30")
        self.assertEqual(disasters, [])

    def test_haversine(self):
        """Test haversine distance calculation"""
        # Test distance between New York and Los Angeles (approximately 3935 km)
        ny_lat, ny_lon = 40.7128, -74.0060
        la_lat, la_lon = 34.0522, -118.2437
        
        distance = haversine(ny_lat, ny_lon, la_lat, la_lon)
        self.assertAlmostEqual(distance, 3935, delta=100)  # Allow 100km margin

        # Test same point (should be 0)
        distance = haversine(ny_lat, ny_lon, ny_lat, ny_lon)
        self.assertEqual(distance, 0)

    def test_filter_disasters_for_event(self):
        """Test filtering disasters for a specific event"""
        # Create a test event with the correct structure
        event = {
            "id": "event1",
            "coordinates": {
                "northeast": {"lat": 40.7128, "lng": -74.0060},
                "southwest": {"lat": 40.7028, "lng": -73.9960}
            },
            "summary": "Test Event 1"
        }
        
        filtered_disasters = filter_disasters_for_event(event, self.sample_disasters)
        
        self.assertEqual(len(filtered_disasters), 1)
        self.assertEqual(filtered_disasters[0]['id'], 'disaster1')

    def test_filter_disasters_for_event_no_matches(self):
        """Test filtering disasters when no matches are found"""
        event = {
            "id": "event3",
            "location": {
                "northeast": {"lat": 0.0, "lng": 0.0},
                "southwest": {"lat": 0.0, "lng": 0.0}
            }
        }
        filtered_disasters = filter_disasters_for_event(event, self.sample_disasters)
        self.assertEqual(len(filtered_disasters), 0)

    @patch('matchingModule.matching.fetch_disasters_bulk')
    def test_process_events(self, mock_fetch):
        """Test processing events and matching with disasters"""
        # Create test events with the correct structure
        test_events = [
            {
                "id": "event1",
                "coordinates": {
                    "northeast": {"lat": 40.7128, "lng": -74.0060},
                    "southwest": {"lat": 40.7028, "lng": -73.9960}
                },
                "summary": "Test Event 1"
            },
            {
                "id": "event2",
                "coordinates": {
                    "northeast": {"lat": 34.0522, "lng": -118.2437},
                    "southwest": {"lat": 34.0422, "lng": -118.2337}
                },
                "summary": "Test Event 2"
            }
        ]
        
        mock_fetch.return_value = self.sample_disasters
        
        processed_events = process_events(test_events, "2024-03-15", "2024-03-30")
        
        self.assertEqual(len(processed_events), 2)
        self.assertIn('matched_disasters', processed_events[0])
        self.assertEqual(len(processed_events[0]['matched_disasters']), 1)

    @patch('redis.Redis')
    def test_store_matched_events_in_redis(self, mock_redis):
        """Test storing matched events in Redis"""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        
        matched_results = [{
            "id": "event1",
            "matched_disasters": self.sample_disasters[:1]
        }]
        
        store_matched_events_in_redis(matched_results)
        
        # Verify Redis operations
        mock_redis_instance.delete.assert_called_once_with("matched_events")
        self.assertEqual(mock_redis_instance.rpush.call_count, 1)

    @patch('redis.Redis')
    def test_update_hotspots_data(self, mock_redis):
        """Test updating hotspots data in Redis"""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        
        matched_results = [{
            "id": "event1",
            "location": self.sample_events[0]["location"],
            "summary": "Test Event 1",
            "matched_disasters": self.sample_disasters[:1]
        }]
        
        update_hotspots_data(matched_results)
        
        # Verify Redis operations
        self.assertEqual(mock_redis_instance.delete.call_count, 2)  # Called for both keys
        self.assertEqual(mock_redis_instance.rpush.call_count, 2)  # Called for both matched_events and hotspots

if __name__ == '__main__':
    unittest.main() 