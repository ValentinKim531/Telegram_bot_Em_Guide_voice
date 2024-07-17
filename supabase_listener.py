import os
import asyncio
import json
import requests
import subprocess
from supabase import create_client, Client
import pygame
from io import BytesIO
from websocket import create_connection, WebSocketConnectionClosedException
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Инициализация клиента Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def handle_new_message(record):
    user_id = record.get("user_id")
    message_json = record.get("message")

    try:
        message_data = json.loads(message_json)
    except json.JSONDecodeError:
        print(
            f"Не удалось декодировать JSON для пользователя {user_id}: {message_json}"
        )
        return

    if "text" in message_data:
        print(
            f"Новое текстовое сообщение от пользователя {user_id}: {message_data['text']}"
        )
    elif "voice" in message_data:
        voice_url = message_data["voice"]
        print(
            f"Новое голосовое сообщение от пользователя {user_id}: {voice_url}"
        )
        download_and_convert_voice(voice_url)
    else:
        print(
            f"Неизвестный формат сообщения от пользователя {user_id}: {message_json}"
        )


def download_and_convert_voice(url):
    response = requests.get(url)
    if response.status_code == 200:
        # Загрузка содержимого файла
        voice_data = BytesIO(response.content)

        # Сохранение временного файла
        temp_oga_filename = "temp_voice_message.oga"
        with open(temp_oga_filename, "wb") as f:
            f.write(voice_data.read())

        # Конвертация в MP3
        mp3_filename = "temp_voice_message.mp3"
        command = f"ffmpeg -i {temp_oga_filename} {mp3_filename}"
        process = subprocess.run(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        if process.returncode == 0:
            print(f"Файл сохранен как: {mp3_filename}")
            play_voice_file(mp3_filename)
        else:
            print(f"Ошибка конвертации: {process.stderr.decode('utf-8')}")

    else:
        print("Ошибка загрузки файла")


def play_voice_file(filename):
    # Воспроизведение MP3 файла
    pygame.mixer.init()
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)


async def subscribe_to_messages():
    while True:
        try:
            # Создаем websocket соединение
            ws_url = (
                SUPABASE_URL.replace("https", "wss")
                + "/realtime/v1/websocket?apikey="
                + SUPABASE_KEY
            )
            print(f"Connecting to {ws_url}")
            ws = create_connection(
                ws_url, header={"Authorization": f"Bearer {SUPABASE_KEY}"}
            )

            # Подписка на изменения в таблице user_messages
            subscription_payload = {
                "event": "phx_join",
                "topic": "realtime:public:user_messages",
                "payload": {},
                "ref": 1,
            }
            ws.send(json.dumps(subscription_payload))

            try:
                while True:
                    result = ws.recv()
                    print(f"Received message: {result}")

                    if result:
                        try:
                            message = json.loads(result)

                            # Обработка новых сообщений
                            if message.get("event") == "INSERT":
                                handle_new_message(
                                    message["payload"]["record"]
                                )
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON: {e}")
                    await asyncio.sleep(1)
            except WebSocketConnectionClosedException:
                print("Connection to remote host was lost. Reconnecting...")
                ws.close()
                await asyncio.sleep(5)  # ждем перед переподключением
        except Exception as e:
            print(f"Unexpected error: {e}. Reconnecting...")
            await asyncio.sleep(5)  # ждем перед переподключением


# Запуск основного цикла событий
if __name__ == "__main__":
    asyncio.run(subscribe_to_messages())
