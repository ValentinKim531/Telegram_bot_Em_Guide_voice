import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, User
from cachetools import TTLCache
from utils.config import THROTTLING_TIME_PERIOD, THROTTLING_MAX_RATE


@dataclass(kw_only=True, slots=True)
class ThrottlingData:
    rate: int = field(default=0)
    sent_warning: bool = field(default=False)


class ThrottlingMiddleware(BaseMiddleware):
    """
    Throttling Middleware protects the bot from spam
    """

    def __init__(self) -> None:
        self._cache: TTLCache[int, ThrottlingData] = TTLCache(
            maxsize=10_000,
            ttl=THROTTLING_TIME_PERIOD,
        )

    async def __call__(
            self,
            handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: dict[str, Any],
    ) -> Any | None:
        try:
            event_user: User = data["event_from_user"]
            throttling_data = self._cache.get(event_user.id)

            if throttling_data is None:
                throttling_data = ThrottlingData()
                self._cache[event_user.id] = throttling_data

            if throttling_data.rate >= THROTTLING_MAX_RATE:
                if not throttling_data.sent_warning:
                    bot: Bot = data["bot"]
                    await bot.send_message(
                        chat_id=event_user.id,
                        text="Дождитесь ответа или повторите попытку",
                    )
                    throttling_data.sent_warning = True
                return None

            throttling_data.rate += 1
            return await handler(event, data)

        except Exception as e:
            logging.error("Произошла ошибка: %s", e, exc_info=True)

