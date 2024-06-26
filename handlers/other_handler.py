from aiogram import Router, F
from aiogram.types import (
    Message,
)
from aiogram.fsm.context import FSMContext
import logging


logger = logging.getLogger(__name__)

router = Router()


@router.message()
async def handle_any_message(message: Message, state: FSMContext):
    data = await state.get_data()
    user_lang = data.get("language", "ru")
    print(user_lang)

    if user_lang == "kk":
        await message.answer(
            text="Мен сіздердің дауыс көмекшілеріңізбін. "
            "Сізге дауыс хабарламасымен жауап беру қажет, "
            "немесе сөйлесуді бастау үшін /start командасын басыңыз."
        )
    else:
        await message.answer(
            text="Я ваш голосовой помощник, "
            "вам необходимо ответить голосовым сообщением, "
            "либо нажмите команду /start для начала общения. "
            "Вы можете это сделать\nв меню ↙️"
        )
