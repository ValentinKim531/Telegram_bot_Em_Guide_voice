import asyncio
import logging
import os
import requests
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, Message
from dotenv import load_dotenv
from pydub import AudioSegment
import aiohttp
import sqlite3
import re
from datetime import datetime
import xlsxwriter
import json

# Настройки окружения и инициализация OpenAI
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
ASSISTANT2_ID = os.getenv("ASSISTANT2_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

YANDEX_OAUTH_TOKEN = os.getenv("YANDEX_OAUTH_TOKEN")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
YANDEX_IAM_TOKEN = None

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройки Telegram-бота
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot=bot, storage=MemoryStorage())
router = Router()


class Form(StatesGroup):
    waiting_for_voice = State()
    thread_id = State()


DATABASE_FILE = "responses.db"


def sanitize_column_name(name: str) -> str:
    name = re.sub(r"\W+", "_", name)
    return name.strip().lower()


def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS responses")
    cursor.execute("DROP TABLE IF EXISTS registration")

    headache_questions = [
        "У вас сегодня болела голова?",
        "Насколько интенсивной была боль (оцените от 1 до 10)?",
        "В какой области болела голова?",
        "Уточняющий вопрос к вопросу 3",
        "Какой был характер головной боли?",
    ]

    registration_questions = [
        "ФИО",
        "Дата рождения",
        "Менструальный цикл",
        "Страна и город",
        "Принимаете ли препарат для купирования боли?",
        "Принимаете ли вы какой-либо препарат на постоянной основе?",
        "Уточняющий ответ на 6-й вопрос",
        "Время напоминания",
    ]

    columns_headache = (
        ["date TEXT"]
        + [f"{sanitize_column_name(q)} TEXT" for q in headache_questions]
        + ["comments TEXT"]
    )
    columns_registration = (
        ["date TEXT"]
        + [f"{sanitize_column_name(q)} TEXT" for q in registration_questions]
        + ["comments TEXT"]
    )

    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS responses ({', '.join(columns_headache)})"
    )
    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS registration ({', '.join(columns_registration)})"
    )

    conn.commit()
    conn.close()
    logger.info("Database initialized with columns for both tables.")


init_db()


def save_response_to_db(state_data, table_name):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        columns = ["date"]
        values = [date_str]

        for key, value in state_data.items():
            columns.append(sanitize_column_name(key))
            values.append(value)

        columns_str = ", ".join(columns)
        values_placeholder = ", ".join(["?"] * len(values))

        logger.info(
            f"Prepared to insert into {table_name} ({columns_str}) VALUES ({values_placeholder}) with values {values}"
        )

        cursor.execute(
            f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_placeholder})",
            values,
        )
        conn.commit()
        logger.info(f"Response data saved to {table_name} successfully")
    except Exception as e:
        logger.error(f"Error saving response to {table_name}: {e}")
    finally:
        conn.close()


EXPORT_FILE = "responses.xlsx"


def export_to_xls():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Export responses
        cursor.execute("SELECT * FROM responses")
        rows_responses = cursor.fetchall()
        columns_responses = [
            description[0] for description in cursor.description
        ]

        workbook = xlsxwriter.Workbook("responses.xlsx")
        worksheet_responses = workbook.add_worksheet("Responses")

        for col_num, column_name in enumerate(columns_responses):
            worksheet_responses.write(0, col_num, column_name)

        for row_num, row in enumerate(rows_responses, start=1):
            for col_num, cell_value in enumerate(row):
                worksheet_responses.write(row_num, col_num, cell_value)

        # Export registration
        cursor.execute("SELECT * FROM registration")
        rows_registration = cursor.fetchall()
        columns_registration = [
            description[0] for description in cursor.description
        ]

        worksheet_registration = workbook.add_worksheet("Registration")

        for col_num, column_name in enumerate(columns_registration):
            worksheet_registration.write(0, col_num, column_name)

        for row_num, row in enumerate(rows_registration, start=1):
            for col_num, cell_value in enumerate(row):
                worksheet_registration.write(row_num, col_num, cell_value)

        workbook.close()
        conn.close()
        logger.info("Data exported to XLS successfully")
    except Exception as e:
        logger.error(f"Error exporting data to XLS: {e}")


