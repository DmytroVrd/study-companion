from companion.llm.providers import LLMProviderError
from companion.llm.socratic import (
    detect_language_preference,
    detect_response_language,
    generate_socratic_question,
    is_language_preference_request,
)


def test_socratic_fallback_asks_question_when_providers_fail(monkeypatch) -> None:
    def fail_generate_text(**kwargs):
        raise LLMProviderError("providers unavailable")

    monkeypatch.setattr("companion.llm.socratic.generate_text", fail_generate_text)

    response = generate_socratic_question(
        context="Backpropagation updates weights by gradients.",
        topic="backpropagation",
        student_answer=None,
        score=0.5,
    )

    assert "Backpropagation updates weights" in response
    assert response.endswith("?")


def test_socratic_marks_do_not_know_as_explain_intent(monkeypatch) -> None:
    captured = {}

    def fake_generate_text(**kwargs):
        captured["user"] = kwargs["user"]
        return "Here is a simple explanation."

    monkeypatch.setattr("companion.llm.socratic.generate_text", fake_generate_text)

    response = generate_socratic_question(
        context="Psychological knowledge helps people understand emotions.",
        topic="psychological knowledge",
        student_answer="I do not know, tell me",
        score=0.5,
    )

    assert response == "Here is a simple explanation."
    assert "Detected intent: explain" in captured["user"]


def test_socratic_uses_user_language_not_context_language(monkeypatch) -> None:
    captured = {}

    def fake_generate_text(**kwargs):
        captured["system"] = kwargs["system"]
        captured["user"] = kwargs["user"]
        return "Це документ з вправами з англійської."

    monkeypatch.setattr("companion.llm.socratic.generate_text", fake_generate_text)

    response = generate_socratic_question(
        context="Fill in the blanks with the correct English word.",
        topic="про що цей документ",
        student_answer="про що цей документ",
        score=0.5,
    )

    assert response.startswith("Це документ")
    assert "Response language: Ukrainian" in captured["system"]
    assert "Response language: Ukrainian" in captured["user"]


def test_language_preference_detection() -> None:
    assert detect_language_preference("укр мовою говори") == "Ukrainian"
    assert detect_response_language("про що цей документ") == "Ukrainian"
    assert is_language_preference_request("укр мовою говори")


def test_voice_transcript_language_detection() -> None:
    assert detect_response_language("Чо таке психологія?") == "Ukrainian"
    assert detect_response_language("Що таке психологія?") == "Ukrainian"
    assert detect_response_language("Что такое психология?") == "Russian"
