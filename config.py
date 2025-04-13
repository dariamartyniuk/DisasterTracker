import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """
    Centralized configuration class for the DisasterTracker application.
    Contains all constants and configuration values used across the project.
    """

    # Redis configuration
    REDIS_HOST = 'localhost'
    REDIS_PORT = 6379
    REDIS_DB = 0
    
    # Service ports
    FRONTEND_SERVICE_PORT = 5002
    CALENDAR_SERVICE_PORT = 5001
    MATCHING_SERVICE_PORT = 5003

    # API URLs
    EONET_EVENTS_API_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
    CALENDAR_API_BASE_URL = f"http://localhost:{CALENDAR_SERVICE_PORT}"
    MAPPING_API_URL = "http://localhost:5003/processed-events"
    
    # Distance threshold for matching disasters to events (in kilometers)
    DISTANCE = 5000

    # Service URLs
    CALENDAR_SERVICE_URL = f"http://localhost:{CALENDAR_SERVICE_PORT}"
    MAPPING_SERVICE_URL = f"http://localhost:{MATCHING_SERVICE_PORT}"
    FRONTEND_SERVICE_URL = f"http://localhost:{FRONTEND_SERVICE_PORT}"

    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = f"{CALENDAR_SERVICE_URL}/callback"
    GOOGLE_SCOPES = ['https://www.googleapis.com/auth/calendar']

    # RabbitMQ
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_EXCHANGE = "calendar_events"
    RABBITMQ_QUEUE = "calendar_queue"
    RABBITMQ_ROUTING_KEY = "default"

    # Redis
    REDIS_MATCHED_EVENTS_KEY = "matched_events"
    REDIS_DISASTERS_KEY = "disasters"
    REDIS_RAW_EVENTS_KEY = "raw_events"

    # API Keys
    GEOCODING_API_KEY = 'AIzaSyCH62GAwaUuxFUqA1RgeS20IfRhU1eOu20'

    # Other constants
    EARTH_RADIUS_KM = 6371  # Earth's radius in kilometers