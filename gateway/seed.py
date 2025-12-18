from __future__ import annotations

import os
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .db import SessionLocal, Base, engine
from . import models


# ---------- helpers ----------

def create_tables():
    Base.metadata.create_all(bind=engine)


def hash_api_key(raw: str) -> str:
    # Simple SHA-256 hash for demo. In production, prefer HMAC w/ server-side pepper.
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_api_key(prefix: str = "gw") -> tuple[str, str]:
    raw = f"{prefix}_{secrets.token_urlsafe(32)}"
    return raw, hash_api_key(raw)


def ensure_one(session, model_cls, where_clause, create_kwargs: dict):
    obj = session.execute(select(model_cls).where(where_clause)).scalar_one_or_none()
    if obj:
        return obj
    obj = model_cls(**create_kwargs)
    session.add(obj)
    session.flush()  # assign PK
    return obj

def ensure_membership(session, user_id: uuid.UUID, group_id: uuid.UUID):
    ug = session.execute(
        select(models.UserGroup).where(
            models.UserGroup.user_id == user_id,
            models.UserGroup.group_id == group_id,
        )
    ).scalar_one_or_none()
    if not ug:
        session.add(models.UserGroup(user_id=user_id, group_id=group_id))

def ensure_api_key(session, user: models.User):
    existing = session.execute(
        select(models.ApiKey).where(
            models.ApiKey.user_id == user.id,
            models.ApiKey.status == "active",
        )
    ).scalars().first()

    if existing:
        return None  # already has one

    raw, key_hash = make_api_key()
    now = datetime.utcnow()
    session.add(
        models.ApiKey(
            user_id=user.id,
            key_hash=key_hash,
            status="active",
            created_at=now,
            expires_at=now + timedelta(days=365),
        )
    )
    return raw

def ensure_rl(session, group_id: uuid.UUID, model_version_id: uuid.UUID, policy_id: uuid.UUID):
    row = session.execute(
        select(models.GroupModelRateLimit).where(
            models.GroupModelRateLimit.group_id == group_id,
            models.GroupModelRateLimit.model_version_id == model_version_id,
        )
    ).scalar_one_or_none()
    if not row:
        session.add(
            models.GroupModelRateLimit(
                group_id=group_id,
                model_version_id=model_version_id,
                policy_id=policy_id,
            )
        )


def ensure_perm_and_policy(session, group_id, model_version_id, allowed, policy_id):
    row = session.execute(
        select(models.GroupModelPermission).where(
            models.GroupModelPermission.group_id == group_id,
            models.GroupModelPermission.model_version_id == model_version_id,
        )
    ).scalar_one_or_none()

    if row:
        # update in-place to match seed intent
        row.allowed = allowed
        row.policy_id = policy_id
        return row

    row = models.GroupModelPermission(
        group_id=group_id,
        model_version_id=model_version_id,
        allowed=allowed,
        policy_id=policy_id,
    )
    session.add(row)
    return row

# ---------- seed data ----------

