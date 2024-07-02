import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from services.database import Postgres
from settings import (
    TELEGRAM_BOT_TOKEN,
    Settings,
    create_bot,
    create_dispatcher,
)
from services.yandex_service import get_iam_token, refresh_iam_token
from handlers import (
    registration_handler,
    voice_handler,
    menu_handlers,
    reminder_handler,
)

# Настройки Telegram-бота
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting bot")
    get_iam_token()
    task = asyncio.create_task(refresh_iam_token())
    _ = task

    database = Postgres()

    settings: Settings = Settings(
        bot_token=TELEGRAM_BOT_TOKEN,
        storage=MemoryStorage(),
        drop_pending_updates=True,
        database=Postgres(),
    )
    bot: Bot = create_bot(settings=settings)

    dp: Dispatcher = create_dispatcher(settings=settings)

    dp.include_router(registration_handler.router)
    dp.include_router(voice_handler.router)
    dp.include_router(menu_handlers.router)
    dp.include_router(reminder_handler.router)
    # dp.include_router(other_handler.router)

    # Логирование текущего времени
    current_time = datetime.now()
    logger.info(f"Current time at bot start: {current_time}")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(
        bot,
        skip_updates=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
