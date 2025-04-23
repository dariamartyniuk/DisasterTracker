import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Google Calendar API configuration
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
    GOOGLE_SCOPES = os.getenv("GOOGLE_SCOPES")
    GEOCODING_API_URL = os.getenv("GEOCODING_API_URL")

    GEOCODING_API_KEY = os.getenv("GEOCODING_API_KEY")
    
    # RabbitMQ configuration
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
    RABBITMQ_EXCHANGE = "calendar_events"
    RABBITMQ_QUEUE = "calendar_queue"
    RABBITMQ_ROUTING_KEY = "default"
    
    # Service configuration
    CALENDAR_SERVICE_PORT = os.getenv("CALENDAR_SERIVCE_PORT")
    FRONTEND_SERVICE_URL = os.getenv("FRONTEND_SERVICE_URL")
    CALENDAR_SERVICE_PORT = 5001
    FRONTEND_SERVICE_URL = "http://localhost:5002"