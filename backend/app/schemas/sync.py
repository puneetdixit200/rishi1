from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class SyncEventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(min_length=1, max_length=120)
    schema_version: int = Field(default=1, ge=1)
    source: str = Field(min_length=1, max_length=40)
    source_device_id: str | None = Field(default=None, max_length=64)
    business_group_id: str | None = Field(default=None, max_length=64)
    company_id: str | None = Field(default=None, max_length=64)
    branch_id: str | None = Field(default=None, max_length=64)
    aggregate_type: str = Field(min_length=1, max_length=80)
    aggregate_id: str = Field(min_length=1, max_length=80)
    aggregate_version: int = Field(ge=1)
    idempotency_key_hash: str | None = Field(default=None, max_length=128)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at", "recorded_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        # Some local/test DB adapters strip tzinfo when reading a UTC timestamp.
        # Treat such values as UTC and always normalize the envelope to UTC.
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class SyncConsumeResult(BaseModel):
    event_id: UUID
    status: str
    duplicate: bool = False
    result: dict[str, Any] | None = None
    detail: str | None = None
