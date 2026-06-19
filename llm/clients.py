import os

from langchain_groq import ChatGroq

from config.settings import GENERATION_MODEL, JUDGE_MODEL


def _require_groq_api_key() -> None:
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY was not found. Add it to your .env file.")


def build_generation_llm(temperature: float = 0.2, model: str | None = None) -> ChatGroq:
    _require_groq_api_key()
    return ChatGroq(
        model=model or os.getenv("GROQ_MODEL", GENERATION_MODEL),
        temperature=temperature,
    )


def build_judge_llm() -> ChatGroq:
    _require_groq_api_key()
    return ChatGroq(model=JUDGE_MODEL, temperature=0)


def judge_text(prompt: str) -> str:
    response = build_judge_llm().invoke(prompt)
    return response.content
