
from fastapi import HTTPException
import httpx

from models import Model, ModelVersion, ProviderAccount

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
