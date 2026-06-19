from config.settings import EVALUATION_RESULT_PATH, TESTSET_RESULT_PATH


def save_evaluation_result(evaluation: dict, user_request: str, generated_email: str) -> None:
    scores = evaluation["scores"]
    details = evaluation["details"]
    key_facts = "\n".join(f"- {fact}" for fact in evaluation["key_facts"])

    report = f"""# Evaluation Result

## Summary

- Matched intent: {evaluation["matched_intent"]}
- Target tone: {evaluation["target_tone"]}
- Overall score: {scores["overall"]}

## Detailed Scores

| Metric | Score |
| --- | ---: |
| Factual Recall and Specificity | {scores["factual_recall"]} |
| Tone Accuracy | {scores["tone_accuracy"]} |
| Conciseness and Structural Efficiency | {scores["conciseness"]} |
| Overall | {scores["overall"]} |

## Metric Details

### Metric 1: Factual Recall and Specificity

- Fact present ratio: {details["metric1"]["fact_present_ratio"]}
- Integration naturalness score: {details["metric1"]["integration_naturalness_score"]}
- Integration naturalness raw score: {details["metric1"]["integration_naturalness_raw"]}
- Missing/hallucinated facts: {details["metric1"]["missing_or_hallucinated"]}
- Reason: {details["metric1"]["reason"]}

### Metric 2: Tone Accuracy

- Automated tone score: {details["metric2"]["auto_score"]}
- LLM rubric score: {details["metric2"]["llm_rubric_score"]}
- LLM raw scores: {details["metric2"]["llm_raw_scores"]}
- Reason: {details["metric2"]["reason"]}

### Metric 3: Conciseness and Structural Efficiency

- Automated score: {details["metric3"]["auto_score"]}
- LLM score: {details["metric3"]["llm_score"]}
- LLM raw scores: {details["metric3"]["llm_raw_scores"]}
- Reason: {details["metric3"]["reason"]}

## Key Facts Checked

{key_facts}

## User Request

```text
{user_request}
```

## Generated Email

```text
{generated_email}
```

## Reference Email

```text
{evaluation["reference_email"]}
```
"""

    EVALUATION_RESULT_PATH.write_text(report, encoding="utf-8")


def save_test_report(results: list[dict]) -> None:
    rows = "\n".join(
        _test_report_row(index, result["evaluation"])
        for index, result in enumerate(results, start=1)
    )

    report = f"""| # | Factual Recall | Tone Accuracy | Conciseness |
| ---: | ---: | ---: | ---: |
{rows}
"""

    TESTSET_RESULT_PATH.write_text(report, encoding="utf-8")


def _test_report_row(index: int, evaluation: dict) -> str:
    scores = evaluation["scores"]
    return (
        f"| {index} | {scores['factual_recall']} | "
        f"{scores['tone_accuracy']} | {scores['conciseness']} |"
    )
