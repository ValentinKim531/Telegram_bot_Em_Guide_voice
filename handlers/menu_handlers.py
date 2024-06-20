import os
from aiogram import Router, F
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message,
    FSInputFile,
)
from aiogram.fsm.context import FSMContext
import aiofiles
from services.database.models import Survey, Database, User
import pandas as pd
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text.in_("/headache"))
async def menu_command_headache(message: Message, state: FSMContext):

    record_for_today = InlineKeyboardButton(
        text="Запись на сегодня", callback_data="record_for_today"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[[record_for_today]])

    data = await state.get_data()
    existing_user = data.get("existing_user")
    print(existing_user)

    # Путь к изображению
    photo_path = "static/img/diary.jpeg"

    if existing_user:
        await message.answer_photo(
            photo=FSInputFile(photo_path),
            caption="Вы можете создать запись на сегодня:",
            reply_markup=markup,
        )
    else:
        await message.answer(
            text="Пожалуйста, сначала зарегистрируйтесь, выбрав язык"
        )


@router.message(F.text.in_("/statistics"))
async def menu_command_statistics(message: Message, state: FSMContext):
    download_statistics_button = InlineKeyboardButton(
        text="Скачать статистику", callback_data="download_statistics"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[[download_statistics_button]]
    )

    data = await state.get_data()
    existing_user = data.get("existing_user")
    print(existing_user)

    # Путь к изображению
    photo_path = "static/img/diary.jpeg"

    if existing_user:
        await message.answer_photo(
            photo=FSInputFile(photo_path),
            caption="Дневник и статистика\n\nВы можете скачать статистику файлом\n\nА также отправить дневник врачу.",
            reply_markup=markup,
        )
    else:
        await message.answer(
            text="Пожалуйста, сначала зарегистрируйтесь, выбрав язык"
        )


@router.callback_query(F.data == "download_statistics")
async def send_statistics_file(
    callback_query: CallbackQuery, state: FSMContext, database: Database
):
    user_id = callback_query.from_user.id

    try:
        # Получаем данные из базы данных
        entities = await database.get_entities(Survey)
        user_info = await database.get_entities(
            User
        )  # Функция получения данных пользователя

        if not entities:
            await callback_query.message.answer(
                "К сожалению, у вас пока нет записей в дневнике."
            )
            return

        # Фильтруем записи по user_id
        user_records = [
            entity for entity in entities if entity.userid == user_id
        ]

        if not user_records:
            await callback_query.message.answer(
                "К сожалению, у вас пока нет записей в дневнике."
            )
            return

        # Подготавливаем данные для DataFrame с записями
        data = [
            {
                "Номер": record.survey_id,
                "Дата создания": record.created_at.strftime("%Y-%m-%d %H:%M"),
                "Дата обновления": record.updated_at.strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "Головная боль сегодня": record.headache_today,
                "Интенсивность боли": record.pain_intensity,
                "Область боли": record.pain_area,
                "Детали области": record.area_detail,
                "Тип боли": record.pain_type,
                "Комментарии": record.comments,
            }
            for record in user_records
        ]

        # Создаем DataFrame для записей
        df_records = pd.DataFrame(data)

        # Фильтруем записи по user_id
        user = [entity for entity in user_info if entity.userid == user_id]

        if not user:
            await callback_query.message.answer(
                "К сожалению, вы не зарегистрированы, пройдите регистрацию"
            )
            return

        # Создаем DataFrame для данных пользователя
        user_data = [
            {
                "User ID": record.userid,
                "username in tg": record.username,
                "username in tg": record.username,
                "firstname": record.firstname,
                "lastname": record.lastname,
                "fio": record.fio,
                "birthdate": record.birthdate.strftime("%Y-%m-%d"),
                "menstrual_cycle": record.menstrual_cycle,
                "country": record.country,
                "city": record.city,
                "medication": record.medication,
                "const_medication": record.const_medication,
                "const_medication_name": record.const_medication_name,
                "reminder_time": record.reminder_time,
                "created_at": record.created_at.strftime("%Y-%m-%d"),
            }
            for record in user
        ]
        df_user = pd.DataFrame(user_data)

        # Сохраняем DataFrame в Excel файл на одном листе
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            df_user.to_excel(
                writer, sheet_name="Statistics", index=False, startrow=0
            )
            df_records.to_excel(
                writer,
                sheet_name="Statistics",
                index=False,
                startrow=len(df_user) + 2,
            )
        excel_buffer.seek(0)

        # Сохраняем в временный файл для отправки
        temp_file_path = "temp_statistics.xlsx"
        async with aiofiles.open(temp_file_path, "wb") as f:
            await f.write(excel_buffer.read())

        # Отправляем файл пользователю
        await callback_query.message.answer_document(
            document=FSInputFile(temp_file_path, filename="statistics.xlsx")
        )
        logging.info(
            f"User {user_id} successfully downloaded their statistics."
        )

        # Удаляем временный файл
        os.remove(temp_file_path)

    except Exception as e:
        logging.error(f"Error generating statistics for user {user_id}: {e}")
        await callback_query.message.answer(
            "Произошла ошибка при попытке получить статистику."
        )


@router.message()
async def handle_any_message(message: Message, state: FSMContext):

    data = await state.get_data()
    user_lang = data.get("language", "ru")
    print(user_lang)

    if user_lang == "kk":
        await message.answer(
            text="Мен сіздің дауыс көмекшіңіз Цефалгологпын, "
            "сізге дауыс хабарламасымен жауап беру қажет."
        )
    else:
        await message.answer(
            text="Я ваш голосовой помощник Цефалголог, "
            "вам необходимо ответить голосовым сообщением."
        )
