from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from companion.config import settings


def format_context(documents: list[Document]) -> str:
    return "\n\n".join(document.page_content for document in documents)


def build_rag_chain() -> object:
    llm = ChatOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
        temperature=0.2,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Answer only from the provided context. If the context is insufficient, say so.",
            ),
            ("human", "Context:\n{context}\n\nQuestion: {question}"),
        ]
    )
    return prompt | llm
