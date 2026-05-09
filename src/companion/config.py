from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str = ""
    LLM_PROVIDER_CHAIN: str = "groq,openrouter,gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    GEMINI_VISION_MODEL: str = "gemini-2.5-flash-lite"
    ENABLE_GEMINI_OCR: bool = True
    ENABLE_LOCAL_OCR: bool = True
    OCR_MAX_IMAGES_PER_FILE: int = 2
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_TRANSCRIPTION_MODEL: str = "whisper-large-v3-turbo"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
    OPENROUTER_EMBEDDING_MODEL: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    DATABASE_URL: str = "sqlite+aiosqlite:///./study_companion.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CHROMA_PERSIST_DIR: str = Field(default_factory=lambda: str(Path(".chroma").resolve()))
    RATE_LIMIT_FILE_UPLOADS_PER_DAY: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