@router.message(Form.waiting_for_voice, F.voice)
async def handle_voice_message(message: Message, state: FSMContext):
    try:
        logger.info("Received voice message")

        user_id = message.from_user.id
        data = await state.get_data()
        user_lang = data.get("language", "ru")
        logger.info(f"User language: {user_lang}")

        voice_file_id = message.voice.file_id
        logger.info(f"Voice file id: {voice_file_id}")
        file_info = await bot.get_file(voice_file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        logger.info(f"File URL: {file_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    file_content = await response.read()
                    with open("voice.oga", "wb") as voice_file:
                        voice_file.write(file_content)
                    logger.info(
                        "File successfully downloaded and saved as voice.oga"
                    )
                else:
                    logger.error(
                        f"Failed to download file: HTTP status {response.status}"
                    )
                    return

        # Конвертация файла в mp3
        logger.info("Converting OGA to MP3")
        audio = AudioSegment.from_file("voice.oga")
        audio.export("voice.mp3", format="mp3")
        logger.info("File successfully converted to voice.mp3")

        # Преобразование аудио в текст с использованием Yandex STT
        logger.info("Starting transcription with Yandex STT")
        recognized_text_original = recognize_speech(
            file_content, lang="kk-KK" if user_lang == "kk" else "ru-RU"
        )
        if user_lang == "kk":
            recognized_text = translate_text(
                recognized_text_original, source_lang="kk", target_lang="ru"
            )

            logger.info(f"Recognized text: {recognized_text}")

            await message.answer(
                text=f"Сіз '{recognized_text_original}' дедіңіз, жауап күтіңіз..."
            )

        else:
            await message.answer(
                text=f"Вы произнесли: '{recognized_text_original}', ожидайте ответа..."
            )
            recognized_text = recognized_text_original

        # Получаем thread_id и тип ассистента из состояния
        thread_id = data.get("thread_id")
        assistant_type = data.get("assistant_type", "registration")
        logger.info(
            f"Using thread_id: {thread_id} with assistant_type: {assistant_type}"
        )

        # Обработка запроса с помощью соответствующего GPT-3 ассистента
        assistant_id = (
            ASSISTANT2_ID if assistant_type == "registration" else ASSISTANT_ID
        )
        logger.info(
            f"Sending question to GPT-3 with assistant_id: {assistant_id} and thread_id: {thread_id}"
        )
        response_text, new_thread_id, full_response = await process_question(
            recognized_text, thread_id, assistant_id
        )
        logger.info(
            f"Response from GPT: {response_text}, new thread_id: {new_thread_id}, full_response: {full_response}"
        )

        if user_lang == "kk":
            response_text = translate_text(
                response_text, source_lang="ru", target_lang="kk"
            )

        # Сохраняем новый thread_id и тип ассистента в состоянии
        await state.update_data(
            thread_id=new_thread_id, assistant_type=assistant_type
        )

        # Преобразование текстового ответа в аудио с использованием TTS API
        logger.info("Generating speech audio with TTS API")
        audio_response_bytes = synthesize_speech(
            response_text, lang_code=user_lang
        )
        logger.info("Generated speech audio")

        mp3_audio_path = "response.mp3"
        with open(mp3_audio_path, "wb") as mp3_audio_file:
            mp3_audio_file.write(audio_response_bytes)

        try:
            await message.answer_voice(
                voice=FSInputFile(mp3_audio_path), caption=response_text
            )
            logger.info("Voice response successfully sent")
        except Exception as e:
            logger.error(f"Failed to send voice response: {e}")
            await message.answer("Не удалось отправить голосовой ответ.")
        finally:
            if os.path.exists(mp3_audio_path):
                os.remove(mp3_audio_path)
                logger.info(f"File {mp3_audio_path} deleted")
            if os.path.exists("voice.oga"):
                os.remove("voice.oga")
                logger.info("File voice.oga deleted")
            if os.path.exists("voice.mp3"):
                os.remove("voice.mp3")
                logger.info("File voice.mp3 deleted")

        # Сохранение ответов в базу данных
        final_response_json = None
        for msg in full_response.data:
            if "json" in msg.content[0].text.value:
                final_response_json = msg.content[0].text.value

        if final_response_json:
            try:
                logger.info(
                    f"Extracting JSON from response: {final_response_json}"
                )
                json_start = final_response_json.find("```json")
                json_end = final_response_json.rfind("```")
                if json_start != -1 and json_end != -1:
                    response_data_str = final_response_json[
                        json_start + len("```json") : json_end
                    ].strip()
                    response_data = json.loads(response_data_str)
                    logger.info(f"Parsed response data: {response_data}")
                    table_name = (
                        "registration"
                        if assistant_type == "registration"
                        else "responses"
                    )
                    save_response_to_db(response_data, table_name)
                    logger.info(f"Response data saved to {table_name}")

                    # Проверка завершения блока регистрации
                    if assistant_type == "registration":
                        await state.update_data(assistant_type="headache")
                        logger.info(
                            "Registration completed. Switching to headache questions."
                        )
                        # Отправка вопроса "Здравствуйте" второму ассистенту
                        new_thread_id = await get_new_thread_id()
                        response_text, new_thread_id, full_response = (
                            await process_question(
                                "Здравствуйте", new_thread_id, ASSISTANT_ID
                            )
                        )
                        logger.info(
                            f"Response from GPT (headache): {response_text}, new thread_id: {new_thread_id}, full_response: {full_response}"
                        )
                        await state.update_data(thread_id=new_thread_id)

                        if user_lang == "kk":
                            response_text = translate_text(
                                response_text,
                                source_lang="ru",
                                target_lang="kk",
                            )

                        # Преобразование текстового ответа в аудио с использованием TTS API
                        audio_response_bytes = synthesize_speech(
                            response_text, lang_code=user_lang
                        )
                        logger.info("Generated speech audio for headache")

                        mp3_audio_path = "response_headache.mp3"
                        with open(mp3_audio_path, "wb") as mp3_audio_file:
                            mp3_audio_file.write(audio_response_bytes)

                        try:
                            await message.answer_voice(
                                voice=FSInputFile(mp3_audio_path),
                                caption=response_text,
                            )
                            logger.info(
                                "Voice response for headache successfully sent"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to send voice response for headache: {e}"
                            )
                            await message.answer(
                                "Не удалось отправить голосовой ответ."
                            )
                        finally:
                            if os.path.exists(mp3_audio_path):
                                os.remove(mp3_audio_path)
                                logger.info(f"File {mp3_audio_path} deleted")
                else:
                    logger.error("JSON format not found in the response.")
            except Exception as e:
                logger.error(f"Error saving response to database: {e}")

    except Exception as e:
        logger.error(f"Error in handle_voice_message: {e}")


@router.message(CommandStart())
async def process_start_command(message: Message):
    """Send a message when the command /start is issued."""
    rus_button = InlineKeyboardButton(
        text="Русский", callback_data="set_lang_ru"
    )
    kaz_button = InlineKeyboardButton(
        text="Қазақ", callback_data="set_lang_kk"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[rus_button], [kaz_button]])

    await message.answer(
        "Выберите язык / Тілді таңдаңыз:", reply_markup=markup
    )


user_languages = {}


@router.callback_query(F.data.in_(["set_lang_ru", "set_lang_kk"]))
async def set_language(callback_query: CallbackQuery, state: FSMContext):
    """Handle language selection."""
    user_id = callback_query.from_user.id
    language = callback_query.data.split("_")[-1]
    user_languages[user_id] = language
    await state.update_data(language=language)

    if language == "ru":
        await callback_query.message.answer("Вы выбрали русский язык.")
    elif language == "kk":
        await callback_query.message.answer("Сіз қазақ тілін таңдадыңыз.")

    await callback_query.answer()

    # Call process_registration function to continue the conversation
    await process_registration(callback_query.message, state)


@router.message()
async def handle_any_message(message: Message):
    await message.answer(
        text="Я ваш голосовой помощник Цефалголог, вам необходимо отвечать боту голосовым сообщением."
    )


async def process_question(
    question, thread_id=None, assistant_id=ASSISTANT_ID
):
    try:
        logger.info("Processing question with GPT-4")
        if not thread_id:
            thread = await client.beta.threads.create()
            thread_id = thread.id
            logger.info(f"New thread created with ID: {thread_id}")

        await client.beta.threads.messages.create(
            thread_id=thread_id, role="user", content=question
        )
        run = await client.beta.threads.runs.create(
            thread_id=thread_id, assistant_id=assistant_id
        )

        while run.status in ["queued", "in_progress", "cancelling"]:
            await asyncio.sleep(1)
            run = await client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run.id
            )

        if run.status == "completed":
            messages = await client.beta.threads.messages.list(
                thread_id=thread_id
            )

            assistant_messages = [
                msg.content[0].text.value.split("```json")[0]
                for msg in messages.data
                if msg.role == "assistant"
            ]

            if assistant_messages:
                return (
                    assistant_messages[0],
                    thread_id,
                    messages,
                )  # Извлекаем первый ответ
            else:
                return (
                    "Не удалось получить ответ от ассистента.",
                    thread_id,
                    messages,
                )
        else:
            return "Не удалось получить ответ от ассистента.", thread_id, run
    except Exception as e:
        logger.error(f"Error in process_question: {e}")
        return "Произошла ошибка при обработке вопроса.", thread_id, None


