from pydantic import ValidationError

from companion.quiz.generator import generate_quiz
from companion.quiz.schemas import QuizBatch, QuizOption, QuizQuestion


def test_quiz_schema_validates_letters() -> None:
    question = QuizQuestion(
        question="What is tested?",
        options=[
            QuizOption(letter="a", text="Understanding"),
            QuizOption(letter="B", text="Memorization"),
            QuizOption(letter="C", text="Noise"),
            QuizOption(letter="D", text="Other"),
        ],
        correct_letter="a",
        explanation="Because it checks reasoning.",
        topic="RAG",
        difficulty=3,
    )

    assert question.options[0].letter == "A"
    assert question.correct_letter == "A"


def test_quiz_schema_rejects_short_batches() -> None:
    try:
        QuizBatch(questions=[])
    except ValidationError as exc:
        assert "questions" in str(exc)
    else:
        raise AssertionError("Expected ValidationError")


def test_generate_quiz_fallback_when_providers_fail(monkeypatch) -> None:
    def fail_generate_text(**kwargs):
        raise RuntimeError("providers unavailable")

    monkeypatch.setattr("companion.quiz.generator.generate_text", fail_generate_text)

    quiz = generate_quiz("Gradient descent material", ["gradient descent"], count=2)

    assert len(quiz.questions) == 2
    assert quiz.questions[0].correct_letter == "A"
    assert quiz.questions[0].topic == "gradient descent"
