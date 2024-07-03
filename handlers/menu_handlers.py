import os
from datetime import datetime

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
from services.database.models import Survey, Database, User
import pandas as pd
from io import BytesIO
import logging

from services.save_survey_response import (
    get_calendar_marks,
    generate_calendar_markup,
    get_survey_by_date,
    get_surveys_for_month,
)
from utils.datetime_utils import get_current_time_in_almaty_naive

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text.in_("/headache"))
async def menu_command_headache(
    message: Message, state: FSMContext, database: Database
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


@router.message(F.text.in_("/calendar"))
async def show_calendar(
    message: Message, state: FSMContext, database: Database
):
    user_id = message.from_user.id
    current_date = get_current_time_in_almaty_naive()
    month = current_date.month
    year = current_date.year

    marks = await get_calendar_marks(database, user_id, month, year)
    calendar_markup = generate_calendar_markup(month, year, marks)

    diary_title = "Ваш дневник\n\nЕсли в календаре уже есть запись, то значок покажет, была ли боль\n🔸 - боль без лекарств\n🔺 - головная боль и лекарства\n✓ - запись об отсутствии головной боли"

    await message.answer(diary_title, reply_markup=calendar_markup)
    await state.update_data(calendar_date=current_date, calendar_marks=marks)


@router.callback_query(lambda c: c.data and c.data.startswith("prev_month"))
async def prev_month(
    callback_query: CallbackQuery, state: FSMContext, database: Database
):
    data = await state.get_data()
    calendar_date = data.get("calendar_date")
    prev_date = calendar_date - relativedelta(months=1)

    marks = await get_calendar_marks(
        database, callback_query.from_user.id, prev_date.month, prev_date.year
    )
    calendar_markup = generate_calendar_markup(
        prev_date.month, prev_date.year, marks
    )

    await callback_query.message.edit_reply_markup(
        reply_markup=calendar_markup
    )
    await state.update_data(calendar_date=prev_date, calendar_marks=marks)


@router.callback_query(lambda c: c.data and c.data.startswith("next_month"))
async def next_month(
    callback_query: CallbackQuery, state: FSMContext, database: Database
):
    data = await state.get_data()
    calendar_date = data.get("calendar_date")
    next_date = calendar_date + relativedelta(months=1)

    marks = await get_calendar_marks(
        database, callback_query.from_user.id, next_date.month, next_date.year
    )
    calendar_markup = generate_calendar_markup(
        next_date.month, next_date.year, marks
    )

    await callback_query.message.edit_reply_markup(
        reply_markup=calendar_markup
    )
    await state.update_data(calendar_date=next_date, calendar_marks=marks)


@router.callback_query(lambda c: c.data and c.data.startswith("date_"))
async def process_date_selection(
    callback_query: CallbackQuery, state: FSMContext, database: Database
):
    user_id = callback_query.from_user.id
    date_str = callback_query.data.split("_")[1]

    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()

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
            f"Дата: {selected_date}\n"
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
    # Сохраняем выбранную дату и текущий месяц, год в состоянии
    await state.update_data(
        selected_date=selected_date,
        selected_month=selected_date.month,
        selected_year=selected_date.year,
    )
    await callback_query.message.edit_text(
        response_text, reply_markup=inline_kb
    )


@router.callback_query(lambda c: c.data == "back_to_calendar")
async def back_to_calendar(
    callback_query: CallbackQuery, state: FSMContext, database: Database
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

    diary_title = "Ваш дневник\n\nЕсли в календаре уже есть запись, то значок покажет, была ли боль\n🔸 - боль без лекарств\n🔺 - головная боль и лекарства\n✓ - запись об отсутствии головной боли"

    await callback_query.message.edit_text(diary_title, reply_markup=markup)
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
async def menu_command_statistics(message: Message, database: Database):
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
                "Головная боль сегодня": record.medicament_today,
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
