from aiogram.fsm.state import StatesGroup, State


class Form(StatesGroup):
    waiting_for_voice = State()
    thread_id = State()


class ReminderStates(StatesGroup):
    set_time = State()
    disable_reminder = State()
