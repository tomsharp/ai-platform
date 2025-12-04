import os
import logging
from time import perf_counter

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from model_loader import load_model_predictor

logger = logging.getLogger("model_api")
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)

MODEL_ID = os.getenv("MODEL_ID", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
DEVICE_PREF = os.getenv("DEVICE", "auto")  # "cpu" | "cuda" | "auto"

app = FastAPI(title="Model API", version="0.1.0")


class PredictRequest(BaseModel):
    text: str


class PredictResponse(BaseModel):
    output: str


@app.on_event("startup")
def startup_event():
    logger.info("Starting up, loading model...")
    global PREDICT_FN
    PREDICT_FN = load_model_predictor(MODEL_ID)
    logger.info("Startup complete, model loaded.")


@app.get("/")
def root():
    return {"message": "Model API"}


@app.get("/health")
def health():
    return {
        "status": "ok" if "PREDICT_FN" in globals() else "loading"
    }


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    if "PREDICT_FN" not in globals():
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    start = perf_counter()
    try:
        output = PREDICT_FN(payload.text)
        status = "success"
    except Exception as e:
        logger.exception("Error occured")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        latency_ms = (perf_counter() - start) * 1000

    logger.info(
        'request event="predict" status=%s latency_ms=%.2f '
        'input="%s" output="%s"',
        status,
        latency_ms,
        payload.text[:200],
        output[:200],
    )

    return PredictResponse(output=output)
