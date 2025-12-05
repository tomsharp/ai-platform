import os
import logging
from time import perf_counter
import uuid
from contextlib import asynccontextmanager


from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from loader import load_model_predictor


FORMAT = '{"ts":"%(asctime)s", "level":"%(levelname)s", "module":"%(module)s", "func":"%(funcName)s", "line":%(lineno)d} "msg":"%(message)s"'
logging.basicConfig(level=logging.INFO, format=FORMAT)


logger = logging.getLogger(__name__)


MODEL_ID = os.getenv("MODEL_ID", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
DEVICE_PREF = os.getenv("DEVICE", "auto")  # "cpu" | "cuda" | "auto"


class PredictRequest(BaseModel):
    text: str


class PredictResponse(BaseModel):
    output: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API starting up")
    app.state.predictor = load_model_predictor(MODEL_ID, DEVICE_PREF)
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


@app.middleware("http")
async def middleware(request, call_next):
    
    # track process time, request id
    process_start = perf_counter()
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    
    # process request, log exception if failure
    try:
        response = await call_next(request)
    except Exception:
        process_time = (perf_counter() - process_start) * 1000
        log_details = {
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": 500,
            "process_time_ms": round(process_time, 2),
            "model_latency_ms": None,
        }
        logger.error("Request failed. Details: %s", log_details)
        raise
    
    # log request/response details
    process_time = (perf_counter() - process_start) * 1000
    log_details = {
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
        "status_code": response.status_code,
        "process_time_ms": round(process_time, 2),
        "model_latency_ms": round(getattr(request.state, "model_latency_ms", None), 2) if getattr(request.state, "model_latency_ms", None) is not None else None,
    }
    logger.info("Request completed. Details: %s", log_details)

    # return request id in response headers
    response.headers["x-request-id"] = request_id
    return response


@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest, request: Request):
    if not hasattr(app.state, "predictor"):
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    try:
        model_start = perf_counter()
        output = app.state.predictor(payload.text)
        model_latency = (perf_counter() - model_start) * 1000
        request.state.model_latency_ms = model_latency
        return PredictResponse(output=output)
    except Exception as e:
        logger.exception("Error occurred")
        raise HTTPException(status_code=500, detail="Internal server error") from e


