from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery, FSInputFile,
)
from aiogram.fsm.context import FSMContext
from services.database import Postgres, User
from datetime import datetime
import logging

from services.scheduler_service import ReminderManager
from states.states import ReminderStates, PersonalSettingsStates

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
    photo_path = "static/img/main_menu.jpg"

    reminders_button = InlineKeyboardButton(
        text="⏰ Напоминания", callback_data="reminder_settings"
    )
    personal_info = InlineKeyboardButton(
        text="👤 Персональная информация", callback_data="personal_info"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[[reminders_button], [personal_info]])

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
        await message.answer_photo(
            photo=FSInputFile(photo_path),
            caption="Здесь можно уточнить информацию о вас, изменить настройки, а ещё скорректировать время уведомлений, чтобы ежедневный опрос был точнее и комфортнее.",
            reply_markup=markup,
        )
    else:
        await message.answer(
            text="Пожалуйста, сначала зарегистрируйтесь, выбрав язык. "
                 "Вы можете это сделать нажав /start \nв меню ↙️"
        )


@router.callback_query(F.data == "reminder_settings")
async def reminder_settings(callback_query: CallbackQuery):
    photo_path = "static/img/reminders.jpg"

    set_time_button = InlineKeyboardButton(
        text="Установить точное время опроса",
        callback_data="set_reminder_time",
    )
    disable_button = InlineKeyboardButton(
        text="Отключить напоминания", callback_data="disable_reminder"
    )
    back_button = InlineKeyboardButton(text="Назад ↩️", callback_data="back_to_settings")

    markup = InlineKeyboardMarkup(
        inline_keyboard=[[set_time_button], [disable_button], [back_button]]
    )
    await callback_query.message.answer_photo(
        photo=FSInputFile(photo_path),
        caption="Настройки напоминаний",
        reply_markup=markup
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
    photo_path = "static/img/pers_settings.jpg"

    buttons = [
        InlineKeyboardButton(text="🌐 Сменить язык", callback_data="change_language"),
        InlineKeyboardButton(text="📝 Указать ФИО", callback_data="set_fullname"),
        InlineKeyboardButton(text="🌸 Указать менструальный цикл", callback_data="set_menstrual_cycle"),
        InlineKeyboardButton(text="🌍 Указать страну", callback_data="set_country"),
        InlineKeyboardButton(text="🏙️ Указать город", callback_data="set_city"),
        InlineKeyboardButton(text="💊Указать постоянный медикамент", callback_data="set_medicament"),
        InlineKeyboardButton(text="Назад ↩️", callback_data="back_to_settings"),
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=[[button] for button in buttons])

    await callback_query.message.delete()
    await callback_query.message.answer_photo(
        photo=FSInputFile(photo_path),
        caption="Здесь вы можете изменить свои персональные данные.",
        reply_markup=markup
    )


@router.callback_query(F.data == "set_fullname")
async def set_fullname_handler(callback_query: CallbackQuery, state: FSMContext):
    button = InlineKeyboardButton(text="Назад ↩️", callback_data="back_to_settings")
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])


    await state.set_state(PersonalSettingsStates.waiting_for_fullname)
    await callback_query.message.delete()
    await callback_query.message.answer("Отправьте ваше ФИО либо вернитесь в меню", reply_markup=markup)



@router.message(PersonalSettingsStates.waiting_for_fullname)
async def receive_fullname(message: Message, state: FSMContext, database: Postgres):
    user_id = message.from_user.id
    fullname = message.text

    try:
        await database.update_entity_parameter(
            entity_id=user_id,
            parameter="fio",
            value=fullname,
            model_class=User
        )
        await state.clear()
        await message.answer("ФИО обновлено.")
    except Exception as e:
        logger.error(f"Error updating fullname: {e}")
        await message.answer("Произошла ошибка при обновлении ФИО.")


@router.callback_query(F.data == "set_menstrual_cycle")
async def set_menstrual_cycle_handler(callback_query: CallbackQuery, state: FSMContext):
    yes_button = InlineKeyboardButton(text="Да", callback_data="menstrual_cycle_yes")
    no_button = InlineKeyboardButton(text="Нет", callback_data="menstrual_cycle_no")
    back_button = InlineKeyboardButton(text="Назад ↩️", callback_data="back_to_settings")
    markup = InlineKeyboardMarkup(inline_keyboard=[[yes_button, no_button], [back_button]])

    await callback_query.message.delete()
    await callback_query.message.answer(
        "Имеется ли у вас менструальный цикл?",
        reply_markup=markup
    )

