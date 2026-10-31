from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.data import load_invoices
from app.schemas import SummaryResponse
from app.summary import build_summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup. A broken data file stops the app here, not on a request.
    app.state.invoices = load_invoices()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/summary", response_model=SummaryResponse)
def read_summary(request: Request) -> SummaryResponse:
    # Uses the data loaded at startup, not a fresh read of the CSVs.
    return build_summary(request.app.state.invoices)
