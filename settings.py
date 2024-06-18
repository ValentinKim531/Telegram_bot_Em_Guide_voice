import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional, Any
from aiogram.fsm.storage.base import BaseStorage

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
ASSISTANT2_ID = os.getenv("ASSISTANT2_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YANDEX_OAUTH_TOKEN = os.getenv("YANDEX_OAUTH_TOKEN")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")


@dataclass
class Settings:
    """
    Settings for telegram bot
    """

    bot_token: Optional[str]
    storage: Optional[BaseStorage]
    drop_pending_updates: bool
    database: Any


def create_bot(settings: Settings) -> Bot:
    """
    :return: Configured Bot
    """

    session: AiohttpSession = AiohttpSession()
    return Bot(
        token=settings.bot_token,
        session=session,
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    """
    :return: Configured Dispatcher with
             included routers
    """

    dispatcher: Dispatcher = Dispatcher(
        name="main_dispatcher",
        settings=settings,
        storage=settings.storage,
        database=settings.database,
    )

    return dispatcher
