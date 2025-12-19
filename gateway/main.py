from typing import Annotated

from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordRequestForm

from .auth import Token, create_token, verify_token, UserSchema

app = FastAPI()

@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    return create_token(form_data.username, form_data.password)

@app.get("/users/me")
async def get_current_active_user(
    current_user: Annotated[UserSchema, Depends(verify_token)],
):
    return current_user