FROM python:3.12.0b4-alpine3.18
WORKDIR /src
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "bot_1h.py"]

# syntax=docker/dockerfile:1

# FROM python:3.8-slim-buster

# WORKDIR /app

# COPY requirements.txt requirements.txt
# RUN pip3 install -r requirements.txt

# COPY . .

# CMD ["python", "bot_1h.py"]