import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from companion.bot.keyboards import quiz_keyboard
from companion.db.crud import (
    get_knowledge_state,
    get_user_documents,
    get_weak_topics,
    save_quiz_result,
    update_knowledge_state,
)
from companion.quiz.generator import generate_quiz
from companion.quiz.schemas import QuizQuestion
from companion.quiz.spaced import SM2State, sm2_update
from companion.rag.vectorstore import query

router = Router()


class QuizState(StatesGroup):
    answering = State()


def _render_question(question: QuizQuestion, index: int, total: int) -> str:
    options_text = "\n".join(f"{option.letter}) {option.text}" for option in question.options)
    return f"Question {index + 1}/{total}\n\n{question.question}\n\n{options_text}"


@router.message(Command("quiz"))
async def cmd_quiz(message: Message, state: FSMContext, session: AsyncSession) -> None:
    weak = await get_weak_topics(session, message.from_user.id, limit=3)
    if not weak:
        await message.answer("Study something with /study first, so I can see weak topics.")
        return

    docs = await get_user_documents(session, message.from_user.id)
    if not docs:
        await message.answer("Upload a PDF in the current context first.")
        return

    await message.answer("Generating quiz...")
    context_chunks = await asyncio.to_thread(query, docs[0].chroma_collection, " ".join(weak), 6)
    context = "\n\n".join(chunk.page_content for chunk in context_chunks)
    quiz = await asyncio.to_thread(generate_quiz, context, weak, 3)
    questions = [question.model_dump() for question in quiz.questions]

    await state.update_data(questions=questions, current=0, results=[])
    await state.set_state(QuizState.answering)

    await message.answer(
        _render_question(quiz.questions[0], 0, len(quiz.questions)),
        reply_markup=quiz_keyboard(),
    )


@router.callback_query(QuizState.answering, F.data.startswith("quiz:"))
async def handle_quiz_answer(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    questions = [QuizQuestion.model_validate(item) for item in data["questions"]]
    current = int(data["current"])
    selected = callback.data.split(":", 1)[1]
    question = questions[current]
    correct = selected == question.correct_letter
    quality = 5 if correct else 2
    score = 1.0 if correct else 0.0

    await save_quiz_result(
        session,
        callback.from_user.id,
        question.topic,
        question.question,
        selected,
        correct,
        score,
    )

    ks = await get_knowledge_state(session, callback.from_user.id, question.topic)
    sm2_state = SM2State(
        easiness=ks.easiness if ks else 2.5,
        interval=ks.interval if ks else 1,
        repetitions=ks.repetitions if ks else 0,
    )
    updated, next_review = sm2_update(sm2_state, quality)
    previous_score = ks.score if ks else 0.5
    next_score = previous_score + (0.12 if correct else -0.12)
    await update_knowledge_state(
        session,
        callback.from_user.id,
        question.topic,
        score=next_score,
        easiness=updated.easiness,
        interval=updated.interval,
        repetitions=updated.repetitions,
        next_review=next_review,
    )

    prefix = (
        "Correct."
        if correct
        else f"Not quite. Correct answer: {question.correct_letter}."
    )
    await callback.message.answer(f"{prefix}\n{question.explanation}")

    current += 1
    if current >= len(questions):
        await state.clear()
        await callback.message.answer("Quiz finished. Progress for this context is updated.")
        await callback.answer()
        return

    await state.update_data(current=current)
    await callback.message.answer(
        _render_question(questions[current], current, len(questions)),
        reply_markup=quiz_keyboard(),
    )
    await callback.answer()
