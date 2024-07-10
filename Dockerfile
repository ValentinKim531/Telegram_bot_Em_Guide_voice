FROM python:3.10.2

WORKDIR /app

# Обновление и установка ffmpeg и других необходимых пакетов
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y ffmpeg

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN python -m venv /app/venv && \
    /app/venv/bin/pip install --upgrade pip && \
    /app/venv/bin/pip install -r requirements.txt

# Копируем весь проект
COPY . .

# Запуск приложения
CMD ["/app/venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
