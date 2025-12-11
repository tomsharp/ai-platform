import os
import logging
from datetime import timedelta
from time import perf_counter
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from loader import load_model_predictor


FORMAT = '{"ts":"%(asctime)s", "level":"%(levelname)s", "module":"%(module)s", "line":%(lineno)d} "msg":"%(message)s"'
logging.basicConfig(level=logging.INFO, format=FORMAT)


logger = logging.getLogger(__name__)

MODEL_ID = os.getenv("MODEL_ID", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")

class PredictRequest(BaseModel):
    text: str


class PredictResponse(BaseModel):
    output: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API starting up")
    app.state.predictor = load_model_predictor(MODEL_ID)
    logger.info("Startup complete")
    yield

app = FastAPI(title="Model API", version="0.1.0", lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "Model API"}

@app.get("/health")
def health():
    return {
        "status": "ok" if hasattr(app.state, "predictor") else "loading"
    }

@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest, request: Request):
    if not hasattr(app.state, "predictor"):
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    try:
        logging.info("Received prediction request")
        model_start = perf_counter()
        output = app.state.predictor(payload.text)
        model_latency = (perf_counter() - model_start) * 1000
        request.state.model_latency_ms = model_latency
        logging.info(f"Inference complete. Model latency: {model_latency:.2f} ms")
        return PredictResponse(output=output)
    except Exception as e:
        logger.exception("Error occurred")
        raise HTTPException(status_code=500, detail="Internal server error") from e


