from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from services.database import Postgres, User
from datetime import datetime
import logging

from services.scheduler_service import ReminderManager
from states.states import ReminderStates

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "/settings")
async def settings_command(message: Message, state: FSMContext, database: Postgres):
    await show_settings_menu(message, state, database)

@router.callback_query(F.data == "back_to_settings")
async def back_to_settings_handler(callback_query: CallbackQuery, state: FSMContext, database: Postgres):
    await callback_query.message.delete()
    await show_settings_menu(callback_query.message, state, database)

async def show_settings_menu(message: Message, state: FSMContext, database: Postgres):
    reminders_button = InlineKeyboardButton(
        text="Напоминания", callback_data="reminder_settings"
    )
    personal_info = InlineKeyboardButton(
        text="Персональная информация", callback_data="personal_info"
    )
    bot_settings = InlineKeyboardButton(
        text="Настройки бота", callback_data="bot_settings"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[reminders_button], [personal_info], [bot_settings]])

    user_id = message.from_user.id
    data = await state.get_data()
    existing_user = data.get("existing_user")

    if existing_user is None:
        existing_user = await database.get_entity_parameter(
            model_class=User, filters={"userid": user_id}
        )
        if existing_user:
            await state.update_data(existing_user=True)

    if existing_user:
        await message.answer(
            "Здесь можно уточнить информацию о вас, изменить настройки, а ещё скорректировать время уведомлений, чтобы ежедневный опрос был точнее и комфортнее.",
            reply_markup=markup,
        )
    else:
        await message.answer(
            text="Пожалуйста, сначала зарегистрируйтесь, выбрав язык. "
                 "Вы можете это сделать нажав /start \nв меню ↙️"
        )


@router.callback_query(F.data == "reminder_settings")
async def reminder_settings(callback_query: CallbackQuery):
    set_time_button = InlineKeyboardButton(
        text="Установить точное время опроса",
        callback_data="set_reminder_time",
    )
    disable_button = InlineKeyboardButton(
        text="Отключить напоминания", callback_data="disable_reminder"
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[set_time_button], [disable_button]]
    )
    await callback_query.message.answer(
        "Настройки напоминаний", reply_markup=markup
    )


@router.callback_query(F.data == "set_reminder_time")
async def set_reminder_time(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer(
        "Укажите время опроса в формате ЧЧ:ММ Например 17:45 или 09:05"
    )
    await state.set_state(ReminderStates.set_time)


@router.message(ReminderStates.set_time)
async def process_set_time(
    message: Message, state: FSMContext, database: Postgres, bot: Bot
):
    try:
        reminder_time_str = message.text
        reminder_time = datetime.strptime(reminder_time_str, "%H:%M").time()
        user_id = message.from_user.id

        await database.update_entity_parameter(
            entity_id=user_id,
            parameter="reminder_time",
            value=reminder_time,
            model_class=User,
        )

        await state.clear()
        reminder_manager = ReminderManager(database, bot, state)
        # await reminder_manager.schedule_reminder(
        #     user_id, reminder_time
        # )
        # Устанавливаем напоминание
        await reminder_manager.schedule_reminder(user_id, reminder_time)

        await message.answer(
            "Время напоминания установлено.\n До скорой встречи!"
        )
    except ValueError as e:
        logger.error(f"Error parsing reminder_time: {e}")
        await message.answer(
            "Неверный формат времени. Пожалуйста, укажите время в формате ЧЧ:ММ."
        )
    except Exception as e:
        logger.error(f"Error setting reminder time: {e}")
        await message.answer(
            "Произошла ошибка при установке времени напоминания. Пожалуйста, попробуйте снова."
        )


@router.callback_query(F.data == "disable_reminder")
async def disable_reminder(
    callback_query: CallbackQuery,
    state: FSMContext,
    database: Postgres,
    bot: Bot,
):
    try:
        user_id = callback_query.from_user.id
        await database.update_entity_parameter(
            entity_id=user_id,
            parameter="reminder_time",
            value=None,
            model_class=User,
        )
        await state.clear()

        reminder_manager = ReminderManager(database, bot, state)

        # Отменяем напоминание
        await reminder_manager.cancel_reminder(user_id)

        await callback_query.message.answer("Напоминание отключено.")
    except Exception as e:
        logger.error(f"Error disabling reminder: {e}")
        await callback_query.message.answer(
            "Произошла ошибка при отключении напоминания. Пожалуйста, попробуйте снова."
        )

@router.callback_query(F.data == "personal_info")
async def personal_info_handler(callback_query: CallbackQuery, state: FSMContext):
    change_language_button = InlineKeyboardButton(
        text="Сменить язык", callback_data="change_language"
    )
    back_button = InlineKeyboardButton(
        text="Назад ↩️", callback_data="back_to_settings"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[change_language_button], [back_button]])

    await callback_query.message.delete()
    await callback_query.message.answer(
        "Здесь вы можете изменить свои персональные данные.",
        reply_markup=markup
    )

@router.callback_query(F.data == "change_language")
async def change_language_handler(callback_query: CallbackQuery):
    rus_button = InlineKeyboardButton(
        text="Русский", callback_data="set_lang_from_menu_ru"
    )
    kaz_button = InlineKeyboardButton(
        text="Қазақ", callback_data="set_lang_from_menu_kk"
    )
    back_button = InlineKeyboardButton(
        text="Назад ↩️", callback_data="personal_info"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[rus_button], [kaz_button], [back_button]])

    await callback_query.message.delete()
    await callback_query.message.answer(
        "Пожалуйста, выберите язык общения с ботом.",
        reply_markup=markup
    )

@router.callback_query(F.data.in_({"set_lang_from_menu_ru", "set_lang_from_menu_kk"}))
async def set_language(callback_query: CallbackQuery, state: FSMContext, database: Postgres):
    user_id = callback_query.from_user.id
    language = "ru" if callback_query.data == "set_lang_from_menu_ru" else "kk"
    language_text = "Русский" if language == "ru" else "Қазақ"

    try:
        await database.update_entity_parameter(
            entity_id=user_id,
            parameter="language",
            value=language,
            model_class=User
        )
        await state.update_data(language=language)
        await callback_query.message.delete()
        await callback_query.message.answer(f"Выбран {language_text} язык.")
    except Exception as e:
        logger.error(f"Error updating language: {e}")
        await callback_query.message.delete()
        await callback_query.message.answer("Произошла ошибка при обновлении языка.")