def seed():

    with SessionLocal() as session:
        try:
            # ----- Groups -----
            admin_group = ensure_one(
                session,
                models.Group,
                models.Group.name == "admins",
                {"name": "admins"},
            )
            devs_group = ensure_one(
                session,
                models.Group,
                models.Group.name == "devs",
                {"name": "devs"},
            )
            svcs_group = ensure_one(
                session,
                models.Group,
                models.Group.name == "systems",
                {"name": "systems"},
            )

            # ----- Users -----
            admin = ensure_one(
                session,
                models.User,
                models.User.username == "admin",
                {"username": "admin", "password_hash": None},
            )
            tom = ensure_one(
                session,
                models.User,
                models.User.username == "tom",
                {"username": "tom", "password_hash": None},
            )
            chatbot_svc = ensure_one(
                session,
                models.User,
                models.User.username == "chatbot-service",
                {"username": "chatbot-service", "password_hash": None},
            )
            ensure_membership(session, admin.id, admin_group.id)
            ensure_membership(session, tom.id, devs_group.id)
            ensure_membership(session, chatbot_svc.id, svcs_group.id)

            # ----- API keys -----
            admin_key = ensure_api_key(session, admin)
            tom_key = ensure_api_key(session, tom)
            svc_key = ensure_api_key(session, chatbot_svc)

            # ----- Models + Versions -----
            # Models
            tiny_llama = ensure_one(
                session,
                models.Model,
                models.Model.name == "tiny-llama",
                {"name": "tiny-llama", "description": "Tiny LLaMA model for testing"},
            )
            gpt_4o_mini = ensure_one(
                session,
                models.Model,
                models.Model.name == "gpt-4o-mini",
                {"name": "gpt-4o-mini", "description": "OpenAI GPT-4o-mini"},
            )

            # Versions
            tiny_llama_v1 = ensure_one(
                session,
                models.ModelVersion,
                (models.ModelVersion.model_id == tiny_llama.id) & (models.ModelVersion.version == "v1"),
                {"model_id": tiny_llama.id, "version": "v1"},
            )
            gpt_4o_mini_v1 = ensure_one(
                session,
                models.ModelVersion,
                (models.ModelVersion.model_id == gpt_4o_mini.id) & (models.ModelVersion.version == "v1"),
                {"model_id": gpt_4o_mini.id, "version": "v1"},
            )

            # ----- Rate limit policies -----
            rl_high = ensure_one(
                session,
                models.RateLimitPolicy,
                (models.RateLimitPolicy.window_seconds == 60*5) & (models.RateLimitPolicy.max_requests == 1000),
                {"window_seconds": 60*5, "max_requests": 1000},
            )
            rl_med = ensure_one(
                session,
                models.RateLimitPolicy,
                (models.RateLimitPolicy.window_seconds == 60*5) & (models.RateLimitPolicy.max_requests == 120),
                {"window_seconds": 60*5, "max_requests": 120},
            )
            rl_low = ensure_one(
                session,
                models.RateLimitPolicy,
                (models.RateLimitPolicy.window_seconds == 60*5) & (models.RateLimitPolicy.max_requests == 20),
                {"window_seconds": 60*5, "max_requests": 20},
            )

            # ---- permissions + policies per group + model_version ----
            ensure_perm_and_policy(session, admin_group.id, gpt_4o_mini_v1.id, True, rl_high.id)
            ensure_perm_and_policy(session, admin_group.id, tiny_llama_v1.id, True, rl_high.id)

            ensure_perm_and_policy(session, devs_group.id, gpt_4o_mini_v1.id, True, rl_med.id)
            ensure_perm_and_policy(session, devs_group.id, tiny_llama_v1.id, True, rl_med.id)

            ensure_perm_and_policy(session, svcs_group.id, tiny_llama_v1.id, True, rl_low.id)
            ensure_perm_and_policy(session, svcs_group.id, gpt_4o_mini_v1.id, False, None)



            # ----- Provider accounts (very simple v1) -----
            openai_key = os["OPENAI_API_KEY"] if "OPENAI_API_KEY" in os.environ else "token-not-set"
            ensure_one(
                session,
                models.ProviderAccount,
                (models.ProviderAccount.provider == "openai") & (models.ProviderAccount.provider == "openai-local"),
                {
                    "provider": "openai",
                    "api_key_hash": hash_api_key(openai_key),
                    "username": None,
                    "password_hash": None,
                },
            )

            session.commit()

            print("✅ Seed complete.")

            # Print newly-created raw keys (ONLY shown once)
            # (If an API key already existed, we won’t print it again.)
            if admin_key:
                print(f"🔑 admin API key (save now): {admin_key}")
            if tom_key:
                print(f"🔑 tom API key (save now): {tom_key}")
            if svc_key:
                print(f"🔑 chatbot-service API key (save now): {svc_key}")

            if not openai_key:
                print("ℹ️ OPENAI_API_KEY not set; provider_accounts.openai-local.api_key is NULL.")

        except IntegrityError as e:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            raise


if __name__ == "__main__":
    create_tables()
    seed()
