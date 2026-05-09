from typing import Any

import pandas as pd
from sqlalchemy import select

from companion.db.crud import get_or_create_active_context, get_user_by_telegram_id
from companion.db.models import KnowledgeState, QuizResult
from companion.db.session import async_session


async def get_user_stats(user_id: int, context_id: int | None = None) -> dict[str, Any]:
    async with async_session() as session:
        ks_query = select(KnowledgeState).where(KnowledgeState.user_id == user_id)
        qr_query = select(QuizResult).where(QuizResult.user_id == user_id)
        if context_id is not None:
            ks_query = ks_query.where(KnowledgeState.context_id == context_id)
            qr_query = qr_query.where(QuizResult.context_id == context_id)

        ks_result = await session.execute(ks_query)
        qr_result = await session.execute(qr_query)
        knowledge_states = list(ks_result.scalars())
        quiz_results = list(qr_result.scalars())

    ks_df = pd.DataFrame(
        [
            {"topic": row.topic, "score": row.score, "next_review": row.next_review}
            for row in knowledge_states
        ]
    )
    qr_df = pd.DataFrame(
        [
            {"topic": row.topic, "correct": row.correct, "created_at": row.created_at}
            for row in quiz_results
        ]
    )

    if ks_df.empty:
        return {"status": "no_data"}

    weak_topics = ks_df.sort_values("score").head(3)["topic"].tolist()
    total_quizzes = len(qr_df)
    success_rate = float(qr_df["correct"].mean()) if not qr_df.empty else 0.0
    topics_progress = (
        qr_df.groupby("topic")["correct"].mean().sort_values().to_dict()
        if not qr_df.empty
        else {}
    )

    return {
        "weak_topics": weak_topics,
        "total_quizzes": total_quizzes,
        "success_rate": round(success_rate, 2),
        "topics_progress": {
            topic: round(float(value), 2) for topic, value in topics_progress.items()
        },
        "topics_count": len(ks_df),
    }


async def get_user_stats_by_telegram_id(telegram_id: int) -> dict[str, Any]:
    async with async_session() as session:
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            return {"status": "no_data"}
        context = await get_or_create_active_context(session, telegram_id)
        user_id = user.id
        context_id = context.id
    return await get_user_stats(user_id, context_id=context_id)
