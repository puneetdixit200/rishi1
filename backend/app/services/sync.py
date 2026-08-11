from __future__ import annotations

import hashlib
import os
import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditLog
from app.models.sync import (
    SyncAggregateVersion,
    SyncCheckpoint,
    SyncDeadLetter,
    SyncDevice,
    SyncInbox,
    SyncOutbox,
)
from app.schemas.sync import SyncConsumeResult, SyncEventEnvelope
from app.services.audit import write_audit_log

SUPPORTED_SYNC_SCHEMA_VERSION = 1


class RetryableSyncError(RuntimeError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class PermanentSyncError(RuntimeError):
    pass


class DeviceCredentialProvider(Protocol):
    def get_secret(self, credential_ref: str) -> str:
        ...


class EnvironmentDeviceCredentialProvider:
    """Resolve a device secret from an environment variable without persisting the secret."""

    def get_secret(self, credential_ref: str) -> str:
        value = os.getenv(credential_ref)
        if not value:
            raise RuntimeError(f"Device credential environment variable {credential_ref!r} is not set.")
        return value


def hash_idempotency_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def enqueue_outbox(db: Session, envelope: SyncEventEnvelope) -> SyncOutbox:
    """Persist an event in the caller's transaction. This helper never commits."""
    row = SyncOutbox(
        event_id=str(envelope.event_id),
        event_type=envelope.event_type,
        schema_version=envelope.schema_version,
        source=envelope.source,
        source_device_id=envelope.source_device_id,
        business_group_id=envelope.business_group_id,
        company_id=envelope.company_id,
        branch_id=envelope.branch_id,
        aggregate_type=envelope.aggregate_type,
        aggregate_id=envelope.aggregate_id,
        aggregate_version=envelope.aggregate_version,
        idempotency_key_hash=envelope.idempotency_key_hash,
        occurred_at=envelope.occurred_at,
        recorded_at=envelope.recorded_at,
        correlation_id=str(envelope.correlation_id),
        causation_id=str(envelope.causation_id) if envelope.causation_id else None,
        payload_json=envelope.payload,
    )
    db.add(row)
    db.flush()
    return row


def envelope_from_outbox(row: SyncOutbox) -> SyncEventEnvelope:
    return SyncEventEnvelope(
        event_id=row.event_id,
        event_type=row.event_type,
        schema_version=row.schema_version,
        source=row.source,
        source_device_id=row.source_device_id,
        business_group_id=row.business_group_id,
        company_id=row.company_id,
        branch_id=row.branch_id,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        aggregate_version=row.aggregate_version,
        idempotency_key_hash=row.idempotency_key_hash,
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
        payload=row.payload_json or {},
    )


def get_or_create_device_identity(
    db: Session,
    *,
    device_id: str,
    credential_ref: str | None,
) -> SyncDevice:
    row = db.scalar(select(SyncDevice).where(SyncDevice.device_id == device_id))
    if row is None:
        row = SyncDevice(device_id=device_id, credential_ref=credential_ref)
        db.add(row)
        db.flush()
    elif credential_ref and row.credential_ref != credential_ref:
        row.credential_ref = credential_ref
        db.flush()
    return row


def _get_aggregate_version(db: Session, envelope: SyncEventEnvelope) -> SyncAggregateVersion | None:
    return db.scalar(
        select(SyncAggregateVersion)
        .where(
            SyncAggregateVersion.aggregate_type == envelope.aggregate_type,
            SyncAggregateVersion.aggregate_id == envelope.aggregate_id,
        )
        .with_for_update()
    )


def _upsert_dead_letter(
    db: Session,
    envelope: SyncEventEnvelope,
    *,
    reason_code: str,
    diagnostic: str,
    status: str = "attention",
) -> SyncDeadLetter:
    event_id = str(envelope.event_id)
    row = db.scalar(
        select(SyncDeadLetter).where(
            SyncDeadLetter.event_id == event_id,
            SyncDeadLetter.reason_code == reason_code,
        )
    )
    if row is None:
        row = SyncDeadLetter(
            event_id=event_id,
            event_type=envelope.event_type,
            aggregate_type=envelope.aggregate_type,
            aggregate_id=envelope.aggregate_id,
            aggregate_version=envelope.aggregate_version,
            correlation_id=str(envelope.correlation_id),
            reason_code=reason_code,
            diagnostic=diagnostic[:2000],
            status=status,
        )
        db.add(row)
    else:
        row.diagnostic = diagnostic[:2000]
        row.status = status
    db.flush()
    return row


EventHandler = Callable[[Session, SyncEventEnvelope], dict[str, Any] | None]


def consume_event(db: Session, envelope: SyncEventEnvelope, handler: EventHandler) -> SyncConsumeResult:
    """Apply one event and its durable receipt in the caller's transaction."""
    event_id = str(envelope.event_id)
    existing = db.get(SyncInbox, event_id)
    if existing is not None:
        return SyncConsumeResult(
            event_id=envelope.event_id,
            status="already_applied",
            duplicate=True,
            result=existing.result_json,
        )

    if envelope.schema_version != SUPPORTED_SYNC_SCHEMA_VERSION:
        _upsert_dead_letter(
            db,
            envelope,
            reason_code="unsupported_schema_version",
            diagnostic=f"Unsupported sync schema version {envelope.schema_version}.",
        )
        return SyncConsumeResult(
            event_id=envelope.event_id,
            status="attention_required",
            detail="unsupported_schema_version",
        )

    version_row = _get_aggregate_version(db, envelope)
    last_version = version_row.last_applied_version if version_row is not None else 0
    expected_version = last_version + 1

    if envelope.aggregate_version > expected_version:
        _upsert_dead_letter(
            db,
            envelope,
            reason_code="aggregate_version_gap",
            diagnostic=(
                f"Expected aggregate version {expected_version} but received "
                f"{envelope.aggregate_version}."
            ),
            status="waiting",
        )
        return SyncConsumeResult(
            event_id=envelope.event_id,
            status="waiting_for_prior_version",
            detail=f"expected_version={expected_version}",
        )

    if envelope.aggregate_version < expected_version:
        _upsert_dead_letter(
            db,
            envelope,
            reason_code="unproven_stale_version",
            diagnostic=(
                f"Aggregate is already at version {last_version}; event version "
                f"{envelope.aggregate_version} has no durable inbox receipt."
            ),
        )
        return SyncConsumeResult(
            event_id=envelope.event_id,
            status="attention_required",
            detail="unproven_stale_version",
        )

    result = handler(db, envelope) or {}
    db.add(
        SyncInbox(
            event_id=event_id,
            event_type=envelope.event_type,
            aggregate_type=envelope.aggregate_type,
            aggregate_id=envelope.aggregate_id,
            aggregate_version=envelope.aggregate_version,
            correlation_id=str(envelope.correlation_id),
            result_json=result,
        )
    )
    if version_row is None:
        version_row = SyncAggregateVersion(
            aggregate_type=envelope.aggregate_type,
            aggregate_id=envelope.aggregate_id,
            last_applied_version=envelope.aggregate_version,
        )
        db.add(version_row)
    else:
        version_row.last_applied_version = envelope.aggregate_version
    db.flush()

    waiting = db.scalars(
        select(SyncDeadLetter).where(
            SyncDeadLetter.aggregate_type == envelope.aggregate_type,
            SyncDeadLetter.aggregate_id == envelope.aggregate_id,
            SyncDeadLetter.reason_code == "aggregate_version_gap",
            SyncDeadLetter.status == "waiting",
            SyncDeadLetter.aggregate_version <= envelope.aggregate_version,
        )
    ).all()
    for dead_letter in waiting:
        dead_letter.status = "resolved"

    return SyncConsumeResult(event_id=envelope.event_id, status="applied", result=result)


def consume_event_transactionally(
    session_factory: sessionmaker[Session],
    envelope: SyncEventEnvelope,
    handler: EventHandler,
) -> SyncConsumeResult:
    with session_factory() as db:
        with db.begin():
            return consume_event(db, envelope, handler)


def get_checkpoint(db: Session, name: str) -> SyncCheckpoint | None:
    return db.get(SyncCheckpoint, name)


def update_checkpoint(
    db: Session,
    *,
    name: str,
    cursor: str | None,
    last_event_id: str | None,
    succeeded_at: datetime | None = None,
) -> SyncCheckpoint:
    row = db.get(SyncCheckpoint, name)
    if row is None:
        row = SyncCheckpoint(name=name)
        db.add(row)
    row.cursor = cursor
    row.last_event_id = last_event_id
    row.last_success_at = succeeded_at or datetime.now(UTC)
    db.flush()
    return row


def pending_outbox_batch(db: Session, *, limit: int, now: datetime | None = None) -> list[SyncOutbox]:
    if limit < 1:
        return []
    current = now or datetime.now(UTC)
    return list(
        db.scalars(
            select(SyncOutbox)
            .where(
                SyncOutbox.status.in_(("pending", "retry")),
                or_(SyncOutbox.next_attempt_at.is_(None), SyncOutbox.next_attempt_at <= current),
            )
            .order_by(SyncOutbox.created_at, SyncOutbox.event_id)
            .limit(limit)
        ).all()
    )


def compute_retry_delay_seconds(
    attempt_count: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_ratio: float = 0.25,
    rng: random.Random | None = None,
) -> float:
    attempt = max(1, attempt_count)
    base = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
    random_source = rng or random
    jitter = random_source.uniform(0, max(0.0, base * jitter_ratio))
    return min(max_delay_seconds, base + jitter)


def schedule_outbox_retry(
    row: SyncOutbox,
    *,
    error: str,
    base_delay_seconds: float,
    max_delay_seconds: float,
    retry_after_seconds: float | None = None,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> float:
    current = now or datetime.now(UTC)
    row.attempt_count += 1
    delay = retry_after_seconds
    if delay is None:
        delay = compute_retry_delay_seconds(
            row.attempt_count,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            rng=rng,
        )
    delay = min(max_delay_seconds, max(0.0, delay))
    row.status = "retry"
    row.last_attempt_at = current
    row.next_attempt_at = current + timedelta(seconds=delay)
    row.last_error = error[:2000]
    return delay


def mark_outbox_sent(row: SyncOutbox, *, now: datetime | None = None) -> None:
    current = now or datetime.now(UTC)
    row.status = "sent"
    row.last_attempt_at = current
    row.sent_at = current
    row.next_attempt_at = None
    row.last_error = None


def dead_letter_outbox(db: Session, row: SyncOutbox, *, reason_code: str, diagnostic: str) -> SyncDeadLetter:
    envelope = envelope_from_outbox(row)
    dead_letter = _upsert_dead_letter(
        db,
        envelope,
        reason_code=reason_code,
        diagnostic=diagnostic,
    )
    row.status = "dead_letter"
    row.last_error = diagnostic[:2000]
    return dead_letter


def request_dead_letter_retry(
    db: Session,
    *,
    dead_letter_id: int,
    user_id: int | None = None,
) -> SyncDeadLetter:
    row = db.get(SyncDeadLetter, dead_letter_id)
    if row is None:
        raise LookupError(f"Sync dead letter {dead_letter_id} does not exist.")
    row.retry_count += 1
    row.last_retry_at = datetime.now(UTC)
    row.status = "retry_requested"
    write_audit_log(
        db,
        action="sync_dead_letter_retry_requested",
        entity_type="sync_dead_letter",
        entity_id=row.id,
        user_id=user_id,
        new_value_json={
            "event_id": row.event_id,
            "reason_code": row.reason_code,
            "retry_count": row.retry_count,
        },
        notes=f"correlation_id={row.correlation_id}",
        commit=False,
    )
    db.flush()
    return row
