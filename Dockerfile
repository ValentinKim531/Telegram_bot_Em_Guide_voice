FROM python:3.10.2

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y ffmpeg && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

COPY . .

CMD ["python", "main.py"]
