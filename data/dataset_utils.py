import re

from data.dataset import email_dataset


def split_key_points(key_points: str) -> list[str]:
    return [line.strip() for line in key_points.splitlines() if line.strip()]


def build_dataset_request(item: dict) -> str:
    return (
        f"Intent: {item['Intent']}\n"
        f"Key points:\n{item['key_points']}\n"
        f"Tone: {item['tone']}"
    )


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def find_dataset_item(user_request: str) -> dict:
    request_tokens = tokens(user_request)

    def overlap_score(item: dict) -> float:
        item_tokens = tokens(build_dataset_request(item))
        if not request_tokens or not item_tokens:
            return 0.0
        return len(request_tokens & item_tokens) / len(request_tokens | item_tokens)

    return max(email_dataset, key=overlap_score)
