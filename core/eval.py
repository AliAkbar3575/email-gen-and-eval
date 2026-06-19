from __future__ import annotations

import re
from statistics import mean

import numpy as np
import spacy
import textstat
from bert_score import score as bert_score
from sentence_transformers import SentenceTransformer, util
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config.settings import EVALUATION_RESULT_PATH
from data.dataset_utils import find_dataset_item, split_key_points, tokens
from llm.clients import judge_text
from utils.report_writer import save_evaluation_result


def load_spacy_model():
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        blank_nlp = spacy.blank("en")
        blank_nlp.add_pipe("sentencizer")
        return blank_nlp


nlp = load_spacy_model()
embedder = SentenceTransformer("all-MiniLM-L6-v2")
vader = SentimentIntensityAnalyzer()

CTA_KEYWORDS = [
    "please",
    "let me know",
    "reply by",
    "respond by",
    "schedule",
    "confirm",
    "review",
    "send",
    "click",
    "complete",
    "by friday",
    "by end of",
    "looking forward to",
    "would appreciate",
]

FILLER_PHRASES = [
    "i hope this email finds you well",
    "just wanted to",
    "i am writing to",
    "as per my last email",
    "to whom it may concern",
    "please do not hesitate",
]

EXPECTED_TONE_PROFILES = {
    "formal": {"min_fk_grade": 9, "max_contractions": 0},
    "polite": {"min_fk_grade": 6, "max_contractions": 1},
    "professional": {"min_fk_grade": 7, "max_contractions": 1},
    "appreciative": {"positive_sentiment": True},
    "apologetic": {"positive_sentiment": True},
    "persuasive": {"positive_sentiment": True},
    "urgent": {"urgency_required": True},
    "formal and supportive": {"min_fk_grade": 8, "positive_sentiment": True},
}


def normalize(raw_score: int) -> float:
    return (raw_score - 1) / 4


def parse_score(label: str, text: str, default: int = 3) -> int:
    match = re.search(rf"{re.escape(label)}\s*:\s*([1-5])", text, re.IGNORECASE)
    return int(match.group(1)) if match else default


