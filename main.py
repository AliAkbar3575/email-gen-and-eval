import streamlit as st
import requests


GENERATE_URL = "http://localhost:8000/generate"
EVALUATE_URL = "http://localhost:8000/evaluate"
TESTSET_EVALUATION_URL = "http://localhost:8000/evaluate-testset"

GENERATE_TIMEOUT = 120
EVALUATION_TIMEOUT = 600
TESTSET_START_TIMEOUT = 30


def request_email_generation(user_request: str, model: str) -> str:
    response = requests.post(
        GENERATE_URL,
        json={"user_request": user_request, "model": model},
        timeout=GENERATE_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["generated_email"]


def request_email_evaluation(user_request: str, generated_email: str) -> dict:
    response = requests.post(
        EVALUATE_URL,
        json={"user_request": user_request, "generated_email": generated_email},
        timeout=EVALUATION_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def start_testset_evaluation() -> dict:
    response = requests.post(
        TESTSET_EVALUATION_URL,
        timeout=TESTSET_START_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="Email Generator", layout="centered")

st.title("Email Generator")

user_request = st.text_area(
    "User request",
    placeholder="Example: Write a professional follow-up email after a product demo.",
    height=180
)

model = st.selectbox(
    "Model",
    ["llama-3.1-8b-instant", "openai/gpt-oss-20b"],
)

if st.button("generate email"):
    if not user_request.strip():
        st.warning("Please enter a request before generating an email.")
    else:
        with st.spinner("Generating email..."):
            try:
                generated_email = request_email_generation(user_request.strip(), model)
                st.session_state["user_request"] = user_request.strip()
                st.session_state["generated_email"] = generated_email
            except Exception as exc:
                st.error(f"Could not generate email: {exc}")

if "generated_email" in st.session_state:
    st.subheader("Generated Email")
    st.text_area(
        "Generated email output",
        value=st.session_state["generated_email"],
        height=360,
        label_visibility="collapsed",
    )

if st.button("Evaluate LLM"):
    if "generated_email" not in st.session_state:
        st.warning("Please generate an email before evaluating.")
    else:
        with st.spinner("Evaluating email..."):
            try:
                st.session_state["evaluation"] = request_email_evaluation(
                    st.session_state["user_request"],
                    st.session_state["generated_email"],
                )
                st.session_state["testset_evaluation"] = start_testset_evaluation()
            except Exception as exc:
                st.error(f"Could not evaluate email: {exc}")

if "evaluation" in st.session_state:
    evaluation = st.session_state["evaluation"]
    scores = evaluation["scores"]

    st.subheader("Evaluation")
    st.write(f"Matched intent: {evaluation['matched_intent']}")
    st.write(f"Target tone: {evaluation['target_tone']}")
    st.metric("Overall Score", scores["overall"])
    st.write(
        {
            "Factual Recall": scores["factual_recall"],
            "Tone Accuracy": scores["tone_accuracy"],
            "Conciseness": scores["conciseness"],
        }
    )
    st.success(f"Saved details to {evaluation['result_file']}")

if "testset_evaluation" in st.session_state:
    st.success(
        "Started testset evaluation. "
        f"Scores will be saved to {st.session_state['testset_evaluation']['result_file']}."
    )
