from pydantic import BaseModel, Field, field_validator


class QuizOption(BaseModel):
    letter: str = Field(description="A, B, C, or D")
    text: str

    @field_validator("letter")
    @classmethod
    def normalize_letter(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"A", "B", "C", "D"}:
            raise ValueError("letter must be A, B, C, or D")
        return value


class QuizQuestion(BaseModel):
    question: str
    options: list[QuizOption] = Field(min_length=4, max_length=4)
    correct_letter: str
    explanation: str
    topic: str
    difficulty: int = Field(ge=1, le=5)

    @field_validator("correct_letter")
    @classmethod
    def normalize_correct_letter(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"A", "B", "C", "D"}:
            raise ValueError("correct_letter must be A, B, C, or D")
        return value


class QuizBatch(BaseModel):
    questions: list[QuizQuestion] = Field(min_length=1, max_length=5)
