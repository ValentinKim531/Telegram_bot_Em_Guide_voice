import json
import os
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional, Any
from aiogram.fsm.storage.base import BaseStorage
import asyncio
from aiohttp import web
from aiogram.types import Update
from supabase import create_client, Client
import logging

load_dotenv()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
ASSISTANT2_ID = os.getenv("ASSISTANT2_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YANDEX_OAUTH_TOKEN = os.getenv("YANDEX_OAUTH_TOKEN")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@dataclass
class Settings:
    """
    Settings for telegram bot
    """

    bot_token: Optional[str]
    storage: Optional[BaseStorage]
    drop_pending_updates: bool
    database: Any
    webhook_url: Optional[str]
    webhook_path: Optional[str]
    host: Optional[str]
    port: Optional[int]


def create_bot(settings: Settings) -> Bot:
    """
    :return: Configured Bot
    """

    session: AiohttpSession = AiohttpSession()
    return Bot(token=settings.bot_token, session=session)


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


async def on_startup(bot: Bot, webhook_url: str):
    await bot.set_webhook(webhook_url, drop_pending_updates=True)


async def on_shutdown(app):
    bot = app["bot"]
    await bot.session.close()


async def save_message_to_supabase(user_id: int, message: dict):
    response = (
        supabase.table("user_messages")
        .insert({"user_id": user_id, "message": json.dumps(message)})
        .execute()
    )
    if "error" in response:
        logger.error(f"Error inserting message: {response['error']}")
    else:
        logger.info("Message inserted successfully")


async def run_webhook(
    app_dispatcher: Dispatcher,
    bot: Bot,
    webhook_url: str,
    webhook_path: str,
    host: str,
    port: int,
):
    app = web.Application()
    app["bot"] = bot
    app["dispatcher"] = app_dispatcher
    app.on_startup.append(lambda app: on_startup(bot, webhook_url))
    app.on_shutdown.append(on_shutdown)

    async def get_file_url(bot, file_id):
        file = await bot.get_file(file_id)
        return f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

    async def handle_webhook(request: web.Request):
        app = request.app
        bot = app["bot"]
        update_dict = await request.json()
        update = Update(**update_dict)
        await app["dispatcher"].feed_update(bot, update)

        if update.message:
            user_id = update.message.from_user.id
            message_content = {}

            if update.message.text:
                message_content["text"] = update.message.text
            if update.message.photo:
                photos = []
                for photo in update.message.photo:
                    photo_url = await get_file_url(bot, photo.file_id)
                    photos.append(photo_url)
                message_content["photo"] = photos
            if update.message.voice:
                voice_url = await get_file_url(
                    bot, update.message.voice.file_id
                )
                message_content["voice"] = voice_url
            if update.message.video:
                video_url = await get_file_url(
                    bot, update.message.video.file_id
                )
                message_content["video"] = video_url

            await save_message_to_supabase(user_id, message_content)

        return web.Response(text="OK")

    async def handle_root(request: web.Request):
        return web.Response(text="Hello! The bot is running.")

    app.router.add_post(webhook_path, handle_webhook)
    app.router.add_get("/", handle_root)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    while True:
        await asyncio.sleep(3600)
