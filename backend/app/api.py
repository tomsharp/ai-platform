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

from auth import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user, Token
from loader import load_model_predictor


FORMAT = '{"ts":"%(asctime)s", "level":"%(levelname)s", "module":"%(module)s", "func":"%(funcName)s", "line":%(lineno)d} "msg":"%(message)s"'
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

@app.get("/")
def root():
    return {"message": "Model API"}

@app.get("/health")
def health():
    return {
        "status": "ok" if hasattr(app.state, "predictor") else "loading"
    }

@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@app.post("/predict", response_model=PredictResponse, dependencies=[Depends(get_current_user)])
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


