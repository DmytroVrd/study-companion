import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from redis.asyncio import Redis

from companion.bot.handlers import build_router
from companion.bot.middleware import DBSessionMiddleware, DocumentUploadRateLimitMiddleware
from companion.config import settings


async def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required to run the Telegram bot.")

    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=settings.BOT_TOKEN)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Start or reset the bot"),
            BotCommand(command="help", description="How to use the bot"),
            BotCommand(command="new", description="Save/delete and start fresh"),
            BotCommand(command="projects", description="Switch to a saved project"),
            BotCommand(command="export", description="Export summary, cards, or quiz"),
        ]
    )
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    dispatcher = Dispatcher()
    dispatcher.update.middleware(DBSessionMiddleware())
    dispatcher.message.middleware(DocumentUploadRateLimitMiddleware(redis))
    dispatcher.include_router(build_router())

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