async def process_registration(message: Message, state: FSMContext):
    logger.info("Processing registration questions")

    # Запрашиваем новый thread_id для регистрации
    logger.info("Requesting new thread_id for registration")
    thread_id = await get_new_thread_id()
    logger.info(f"New thread_id for registration received: {thread_id}")

    await state.update_data(thread_id=thread_id, assistant_type="registration")

    # Получаем выбранный язык из состояния
    data = await state.get_data()
    user_lang = data.get("language", "ru")

    # Направляем первый вопрос по регистрации
    response_text, new_thread_id, full_response = await process_question(
        "Здравствуйте" if user_lang == "ru" else "Здравствуйте",
        thread_id,
        ASSISTANT2_ID,
    )
    logger.info(
        f"Response from GPT (registration): {response_text}, new thread_id: {new_thread_id}, full response: {full_response}"
    )

    await state.update_data(thread_id=new_thread_id)

    # Перевод ответа на казахский язык, если выбран казахский язык
    if user_lang == "kk":
        logger.info(f"response_text111: {response_text}")
        response_text = translate_text(
            response_text, source_lang="ru", target_lang="kk"
        )

    # Преобразование текстового ответа в аудио с использованием TTS API
    logger.info("Generating speech audio with TTS API")
    audio_response_bytes = synthesize_speech(
        response_text, lang_code=user_lang
    )
    logger.info("Generated speech audio")

    mp3_audio_path = "response.mp3"
    with open(mp3_audio_path, "wb") as mp3_audio_file:
        mp3_audio_file.write(audio_response_bytes)

    try:
        await message.answer_voice(
            voice=FSInputFile(mp3_audio_path), caption=response_text
        )
        logger.info("Voice response for registration successfully sent")
    except Exception as e:
        logger.error(f"Failed to send voice response for registration: {e}")
        await message.answer("Не удалось отправить голосовой ответ.")
    finally:
        if os.path.exists(mp3_audio_path):
            os.remove(mp3_audio_path)
            logger.info(f"File {mp3_audio_path} deleted")

    await state.set_state(Form.waiting_for_voice)


