from aiogram.fsm.state import StatesGroup, State


class Form(StatesGroup):
    waiting_for_voice = State()
    thread_id = State()


class ReminderStates(StatesGroup):
    set_time = State()
    disable_reminder = State()


class PersonalSettingsStates(StatesGroup):
    waiting_for_fullname = State()
    set_country = State()
    waiting_for_city = State()
    set_medicament = State()




