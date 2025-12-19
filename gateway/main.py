from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
import httpx

from .auth import Token, create_token, verify_token, UserSchema
from .models import Model, ModelVersion, ProviderAccount, ProviderEnum
from .db import SessionLocal

app = FastAPI()

class PredictRequest(BaseModel):
    text: str


class PredictResponse(BaseModel):
    output: str


@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    return create_token(form_data.username, form_data.password)


async def call_openai(
    account: ProviderAccount,
    upstream_model: str,
    text: str,
) -> str:
    if not account.api_key:
        raise HTTPException(status_code=500, detail="ProviderAccount.api_key is missing for OpenAI")
    
    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {account.api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": upstream_model, "input": text}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"OpenAI error {r.status_code}: {r.text[:500]}")

    try:
        data = r.json()
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from OpenAI: {r.text[:500]}") from e
    try:
        for item in data.get("output", []):
            for c in item.get("content", []):
                if c.get("type") == "output_text" and isinstance(c.get("text"), str):
                    return c["text"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Invalid response from OpenAI: {r.text[:500]}") from e
        



@app.post("/predict/{model_name}/{version}", response_model=PredictResponse)
async def infer(
    model_name: str,
    version: str,
    body: PredictRequest,
    current_user: Annotated[UserSchema, Depends(verify_token)],
):
    # 1) Fetch model + version + provider account
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

    if mv.provider == ProviderEnum.openai.value:
        output = await call_openai(
            account=mv.provider_account,
            upstream_model=mv.model.name,
            text=body.text,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {mv.provider}")
    
    return PredictResponse(output=output)