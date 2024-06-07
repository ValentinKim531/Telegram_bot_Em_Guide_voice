import asyncio
import logging
import os
import requests
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, Message
from dotenv import load_dotenv
from pydub import AudioSegment
import aiohttp

# Настройки окружения и инициализация OpenAI
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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

# Обработка команды /start
@router.message(CommandStart())
async def process_start_command(message: Message, state: FSMContext):
    logger.info("Received /start command")

    # Запрашиваем новый thread_id
    logger.info("Requesting new thread_id")
    thread_id = await get_new_thread_id()
    logger.info(f"New thread_id received: {thread_id}")

    await state.update_data(thread_id=thread_id)

    # Направляем сообщение "Здравствуйте" напрямую в ассистента
    response_text, new_thread_id, full_response = await process_question("Здравствуйте", thread_id)
    logger.info(f"Response from GPT: {response_text}, new thread_id: {new_thread_id}, full response: {full_response}")

    await state.update_data(thread_id=new_thread_id)

    # Преобразование текстового ответа в аудио с использованием TTS API
    logger.info("Generating speech audio with TTS API")
    audio_response_bytes = await generate_speech(response_text)
    logger.info("Generated speech audio")

    mp3_audio_path = "response.mp3"
    with open(mp3_audio_path, "wb") as mp3_audio_file:
        mp3_audio_file.write(audio_response_bytes)

    try:
        await message.answer_voice(voice=FSInputFile(mp3_audio_path), caption=response_text)
        logger.info("Voice response successfully sent")
    except Exception as e:
        logger.error(f"Failed to send voice response: {e}")
        await message.answer("Не удалось отправить голосовой ответ.")
    finally:
        if os.path.exists(mp3_audio_path):
            os.remove(mp3_audio_path)
            logger.info(f"File {mp3_audio_path} deleted")

    await state.set_state(Form.waiting_for_voice)

async def get_new_thread_id():
    thread = await client.beta.threads.create()
    return thread.id

# Обработка голосовых сообщений
@router.message(Form.waiting_for_voice, F.voice)
async def handle_voice_message(message: Message, state: FSMContext):
    try:
        logger.info("Received voice message")

        voice_file_id = message.voice.file_id
        logger.info(f"Voice file id: {voice_file_id}")
        file_info = await bot.get_file(voice_file_id)
        file_url = f'https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}'
        logger.info(f"File URL: {file_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    file_content = await response.read()
                    with open("voice.oga", "wb") as voice_file:
                        voice_file.write(file_content)
                    logger.info("File successfully downloaded and saved as voice.oga")
                else:
                    logger.error(f"Failed to download file: HTTP status {response.status}")
                    return

        # Конвертация файла в mp3
        logger.info("Converting OGA to MP3")
        audio = AudioSegment.from_file("voice.oga")
        audio.export("voice.mp3", format="mp3")
        logger.info("File successfully converted to voice.mp3")

        # Преобразование аудио в текст с использованием Whisper API через requests
        logger.info("Starting transcription with Whisper API")
        speech_text = transcribe_audio("voice.mp3")
        logger.info(f"Recognized text: {speech_text}")
        await message.answer(text=f"Вы произнесли: '{speech_text}', ожидайте ответа...")

        # Получаем thread_id из состояния
        data = await state.get_data()
        thread_id = data.get('thread_id')
        logger.info(f"Using thread_id: {thread_id}")

        # Обработка запроса с помощью GPT-3
        logger.info(f"Sending question to GPT-3 with thread_id: {thread_id}")
        response_text, new_thread_id, full_response = await process_question(speech_text, thread_id)
        logger.info(
            f"Response from GPT: {response_text}, new thread_id: {new_thread_id}, full response: {full_response}")

        # Сохраняем новый thread_id в состоянии
        await state.update_data(thread_id=new_thread_id)

        # Преобразование текстового ответа в аудио с использованием TTS API
        logger.info("Generating speech audio with TTS API")
        audio_response_bytes = await generate_speech(response_text)
        logger.info("Generated speech audio")

        mp3_audio_path = "response.mp3"
        with open(mp3_audio_path, "wb") as mp3_audio_file:
            mp3_audio_file.write(audio_response_bytes)

        try:
            await message.answer_voice(voice=FSInputFile(mp3_audio_path), caption=response_text)
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
    except Exception as e:
        logger.error(f"Error in handle_voice_message: {e}")

# Функция для транскрибации аудио с использованием requests
def transcribe_audio(file_path):
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    files = {
        'file': open(file_path, 'rb'),
        'model': (None, 'whisper-1'),
        'language': (None, 'ru')
    }
    response = requests.post(url, headers=headers, files=files)
    response_data = response.json()
    logger.info(f"Transcription API response: {response_data}")
    if response.status_code == 200:
        return response_data['text']
    else:
        logger.error(f"Error in transcribe_audio: {response_data}")
        return "Произошла ошибка при транскрибации аудио."

# Функции для обработки запросов и генерации ответов
async def process_question(question, thread_id=None):
    try:
        logger.info("Processing question with GPT-3")
        if not thread_id:
            thread = await client.beta.threads.create()
            thread_id = thread.id
            logger.info(f"New thread created with ID: {thread_id}")

        await client.beta.threads.messages.create(thread_id=thread_id, role="user", content=question)
        run = await client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_ID)

        while run.status in ['queued', 'in_progress', 'cancelling']:
            await asyncio.sleep(1)
            run = await client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

        if run.status == 'completed':
            messages = await client.beta.threads.messages.list(thread_id=thread_id)
            assistant_messages = [msg.content[0].text.value for msg in messages.data if msg.role == 'assistant']
            if assistant_messages:
                return assistant_messages[0], thread_id, messages  # Извлекаем первый ответ
            else:
                return "Не удалось получить ответ от ассистента.", thread_id, messages
        else:
            return "Не удалось получить ответ от ассистента.", thread_id, run
    except Exception as e:
        logger.error(f"Error in process_question: {e}")
        return "Произошла ошибка при обработке вопроса.", thread_id, None


async def generate_speech(text):
    try:
        logger.info("Generating speech with TTS API")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.openai.com/v1/audio/speech',
                headers={'Authorization': f'Bearer {OPENAI_API_KEY}'},
                json={'model': 'tts-1', 'voice': 'alloy', 'input': text}
            ) as response:
                result = await response.read()
                logger.info(f"Generated speech length: {len(result)} bytes")
                return result
    except Exception as e:
        logger.error(f"Error in generate_speech: {e}")
        return b''

dp.include_router(router)

async def main():
    logger.info("Starting bot")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
