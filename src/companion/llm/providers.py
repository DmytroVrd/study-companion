import asyncio
import base64
import logging
from collections.abc import Iterable
from typing import Any

import httpx
from langchain_openai import ChatOpenAI

from companion.config import settings

logger = logging.getLogger(__name__)


class LLMProviderError(RuntimeError):
    pass


def _provider_chain() -> list[str]:
    return [
        provider.strip().lower()
        for provider in settings.LLM_PROVIDER_CHAIN.split(",")
        if provider.strip()
    ]


def _run_async_blocking(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise LLMProviderError("Use the async provider API from an active event loop.")


async def _generate_gemini_async(
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> str:
    if not settings.GEMINI_API_KEY:
        raise LLMProviderError("Gemini API key is not configured.")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            url,
            headers={
                "x-goog-api-key": settings.GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
        )
    response.raise_for_status()
    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise LLMProviderError(f"Gemini returned an unexpected response: {data}") from exc


def _generate_gemini(system: str, user: str, max_tokens: int, temperature: float) -> str:
    return _run_async_blocking(
        _generate_gemini_async(system, user, max_tokens, temperature)
    )


async def gemini_ocr_image_async(image_bytes: bytes, mime_type: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise LLMProviderError("Gemini API key is not configured.")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_VISION_MODEL}:generateContent"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Extract all readable text from this educational image. "
                            "Preserve lists, table structure, headings, and Ukrainian text. "
                            "Return only the extracted text."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 1024,
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url,
            headers={
                "x-goog-api-key": settings.GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
        )
    response.raise_for_status()
    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise LLMProviderError(f"Gemini OCR returned an unexpected response: {data}") from exc


def gemini_ocr_image(image_bytes: bytes, mime_type: str) -> str:
    return _run_async_blocking(gemini_ocr_image_async(image_bytes, mime_type))


def _generate_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> str:
    if not api_key:
        raise LLMProviderError(f"{model} API key is not configured.")

    llm = ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=0,
        timeout=20,
    )
    response = llm.invoke([("system", system), ("human", user)])
    return str(response.content).strip()


async def _generate_openai_compatible_async(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> str:
    return await asyncio.to_thread(
        _generate_openai_compatible,
        base_url=base_url,
        api_key=api_key,
        model=model,
        system=system,
        user=user,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _generate_groq(system: str, user: str, max_tokens: int, temperature: float) -> str:
    return _generate_openai_compatible(
        base_url=settings.GROQ_BASE_URL,
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        system=system,
        user=user,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def _generate_groq_async(
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> str:
    return await _generate_openai_compatible_async(
        base_url=settings.GROQ_BASE_URL,
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        system=system,
        user=user,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def transcribe_audio(
    *,
    audio_bytes: bytes,
    filename: str,
    content_type: str = "audio/ogg",
) -> str:
    if not settings.GROQ_API_KEY:
        raise LLMProviderError("Groq API key is not configured.")

    url = f"{settings.GROQ_BASE_URL.rstrip('/')}/audio/transcriptions"
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            data={
                "model": settings.GROQ_TRANSCRIPTION_MODEL,
                "response_format": "json",
                "temperature": "0",
                "prompt": "Telegram voice message for a study/file companion bot.",
            },
            files={"file": (filename, audio_bytes, content_type)},
        )
    response.raise_for_status()
    data = response.json()
    text = str(data.get("text", "")).strip()
    if not text:
        raise LLMProviderError(f"Groq transcription returned no text: {data}")
    return text


def _generate_openrouter(system: str, user: str, max_tokens: int, temperature: float) -> str:
    return _generate_openai_compatible(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
        system=system,
        user=user,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def _generate_openrouter_async(
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> str:
    return await _generate_openai_compatible_async(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
        system=system,
        user=user,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def generate_text_async(
    *,
    system: str,
    user: str,
    max_tokens: int = 512,
    temperature: float = 0.3,
    providers: Iterable[str] | None = None,
) -> str:
    provider_names = list(providers) if providers is not None else _provider_chain()
    errors: list[str] = []

    for provider in provider_names:
        try:
            if provider == "gemini":
                return await _generate_gemini_async(system, user, max_tokens, temperature)
            if provider == "groq":
                return await _generate_groq_async(system, user, max_tokens, temperature)
            if provider == "openrouter":
                return await _generate_openrouter_async(system, user, max_tokens, temperature)
            logger.warning("Skipping unknown LLM provider: %s", provider)
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            logger.warning("LLM provider %s failed: %s", provider, exc)

    raise LLMProviderError("; ".join(errors) or "No LLM providers configured.")


def generate_text(
    *,
    system: str,
    user: str,
    max_tokens: int = 512,
    temperature: float = 0.3,
    providers: Iterable[str] | None = None,
) -> str:
    return _run_async_blocking(
        generate_text_async(
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
            providers=providers,
        )
    )


def provider_status_text() -> str:
    return " -> ".join(_provider_chain())
