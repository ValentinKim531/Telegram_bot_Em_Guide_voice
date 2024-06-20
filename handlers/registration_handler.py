import os
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message,
    FSInputFile,
)
from aiogram.fsm.context import FSMContext
from services.openai_service import process_question, get_new_thread_id
from services.yandex_service import translate_text, synthesize_speech
from services.database.models import User, Database
from settings import ASSISTANT_ID, ASSISTANT2_ID
from states.states import Form
from utils.datetime_utils import get_current_time_in_almaty_naive
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def process_start_command(
    message: Message, state: FSMContext, database: Database
):
    """Send a message when the command /start is issued."""
    rus_button = InlineKeyboardButton(
        text="Русский", callback_data="set_lang_ru"
    )
    kaz_button = InlineKeyboardButton(
        text="Қазақ", callback_data="set_lang_kk"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[rus_button], [kaz_button]])

    user_id = message.from_user.id
    print(f"User ID in process_start_command: {user_id}")

    # Check if user exists
    existing_user = await database.get_entity_parameter(
        user_id, "userid", User
    )

    existing_user_language = await database.get_entity_parameter(
        user_id, "language", User
    )
    logger.info(f"existing_user language: {existing_user_language}")
    if existing_user_language:
        await state.update_data(
            language=existing_user_language, existing_user=existing_user
        )
    else:
        await state.update_data(language="ru", existing_user=existing_user)

    await message.answer(
        "Выберите язык / Тілді таңдаңыз:", reply_markup=markup
    )


@router.callback_query(
    F.data.in_(["set_lang_ru", "set_lang_kk", "record_for_today"])
)
async def set_language(
    callback_query: CallbackQuery,
    state: FSMContext,
    database: Database,
):
    """Handle language selection."""

    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    first_name = callback_query.from_user.first_name
    last_name = callback_query.from_user.last_name
    print(f"User ID in set_language: {user_id}")

    language = callback_query.data.split("_")[-1]
    print(f"language set_language: {language}")

    if language == "ru":
        await callback_query.message.answer("Вы выбрали русский язык.")
    elif language == "kk":
        await callback_query.message.answer("Сіз қазақ тілін таңдадыңыз.")

    await callback_query.answer()

    # Check if user exists
    existing_user = await database.get_entity_parameter(
        user_id, "userid", User
    )

    # Обновляем состояние
    await state.update_data(language=language, existing_user=existing_user)

    logger.info(f"existing_user: {existing_user}")
    if existing_user:
        await state.update_data(assistant_type="headache")
        await start_survey(callback_query.message, state, database)
    else:
        await process_registration(
            callback_query.message,
            state,
            database,
            user_id,
            username,
            first_name,
            last_name,
        )


async def process_registration(
    message: Message,
    state: FSMContext,
    database: Database,
    user_id: int,
    username: str,
    first_name: str,
    last_name: str,
):
    logger.info("Processing registration questions")

    data = await state.get_data()
    user_lang = data.get("language", "ru")
    logger.info(f"User language on process_registration: {user_lang}")

    # Запрашиваем новый thread_id для регистрации
    logger.info("Requesting new thread_id for registration")
    thread_id = await get_new_thread_id()
    logger.info(f"New thread_id for registration received: {thread_id}")

    await state.update_data(thread_id=thread_id, assistant_type="registration")

    username = username or "none"
    firstname = first_name or "none"
    lastname = last_name or "none"
    current_time = get_current_time_in_almaty_naive()

    user_data = User(
        userid=user_id,
        username=username,
        firstname=firstname,
        lastname=lastname,
        language=user_lang,
        created_at=current_time,
        updated_at=current_time,
    )
    await database.add_entity(user_data, User)

    # Направляем первый вопрос по регистрации
    response_text, new_thread_id, full_response = await process_question(
        "Здравствуйте",
        thread_id,
        ASSISTANT2_ID,
    )
    logger.info(
        f"Response from GPT (registration): {response_text}, new thread_id: {new_thread_id}, full_response: {full_response}"
    )

    await state.update_data(thread_id=new_thread_id)

    # Перевод ответа на казахский язык, если выбран казахский язык
    if user_lang == "kk":
        logger.info(f"response_text: {response_text}")
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


async def start_survey(
    message: Message,
    state: FSMContext,
    database: Database,
):
    logger.info("Starting survey questions")

    data = await state.get_data()
    user_lang = data.get("language", "ru")
    thread_id = await get_new_thread_id()
    await state.update_data(thread_id=thread_id, assistant_type="headache")

    # Направляем первый вопрос по опросу
    response_text, new_thread_id, full_response = await process_question(
        "Здравствуйте",
        thread_id,
        ASSISTANT_ID,
    )
    logger.info(
        f"Response from GPT (survey): {response_text}, new thread_id: {new_thread_id}, full_response: {full_response}"
    )

    await state.update_data(thread_id=new_thread_id)

    # Перевод ответа на казахский язык, если выбран казахский язык
    if user_lang == "kk":
        logger.info(f"response_text: {response_text}")
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
        logger.info("Voice response for survey successfully sent")
    except Exception as e:
        logger.error(f"Failed to send voice response for survey: {e}")
        await message.answer("Не удалось отправить голосовой ответ.")
    finally:
        if os.path.exists(mp3_audio_path):
            os.remove(mp3_audio_path)
            logger.info(f"File {mp3_audio_path} deleted")

    await state.set_state(Form.waiting_for_voice)


