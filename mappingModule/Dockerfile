FROM python:3.12

WORKDIR /app

# Add group and user to run a container securely
RUN groupadd -r webservice && useradd --no-log-init -r -g webservice webservice

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER webservice:webservice

EXPOSE 5003

CMD ["python", "match_service.py"]
