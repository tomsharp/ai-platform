import os
import logging 
from time import perf_counter

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Model API", version="0.1.0")

logger = logging.getLogger("model_api")
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)

class PredictRequest(BaseModel):
    text: str

class PredictResponse(BaseModel):
    output: str

def load_model():
    # TODO: replace with actual model loading logic
    model_id = os.getenv("MODEL_ID")
    model_version = os.getenv("MODEL_VERSION")
    return lambda text: text[::-1]  # simple reversed text as example

@app.on_event("startup")
def startup_event():
    global MODEL
    MODEL = load_model()

@app.get("/")
def root():
    return {"message": "Model API is running"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": MODEL is not None,
        "model_id": getattr(MODEL, "id", None),
        "model_name": getattr(MODEL, "name", None),
        "model_version": getattr(MODEL, "version", None),
        "model_type": getattr(MODEL, "type", None),
    }

@app.get("/model")
def health():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    start = perf_counter()
    try:
        output_text = MODEL(payload.text)
        status = "success"
    except Exception as e:
        logger.exception("Error occured")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        latency_ms = (perf_counter() - start) * 1000

    # minimal Phase 1 logging (no DB yet)
    logger.info(
        'request event="predict" status=%s latency_ms=%.2f '
        'input="%s" output="%s"',
        status,
        latency_ms,
        payload.text[:200],
        output_text[:200],
    )

    return PredictResponse(output=output_text)