def parse_reason(text: str) -> str:
    match = re.search(r"Reason\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_key_entities(key_facts: list[str]) -> list[str]:
    entities = []
    for fact in key_facts:
        doc = nlp(fact)
        found = [
            ent.text
            for ent in doc.ents
            if ent.label_ in ("DATE", "MONEY", "PERCENT", "CARDINAL", "ORG", "PERSON", "GPE")
        ]
        entities.extend(found if found else [fact])
    return entities


def keyword_overlap_ratio(key_facts: list[str], email_text: str) -> float:
    if not key_facts:
        return 0.0

    email_lower = email_text.lower()
    found = 0
    for fact in key_facts:
        entities = extract_key_entities([fact])
        if any(entity.lower() in email_lower for entity in entities):
            found += 1
    return found / len(key_facts)


def semantic_similarity_score(key_facts: list[str], email_text: str, threshold: float = 0.6) -> float:
    if not key_facts:
        return 0.0

    email_sentences = [sentence.text.strip() for sentence in nlp(email_text).sents if sentence.text.strip()]
    if not email_sentences:
        return 0.0

    fact_embeddings = embedder.encode(key_facts, convert_to_tensor=True)
    sentence_embeddings = embedder.encode(email_sentences, convert_to_tensor=True)

    matched = 0
    for fact_embedding in fact_embeddings:
        similarities = util.cos_sim(fact_embedding, sentence_embeddings)
        if similarities.max().item() >= threshold:
            matched += 1
    return matched / len(key_facts)


def bertscore_factual_similarity(generated_email: str, reference_email: str) -> float:
    _, _, f1 = bert_score([generated_email], [reference_email], lang="en")
    return f1.mean().item()


def fact_present_ratio(key_facts: list[str], generated_email: str, reference_email: str) -> float:
    keyword_score = keyword_overlap_ratio(key_facts, generated_email)
    semantic_score = semantic_similarity_score(key_facts, generated_email)
    bert_f1 = bertscore_factual_similarity(generated_email, reference_email)
    return (keyword_score * 0.4) + (semantic_score * 0.3) + (bert_f1 * 0.3)


def integration_naturalness_score(key_facts: list[str], generated_email: str) -> dict:
    prompt = f"""SYSTEM
You are a strict fact-checking evaluator for AI-generated emails. You verify two
things: (1) that no required fact is missing or altered/hallucinated, and (2) how
naturally the present facts are integrated into the prose. You do not evaluate
grammar, tone, or style -- only factual completeness and integration quality.

INPUT
KEY_FACTS (must all be present, unaltered):
{chr(10).join(f"- {fact}" for fact in key_facts)}

GENERATED_EMAIL:
{generated_email}

INSTRUCTIONS
Step 1 -- Hallucination & Omission Check:
List any facts from KEY_FACTS that are missing, altered, or contradicted in the
GENERATED_EMAIL. If none, state "None."

Step 2 -- Integration Naturalness Rating (1-5):
Score how naturally the present facts are woven into the email's prose.

OUTPUT FORMAT (strict, no extra commentary):
Missing/Hallucinated Facts: <"None" or list>
Naturalness Score: <integer 1-5>
Reason: <one sentence justification>
"""
    output = judge_text(prompt)
    raw_score = parse_score("Naturalness Score", output)
    missing_match = re.search(
        r"Missing/Hallucinated Facts\s*:\s*(.+?)(?:\nNaturalness Score\s*:|$)",
        output,
        re.IGNORECASE | re.DOTALL,
    )
    missing = missing_match.group(1).strip() if missing_match else ""
    return {
        "raw_score": raw_score,
        "score": normalize(raw_score),
        "missing_or_hallucinated": missing,
        "reason": parse_reason(output),
        "judge_output": output,
    }


def calculate_metric1(key_facts: list[str], generated_email: str, reference_email: str) -> dict:
    facts_ratio = fact_present_ratio(key_facts, generated_email, reference_email)
    naturalness = integration_naturalness_score(key_facts, generated_email)

    if naturalness["missing_or_hallucinated"].lower() not in ("none", '"none"', ""):
        facts_ratio = min(facts_ratio, 0.7)

    final_score = (facts_ratio * 0.5) + (naturalness["score"] * 0.5)
    return {
        "score": final_score,
        "fact_present_ratio": facts_ratio,
        "integration_naturalness_score": naturalness["score"],
        "integration_naturalness_raw": naturalness["raw_score"],
        "missing_or_hallucinated": naturalness["missing_or_hallucinated"],
        "reason": naturalness["reason"],
    }


def formality_score(email_text: str) -> float:
    return textstat.flesch_kincaid_grade(email_text)


def sentiment_profile(email_text: str) -> dict:
    return vader.polarity_scores(email_text)


def count_contractions(email_text: str) -> int:
    return len(re.findall(r"\b\w+'\w+\b", email_text))


def auto_tone_score(tone: str, email_text: str) -> float:
    profile = EXPECTED_TONE_PROFILES.get(tone.lower(), {})
    fk_grade = formality_score(email_text)
    sentiment = sentiment_profile(email_text)["compound"]
    contractions = count_contractions(email_text)
    components = []

    if "min_fk_grade" in profile:
        components.append(min(1.0, fk_grade / profile["min_fk_grade"]))

    if "max_contractions" in profile:
        max_contractions = profile["max_contractions"]
        components.append(1.0 if contractions <= max_contractions else max(0.0, 1 - contractions * 0.2))

    if profile.get("positive_sentiment"):
        components.append(1.0 if sentiment > 0 else 0.3)

    if profile.get("urgency_required"):
        urgency_markers = ["asap", "immediately", "urgent", "right away", "as soon as possible", "quickly"]
        components.append(1.0 if any(marker in email_text.lower() for marker in urgency_markers) else 0.4)

    return mean(components) if components else 0.5


def llm_tone_rubric_score(tone: str, generated_email: str, reference_email: str) -> dict:
    prompt = f"""SYSTEM
You are a strict evaluator scoring whether a generated email matches a TARGET
TONE specified in the original input scenario. Score three dimensions using the
5-point rubric below. Use the Human Reference Email only as a tonal calibration
anchor -- do not penalize differences in wording or content choices.

INPUT
TARGET_TONE: {tone}

HUMAN_REFERENCE_EMAIL (tone calibration only):
{reference_email}

GENERATED_EMAIL (to be scored):
{generated_email}

RUBRIC (apply to all three dimensions below):
5 -- Perfect tone match
4 -- Minor mismatch
3 -- Partially correct
2 -- Mostly incorrect
1 -- Completely wrong tone

DIMENSIONS TO SCORE:
1. Professionalism -- Is the level of formality/professionalism appropriate for
   TARGET_TONE and business context?
2. Empathy/Appropriateness -- Does the emotional register suit TARGET_TONE and
   the scenario?
3. Tone Consistency -- Is TARGET_TONE maintained consistently from greeting to
   sign-off, with no jarring shifts in register?

OUTPUT FORMAT (strict, no extra commentary):
Professionalism Score: <integer 1-5>
Empathy/Appropriateness Score: <integer 1-5>
Tone Consistency Score: <integer 1-5>
Reason: <one or two sentence justification covering all three scores>
"""
    output = judge_text(prompt)
    raw_scores = [
        parse_score("Professionalism Score", output),
        parse_score("Empathy/Appropriateness Score", output),
        parse_score("Tone Consistency Score", output),
    ]
    normalized_scores = [normalize(score) for score in raw_scores]
    return {
        "raw_scores": raw_scores,
        "score": mean(normalized_scores),
        "reason": parse_reason(output),
        "judge_output": output,
    }


def calculate_metric2(tone: str, generated_email: str, reference_email: str) -> dict:
    auto_score = auto_tone_score(tone, generated_email)
    llm_rubric_score = llm_tone_rubric_score(tone, generated_email, reference_email)
    final_score = (llm_rubric_score["score"] * 0.6) + (auto_score * 0.4)
    return {
        "score": final_score,
        "auto_score": auto_score,
        "llm_rubric_score": llm_rubric_score["score"],
        "llm_raw_scores": llm_rubric_score["raw_scores"],
        "reason": llm_rubric_score["reason"],
    }


def _fact_overlaps(sentence: str, fact: str, threshold: float = 0.3) -> bool:
    sentence_tokens = tokens(sentence)
    fact_tokens = tokens(fact)
    if not fact_tokens:
        return False
    return len(sentence_tokens & fact_tokens) / len(fact_tokens) >= threshold


def information_density(email_text: str, key_facts: list[str]) -> float:
    sentences = re.split(r"(?<=[.!?])\s+", email_text)
    total_words = len(email_text.split())
    fact_words = 0

    for sentence in sentences:
        if any(_fact_overlaps(sentence, fact) for fact in key_facts):
            fact_words += len(sentence.split())

    return fact_words / total_words if total_words else 0.0


def cta_clarity_score(email_text: str) -> float:
    hits = sum(1 for keyword in CTA_KEYWORDS if keyword in email_text.lower())
    return min(1.0, hits)


def sentence_length_variance(email_text: str) -> float:
    sentences = [sentence for sentence in re.split(r"(?<=[.!?])\s+", email_text) if sentence.strip()]
    lengths = [len(sentence.split()) for sentence in sentences]
    if len(lengths) < 2:
        return 1.0

    variance = np.var(lengths)
    return max(0.0, 1 - min(variance, 200) / 200)


def redundancy_penalty(email_text: str) -> float:
    sentences = [sentence for sentence in re.split(r"(?<=[.!?])\s+", email_text) if sentence.strip()]
    if len(sentences) < 2:
        return 1.0

    embeddings = embedder.encode(sentences, convert_to_tensor=True)
    similarity_matrix = util.cos_sim(embeddings, embeddings)
    sentence_count = len(sentences)
    redundant_pairs = sum(
        1
        for first in range(sentence_count)
        for second in range(first + 1, sentence_count)
        if similarity_matrix[first][second] > 0.85
    )
    return max(0.0, 1 - redundant_pairs * 0.2)


def compression_ratio(generated_email: str, reference_email: str) -> float:
    generated_length = len(generated_email.split())
    reference_length = len(reference_email.split())
    if reference_length == 0:
        return 0.5

    ratio = generated_length / reference_length
    return max(0.0, 1 - abs(1 - ratio))


def metric3_automated_score(generated_email: str, key_facts: list[str], reference_email: str) -> float:
    return float(
        np.mean(
            [
                information_density(generated_email, key_facts),
                cta_clarity_score(generated_email),
                sentence_length_variance(generated_email),
                redundancy_penalty(generated_email),
                compression_ratio(generated_email, reference_email),
            ]
        )
    )


def llm_conciseness_score(key_facts: list[str], generated_email: str) -> dict:
    prompt = f"""SYSTEM
You are a strict evaluator scoring an email on two dimensions: clarity of its
call-to-action, and conciseness without loss of important detail. You are not
evaluating tone, grammar, or factual accuracy -- only structural efficiency.

INPUT
KEY_FACTS (for reference -- to judge whether anything important was cut):
{chr(10).join(f"- {fact}" for fact in key_facts)}

GENERATED_EMAIL:
{generated_email}

INSTRUCTIONS
Step 1 -- Call-to-Action Clarity (1-5):
5 -- A single, unambiguous next step is stated clearly (who does what, by when).
4 -- A clear next step is present but timing or ownership is slightly vague.
3 -- A next step is implied but not explicitly stated.
2 -- Multiple possible next steps are implied, causing ambiguity.
1 -- No discernible call-to-action.

Step 2 -- Conciseness Without Information Loss (1-5):
5 -- Maximally concise; every sentence earns its place; no important detail
     from KEY_FACTS is lost or vague.
4 -- Mostly concise; one sentence could be trimmed without loss.
3 -- Some padding/filler present, but no information lost.
2 -- Noticeably padded AND/OR one important detail is vague/lost.
1 -- Rambling, redundant, and/or important details are missing or unclear.

OUTPUT FORMAT (strict, no extra commentary):
CTA Clarity Score: <integer 1-5>
Conciseness Score: <integer 1-5>
Reason: <one or two sentence justification covering both scores>
"""
    output = judge_text(prompt)
    raw_scores = [
        parse_score("CTA Clarity Score", output),
        parse_score("Conciseness Score", output),
    ]
    normalized_scores = [normalize(score) for score in raw_scores]
    return {
        "raw_scores": raw_scores,
        "score": mean(normalized_scores),
        "reason": parse_reason(output),
        "judge_output": output,
    }


def calculate_metric3(key_facts: list[str], generated_email: str, reference_email: str) -> dict:
    auto_score = metric3_automated_score(generated_email, key_facts, reference_email)
    llm_score = llm_conciseness_score(key_facts, generated_email)
    final_score = (llm_score["score"] * 0.6) + (auto_score * 0.4)
    return {
        "score": final_score,
        "auto_score": auto_score,
        "llm_score": llm_score["score"],
        "llm_raw_scores": llm_score["raw_scores"],
        "reason": llm_score["reason"],
    }


def evaluate_email(user_request: str, generated_email: str, save_report: bool = True) -> dict:
    dataset_item = find_dataset_item(user_request)
    key_facts = split_key_points(dataset_item["key_points"])
    reference_email = dataset_item["email"]
    target_tone = dataset_item["tone"]

    metric1 = calculate_metric1(key_facts, generated_email, reference_email)
    metric2 = calculate_metric2(target_tone, generated_email, reference_email)
    metric3 = calculate_metric3(key_facts, generated_email, reference_email)
    overall = mean([metric1["score"], metric2["score"], metric3["score"]])

    evaluation = {
        "matched_intent": dataset_item["Intent"],
        "target_tone": target_tone,
        "scores": {
            "factual_recall": round(metric1["score"], 3),
            "tone_accuracy": round(metric2["score"], 3),
            "conciseness": round(metric3["score"], 3),
            "overall": round(overall, 3),
        },
        "details": {
            "metric1": {key: round(value, 3) if isinstance(value, float) else value for key, value in metric1.items()},
            "metric2": {key: round(value, 3) if isinstance(value, float) else value for key, value in metric2.items()},
            "metric3": {key: round(value, 3) if isinstance(value, float) else value for key, value in metric3.items()},
        },
        "key_facts": key_facts,
        "reference_email": reference_email,
    }

    if save_report:
        save_evaluation_result(evaluation, user_request, generated_email)
        evaluation["result_file"] = str(EVALUATION_RESULT_PATH)

    return evaluation
