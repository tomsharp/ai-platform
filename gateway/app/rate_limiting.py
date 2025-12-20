
from typing import  Tuple
import time

import redis
from fastapi import HTTPException

from models import GroupModelPermission, ModelVersion, RateLimitPolicy, UserGroup
from db import SessionLocal
from custom_logger import get_logger

logger = get_logger(__name__)

_policy_cache: dict[Tuple[str, str], Tuple[float, RateLimitPolicy]] = {}
CACHE_TTL = 5*60.0 # cache for 5 minutes

def _get_policy_from_db(user_id: str, model_version_id: str) -> RateLimitPolicy:
    logger.info(f"Fetching rate limit policy for user {user_id} and model version {model_version_id}")
    with SessionLocal() as session:
        policy = (
            session.query(RateLimitPolicy)
            .join(GroupModelPermission, RateLimitPolicy.id == GroupModelPermission.policy_id)
            .join(ModelVersion, GroupModelPermission.model_version_id == ModelVersion.id)
            .join(UserGroup, GroupModelPermission.group_id == UserGroup.group_id)
            .filter(
                UserGroup.user_id == user_id,
                ModelVersion.id == model_version_id,
            )
            .first()
        )
    if not policy:
        raise Exception("No rate limit policy found.")
    return policy

async def get_policy_cached(user_id: str, model_version_id: str) -> RateLimitPolicy:
    key = (user_id, model_version_id)
    now = int(time.time())
    cached = _policy_cache.get(key)
    if cached and cached[0] > now:
        return cached[1]

    policy = _get_policy_from_db(user_id, model_version_id)

    _policy_cache[key] = (now + CACHE_TTL, policy)
    return policy

async def enforce_rate_limit(redis: redis.Redis, user_id: str, model_version_id: str) -> None:
    policy = await get_policy_cached(user_id, model_version_id)
    window_seconds = int(policy.window_seconds)
    max_requests = int(policy.max_requests)

    now = int(time.time())
    bucket = now // window_seconds
    redis_key = f"rl:{user_id}:{model_version_id}:{bucket}"

    # create or increment request count
    count = await redis.incr(redis_key)
    # if first request, set expiration w/ 5s buffer
    if count == 1:
        await redis.expire(redis_key, window_seconds + 5)

    if count > max_requests:
        retry_after = window_seconds - (now % window_seconds)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )