from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from companion.analytics.stats import get_user_stats_by_telegram_id

router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    stats = await get_user_stats_by_telegram_id(message.from_user.id)

    if stats.get("status") == "no_data":
        await message.answer("No progress data yet. Upload a file and ask a few questions first.")
        return

    weak_text = "\n".join(f"  - {topic}" for topic in stats["weak_topics"]) or "  none yet"
    topics_text = "\n".join(
        f"  {'🟢' if value >= 0.7 else '🟡' if value >= 0.4 else '🔴'} "
        f"{topic}: {value:.0%}"
        for topic, value in stats["topics_progress"].items()
    ) or "  no data"

    await message.answer(
        "*Your progress*\n\n"
        f"Quizzes completed: {stats['total_quizzes']}\n"
        f"Success rate: {stats['success_rate']:.0%}\n"
        f"Topics studied: {stats['topics_count']}\n\n"
        f"*Weak topics:*\n{weak_text}\n\n"
        f"*By topic:*\n{topics_text}",
        parse_mode="Markdown",
    )
