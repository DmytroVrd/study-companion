import logging
import re

from companion.llm.providers import LLMProviderError, generate_text

logger = logging.getLogger(__name__)

SOCRATIC_SYSTEM = """You are an adaptive study companion for students.
Your job is to help the student understand the uploaded material, using ONLY the provided context.

Response language: {response_language}

Rules:
1. If the student asks a direct factual question, answer directly from the context first.
2. Direct factual questions include "what is", "name", "goal", "explain", and "help me".
3. If the student is practicing an answer, ask ONE focused Socratic follow-up question.
4. If the detected intent is explain, example, or direct_answer, teach first.
5. If the student says they do not know, give a simple explanation and an example.
6. Do not invent facts. If the answer is absent, say it is not visible in the file text.
7. Prefer concise answers: 2-5 sentences for explanations, 1-2 sentences for follow-ups.
8. Quote short key phrases from the material when useful, but explain them in your own words.
9. Always respond in the Response language, not necessarily in the material language.
10. After a direct answer, ask a short checking question only when the student is clearly
    practicing. If they ask for facts, lists, definitions, examples, or summaries, answer cleanly
    and stop.
11. Do not turn every answer into only a question.
12. If the material is for learning a foreign language, keep target-language words as examples,
    but explain them in the Response language.
13. Some context comes from OCR of tables, diagrams, and screenshots. OCR text can have broken
    line order, missing bullets, or noisy characters. If the student asks about a category from a
    diagram/table, carefully reconstruct the relevant list from nearby OCR fragments instead of
    ignoring it.
14. Before saying that something is absent, check all context fragments, especially OCR/image
    fragments and figure captions.

Context from student's materials:
{context}

Student's current understanding score for this topic: {score:.0%}
"""

_EXPLAIN_PATTERNS = [
    r"\bне знаю\b",
    r"\bхз\b",
    r"\bскажи\b",
    r"\bпоясни\b",
    r"\bпоясніть\b",
    r"\bдай приклад\b",
    r"\bнаведи приклад\b",
    r"\bi do not know\b",
    r"\bi don'?t know\b",
    r"\btell me\b",
    r"\bexplain\b",
    r"\bgive an example\b",
    r"\bnie wiem\b",
    r"\bwytłumacz\b",
]

_DIRECT_PATTERNS = [
    r"\bщо таке\b",
    r"\bшо таке\b",
    r"\bчо таке\b",
    r"\bщо це\b",
    r"\bщо означає\b",
    r"\bхто такий\b",
    r"\bназви\b",
    r"\bмета\b",
    r"\bяка ціль\b",
    r"\bчто такое\b",
    r"\bчто это\b",
    r"\bчто означает\b",
    r"\bwhat is\b",
    r"\bdefine\b",
    r"\bname\b",
    r"\bgoal\b",
    r"\bcel\b",
    r"\bco to\b",
]

_PRACTICE_PATTERNS = [
    r"\bперевір\b",
    r"\bспитай\b",
    r"\bзапитай\b",
    r"\bquiz\b",
    r"\btest me\b",
    r"\bask me\b",
]

_LANGUAGE_PREFERENCES = [
    ("Ukrainian", [r"укр", r"україн", r"украин"]),
    ("English", [r"англ", r"english"]),
    ("Polish", [r"поль", r"polish", r"polski"]),
    ("Chinese", [r"китай", r"chinese", r"中文"]),
    ("German", [r"німец", r"німець", r"немец", r"german", r"deutsch"]),
    ("French", [r"франц", r"french", r"français"]),
    ("Spanish", [r"іспан", r"испан", r"spanish", r"español"]),
]


def _context_sentence(context: str, topic: str) -> str:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", context)
        if len(sentence.strip()) > 40
    ]
    topic_terms = {term.lower() for term in re.findall(r"\w+", topic, flags=re.UNICODE)}
    for sentence in sentences:
        words = set(re.findall(r"\w+", sentence.lower(), flags=re.UNICODE))
        if topic_terms & words:
            return sentence[:500]
    return sentences[0][:500] if sentences else ""


def _matches_any(text: str, patterns: list[str]) -> bool:
    normalized = text.lower()
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)


def detect_language_preference(text: str) -> str | None:
    normalized = text.lower()
    for language, patterns in _LANGUAGE_PREFERENCES:
        if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns):
            return language
    return None


def _looks_russian(text: str) -> bool:
    normalized = text.lower()
    return bool(
        re.search(
            r"\b(что|чего|почему|зачем|давай|можем|можно|рус|россий|скажи|напиши)\b",
            normalized,
        )
    )


def detect_response_language(text: str, preferred_language: str | None = None) -> str:
    if preferred_language:
        return preferred_language

    explicit_language = detect_language_preference(text)
    if explicit_language:
        return explicit_language

    if re.search(r"[\u4e00-\u9fff]", text):
        return "Chinese"
    if re.search(r"[ąćęłńóśźż]", text.lower()):
        return "Polish"
    if re.search(r"[іїєґІЇЄҐ]", text):
        return "Ukrainian"
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "Russian" if _looks_russian(text) else "Ukrainian"
    return "English"


def is_language_preference_request(text: str) -> bool:
    normalized = text.lower()
    if detect_language_preference(normalized) is None:
        return False
    return any(
        phrase in normalized
        for phrase in ("говори", "відповідай", "пиши", "speak", "answer", "respond")
    )


def _detect_intent(topic: str, student_answer: str | None) -> str:
    text = f"{topic}\n{student_answer or ''}"
    if _matches_any(text, _PRACTICE_PATTERNS):
        return "practice"
    if student_answer and _matches_any(student_answer, _EXPLAIN_PATTERNS):
        return "explain"
    if _matches_any(text, _DIRECT_PATTERNS) or "?" in text:
        return "direct_answer"
    if student_answer:
        return "answer_check"
    return "guided_start"


def _fallback_question(context: str, topic: str, student_answer: str | None) -> str:
    anchor = _context_sentence(context, topic)
    if student_answer:
        if anchor:
            return (
                "AI providers are temporarily unavailable, so I am using local context mode. "
                f"From the extracted file text I can see this relevant point: \"{anchor}\". "
                "If you want, ask a more specific question about this fragment."
            )
        return (
            "AI providers are temporarily unavailable, and I cannot find enough extracted "
            f"text about '{topic}' to answer confidently."
        )
    if anchor:
        return (
            "AI providers are temporarily unavailable, so I am using local context mode. "
            f"The material says: \"{anchor}\". What does this mean in your own words?"
        )
    return f"What do you already know about '{topic}', and what example supports it?"


def generate_socratic_question(
    context: str,
    topic: str,
    student_answer: str | None,
    score: float,
    response_language: str | None = None,
) -> str:
    intent = _detect_intent(topic, student_answer)
    response_language = detect_response_language(student_answer or topic, response_language)
    user_message = (
        f"Detected intent: {intent}\n"
        f"Response language: {response_language}\n"
        f"Current study topic: {topic}\n"
        f"Student message: {student_answer}"
        if student_answer
        else (
            f"Detected intent: {intent}\n"
            f"Response language: {response_language}\n"
            f"I want to study this topic: {topic}"
        )
    )
    try:
        return generate_text(
            system=SOCRATIC_SYSTEM.format(
                context=context,
                score=score,
                response_language=response_language,
            ),
            user=user_message,
            max_tokens=450,
            temperature=0.4,
        )
    except LLMProviderError as exc:
        logger.warning("All Socratic LLM providers failed: %s", exc)
        return _fallback_question(context, topic, student_answer)
