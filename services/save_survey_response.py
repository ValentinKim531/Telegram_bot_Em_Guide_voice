import calendar
import logging
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from services.database import Survey, Database
from utils.datetime_utils import get_current_time_in_almaty_naive

logger = logging.getLogger(__name__)


async def save_survey_response(database, response_data, selected_date):
    existing_survey = await get_survey_by_date(
        database, response_data["userid"], selected_date
    )

    current_time = get_current_time_in_almaty_naive().time()
    combined_datetime = datetime.combine(selected_date, current_time)
    response_data["updated_at"] = combined_datetime

    if existing_survey:
        try:
            for parameter, value in response_data.items():
                if parameter != "userid":
                    await database.update_entity_parameter(
                        entity_id=(
                            existing_survey.survey_id,
                            existing_survey.userid,
                        ),
                        parameter=parameter,
                        value=value,
                        model_class=Survey,
                    )
        except Exception as e:
            logger.error(f"Error updating existing survey: {e}")

    else:
        try:
            survey_data = Survey(
                userid=response_data["userid"],
                headache_today=response_data["headache_today"],
                medicament_today=response_data["medicament_today"],
                pain_intensity=response_data["pain_intensity"],
                pain_area=response_data["pain_area"],
                area_detail=response_data["area_detail"],
                pain_type=response_data["pain_type"],
                comments=response_data["comments"],
                created_at=combined_datetime,
                updated_at=get_current_time_in_almaty_naive(),
            )
            await database.add_entity(
                entity_data=survey_data,
                model_class=Survey,
            )
        except Exception as e:
            logger.error(f"Error adding new survey: {e}")


async def get_survey_by_date(database, user_id, date: datetime.date):
    print(date)
    filters = {"userid": user_id}
    surveys = await database.get_entities_parameter(Survey, filters)

    for survey in surveys:
        logger.info(f"Survey date: {survey.created_at.date()}")

    # Фильтрация опросов по дате
    survey = next(
        (survey for survey in surveys if survey.created_at.date() == date),
        None,
    )
    logger.info(f"Found survey: {survey}")
    return survey


async def get_surveys_for_month(
    database: Database, user_id: int, month: int, year: int
) -> list:
    try:
        async with database.Session() as session:
            start_date = datetime(year, month, 1)
            end_date = start_date + relativedelta(months=1)

            result = await session.execute(
                select(Survey)
                .where(Survey.userid == user_id)
                .where(Survey.created_at >= start_date)
                .where(Survey.created_at < end_date)
            )
            return result.scalars().all()
    except Exception as e:
        logger.error(f"Error fetching surveys for month: {e}")
        return []


async def get_calendar_marks(
    database: Database, user_id: int, month: int, year: int
) -> dict:
    surveys = await get_surveys_for_month(database, user_id, month, year)
    marks = {}
    count_headache = 0
    count_headache_medicament_today = 0
    headache_medicament_today = []

    for survey in surveys:
        date_str = survey.created_at.strftime("%Y-%m-%d")
        if "да" in survey.headache_today.lower():
            if survey.medicament_today:
                marks[date_str] = "🔺"
                count_headache += 1
                count_headache_medicament_today += 1
                headache_medicament_today.append(survey.medicament_today)
            else:
                marks[date_str] = "🔸"
                count_headache += 1
        elif "нет" in survey.headache_today.lower():
            marks[date_str] = "✓"
    marks["count_headache"] = count_headache
    marks["count_headache_medicament_today"] = count_headache_medicament_today
    marks["headache_medicament_today"] = headache_medicament_today
    print(marks)
    return marks


def generate_calendar_markup(
    month: int, year: int, marks: dict
) -> InlineKeyboardMarkup:
    keyboard = []

    # Добавляем кнопку с текущим месяцем и годом на русском языке
    months_ru = [
        "",
        "Январь",
        "Февраль",
        "Март",
        "Апрель",
        "Май",
        "Июнь",
        "Июль",
        "Август",
        "Сентябрь",
        "Октябрь",
        "Ноябрь",
        "Декабрь",
    ]
    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"{months_ru[month]} {year}", callback_data="ignore"
            )
        ]
    )

    # Добавим дни недели
    keyboard.append(
        [
            InlineKeyboardButton(text=day, callback_data="ignore")
            for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        ]
    )

    # Генерация дней месяца
    month_calendar = calendar.monthcalendar(year, month)
    today = datetime.today().date()
    for week in month_calendar:
        row = []
        for day in week:
            if day == 0 or datetime(year, month, day).date() > today:
                row.append(
                    InlineKeyboardButton(text=" ", callback_data="ignore")
                )
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                text = f"{day}"
                if date_str in marks:
                    text += f" {marks[date_str]}"
                row.append(
                    InlineKeyboardButton(
                        text=text, callback_data=f"date_{date_str}"
                    )
                )
        # Удаляем пустые строки, если они идут после сегодняшнего дня
        if any(button.text.strip() for button in row):
            keyboard.append(row)

    # Кнопки для переключения месяцев
    keyboard.append(
        [
            InlineKeyboardButton(text="⬅️", callback_data="prev_month"),
            InlineKeyboardButton(text="➡️", callback_data="next_month"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
