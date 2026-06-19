from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

GENERATION_MODEL = "llama-3.1-8b-instant" # openai/gpt-oss-20b
JUDGE_MODEL = "openai/gpt-oss-120b"

EVALUATION_RESULT_PATH = Path("outputs/evaluation_result.md")
TESTSET_RESULT_PATH = Path("outputs/test_llm.md")
