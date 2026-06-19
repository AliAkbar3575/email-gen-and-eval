from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from llm.clients import build_generation_llm
from models.schemas import EmailState, EmailStructure
from config.prompts import email_gen_prompt, structured_output_prompt


def structural_output(state: EmailState) -> EmailState:
    llm = build_generation_llm(temperature=0, model=state.get("model"))
    structured_llm = llm.with_structured_output(EmailStructure)

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system", structured_output_prompt,
            ),
            ("human", "{user_request}"),
        ]
    )

    chain = template | structured_llm
    structure = chain.invoke({"user_request": state["user_request"]})
    return {"structure": structure}


def email_generation(state: EmailState) -> EmailState:
    llm = build_generation_llm(temperature=0.4, model=state.get("model"))
    structure = state["structure"]

    email_gen_template = ChatPromptTemplate.from_messages(
        [
            (
                "system", email_gen_prompt,
            ),
            (
                "human",
                "Original request:\n{user_request}\n\n"
                "Intent: {intent}\n"
                "Tone: {tone}\n"
                "Key facts:\n{key_facts}\n\n"
                "Now write the email.",
            ),
        ]
    )

    chain = email_gen_template | llm
    response = chain.invoke(
        {
            "user_request": state["user_request"],
            "intent": structure.intent,
            "tone": structure.tone,
            "key_facts": "\n".join(f"- {fact}" for fact in structure.key_facts),
        }
    )

    return {"generated_email": response.content}


def build_graph():
    graph = StateGraph(EmailState)

    graph.add_node("structural_output", structural_output)
    graph.add_node("email_generation", email_generation)

    graph.add_edge(START, "structural_output")
    graph.add_edge("structural_output", "email_generation")
    graph.add_edge("email_generation", END)

    return graph.compile()


def generate_email(user_request: str, model: str | None = None) -> str:
    app = build_graph()
    result = app.invoke({"user_request": user_request, "model": model})
    return result["generated_email"]
