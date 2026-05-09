import json
import re

from companion.llm.providers import LLMProviderError, generate_text
from companion.quiz.schemas import QuizBatch, QuizOption, QuizQuestion

QUIZ_SYSTEM = """Generate quiz questions to test understanding of the provided material.
Focus on the student's weak areas. Questions must test understanding, not memorization.
Return ONLY valid JSON with this shape:
{
  "questions": [
    {
      "question": "string",
      "options": [
        {"letter": "A", "text": "string"},
        {"letter": "B", "text": "string"},
        {"letter": "C", "text": "string"},
        {"letter": "D", "text": "string"}
      ],
      "correct_letter": "A",
      "explanation": "string",
      "topic": "string",
      "difficulty": 1
    }
  ]
}
"""


def _fallback_quiz(weak_topics: list[str], count: int) -> QuizBatch:
    topics = weak_topics or ["material"]
    questions: list[QuizQuestion] = []
    for index in range(count):
        topic = topics[index % len(topics)]
        questions.append(
            QuizQuestion(
                question=f"Which option best shows real understanding of '{topic}'?",
                options=[
                    QuizOption(letter="A", text="It explains the cause-effect relationship."),
                    QuizOption(letter="B", text="It only repeats a definition without an example."),
                    QuizOption(letter="C", text="It ignores the context from the notes."),
                    QuizOption(letter="D", text="It replaces the topic with another one."),
                ],
                correct_letter="A",
                explanation=(
                    "Understanding is visible when you explain relationships, not just terms."
                ),
                topic=topic,
                difficulty=2,
            )
        )
    return QuizBatch(questions=questions)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in model response.")
    return json.loads(text[start : end + 1])


def generate_quiz(context: str, weak_topics: list[str], count: int = 3) -> QuizBatch:
    count = max(1, min(5, count))
    user = (
        f"Generate exactly {count} questions.\n\n"
        f"Material:\n{context}\n\n"
        f"Weak topics: {', '.join(weak_topics)}"
    )

    try:
        response = generate_text(system=QUIZ_SYSTEM, user=user, max_tokens=1200, temperature=0.2)
        return QuizBatch.model_validate(_extract_json(response))
    except (LLMProviderError, ValueError, json.JSONDecodeError, RuntimeError):
        return _fallback_quiz(weak_topics, count)
