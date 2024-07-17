import os
from datetime import datetime
from collections import Counter
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
from dateutil.relativedelta import relativedelta

from handlers.registration_handler import start_survey
from services.database import Survey, Postgres, User
import pandas as pd
from io import BytesIO
import logging

from services.save_survey_response import (
    get_calendar_marks,
    generate_calendar_markup,
    get_survey_by_date,
)
from services.statistics import generate_statistics_file
from utils.datetime_utils import get_current_time_in_almaty_naive

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text.in_("/headache"))
async def menu_command_headache(
    message: Message, state: FSMContext, database: Postgres
):

    record_for_today_ru = InlineKeyboardButton(
        text="📝 Запись на сегодня", callback_data="record_for_ru"
    )
    record_for_today_kz = InlineKeyboardButton(
        text="📝 Бүгінгі жазба", callback_data="record_for_kk"
    )

    markup_ru = InlineKeyboardMarkup(inline_keyboard=[[record_for_today_ru]])
    markup_kz = InlineKeyboardMarkup(inline_keyboard=[[record_for_today_kz]])

    # Check if user exists
    user_id = message.from_user.id
    existing_user_language = await database.get_entity_parameter(
        model_class=User, filters={"userid": user_id}, parameter="language"
    )
    # Путь к изображению
    photo_path = "static/img/diary.jpeg"

    if existing_user_language:
        if existing_user_language == "kk":
            await message.answer_photo(
                photo=FSInputFile(photo_path),
                caption="Бүгінге жазба жасай аласыз:",
                reply_markup=markup_kz,
            )
        else:
            await message.answer_photo(
                photo=FSInputFile(photo_path),
                caption="Вы можете создать запись на сегодня:",
                reply_markup=markup_ru,
            )
    else:
        await message.answer(
            text="Пожалуйста, сначала зарегистрируйтесь, выбрав язык."
            "Вы можете это сделать нажав /start \nв меню ↙️"
        )


async def generate_diary_title(marks):
    if not marks:
        return "Записей в этом месяце нет."

    counter = Counter(marks.get("headache_medicament_today", []))
    medicament_output = "\n".join(
        f"{medicament.title()} - {count}"
        for medicament, count in counter.items()
    )

    diary_title = (
        f"Ваш дневник\n\nЕсли в календаре уже есть запись, то значок покажет, была ли боль\n"
        "🔸 - боль без лекарств\n"
        "🔺 - головная боль и лекарства"
        "\n✓ - запись об отсутствии головной боли\n\n"
    )

    if marks.get("count_headache"):
        diary_title += f"Дней с головной болью: {marks['count_headache']}\n\n"
    else:
        diary_title += f"🗒 Записей в этом месяце нет"
    if marks.get("count_headache_medicament_today"):
        diary_title += f"Дней, когда вы принимали обезболивающее: {marks['count_headache_medicament_today']}\n\n"
    if medicament_output:
        diary_title += f"Вы принимали обезболивающие:\n{medicament_output} "

    return diary_title


async def edit_message_if_needed(callback_query, new_text, new_markup):
    try:
        current_message = callback_query.message
        if (current_message.text != new_text) or (
            current_message.reply_markup != new_markup
        ):
            await callback_query.message.edit_text(
                new_text, reply_markup=new_markup
            )
    except Exception as e:
        print(f"Failed to edit message: {e}")


@router.message(F.text.in_("/calendar"))
async def show_calendar(
    message: Message, state: FSMContext, database: Postgres
):
    user_id = message.from_user.id
    current_date = get_current_time_in_almaty_naive()
    month = current_date.month
    year = current_date.year

    marks = await get_calendar_marks(database, user_id, month, year)
    calendar_markup = generate_calendar_markup(month, year, marks)
    diary_title = await generate_diary_title(marks)

    await message.answer(diary_title, reply_markup=calendar_markup)
    await state.update_data(calendar_date=current_date, calendar_marks=marks)


async def handle_month_change(
    callback_query: CallbackQuery,
    state: FSMContext,
    database: Postgres,
    months_delta: int,
):
    data = await state.get_data()
    calendar_date = data.get("calendar_date")
    new_date = calendar_date + relativedelta(months=months_delta)

    marks = await get_calendar_marks(
        database, callback_query.from_user.id, new_date.month, new_date.year
    )
    calendar_markup = generate_calendar_markup(
        new_date.month, new_date.year, marks
    )
    diary_title = await generate_diary_title(marks)

    await edit_message_if_needed(callback_query, diary_title, calendar_markup)
    await state.update_data(calendar_date=new_date, calendar_marks=marks)


