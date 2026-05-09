from langchain_openai import ChatOpenAI

from companion.config import settings


def get_openrouter_chat(temperature: float = 0.3) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
        temperature=temperature,
    )
