from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from pydub import AudioSegment
import aiohttp
import os
import logging
from services.openai_service import process_question, get_new_thread_id
from services.yandex_service import (
    recognize_speech,
    synthesize_speech,
    translate_text,
)
from settings import ASSISTANT2_ID, ASSISTANT_ID
from states.states import Form
import json
from services.database.models import Database, User, Survey
from utils.datetime_utils import get_current_time_in_almaty_naive

router = Router()
logger = logging.getLogger(__name__)


@router.message(Form.waiting_for_voice, F.voice)
async def handle_voice_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    database: Database,
):
    try:
        logger.info("Received voice message")

        user_id = message.from_user.id
        data = await state.get_data()
        user_lang = data.get("language", "ru")
        logger.info(f"User language in handle_voice_message: {user_lang}")

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
        if recognized_text_original is None and user_lang == "ru":
            response_text = "Пожалуйста, повторите ваш ответ еще раз"
        elif recognized_text_original is None and user_lang == "kk":
            response_text = "Жауабыңызды қайта қайталаңызшы."
        else:

            if user_lang == "kk":
                recognized_text = translate_text(
                    recognized_text_original,
                    source_lang="kk",
                    target_lang="ru",
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
                ASSISTANT2_ID
                if assistant_type == "registration"
                else ASSISTANT_ID
            )
            logger.info(
                f"Sending question to GPT-4 with assistant_id: {assistant_id} and thread_id: {thread_id}"
            )
            response_text, new_thread_id, full_response = (
                await process_question(
                    recognized_text, thread_id, assistant_id
                )
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

                    # Добавляем userid в данные ответа
                    response_data["userid"] = message.from_user.id
                    logger.info(f"userid: {response_data['userid']}")
                    logger.info(f"response_data: {response_data}")

                    # Преобразование даты рождения в объект date
                    if "birthdate" in response_data:
                        try:
                            birthdate_str = response_data["birthdate"]
                            birthdate = datetime.strptime(
                                birthdate_str, "%d %B %Y"
                            ).date()
                            response_data["birthdate"] = birthdate
                        except ValueError as e:
                            logger.error(f"Error parsing birthdate: {e}")

                    # Преобразование времени напоминания в объект time
                    if "reminder_time" in response_data:
                        try:
                            reminder_time_str = response_data["reminder_time"]
                            reminder_time = datetime.strptime(
                                reminder_time_str, "%H:%M"
                            ).time()
                            response_data["reminder_time"] = reminder_time
                            logger.info(
                                f"Converted reminder_time: {reminder_time}"
                            )
                        except ValueError as e:
                            logger.error(f"Error parsing reminder_time: {e}")

                    try:
                        if assistant_type == "registration":
                            for parameter, value in response_data.items():
                                try:
                                    logger.info(
                                        f"Updating {parameter} with value {value} for user {response_data['userid']}"
                                    )
                                    await database.update_entity_parameter(
                                        entity_id=response_data["userid"],
                                        parameter=parameter,
                                        value=value,
                                        model_class=User,
                                    )
                                    logger.info(
                                        f"Updated {parameter} successfully"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Error updating {parameter}: {e}"
                                    )
                        else:
                            try:
                                current_time = (
                                    get_current_time_in_almaty_naive()
                                )
                                survey_data = Survey(
                                    userid=response_data["userid"],
                                    headache_today=response_data[
                                        "headache_today"
                                    ],
                                    pain_intensity=int(
                                        response_data["pain_intensity"]
                                    ),
                                    pain_area=response_data["pain_area"],
                                    area_detail=response_data["area_detail"],
                                    pain_type=response_data["pain_type"],
                                    comments=response_data["comments"],
                                    created_at=current_time,
                                    updated_at=current_time,
                                )
                                await database.add_entity(
                                    entity_data=survey_data,
                                    model_class=Survey,
                                )
                                logger.info("Updated successfully")
                            except Exception as e:
                                logger.error(
                                    f"Error updating {response_data}: {e}"
                                )

                    except Exception as e:
                        logger.error(
                            f"Error updating or adding user data: {e}"
                        )

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
