Disaster Tracker Project
Calendar Module README (Author Lidiya Hanicheva)

This module takes user's Google Calendar events data,
filter fields, match events with location geo data and
publishes processed events to RabbitMQ topic.

-----get events using HTTP------------
http://localhost:5001/?date_from=2024-02-01&date_to=2024-02-10

-----get events using Python---------
response = requests.get("http://localhost:5000", params={"date_from": "2024-01-01", "date_to": "2024-02-01"})

-----build calendar----------
docker build -t calendar:latest .

-----run calendar------------
docker run -d -p 5001:5001 --name calendar -e RABBITMQ_HOST=rabbitmq calendar:latest                     

-----run RabbitMQ-----
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

---run docker compose----
docker-compose up -d

