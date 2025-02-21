FROM python:3.12

WORKDIR /app

# add group and user to run a container
RUN groupadd -r webservice && useradd --no-log-init -r -g webservice webservice

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER webservice:webservice

EXPOSE 5000

CMD ["python", "main.py"]