async def generate_speech(text):
    try:
        logger.info("Generating speech with TTS API")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model": "tts-1", "voice": "alloy", "input": text},
            ) as response:
                result = await response.read()
                logger.info(f"Generated speech length: {len(result)} bytes")
                return result
    except Exception as e:
        logger.error(f"Error in generate_speech: {e}")
        return b""


def transcribe_audio(file_path):
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    files = {
        "file": open(file_path, "rb"),
        "model": (None, "whisper-1"),
        "language": (None, "ru"),
    }
    response = requests.post(url, headers=headers, files=files)
    response_data = response.json()
    logger.info(f"Transcription API response: {response_data}")
    if response.status_code == 200:
        return response_data["text"]
    else:
        logger.error(f"Error in transcribe_audio: {response_data}")
        return "Произошла ошибка при транскрибации аудио."


async def get_new_thread_id():
    thread = await client.beta.threads.create()
    return thread.id


def get_iam_token():
    global YANDEX_IAM_TOKEN
    url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
    payload = {"yandexPassportOauthToken": YANDEX_OAUTH_TOKEN}
    response = requests.post(url, json=payload)
    response.raise_for_status()
    YANDEX_IAM_TOKEN = response.json()["iamToken"]
    logger.info(f"Received new IAM token: {YANDEX_IAM_TOKEN}")


