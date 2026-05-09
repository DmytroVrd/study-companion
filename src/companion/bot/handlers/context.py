from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from companion.db.crud import (
    clear_context,
    delete_active_context,
    get_or_create_active_context,
    list_contexts,
    use_context,
)
from companion.rag.vectorstore import delete_collection

router = Router()


class ProjectState(StatesGroup):
    naming_saved_project = State()


def _command_arg(message: Message) -> str:
    text = message.text or ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


@router.message(Command("new"))
async def cmd_new(message: Message, session: AsyncSession) -> None:
    context = await get_or_create_active_context(session, message.from_user.id)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Save and start fresh", callback_data="clear:save"),
            ],
            [
                InlineKeyboardButton(text="Delete and start fresh", callback_data="clear:delete"),
                InlineKeyboardButton(text="Cancel", callback_data="clear:cancel"),
            ]
        ]
    )
    await message.answer(
        f"Current project: {context.title}\n\n"
        "Start a fresh project? Save this one if you want to return to these files later. "
        "Delete it if this was only a temporary upload.",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "clear:save")
async def ask_saved_project_name(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProjectState.naming_saved_project)
    await callback.message.answer(
        "Name this project so you can return to it later.\n"
        "Example: English Unit 5"
    )
    await callback.answer()


@router.message(ProjectState.naming_saved_project, F.text)
async def save_project_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Send a project name, for example: English Unit 5")
        return

    context = await clear_context(session, message.from_user.id, saved_title=title)
    await state.clear()
    await message.answer(
        f"Saved project as: {title}\n"
        f"Started fresh project: {context.title}.\n"
        "Upload files, then ask questions."
    )


@router.callback_query(F.data == "clear:delete")
async def delete_clear(callback: CallbackQuery, session: AsyncSession) -> None:
    context, collection_names = await delete_active_context(session, callback.from_user.id)
    for collection_name in collection_names:
        delete_collection(collection_name)
    await callback.message.answer(
        f"Deleted current project and started fresh: {context.title}.\n"
        "Upload files, then ask questions."
    )
    await callback.answer()


@router.callback_query(F.data == "clear:cancel")
async def cancel_clear(callback: CallbackQuery) -> None:
    await callback.message.answer("Cancelled. Current project is unchanged.")
    await callback.answer()


@router.message(Command("projects", "contexts"))
async def cmd_projects(message: Message, session: AsyncSession) -> None:
    contexts = await list_contexts(session, message.from_user.id)
    if not contexts:
        context = await get_or_create_active_context(session, message.from_user.id)
        contexts = [context]

    keyboard_rows = []
    for context in contexts[:20]:
        marker = "[active] " if context.is_active else ""
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker}{context.title}",
                    callback_data=f"project:use:{context.id}",
                )
            ]
        )
    await message.answer(
        "Projects are saved workspaces with their own files and chat memory.\n"
        "Choose a project to switch back to it:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )


@router.callback_query(F.data.startswith("project:use:"))
async def use_project_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    context_id = int((callback.data or "").rsplit(":", maxsplit=1)[-1])
    context = await use_context(session, callback.from_user.id, context_id)
    if context is None:
        await callback.message.answer("I cannot find that project for your account.")
        await callback.answer()
        return
    await callback.message.answer(
        f"Switched to project: {context.title}.\n"
        "You can now ask questions about its files."
    )
    await callback.answer()


@router.message(Command("use"))
async def cmd_use(message: Message, session: AsyncSession) -> None:
    arg = _command_arg(message)
    if not arg.isdigit():
        await message.answer("Usage: /use 3")
        return

    context = await use_context(session, message.from_user.id, int(arg))
    if context is None:
        await message.answer("I cannot find that project for your account.")
        return
    await message.answer(f"Switched to project: {context.title}.")


@router.message(Command("current"))
async def cmd_current(message: Message, session: AsyncSession) -> None:
    context = await get_or_create_active_context(session, message.from_user.id)
    await message.answer(f"Current project: {context.title}.")
