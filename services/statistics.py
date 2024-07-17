import pandas as pd
from io import BytesIO
import aiofiles
import locale
from babel.dates import format_date

# Устанавливаем локаль на русскую
locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")


async def generate_statistics_file(user_records, user_info, user_id):
    # Фильтруем записи по user_id
    user_records = [record for record in user_records if record.userid == user_id]
    user_info = [record for record in user_info if record.userid == user_id]

    # Подготавливаем данные для DataFrame с записями
    data = [
        {
            "Номер": record.survey_id,
            "Дата создания": record.created_at.strftime("%Y-%m-%d %H:%M"),
            "Дата обновления": record.updated_at.strftime("%Y-%m-%d %H:%M"),
            "Головная боль сегодня": record.headache_today,
            "Принимали ли медикаменты": record.medicament_today,
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

    # Создаем DataFrame для данных пользователя
    user_data = [
        {
            "ID Пользователя": record.userid,
            "Имя пользователя в Telegram": record.username,
            "Имя": record.firstname,
            "Фамилия": record.lastname,
            "ФИО": record.fio,
            "Дата рождения": (
                record.birthdate.strftime("%Y-%m-%d")
                if record.birthdate
                else None
            ),
            "Менструальный цикл": record.menstrual_cycle,
            "Страна": record.country,
            "Город": record.city,
            "Медикаменты": record.medication,
            "Постоянные медикаменты": record.const_medication,
            "Название постоянных медикаментов": record.const_medication_name,
            "Время напоминания": (
                record.reminder_time.strftime("%H:%M:%S")
                if record.reminder_time
                else None
            ),
            "Дата создания": record.created_at.strftime("%Y-%m-%d"),
        }
        for record in user_info
    ]
    df_user = pd.DataFrame(user_data)

    # Сохраняем DataFrame в Excel файл на одном листе
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        # Записываем данные пользователя
        df_user.to_excel(
            writer, sheet_name="Statistics", index=False, startrow=0
        )

        # Получаем workbook и worksheet для форматирования
        workbook = writer.book
        worksheet = writer.sheets["Statistics"]

        # Форматирование заголовков таблицы пользователя
        header_format = workbook.add_format(
            {"bold": True, "bg_color": "#C6EFCE", "border": 2}
        )
        for col_num, value in enumerate(df_user.columns.values):
            worksheet.write(0, col_num, value, header_format)

        # Форматирование таблицы пользователя
        user_rows = len(df_user)
        user_format = workbook.add_format({"bg_color": "#C6EFCE", "border": 2})
        worksheet.conditional_format(
            1,
            0,
            user_rows,
            len(df_user.columns) - 1,
            {
                "type": "no_errors",
                "format": user_format,
            },
        )

        # Записываем данные опросов по месяцам
        df_records["Дата создания"] = pd.to_datetime(
            df_records["Дата создания"], format="%Y-%m-%d %H:%M"
        )
        months = (
            df_records["Дата создания"]
            .dt.to_period("M")
            .sort_values(ascending=False)
            .unique()
        )
        start_row = user_rows + 2

        for month in months:
            month_data = df_records[
                df_records["Дата создания"].dt.to_period("M") == month
            ]

            # Пишем название месяца и года в именительном падеже с большой буквы и жирным шрифтом
            month_name = format_date(
                month.start_time, "LLLL yyyy", locale="ru"
            ).capitalize()
            bold_format = workbook.add_format({"bold": True})
            worksheet.write(start_row, 0, month_name, bold_format)
            start_row += 1

            # Пишем данные за месяц
            month_data.to_excel(
                writer,
                sheet_name="Statistics",
                index=False,
                startrow=start_row,
            )

            # Форматирование заголовков таблицы опросов
            for col_num, value in enumerate(month_data.columns.values):
                worksheet.write(start_row, col_num, value, header_format)

            # Форматирование таблицы опросов
            end_row = start_row + len(month_data)
            survey_format = workbook.add_format(
                {"bg_color": "#DDEBF7", "border": 2}
            )
            worksheet.conditional_format(
                start_row + 1,
                0,
                end_row,
                len(month_data.columns) - 1,
                {
                    "type": "no_errors",
                    "format": survey_format,
                },
            )

            start_row = end_row + 3  # Добавляем отступ между таблицами

        # Автоматическая подгонка ширины колонок под содержимое
        for column in df_user.columns:
            column_width = (
                max(df_user[column].astype(str).map(len).max(), len(column))
                + 2
            )
            col_idx = df_user.columns.get_loc(column)
            worksheet.set_column(col_idx, col_idx, column_width)

    excel_buffer.seek(0)

    # Сохраняем в временный файл для отправки
    temp_file_path = "temp_statistics.xlsx"
    async with aiofiles.open(temp_file_path, "wb") as f:
        await f.write(excel_buffer.read())

    return temp_file_path