# @router.message(CommandStart())
# async def process_start_command(message: Message):
#     """Send a message when the command /start is issued."""
#     rus_button = InlineKeyboardButton(
#         text="Русский", callback_data="set_lang_ru"
#     )
#     kaz_button = InlineKeyboardButton(
#         text="Қазақ", callback_data="set_lang_kk"
#     )
#     markup = InlineKeyboardMarkup(inline_keyboard=[[rus_button], [kaz_button]])
#
#     user_id = message.from_user.id
#     print(f"User ID in process_start_command: {user_id}")
#
#     await message.answer(
#         "Выберите язык / Тілді таңдаңыз:", reply_markup=markup
#     )


# @router.callback_query(F.data.in_(["set_lang_ru", "set_lang_kk"]))
# async def set_language(
#     callback_query: CallbackQuery,
#     state: FSMContext,
#     database: Database,
# ):
#     """Handle language selection."""
#
#     user_id = callback_query.from_user.id
#     username = callback_query.from_user.username
#     first_name = callback_query.from_user.first_name
#     last_name = callback_query.from_user.last_name
#     print(f"User ID in set_language: {user_id}")
#
#     language = callback_query.data.split("_")[-1]
#     print(f"language set_language: {language}")
#
#     # Обновляем состояние
#     await state.update_data(language=language)
#
#     # Получение данных из состояния
#     state_data = await state.get_data()
#
#     # Вывод содержимого состояния в консоль
#     print("State data:", state_data)
#
#     if language == "ru":
#         await callback_query.message.answer("Вы выбрали русский язык.")
#     elif language == "kk":
#         await callback_query.message.answer("Сіз қазақ тілін таңдадыңыз.")
#
#     await callback_query.answer()
#     await process_registration(
#         callback_query.message,
#         state,
#         database,
#         user_id,
#         username,
#         first_name,
#         last_name,
#     )
#
#
# async def process_registration(
#     message: Message,
#     state: FSMContext,
#     database: Database,
#     user_id: int,
#     username: str,
#     first_name: str,
#     last_name: str,
# ):
#     logger.info("Processing registration questions")
#
#     data = await state.get_data()
#     user_lang = data.get("language", "ru")
#     logger.info(f"User language on process_registration: {user_lang}")
#
#     # Запрашиваем новый thread_id для регистрации
#     logger.info("Requesting new thread_id for registration")
#     thread_id = await get_new_thread_id()
#     logger.info(f"New thread_id for registration received: {thread_id}")
#
#     await state.update_data(thread_id=thread_id, assistant_type="registration")
#
#     username = username or "none"
#     firstname = first_name or "none"
#     lastname = last_name or "none"
#     current_time = get_current_time_in_almaty_naive()
#
#     existing_user = await database.get_entity_parameter(
#         user_id, "userid", User
#     )
#
#     if existing_user:
#         for parameter, value in [
#             ("username", username),
#             ("firstname", firstname),
#             ("lastname", lastname),
#             ("language", user_lang),
#         ]:
#             current_value = await database.get_entity_parameter(
#                 user_id, parameter, User
#             )
#             if current_value != value:
#                 await database.update_entity_parameter(
#                     user_id, parameter, value, User
#                 )
#     else:
#         user_data = User(
#             userid=user_id,
#             username=username,
#             firstname=firstname,
#             lastname=lastname,
#             language=user_lang,
#             created_at=current_time,
#             updated_at=current_time,
#         )
#         await database.add_entity(user_data, User)
#
#     # Направляем первый вопрос по регистрации
#     response_text, new_thread_id, full_response = await process_question(
#         "Здравствуйте",
#         thread_id,
#         ASSISTANT2_ID,
#     )
#     logger.info(
#         f"Response from GPT (registration): {response_text}, new thread_id: {new_thread_id}, full_response: {full_response}"
#     )
#
#     await state.update_data(thread_id=new_thread_id)
#
#     # Перевод ответа на казахский язык, если выбран казахский язык
#     if user_lang == "kk":
#         logger.info(f"response_text: {response_text}")
#         response_text = translate_text(
#             response_text, source_lang="ru", target_lang="kk"
#         )
#
#     # Преобразование текстового ответа в аудио с использованием TTS API
#     logger.info("Generating speech audio with TTS API")
#     audio_response_bytes = synthesize_speech(
#         response_text, lang_code=user_lang
#     )
#     logger.info("Generated speech audio")
#
#     mp3_audio_path = "response.mp3"
#     with open(mp3_audio_path, "wb") as mp3_audio_file:
#         mp3_audio_file.write(audio_response_bytes)
#
#     try:
#         await message.answer_voice(
#             voice=FSInputFile(mp3_audio_path), caption=response_text
#         )
#         logger.info("Voice response for registration successfully sent")
#     except Exception as e:
#         logger.error(f"Failed to send voice response for registration: {e}")
#         await message.answer("Не удалось отправить голосовой ответ.")
#     finally:
#         if os.path.exists(mp3_audio_path):
#             os.remove(mp3_audio_path)
#             logger.info(f"File {mp3_audio_path} deleted")
#
#     await state.set_state(Form.waiting_for_voice)
