from __future__ import annotations

from typing import List, TypedDict

from pydantic import BaseModel, Field


class EmailStructure(BaseModel):
    intent: str = Field(
        description="The main purpose of the email, such as request, follow-up, apology, update, or invitation."
    )
    key_facts: List[str] = Field(
        description="Important facts, details, constraints, names, dates, or asks that must appear in the email."
    )
    tone: str = Field(
        description="The best tone for the email, such as professional, friendly, urgent, apologetic, or persuasive."
    )


class EmailState(TypedDict, total=False):
    user_request: str
    structure: EmailStructure
    generated_email: str
    model: str


class EmailRequest(BaseModel):
    user_request: str
    model: str = "llama-3.1-8b-instant"


class EvaluationRequest(BaseModel):
    user_request: str
    generated_email: str
