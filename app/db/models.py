"""Persist digests and bounded metadata without storing source documents."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        CheckConstraint("hash_algorithm = 'sha256'", name="ck_registrations_algorithm"),
        CheckConstraint("digest ~ '^[0-9a-f]{64}$'", name="ck_registrations_digest"),
        CheckConstraint("format_version = 1", name="ck_registrations_version"),
        CheckConstraint("jsonb_typeof(registration_metadata) = 'object'", name="ck_registrations_metadata_object"),
        CheckConstraint("octet_length(registration_metadata::text) <= 8192", name="ck_registrations_metadata_size"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    digest: Mapped[str] = mapped_column(Text, nullable=False)
    hash_algorithm: Mapped[str] = mapped_column(String(16), nullable=False, server_default="sha256")
    registration_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.statement_timestamp())
    format_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
