from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from redis.asyncio import Redis

from companion.config import settings
from companion.db.session import async_session


class DBSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            return await handler(event, data)


class DocumentUploadRateLimitMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, limit: int | None = None) -> None:
        self.redis = redis
        self.limit = limit or settings.RATE_LIMIT_FILE_UPLOADS_PER_DAY

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message = (
            event
            if isinstance(event, Message)
            else getattr(data.get("event_update"), "message", None)
        )
        if message is None:
            return await handler(event, data)

        document = getattr(message, "document", None)
        user = getattr(message, "from_user", None)
        if not document or not user:
            return await handler(event, data)

        today = datetime.utcnow().strftime("%Y%m%d")
        key = f"document_upload:{user.id}:{today}"
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, 60 * 60 * 24)
        if current > self.limit:
            await message.answer(
                f"Daily file upload limit reached ({self.limit}/day). "
                "Try again tomorrow or start the bot with a higher upload limit."
            )
            return None

        return await handler(event, data)
