import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Google Calendar API configuration
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = "http://localhost:5001/callback"
    GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    GEOCODING_API_URL="https://maps.googleapis.com/maps/api/geocode/json"
    GEOCODING_API_KEY = 'AIzaSyCH62GAwaUuxFUqA1RgeS20IfRhU1eOu20'
    
    # RabbitMQ configuration
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
    RABBITMQ_EXCHANGE = "calendar_events"
    RABBITMQ_QUEUE = "calendar_queue"
    RABBITMQ_ROUTING_KEY = "default"
    
    # Service configuration
    CALENDAR_SERVICE_PORT = 5001
    FRONTEND_SERVICE_URL = "http://localhost:5002"