@router.callback_query(lambda c: c.data and c.data.startswith("prev_month"))
async def prev_month(
    callback_query: CallbackQuery, state: FSMContext, database: Postgres
):
    await handle_month_change(callback_query, state, database, -1)


@router.callback_query(lambda c: c.data and c.data.startswith("next_month"))
async def next_month(
    callback_query: CallbackQuery, state: FSMContext, database: Postgres
):
    await handle_month_change(callback_query, state, database, 1)


@router.callback_query(lambda c: c.data and c.data.startswith("date_"))
async def process_date_selection(
    callback_query: CallbackQuery, state: FSMContext, database: Postgres
):
    user_id = callback_query.from_user.id
    date_str = callback_query.data.split("_")[1]
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    print(f"selected_date: {selected_date}")
    survey = await get_survey_by_date(database, user_id, selected_date)

    if survey:
        response_text = (
            f"Дата: {selected_date}\n"
            f"Время: {survey.created_at.time()}\n"
            f"Головная боль: {survey.headache_today}\n"
            f"Принятое лекарство: {survey.medicament_today or 'Нет'}\n"
            f"Комментарии: {survey.comments or 'Нет'}"
        )
        button_text = f"Изменить {selected_date}"
    else:
        response_text = (
            f"Дата: {selected_date}\n\n"
            f"Запись отсутствует. Нажмите кнопку ниже, чтобы добавить запись."
        )
        button_text = f"Добавить запись на {selected_date}"

    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=button_text, callback_data=f"add_{date_str}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад ↩️", callback_data="back_to_calendar"
                )
            ],
        ]
    )
    await state.update_data(
        selected_date=selected_date,
        selected_month=selected_date.month,
        selected_year=selected_date.year,
    )
    await edit_message_if_needed(callback_query, response_text, inline_kb)


@router.callback_query(lambda c: c.data == "back_to_calendar")
async def back_to_calendar(
    callback_query: CallbackQuery, state: FSMContext, database: Postgres
):
    data = await state.get_data()
    selected_month = data.get("selected_month")
    selected_year = data.get("selected_year")

    if not selected_month or not selected_year:
        now = datetime.now()
        selected_month = now.month
        selected_year = now.year

    marks = await get_calendar_marks(
        database, callback_query.from_user.id, selected_month, selected_year
    )
    markup = generate_calendar_markup(selected_month, selected_year, marks)
    diary_title = await generate_diary_title(marks)

    await edit_message_if_needed(callback_query, diary_title, markup)
    await state.update_data(
        selected_month=selected_month, selected_year=selected_year
    )


@router.callback_query(lambda c: c.data and c.data.startswith("add_"))
async def add_or_update_record(
    callback_query: CallbackQuery, state: FSMContext
):
    date_str = callback_query.data.split("_")[1]
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    await state.update_data(selected_date=selected_date)
    await start_survey(
        state,
        message=callback_query.message,
        bot=callback_query.bot,
        user_id=callback_query.from_user.id,
    )


@router.message(F.text.in_("/statistics"))
async def menu_command_statistics(message: Message, database: Postgres):
    download_statistics_button = InlineKeyboardButton(
        text="Скачать статистику", callback_data="download_statistics"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[[download_statistics_button]]
    )

    # Check if user exists
    user_id = message.from_user.id
    existing_user = await database.get_entity_parameter(
        model_class=User, filters={"userid": user_id}
    )

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
            text="Пожалуйста, сначала зарегистрируйтесь, выбрав язык."
            "Вы можете это сделать нажав /start \nв меню ↙️"
        )


@router.callback_query(F.data == "download_statistics")
async def send_statistics_file(
    callback_query: CallbackQuery, state: FSMContext, database: Postgres
):
    user_id = callback_query.from_user.id

    try:
        # Получаем данные из базы данных
        entities = await database.get_entities(Survey)
        user_info = await database.get_entities(User)

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

        # Подготовка и отправка файла
        temp_file_path = await generate_statistics_file(
            user_records, user_info, user_id
        )

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