async def refresh_iam_token():
    while True:
        await asyncio.sleep(6 * 3600)
        get_iam_token()
        logger.info("IAM token refreshed")


def recognize_speech(audio_content, lang="ru-RU"):
    if not YANDEX_IAM_TOKEN:
        get_iam_token()
    url = f"https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?folderId={YANDEX_FOLDER_ID}&lang={lang}"
    headers = {"Authorization": f"Bearer {YANDEX_IAM_TOKEN}"}

    logger.info(f"Sending {len(audio_content)} bytes to Yandex STT.")
    response = requests.post(url, headers=headers, data=audio_content)
    response.raise_for_status()

    if response.status_code == 200:
        result = response.json().get("result")
        logger.info(f"Recognition result: {result}")
        return result
    else:
        error_message = (
            f"Failed to recognize speech, status code: {response.status_code}"
        )
        logger.error(error_message)
        raise Exception(error_message)


def synthesize_speech(text, lang_code):
    voice_settings = {
        "ru": {"lang": "ru-RU", "voice": "oksana"},
        "kk": {"lang": "kk-KK", "voice": "amira"},
    }
    settings = voice_settings.get(lang_code, voice_settings["ru"])

    url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
    headers = {"Authorization": f"Bearer {YANDEX_IAM_TOKEN}"}
    data = {
        "text": text,
        "lang": settings["lang"],
        "voice": settings["voice"],
        "folderId": YANDEX_FOLDER_ID,
        "format": "mp3",
        "sampleRateHertz": 48000,
    }

    response = requests.post(url, headers=headers, data=data, stream=True)
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response Headers: {response.headers}")

    if response.status_code == 200:
        audio_content = response.content
        logger.info(
            f"Received audio content length: {len(audio_content)} bytes"
        )
        with open("response.mp3", "wb") as file:
            file.write(audio_content)
        logger.info("Audio content saved as 'response.mp3'.")
        return audio_content
    else:
        error_message = f"Failed to synthesize speech, status code: {response.status_code}, response text: {response.text}"
        logger.error(error_message)
        raise Exception(error_message)


def translate_text(text, source_lang="ru", target_lang="kk"):
    url = "https://translate.api.cloud.yandex.net/translate/v2/translate"
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "folder_id": YANDEX_FOLDER_ID,
        "texts": [text],
        "targetLanguageCode": target_lang,
        "sourceLanguageCode": source_lang,
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        translations = response.json().get("translations", [])
        if translations:
            return translations[0]["text"]
        else:
            return "Перевод не найден."
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
        return "Перевод не удался."
    except Exception as err:
        logging.error(f"An error occurred: {err}")
        return "Перевод не удался."


dp.include_router(router)


async def main():
    logger.info("Starting bot")
    get_iam_token()
    task = asyncio.create_task(refresh_iam_token())
    _ = task
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
