import hashlib
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from companion.config import settings


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text.lower())
    return [
        token
        for token in re.findall(r"[\w']+", normalized, flags=re.UNICODE)
        if len(token) > 2
    ]


def _token_weight(token: str) -> float:
    """Generic lexical weight, intentionally not tuned to one eval/domain."""
    if len(token) >= 10:
        return 1.6
    if len(token) >= 8:
        return 1.3
    return 1.0


class HashEmbeddings(Embeddings):
    """Free local lexical embeddings for demos when paid embedding APIs are unavailable."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def _features(self, text: str) -> list[str]:
        words = _tokens(text)
        features = [f"w:{word}" for word in words]
        compact = " ".join(words)
        for size in (3, 4, 5):
            features.extend(
                f"c{size}:{compact[index:index + size]}"
                for index in range(len(compact) - size + 1)
            )
        return features

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for feature in self._features(text) or [text]:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.PersistentClient:
    Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    if not settings.OPENROUTER_API_KEY or not settings.OPENROUTER_EMBEDDING_MODEL:
        return HashEmbeddings()

    kwargs: dict[str, Any] = {
        "api_key": settings.OPENROUTER_API_KEY,
        "base_url": settings.OPENROUTER_BASE_URL,
        "model": settings.OPENROUTER_EMBEDDING_MODEL,
    }
    return OpenAIEmbeddings(**kwargs)


def get_vectorstore(collection_name: str) -> Chroma:
    return Chroma(
        client=get_chroma_client(),
        collection_name=collection_name,
        embedding_function=get_embeddings(),
    )


def add_documents(collection_name: str, docs: list[Document]) -> int:
    if not docs:
        return 0
    client = get_chroma_client()
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    vectorstore = get_vectorstore(collection_name)
    vectorstore.add_documents(docs)
    return len(docs)


def delete_collection(collection_name: str) -> None:
    try:
        get_chroma_client().delete_collection(collection_name)
    except Exception:
        pass


def _keyword_score(question: str, document: Document) -> float:
    query_tokens = _tokens(question)
    if not query_tokens:
        return 0.0

    content = unicodedata.normalize("NFKC", document.page_content.lower())
    content_tokens = set(_tokens(document.page_content))
    total_weight = sum(_token_weight(token) for token in query_tokens) or 1.0
    overlap = (
        sum(_token_weight(token) for token in query_tokens if token in content_tokens)
        / total_weight
    )

    fuzzy_overlap = 0.0
    fuzzy_specificity_bonus = 0.0
    for token in query_tokens:
        if len(token) < 5 or token in content_tokens:
            continue
        stem = token[:5]
        if any(content_token.startswith(stem) for content_token in content_tokens):
            fuzzy_overlap += 0.65 * _token_weight(token) / total_weight
            if len(token) >= 8:
                fuzzy_specificity_bonus += 0.12

    phrase = " ".join(query_tokens)
    phrase_bonus = 0.4 if phrase and phrase in content else 0.0
    ordered_bonus = 0.0
    for left, right in zip(query_tokens, query_tokens[1:], strict=False):
        if f"{left} {right}" in content:
            ordered_bonus += 0.08

    image_bonus = 0.2 if "image" in str(document.metadata.get("source_type", "")) else 0.0

    return (
        overlap
        + fuzzy_overlap
        + min(fuzzy_specificity_bonus, 0.35)
        + phrase_bonus
        + min(ordered_bonus, 0.4)
        + image_bonus
    )


def _rerank(question: str, documents: list[Document], k: int) -> list[Document]:
    seen = set()
    unique_documents = []
    for document in documents:
        key = (
            document.metadata.get("source"),
            document.metadata.get("page"),
            document.metadata.get("slide"),
            document.metadata.get("image"),
            document.page_content[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        unique_documents.append(document)

    ranked = sorted(
        enumerate(unique_documents),
        key=lambda item: (_keyword_score(question, item[1]), -item[0]),
        reverse=True,
    )
    return [document for _, document in ranked[:k]]


def _lexical_search(collection_name: str, question: str, limit: int) -> list[Document]:
    collection = get_chroma_client().get_collection(collection_name)
    count = min(collection.count(), 500)
    if count == 0:
        return []

    rows = collection.get(limit=count, include=["documents", "metadatas"])
    documents = rows.get("documents") or []
    metadatas = rows.get("metadatas") or []

    candidates: list[Document] = []
    for content, metadata in zip(documents, metadatas, strict=False):
        if not content:
            continue
        document = Document(page_content=content, metadata=metadata or {})
        if _keyword_score(question, document) > 0:
            candidates.append(document)

    return _rerank(question, candidates, limit)


def query(collection_name: str, question: str, k: int = 5) -> list[Document]:
    vectorstore = get_vectorstore(collection_name)
    candidates = vectorstore.similarity_search(question, k=max(k * 4, 12))
    candidates.extend(_lexical_search(collection_name, question, limit=max(k * 4, 12)))
    return _rerank(question, candidates, k)
