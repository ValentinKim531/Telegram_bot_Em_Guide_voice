FROM python:3.10.2

WORKDIR /app

COPY requirements.txt .


RUN apt-get update && apt-get install -y ffmpeg


RUN python -m venv /app/venv && \
    /app/venv/bin/pip install --upgrade pip && \
    /app/venv/bin/pip install -r requirements.txt

COPY . .


CMD ["/app/venv/bin/python", "main.py"]
