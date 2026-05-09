import logging
import os
import tempfile

import httpx
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from companion.bot.handlers.study import (
    StudyState,
    process_direct_question,
    process_study_answer,
)
from companion.llm.providers import LLMProviderError, transcribe_audio
from companion.llm.socratic import detect_response_language

logger = logging.getLogger(__name__)
router = Router()


def _voice_text(key: str, language: str) -> str:
    texts = {
        "heard": {
            "Ukrainian": "Я почув: {transcript}",
            "Russian": "Я услышал: {transcript}",
            "English": "I heard: {transcript}",
        },
        "transcription_failed": {
            "Ukrainian": (
                "Не зміг розпізнати голосове повідомлення. "
                "Спробуй ще раз або напиши текстом."
            ),
            "Russian": (
                "Не смог распознать голосовое сообщение. "
                "Попробуй еще раз или напиши текстом."
            ),
            "English": (
                "I could not transcribe this voice message. "
                "Please try again or type the text."
            ),
        },
        "transcription_unavailable": {
            "Ukrainian": "Голосове розпізнавання зараз недоступне. Напиши, будь ласка, текстом.",
            "Russian": "Распознавание голоса сейчас недоступно. Напиши, пожалуйста, текстом.",
            "English": "Voice transcription is unavailable right now. Please type the text.",
        },
        "finish_current_step": {
            "Ukrainian": "Заверши поточний крок текстовою відповіддю.",
            "Russian": "Заверши текущий шаг текстовым ответом.",
            "English": "Please finish the current step by typing your answer.",
        },
    }
    return texts[key].get(language, texts[key]["English"])


@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext, session: AsyncSession) -> None:
    voice = message.voice
    if voice is None:
        return

    tmp_name = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_name = tmp.name
        await message.bot.download(voice, tmp_name)

        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            with open(tmp_name, "rb") as file:
                transcript = await transcribe_audio(
                    audio_bytes=file.read(),
                    filename="telegram_voice.ogg",
                    content_type=voice.mime_type or "audio/ogg",
                )
    except httpx.HTTPStatusError as exc:
        logger.warning("Groq voice transcription failed: %s", exc)
        await message.answer(
            _voice_text("transcription_failed", "English")
        )
        return
    except (OSError, LLMProviderError) as exc:
        logger.warning("Voice transcription failed: %s", exc)
        await message.answer(
            _voice_text("transcription_unavailable", "English")
        )
        return
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)

    language = detect_response_language(transcript)
    await message.answer(_voice_text("heard", language).format(transcript=transcript))

    current_state = await state.get_state()
    if current_state == StudyState.waiting_answer.state:
        await process_study_answer(message, state, session, transcript)
        return
    if current_state is None:
        await process_direct_question(message, state, session, transcript)
        return

    await message.answer(_voice_text("finish_current_step", language))
