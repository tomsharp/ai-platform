from __future__ import annotations

import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    String, Boolean, DateTime, Integer, ForeignKey, UniqueConstraint, Text, CheckConstraint
)
from sqlalchemy import Enum as sqlalchemyEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

def utcnow() -> datetime:
    return datetime.utcnow()

# -------------------------
# Identity / API keys
# -------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    groups: Mapped[list["UserGroup"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)

    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)  # active/revoked

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship(back_populates="api_keys")

# -------------------------
# Groups / Memberships
# -------------------------

class Group(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    members: Mapped[list["UserGroup"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    model_perms: Mapped[list["GroupModelPermission"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

class UserGroup(Base):
    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="groups")
    group: Mapped["Group"] = relationship(back_populates="members")

# -------------------------
# Model Provider credentials
# -------------------------
class ProviderEnum(enum.Enum):
    openai = "openai"
    internal = "internal"

class ProviderAccount(Base):
    __tablename__ = "provider_accounts"
    __table_args__ = (
        UniqueConstraint("provider", name="uq_provider_account"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[ProviderEnum] = mapped_column(
        sqlalchemyEnum(ProviderEnum, name="provider_enum"),
        index=True,
        nullable=False,
    )
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)


# -------------------------
# Models / Versions
# -------------------------

class Model(Base):
    __tablename__ = "models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    documentation_url: Mapped[str] = mapped_column(String(300), nullable=True)

    versions: Mapped[list["ModelVersion"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )

class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_id", "version", name="uq_model_version"),
        CheckConstraint(
            """
            (provider = 'internal' AND internal_endpoint_url IS NOT NULL)
            OR
            (provider != 'internal' AND internal_endpoint_url IS NULL)
            """,
            name="ck_internal_endpoint_required_for_internal_provider",
        ),
    )


    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("models.id"), index=True)
    version: Mapped[str] = mapped_column(String(120), index=True)

    provider: Mapped[str] = mapped_column(String(64), index=True)
    provider_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_accounts.id"), index=True
    )
    internal_endpoint_url: Mapped[str | None] = mapped_column(String(400), nullable=True)

    model: Mapped["Model"] = relationship(back_populates="versions")
    provider_account: Mapped["ProviderAccount"] = relationship()

# -------------------------
# Rate limits
# -------------------------

class RateLimitPolicy(Base):
    __tablename__ = "rate_limit_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    window_seconds: Mapped[int] = mapped_column(Integer)  # e.g. 300
    max_requests: Mapped[int] = mapped_column(Integer)    # e.g. 120

# -------------------------
# Permissions (+ optional rate policy)
# group + model_version => allowed/disallowed + rate limit policy
# -------------------------

class GroupModelPermission(Base):
    __tablename__ = "group_model_permissions"
    __table_args__ = (
        UniqueConstraint("group_id", "model_version_id", name="uq_group_model_perm"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id"), index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("model_versions.id"), index=True)

    allowed: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # nullable so deny rules don't have to carry a policy
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rate_limit_policies.id"),
        index=True,
        nullable=True,
    )

    group: Mapped["Group"] = relationship(back_populates="model_perms")
    model_version: Mapped["ModelVersion"] = relationship()
    policy: Mapped["RateLimitPolicy"] = relationship()