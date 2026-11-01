from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from app.data import load_invoices
from app.llm import LLMError, OllamaLLM
from app.pipeline import answer_question
from app.policy import load_policy
from app.schemas import AskRequest, AskResponse, SummaryResponse
from app.settings import DEFAULT_HOST, DEFAULT_MODEL, get_setting, read_env_file
from app.summary import build_summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup. A broken data file stops the app here, not on a request.
    app.state.invoices = load_invoices()
    app.state.policy = load_policy()

    file_values = read_env_file()
    app.state.llm = OllamaLLM(
        model=get_setting("OLLAMA_MODEL", DEFAULT_MODEL, file_values),
        host=get_setting("OLLAMA_HOST", DEFAULT_HOST, file_values),
    )
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/summary", response_model=SummaryResponse)
def read_summary(request: Request) -> SummaryResponse:
    # Uses the data loaded at startup, not a fresh read of the CSVs.
    return build_summary(request.app.state.invoices)


# Plain `def`: the model call blocks, and FastAPI runs plain functions in a thread pool.
@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request) -> AskResponse:
    state = request.app.state
    try:
        return answer_question(body.question, state.llm, state.invoices, state.policy)
    except LLMError as error:
        # The model is down or too slow. This is a service problem, not a bad question.
        raise HTTPException(status_code=503, detail=str(error))
