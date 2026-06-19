from __future__ import annotations

from data.dataset import email_dataset
from core.email_generator import generate_email
from core.eval import evaluate_email
from config.settings import TESTSET_RESULT_PATH
from data.dataset_utils import build_dataset_request
from utils.report_writer import save_test_report


def run_testset_evaluation() -> list[dict]:
    results = []

    for item in email_dataset:
        user_request = build_dataset_request(item)
        generated_email = generate_email(user_request)
        evaluation = evaluate_email(user_request, generated_email, save_report=False)
        results.append(
            {
                "item": item,
                "user_request": user_request,
                "generated_email": generated_email,
                "evaluation": evaluation,
            }
        )

    save_test_report(results)
    return results


if __name__ == "__main__":
    run_testset_evaluation()
    print(f"Saved testset evaluation to {TESTSET_RESULT_PATH}")
