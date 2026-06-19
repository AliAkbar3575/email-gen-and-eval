from fastapi import BackgroundTasks, FastAPI

from config.settings import TESTSET_RESULT_PATH
from core.eval import evaluate_email
from core.email_generator import generate_email
from models.schemas import EmailRequest, EvaluationRequest
from core.testset_eval import run_testset_evaluation


app = FastAPI()


@app.post("/generate")
def generate_email_api(request: EmailRequest):
    generated_email = generate_email(request.user_request, model=request.model)
    return {"generated_email": generated_email}


@app.post("/evaluate")
def evaluate_email_api(request: EvaluationRequest):
    return evaluate_email(request.user_request, request.generated_email)


@app.post("/evaluate-testset")
def evaluate_testset_api(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_testset_evaluation)
    return {"status": "started", "result_file": str(TESTSET_RESULT_PATH)}
