from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    study_contexts: Mapped[list["StudyContext"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_states: Mapped[list["KnowledgeState"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    quiz_results: Mapped[list["QuizResult"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class StudyContext(Base):
    __tablename__ = "study_contexts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(128), default="General")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="study_contexts")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="study_context", cascade="all, delete-orphan"
    )
    knowledge_states: Mapped[list["KnowledgeState"]] = relationship(
        back_populates="study_context", cascade="all, delete-orphan"
    )
    quiz_results: Mapped[list["QuizResult"]] = relationship(
        back_populates="study_context", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    context_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_contexts.id"), index=True, nullable=True
    )
    filename: Mapped[str] = mapped_column(String(256))
    chroma_collection: Mapped[str] = mapped_column(String(128), unique=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="documents")
    study_context: Mapped["StudyContext | None"] = relationship(back_populates="documents")


class KnowledgeState(Base):
    __tablename__ = "knowledge_states"
    __table_args__ = (
        UniqueConstraint("context_id", "topic", name="uq_knowledge_context_topic"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    context_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_contexts.id"), index=True, nullable=True
    )
    topic: Mapped[str] = mapped_column(String(256), index=True)
    easiness: Mapped[float] = mapped_column(Float, default=2.5)
    interval: Mapped[int] = mapped_column(Integer, default=1)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    next_review: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    score: Mapped[float] = mapped_column(Float, default=0.5)

    user: Mapped["User"] = relationship(back_populates="knowledge_states")
    study_context: Mapped["StudyContext | None"] = relationship(back_populates="knowledge_states")


class QuizResult(Base):
    __tablename__ = "quiz_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    context_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_contexts.id"), index=True, nullable=True
    )
    topic: Mapped[str] = mapped_column(String(256), index=True)
    question: Mapped[str] = mapped_column(Text)
    user_answer: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="quiz_results")
    study_context: Mapped["StudyContext | None"] = relationship(back_populates="quiz_results")
