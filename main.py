import asyncio
import logging
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
from handlers import registration_handler, voice_handler

# Настройки Telegram-бота
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting bot")
    get_iam_token()
    task = asyncio.create_task(refresh_iam_token())
    _ = task  # Чтобы избежать предупреждения о неиспользуемой переменной

    settings: Settings = Settings(
        bot_token=TELEGRAM_BOT_TOKEN,
        storage=MemoryStorage(),
        drop_pending_updates=True,
        database=Postgres(),
    )
    bot: Bot = create_bot(settings=settings)

    dp: Dispatcher = create_dispatcher(settings=settings)
    # Включение роутеров
    dp.include_router(registration_handler.router)
    dp.include_router(voice_handler.router)
    await dp.start_polling(
        bot,
        skip_updates=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
