from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from companion.bot.keyboards import main_keyboard
from companion.db.crud import get_or_create_active_context, get_or_create_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    context = await get_or_create_active_context(session, message.from_user.id)
    await message.answer(
        "Hi. I help you understand files.\n\n"
        f"Current project: {context.title}.\n"
        "Upload a PDF, DOCX, PPTX, or TXT file, then ask questions in plain language.\n\n"
        "You can also ask me to make an Anki CSV, vocabulary list, quiz, or markdown summary.",
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Upload a file, then ask naturally:\n"
        "- what is this file about?\n"
        "- explain this topic\n"
        "- send a voice question\n"
        "- make Anki cards\n"
        "- make a Word document\n"
        "- export a markdown summary\n"
        "- make a quiz\n\n"
        "Useful commands:\n"
        "/new - save/delete current project and start fresh\n"
        "/projects - switch to a saved project\n"
        "/export - choose an export format",
        reply_markup=main_keyboard(),
    )
