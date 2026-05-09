import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from companion.db.crud import (
    get_knowledge_state,
    get_user_documents,
    update_knowledge_state,
)
from companion.llm.socratic import (
    detect_language_preference,
    detect_response_language,
    generate_socratic_question,
    is_language_preference_request,
)
from companion.rag.vectorstore import query

router = Router()


def _source_locations(chunks: list) -> str:
    locations = []
    for chunk in chunks:
        location = chunk.metadata.get("loc_label")
        if not location and chunk.metadata.get("page"):
            location = f"page {chunk.metadata['page']}"
        if not location and chunk.metadata.get("slide"):
            location = f"slide {chunk.metadata['slide']}"
        if location and location not in locations:
            locations.append(location)
    return ", ".join(str(location) for location in locations[:3])


def _is_command(message: Message) -> bool:
    return bool((message.text or "").strip().startswith("/"))


def _is_affirmative_continuation(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {
        "так",
        "да",
        "давай",
        "ага",
        "угу",
        "ок",
        "окей",
        "yes",
        "yeah",
        "sure",
        "go on",
    }


def _extract_follow_up_question(answer: str) -> str | None:
    candidates = [
        part.strip()
        for part in answer.replace("\n", " ").split("?")
        if len(part.strip()) > 12
    ]
    if not candidates:
        return None
    return f"{candidates[-1]}?"


async def _handle_language_preference(message: Message, state: FSMContext) -> bool:
    text = message.text or ""
    if not is_language_preference_request(text):
        return False

    language = detect_language_preference(text)
    if not language:
        return False

    await state.update_data(preferred_language=language)
    if language == "Ukrainian":
        await message.answer("Добре, далі відповідатиму українською.")
    else:
        await message.answer(f"Okay, I will answer in {language}.")
    return True


def _query_study_context(docs: list, text: str, *, per_document_k: int = 4) -> tuple[str, str]:
    chunks = []
    for doc in docs:
        chunks.extend(query(doc.chroma_collection, text, k=per_document_k))
    context = "\n\n".join(chunk.page_content for chunk in chunks)
    return context, _source_locations(chunks)


class StudyState(StatesGroup):
    topic = State()
    waiting_answer = State()


@router.message(Command("study"))
async def cmd_study(message: Message, state: FSMContext, session: AsyncSession) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip():
        await _start_topic(message, state, session, parts[1].strip())
        return

    docs = await get_user_documents(session, message.from_user.id)
    if not docs:
        await message.answer("Upload a file first.")
        return

    await message.answer("What topic are we studying? Send a topic name or question.")
    await state.set_state(StudyState.topic)


async def _start_topic(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    topic: str,
) -> None:
    if not topic:
        await message.answer("Send the topic as text, for example: 'psychological knowledge'.")
        return

    docs = await get_user_documents(session, message.from_user.id)
    context, sources = _query_study_context(docs, topic, per_document_k=4)

    if len(context.strip()) < 120:
        await message.answer(
            "I found very little relevant text for this topic. "
            "Try a more specific phrase from the file, or upload a text-based file."
        )
        return

    ks = await update_knowledge_state(session, message.from_user.id, topic)
    data = await state.get_data()
    response_language = detect_response_language(topic, data.get("preferred_language"))
    question = await asyncio.to_thread(
        generate_socratic_question,
        context,
        topic,
        None,
        ks.score,
        response_language=response_language,
    )

    await state.update_data(
        topic=topic,
        context=context,
        sources=sources,
        preferred_language=response_language,
    )
    await state.set_state(StudyState.waiting_answer)
    source_line = f"\n\nSources: {sources}" if sources else ""
    await message.answer(f"{question}{source_line}")


@router.message(StudyState.topic, F.text)
async def handle_topic(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if _is_command(message):
        return
    if await _handle_language_preference(message, state):
        return
    await _start_topic(message, state, session, (message.text or "").strip())


async def process_study_answer(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    answer_text: str,
) -> None:
    data = await state.get_data()
    topic = data.get("topic")
    context = data.get("context", "")
    sources = data.get("sources", "")
    if _is_affirmative_continuation(answer_text) and data.get("last_bot_question"):
        answer_text = str(data["last_bot_question"])
    response_language = detect_response_language(answer_text, data.get("preferred_language"))
    if not topic:
        await message.answer("Start /study first and choose a topic.")
        return

    docs = await get_user_documents(session, message.from_user.id)
    if docs:
        refreshed_context, refreshed_sources = _query_study_context(
            docs,
            f"{topic}\n{answer_text}",
            per_document_k=8,
        )
        if len(refreshed_context.strip()) >= 120:
            context = refreshed_context
            sources = refreshed_sources
            await state.update_data(context=context, sources=sources)

    ks = await get_knowledge_state(session, message.from_user.id, topic)
    score = ks.score if ks else 0.5
    new_score = min(1.0, score + 0.04) if len(answer_text.strip()) > 20 else max(0.0, score - 0.03)
    await update_knowledge_state(session, message.from_user.id, topic, score=new_score)

    await state.update_data(preferred_language=response_language)
    follow_up = await asyncio.to_thread(
        generate_socratic_question,
        context,
        topic,
        answer_text,
        new_score,
        response_language=response_language,
    )
    await state.update_data(last_bot_question=_extract_follow_up_question(follow_up))
    source_line = f"\n\nSources: {sources}" if sources else ""
    await message.answer(f"{follow_up}{source_line}")


@router.message(StudyState.waiting_answer, F.text)
async def handle_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if _is_command(message):
        return
    if await _handle_language_preference(message, state):
        return
    await process_study_answer(message, state, session, message.text or "")


async def process_direct_question(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    raw_question: str,
) -> None:
    raw_question = raw_question.strip()
    if not raw_question:
        return
    if await _handle_language_preference(message, state):
        return

    docs = await get_user_documents(session, message.from_user.id)
    if not docs:
        await message.answer("Upload a file first, then ask a question about it.")
        return

    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        data = await state.get_data()
        question = raw_question
        if _is_affirmative_continuation(raw_question) and data.get("last_bot_question"):
            question = str(data["last_bot_question"])

        response_language = detect_response_language(raw_question, data.get("preferred_language"))
        await state.update_data(preferred_language=response_language)
        context, sources = _query_study_context(docs, question, per_document_k=8)
        if len(context.strip()) < 120:
            await message.answer(
                "I could not find enough relevant text in the uploaded PDF. "
                "Try a phrase from the file, or upload a text-based file."
            )
            return

        answer = await asyncio.to_thread(
            generate_socratic_question,
            context,
            question,
            None,
            0.5,
            response_language=response_language,
        )

    source_line = f"\n\nSources: {sources}" if sources else ""
    await state.update_data(last_bot_question=_extract_follow_up_question(answer))
    await message.answer(f"{answer}{source_line}")


@router.message(F.text)
async def handle_direct_pdf_question(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if _is_command(message) or await state.get_state() is not None:
        return

    await process_direct_question(message, state, session, message.text or "")
