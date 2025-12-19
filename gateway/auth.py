# ref: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt
import uuid
from typing import Union
from datetime import datetime, timezone, timedelta

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select
from pwdlib import PasswordHash

from .db import SessionLocal
from .models import User

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
password_hash = PasswordHash.recommended()

class UserSchema(BaseModel):
    id: uuid.UUID
    username: str

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Union[str, None] = None


def get_user_by_username(username: str) -> User:
    with SessionLocal() as session:
        return session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

def get_user_by_id(user_id: uuid.UUID) -> User | None:
    with SessionLocal() as session:
        return session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

def authenticate_user(username: str, password: str):
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_encoded_jwt(user: User) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_token(username: str, password: str) -> Token:
    user = authenticate_user(username, password)
    encoded = get_encoded_jwt(user)
    return Token(access_token=encoded, token_type="bearer")


def verify_token(token: str = Depends(oauth2_scheme)) -> UserSchema:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # get user_id from payload
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError:
        raise credentials_exception
    
    # process sub
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise credentials_exception
    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise credentials_exception
    
    # lookup user in db
    user = get_user_by_id(user_id)
    if not user:
        raise credentials_exception
    
    return UserSchema(id=user.id, username=user.username)