from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SyncDeviceStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class SyncOutboxStatus(str, enum.Enum):
    PENDING = "pending"
    RETRY = "retry"
    SENT = "sent"
    DEAD_LETTER = "dead_letter"


class SyncInboxStatus(str, enum.Enum):
    PENDING = "pending"
    RETRY = "retry"
    BLOCKED = "blocked"
    PROCESSED = "processed"
    DEAD_LETTER = "dead_letter"


class SyncDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class SyncDeadLetterStatus(str, enum.Enum):
    OPEN = "open"
    RETRY_PENDING = "retry_pending"
    RESOLVED = "resolved"


def _enum_type(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda values: [member.value for member in values],
    )


class SyncDevice(TimestampMixin, Base):
    __tablename__ = "sync_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[SyncDeviceStatus] = mapped_column(
        _enum_type(SyncDeviceStatus, "sync_device_status"),
        nullable=False,
        default=SyncDeviceStatus.ACTIVE,
        server_default=SyncDeviceStatus.ACTIVE.value,
    )
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_sync_devices_status", "status"),)


class SyncOutbox(TimestampMixin, Base):
    __tablename__ = "sync_outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    business_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    branch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    causation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[SyncOutboxStatus] = mapped_column(
        _enum_type(SyncOutboxStatus, "sync_outbox_status"),
        nullable=False,
        default=SyncOutboxStatus.PENDING,
        server_default=SyncOutboxStatus.PENDING.value,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_sync_outbox_status_next_attempt", "status", "next_attempt_at"),
        Index("ix_sync_outbox_aggregate", "aggregate_type", "aggregate_id", "aggregate_version"),
        Index("ix_sync_outbox_correlation_id", "correlation_id"),
    )


class SyncInbox(TimestampMixin, Base):
    __tablename__ = "sync_inbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    business_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    branch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    causation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[SyncInboxStatus] = mapped_column(
        _enum_type(SyncInboxStatus, "sync_inbox_status"),
        nullable=False,
        default=SyncInboxStatus.PENDING,
        server_default=SyncInboxStatus.PENDING.value,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_sync_inbox_status_next_attempt", "status", "next_attempt_at"),
        Index("ix_sync_inbox_aggregate", "aggregate_type", "aggregate_id", "aggregate_version"),
        Index("ix_sync_inbox_correlation_id", "correlation_id"),
    )


class SyncCheckpoint(TimestampMixin, Base):
    __tablename__ = "sync_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    stream_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    checkpoint_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SyncDeadLetter(TimestampMixin, Base):
    __tablename__ = "sync_dead_letters"

    id: Mapped[int] = mapped_column(primary_key=True)
    direction: Mapped[SyncDirection] = mapped_column(
        _enum_type(SyncDirection, "sync_direction"), nullable=False
    )
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_envelope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_code: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[SyncDeadLetterStatus] = mapped_column(
        _enum_type(SyncDeadLetterStatus, "sync_dead_letter_status"),
        nullable=False,
        default=SyncDeadLetterStatus.OPEN,
        server_default=SyncDeadLetterStatus.OPEN.value,
    )
    first_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("direction", "event_id", name="uq_sync_dead_letters_direction_event"),
        Index("ix_sync_dead_letters_status", "status"),
        Index("ix_sync_dead_letters_correlation_id", "correlation_id"),
    )


class SyncAggregateVersion(TimestampMixin, Base):
    __tablename__ = "sync_aggregate_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    last_applied_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("aggregate_type", "aggregate_id", name="uq_sync_aggregate_versions_aggregate"),
        Index("ix_sync_aggregate_versions_aggregate", "aggregate_type", "aggregate_id"),
    )