@router.callback_query(lambda c: c.data in ["menstrual_cycle_yes", "menstrual_cycle_no"])
async def receive_menstrual_cycle(callback_query: CallbackQuery, state: FSMContext, database: Postgres):
    user_id = callback_query.from_user.id
    menstrual_cycle = "да" if callback_query.data == "menstrual_cycle_yes" else "нет"

    try:
        await database.update_entity_parameter(
            entity_id=user_id,
            parameter="menstrual_cycle",
            value=menstrual_cycle,
            model_class=User
        )
        await callback_query.message.delete()
        await callback_query.message.answer("Данные о менструальном цикле обновлены.")
    except Exception as e:
        logger.error(f"Error updating menstrual cycle: {e}")
        await callback_query.message.delete()
        await callback_query.message.answer("Произошла ошибка при обновлении данных о менструальном цикле.")



@router.callback_query(F.data == "set_country")
async def set_country_handler(callback_query: CallbackQuery, state: FSMContext):
    button = InlineKeyboardButton(text="Назад ↩️", callback_data="back_to_settings")
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await state.set_state(PersonalSettingsStates.set_country)
    await callback_query.message.delete()
    await callback_query.message.answer("Напишите и отправьте вашу страну, либо вернитесь в меню настроек", reply_markup=markup)


@router.message(PersonalSettingsStates.set_country)
async def receive_country(message: Message, state: FSMContext, database: Postgres):
    user_id = message.from_user.id
    country = message.text

    try:
        await database.update_entity_parameter(
            entity_id=user_id,
            parameter="country",
            value=country,
            model_class=User
        )
        await state.clear()
        await message.answer("Ваша страна обновлена.")
    except Exception as e:
        logger.error(f"Error updating country: {e}")
        await message.answer("Произошла ошибка при обновлении страны.")


@router.callback_query(F.data =="set_city")
async def set_city_handler(callback_query: CallbackQuery, state: FSMContext):
    button = InlineKeyboardButton(text="Назад ↩️", callback_data="back_to_settings")
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await state.set_state(PersonalSettingsStates.waiting_for_city)
    await callback_query.message.delete()
    await callback_query.message.answer("Напишите и отправьте ваш город, либо вернитесь в меню настроек", reply_markup=markup)


@router.message(PersonalSettingsStates.waiting_for_city)
async def receive_city(message: Message, state: FSMContext, database: Postgres):
    user_id = message.from_user.id
    city = message.text

    try:
        await database.update_entity_parameter(
            entity_id=user_id,
            parameter="city",
            value=city,
            model_class=User
        )
        await state.clear()
        await message.answer("Ваш город обновлен.")
    except Exception as e:
        logger.error(f"Error updating city: {e}")
        await message.answer("Произошла ошибка при обновлении города.")


@router.callback_query(F.data =="set_medicament")
async def set_medicament_handler(callback_query: CallbackQuery, state: FSMContext):
    button = InlineKeyboardButton(text="Назад ↩️", callback_data="back_to_settings")
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await state.set_state(PersonalSettingsStates.set_medicament)
    await callback_query.message.delete()
    await callback_query.message.answer(
        "Напишите и отправьте название препарата, "
        "который вы принимаете на постоянной основе "
        "для лечения хронической головной боли,"
        "либо вернитесь в меню настроек",
        reply_markup=markup
    )


@router.message(PersonalSettingsStates.set_medicament)
async def receive_medicament(message: Message, state: FSMContext, database: Postgres):
    user_id = message.from_user.id
    medicament = message.text

    try:
        await database.update_entity_parameter(
            entity_id=user_id,
            parameter="const_medication_name",
            value=medicament,
            model_class=User
        )
        await state.clear()
        await message.answer("Название постоянного медикамента обновлено.")
    except Exception as e:
        logger.error(f"Error updating medicament: {e}")
        await message.answer("Произошла ошибка при обновлении названия медикамента.")



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
















