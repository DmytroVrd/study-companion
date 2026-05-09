from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from companion.db.models import Document, KnowledgeState, QuizResult, StudyContext, User


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, username: str | None = None
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        if username and user.username != username:
            user.username = username
            await session.commit()
        return user

    user = User(telegram_id=telegram_id, username=username)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_or_create_active_context(
    session: AsyncSession,
    telegram_id: int,
    title: str = "Untitled project",
) -> StudyContext:
    user = await get_or_create_user(session, telegram_id)
    result = await session.execute(
        select(StudyContext)
        .where(
            StudyContext.user_id == user.id,
            StudyContext.is_active.is_(True),
            StudyContext.archived_at.is_(None),
        )
        .order_by(StudyContext.created_at.desc())
    )
    context = result.scalars().first()
    if context:
        return context

    context = StudyContext(user_id=user.id, title=title, is_active=True)
    session.add(context)
    await session.commit()
    await session.refresh(context)
    return context


async def create_context(session: AsyncSession, telegram_id: int, title: str) -> StudyContext:
    user = await get_or_create_user(session, telegram_id)
    await session.execute(
        update(StudyContext).where(StudyContext.user_id == user.id).values(is_active=False)
    )
    context = StudyContext(user_id=user.id, title=title[:128], is_active=True)
    session.add(context)
    await session.commit()
    await session.refresh(context)
    return context


async def clear_context(
    session: AsyncSession,
    telegram_id: int,
    saved_title: str | None = None,
) -> StudyContext:
    user = await get_or_create_user(session, telegram_id)
    active_context = await get_or_create_active_context(session, telegram_id)
    if saved_title:
        active_context.title = saved_title[:128]
        active_context.archived_at = None

    await session.execute(
        update(StudyContext).where(StudyContext.user_id == user.id).values(is_active=False)
    )
    context = StudyContext(
        user_id=user.id,
        title="Untitled project",
        is_active=True,
    )
    session.add(context)
    await session.commit()
    await session.refresh(context)
    return context


async def delete_active_context(
    session: AsyncSession,
    telegram_id: int,
) -> tuple[StudyContext, list[str]]:
    user = await get_or_create_user(session, telegram_id)
    context = await get_or_create_active_context(session, telegram_id)
    result = await session.execute(
        select(Document.chroma_collection).where(Document.context_id == context.id)
    )
    collection_names = list(result.scalars())

    await session.execute(delete(QuizResult).where(QuizResult.context_id == context.id))
    await session.execute(delete(KnowledgeState).where(KnowledgeState.context_id == context.id))
    await session.execute(delete(Document).where(Document.context_id == context.id))
    await session.execute(delete(StudyContext).where(StudyContext.id == context.id))

    new_context = StudyContext(
        user_id=user.id,
        title="Untitled project",
        is_active=True,
    )
    session.add(new_context)
    await session.commit()
    await session.refresh(new_context)
    return new_context, collection_names


async def list_contexts(session: AsyncSession, telegram_id: int) -> list[StudyContext]:
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return []
    result = await session.execute(
        select(StudyContext)
        .where(StudyContext.user_id == user.id)
        .order_by(StudyContext.is_active.desc(), StudyContext.created_at.desc())
    )
    return list(result.scalars())


async def use_context(
    session: AsyncSession, telegram_id: int, context_id: int
) -> StudyContext | None:
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None
    result = await session.execute(
        select(StudyContext).where(
            StudyContext.id == context_id,
            StudyContext.user_id == user.id,
        )
    )
    context = result.scalar_one_or_none()
    if context is None:
        return None
    await session.execute(
        update(StudyContext).where(StudyContext.user_id == user.id).values(is_active=False)
    )
    context.is_active = True
    context.archived_at = None
    await session.commit()
    await session.refresh(context)
    return context


async def save_document(
    session: AsyncSession,
    telegram_id: int,
    filename: str,
    chroma_collection: str,
    chunk_count: int,
) -> Document:
    user = await get_or_create_user(session, telegram_id)
    context = await get_or_create_active_context(session, telegram_id)
    result = await session.execute(
        select(Document).where(
            Document.chroma_collection == chroma_collection,
            Document.context_id == context.id,
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        document = Document(
            user_id=user.id,
            context_id=context.id,
            filename=filename,
            chroma_collection=chroma_collection,
            chunk_count=chunk_count,
        )
        session.add(document)
    else:
        document.user_id = user.id
        document.context_id = context.id
        document.filename = filename
        document.chunk_count = chunk_count
        document.created_at = datetime.utcnow()

    await session.commit()
    await session.refresh(document)
    return document


async def get_user_documents(session: AsyncSession, telegram_id: int) -> list[Document]:
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return []
    context = await get_or_create_active_context(session, telegram_id)
    result = await session.execute(
        select(Document)
        .where(Document.user_id == user.id, Document.context_id == context.id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars())


async def get_knowledge_state(
    session: AsyncSession, telegram_id: int, topic: str
) -> KnowledgeState | None:
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None
    context = await get_or_create_active_context(session, telegram_id)
    result = await session.execute(
        select(KnowledgeState).where(
            KnowledgeState.user_id == user.id,
            KnowledgeState.context_id == context.id,
            KnowledgeState.topic == topic,
        )
    )
    return result.scalar_one_or_none()


async def update_knowledge_state(
    session: AsyncSession,
    telegram_id: int,
    topic: str,
    *,
    score: float | None = None,
    easiness: float | None = None,
    interval: int | None = None,
    repetitions: int | None = None,
    next_review: datetime | None = None,
) -> KnowledgeState:
    user = await get_or_create_user(session, telegram_id)
    context = await get_or_create_active_context(session, telegram_id)
    result = await session.execute(
        select(KnowledgeState).where(
            KnowledgeState.user_id == user.id,
            KnowledgeState.context_id == context.id,
            KnowledgeState.topic == topic,
        )
    )
    state = result.scalar_one_or_none()
    if state is None:
        state = KnowledgeState(user_id=user.id, context_id=context.id, topic=topic)
        session.add(state)

    if score is not None:
        state.score = max(0.0, min(1.0, score))
    if easiness is not None:
        state.easiness = easiness
    if interval is not None:
        state.interval = interval
    if repetitions is not None:
        state.repetitions = repetitions
    if next_review is not None:
        state.next_review = next_review

    await session.commit()
    await session.refresh(state)
    return state


async def get_weak_topics(session: AsyncSession, telegram_id: int, limit: int = 3) -> list[str]:
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return []
    context = await get_or_create_active_context(session, telegram_id)
    result = await session.execute(
        select(KnowledgeState.topic)
        .where(KnowledgeState.user_id == user.id, KnowledgeState.context_id == context.id)
        .order_by(KnowledgeState.score.asc(), KnowledgeState.next_review.asc())
        .limit(limit)
    )
    return list(result.scalars())


async def save_quiz_result(
    session: AsyncSession,
    telegram_id: int,
    topic: str,
    question: str,
    user_answer: str,
    correct: bool,
    score: float,
) -> QuizResult:
    user = await get_or_create_user(session, telegram_id)
    context = await get_or_create_active_context(session, telegram_id)
    result = QuizResult(
        user_id=user.id,
        context_id=context.id,
        topic=topic,
        question=question,
        user_answer=user_answer,
        correct=correct,
        score=score,
    )
    session.add(result)
    await session.commit()
    await session.refresh(result)
    return result
