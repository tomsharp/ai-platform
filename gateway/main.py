import os 
import uuid
from typing import Annotated
from time import perf_counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from redis.asyncio import Redis
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from .rate_limiting import enforce_rate_limit
from .auth import Token, issue_token, authenticate_request, Principal
from .models import Model, ModelVersion, ProviderEnum
from .db import SessionLocal
from .logging import get_logger
from .providers import call_openai

logger = get_logger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class PredictRequest(BaseModel):
    text: str

class PredictResponse(BaseModel):
    output: str

async def require_principal(
    request: Request,
    token: str = Depends(oauth2_scheme),
) -> Principal:
    principal = authenticate_request(token)
    request.state.principal = principal
    return principal

# ---- App and Middleware ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...", extra={"event": "startup"})
    global redis
    REDIS_URL = os.environ["REDIS_URL"]
    redis = Redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await redis.ping()

    yield

    logger.info("Shutting down...", extra={"event": "shutdown"})
    await redis.close() 


app = FastAPI(lifespan=lifespan, title="Model Gateway", version="0.1.0")

@app.middleware("http")
async def middleware(request, call_next):
    
    # track process time, request id
    process_start = perf_counter()
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

    # log received request
    logger.info(
        "Request received.",
        extra={
            "event": "request_received",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        },
    )
    
    # process request, log exception if failure
    try:
        response = await call_next(request)
    except Exception:
        process_time = (perf_counter() - process_start) * 1000
        principal = getattr(request.state, "principal", None)
        log_details = {
            "event": "request_failed",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "principal_id": getattr(principal, "id", None),
            "process_time_ms": round(process_time, 2),
            "status_code": 500,
        }
        logger.exception("Request failed.", extra=log_details)
        raise
    
    # log successful request
    process_time = (perf_counter() - process_start) * 1000
    principal = getattr(request.state, "principal", None)
    log_details = {
        "event": "request_completed",
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
        "principal_id": getattr(principal, "id", None),
        "process_time_ms": round(process_time, 2),
        "status_code": response.status_code,
    }
    logger.info("Request completed.", extra=log_details)
    
    # add request id to response headers and return response
    response.headers["x-request-id"] = request_id
    return response

# ---- Routes ----
@app.get("/")
def root():
    return {"message": "Model Gateway"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    return issue_token(form_data.username, form_data.password)


@app.post("/predict/{model_name}/{version}", response_model=PredictResponse)
async def infer(
    model_name: str,
    version: str,
    body: PredictRequest,
    principal: Annotated[Principal, Depends(require_principal)],
):
    # fetch model version
    with SessionLocal() as session:
        mv = session.execute(
            select(ModelVersion)
            .options(
                joinedload(ModelVersion.model),
                joinedload(ModelVersion.provider_account),
            )
            .where(
                ModelVersion.version == version,
                ModelVersion.model.has(Model.name == model_name),
            )
        ).scalar_one_or_none()
    if not mv:
        raise HTTPException(status_code=404, detail="Unknown model/version")
    
    # enforce rate limit per model_version/user
    await enforce_rate_limit(
        redis=redis,
        user_id=str(principal.id),
        model_version_id=str(mv.id),
    )

    # route to provider
    if mv.provider == ProviderEnum.openai.value:
        output = await call_openai(
            account=mv.provider_account,
            upstream_model=mv.model.name,
            text=body.text,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {mv.provider}")
    
    # return response from inference api
    return PredictResponse(output=output)