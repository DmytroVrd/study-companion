import asyncio
import os
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from companion.db.crud import get_or_create_active_context, save_document
from companion.rag.loader import SUPPORTED_EXTENSIONS, load_document, split_documents
from companion.rag.vectorstore import add_documents

router = Router()


def _quality_message(
    unit_count: int,
    total_chars: int,
    file_extension: str,
    ocr_image_count: int = 0,
) -> str:
    ocr_note = f" OCR read {ocr_image_count} embedded image(s)." if ocr_image_count else ""
    if total_chars < 500:
        if file_extension == ".pdf":
            return (
                "Warning: I extracted very little text from this PDF. "
                "If these are image-based slides, I will not understand them well without OCR."
                f"{ocr_note}"
            )
        return (
            "Warning: I extracted very little text from this file. "
            "Check that the file contains selectable text."
            f"{ocr_note}"
        )
    avg_chars = total_chars // max(unit_count, 1)
    return (
        f"Extracted {total_chars} text chars from {unit_count} sections, "
        f"avg {avg_chars}/section."
        f"{ocr_note}"
    )


@router.message(F.document)
async def handle_document(message: Message, session: AsyncSession) -> None:
    file_name = message.document.file_name or "notes"
    extension = Path(file_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        await message.answer(f"Unsupported file type. Send one of: {supported}.")
        return

    await message.answer("Processing file...")
    tmp_name = ""
    count = 0
    raw_docs = []
    total_chars = 0
    ocr_image_count = 0
    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
                tmp_name = tmp.name
            await message.bot.download(message.document, tmp_name)

            raw_docs = await asyncio.to_thread(load_document, tmp_name)
            ocr_image_count = sum(doc.page_content.count("Image OCR ") for doc in raw_docs)
            chunks = await asyncio.to_thread(split_documents, raw_docs)
            for chunk in chunks:
                chunk.metadata["filename"] = file_name
            total_chars = sum(len(doc.page_content) for doc in raw_docs)
            context = await get_or_create_active_context(session, message.from_user.id)
            collection_name = (
                f"user_{message.from_user.id}_ctx_{context.id}_{message.document.file_unique_id}"
            )
            count = await asyncio.to_thread(add_documents, collection_name, chunks)

        await save_document(
            session,
            message.from_user.id,
            file_name,
            collection_name,
            count,
        )
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)

    if count == 0:
        await message.answer(
            "File uploaded, but I did not find selectable text. "
            "Try a text-based file; image-only PDFs need OCR."
        )
        return

    await message.answer(
        f"Uploaded: {file_name}\n"
        f"Project: {context.title}\n"
        f"Split into {count} chunks.\n"
        f"{_quality_message(len(raw_docs), total_chars, extension, ocr_image_count)}\n\n"
        "Ask a question by text or voice, or ask me to make Anki cards, "
        "a quiz, a summary, or a Word document."
    )
