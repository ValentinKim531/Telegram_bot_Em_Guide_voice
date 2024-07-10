import asyncio
import logging
import os
from datetime import datetime
from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from services.database import Postgres
from settings import (
    TELEGRAM_BOT_TOKEN,
    Settings,
    create_bot,
    create_dispatcher,
    run_webhook,
)
from services.yandex_service import get_iam_token, refresh_iam_token
from handlers import (
    registration_handler,
    voice_handler,
    menu_handlers,
    reminder_handler,
)
from utils.config import WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT

# Настройки Telegram-бота
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.on_event("startup")
async def startup():
    logger.info("Starting bot")
    get_iam_token()
    task = asyncio.create_task(refresh_iam_token())
    _ = task

    database = Postgres()

    settings: Settings = Settings(
        bot_token=TELEGRAM_BOT_TOKEN,
        storage=MemoryStorage(),
        drop_pending_updates=True,
        database=database,
        webhook_url=WEBHOOK_URL,
        webhook_path=WEBHOOK_PATH,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
    bot: Bot = create_bot(settings=settings)

    dp: Dispatcher = create_dispatcher(settings=settings)

    dp.include_router(registration_handler.router)
    dp.include_router(voice_handler.router)
    dp.include_router(menu_handlers.router)
    dp.include_router(reminder_handler.router)

    # Логирование текущего времени
    current_time = datetime.now()
    logger.info(f"Current time at bot start: {current_time}")

    await run_webhook(
        app_dispatcher=dp,
        bot=bot,
        webhook_url=WEBHOOK_URL,
        webhook_path=WEBHOOK_PATH,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
