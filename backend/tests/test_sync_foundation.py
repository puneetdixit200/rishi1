from __future__ import annotations

import random
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditLog
from app.models.sync import SyncCheckpoint, SyncDeadLetter, SyncDevice, SyncInbox, SyncOutbox
from app.schemas.sync import SyncEventEnvelope
from app.services.sync import (
    EnvironmentDeviceCredentialProvider,
    compute_retry_delay_seconds,
    consume_event_transactionally,
    enqueue_outbox,
    get_or_create_device_identity,
    request_dead_letter_retry,
    schedule_outbox_retry,
)
from app.workers.sync_worker import FileDeviceIdentityStore, LocalSyncWorker


def make_envelope(
    *,
    aggregate_id: str = "aggregate-1",
    aggregate_version: int = 1,
    schema_version: int = 1,
    event_type: str = "test.changed",
) -> SyncEventEnvelope:
    return SyncEventEnvelope(
        event_type=event_type,
        schema_version=schema_version,
        source="local_hub",
        aggregate_type="test_aggregate",
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        payload={"value": aggregate_version},
    )


def count_rows(db: Session, model: type[object]) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def test_outbox_commits_with_domain_change(db_session_factory: sessionmaker[Session]) -> None:
    envelope = make_envelope()
    with db_session_factory() as db:
        with db.begin():
            db.add(AuditLog(action="domain_change", entity_type="test"))
            enqueue_outbox(db, envelope)

    with db_session_factory() as db:
        assert count_rows(db, AuditLog) == 1
        assert count_rows(db, SyncOutbox) == 1
        assert db.get(SyncOutbox, str(envelope.event_id)) is not None


def test_domain_rollback_also_rolls_back_outbox(db_session_factory: sessionmaker[Session]) -> None:
    envelope = make_envelope()
    with db_session_factory() as db:
        transaction = db.begin()
        db.add(AuditLog(action="rolled_back_change", entity_type="test"))
        enqueue_outbox(db, envelope)
        transaction.rollback()

    with db_session_factory() as db:
        assert count_rows(db, AuditLog) == 0
        assert count_rows(db, SyncOutbox) == 0


def test_duplicate_delivery_creates_one_business_effect(db_session_factory: sessionmaker[Session]) -> None:
    envelope = make_envelope()

    def handler(db: Session, _event: SyncEventEnvelope) -> dict[str, object]:
        row = AuditLog(action="business_effect", entity_type="test")
        db.add(row)
        db.flush()
        return {"audit_id": row.id}

    first = consume_event_transactionally(db_session_factory, envelope, handler)
    second = consume_event_transactionally(db_session_factory, envelope, handler)

    assert first.status == "applied"
    assert second.status == "already_applied"
    assert second.duplicate is True
    assert second.result == first.result
    with db_session_factory() as db:
        assert count_rows(db, AuditLog) == 1
        assert count_rows(db, SyncInbox) == 1


def test_lost_acknowledgement_allows_safe_redelivery(db_session_factory: sessionmaker[Session]) -> None:
    envelope = make_envelope(aggregate_id="lost-ack")

    def handler(db: Session, _event: SyncEventEnvelope) -> dict[str, object]:
        row = AuditLog(action="lost_ack_effect", entity_type="test")
        db.add(row)
        db.flush()
        return {"committed": True, "id": row.id}

    consume_event_transactionally(db_session_factory, envelope, handler)
    redelivery = consume_event_transactionally(db_session_factory, envelope, handler)

    assert redelivery.duplicate is True
    assert redelivery.result and redelivery.result["committed"] is True
    with db_session_factory() as db:
        assert count_rows(db, AuditLog) == 1


class RecordingTransport:
    def __init__(self) -> None:
        self.event_ids: list[str] = []

    def send(self, envelope: SyncEventEnvelope) -> dict[str, object]:
        self.event_ids.append(str(envelope.event_id))
        return {"accepted": True}


def test_worker_restart_resumes_pending_state_and_checkpoint(
    db_session_factory: sessionmaker[Session],
) -> None:
    first_event = make_envelope(aggregate_id="restart-1")
    second_event = make_envelope(aggregate_id="restart-2")
    with db_session_factory() as db:
        with db.begin():
            first_row = enqueue_outbox(db, first_event)
            second_row = enqueue_outbox(db, second_event)
            first_row.created_at = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
            second_row.created_at = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)

    transport = RecordingTransport()
    first_process = LocalSyncWorker(
        db_session_factory,
        transport=transport,
        batch_size=1,
        poll_interval_seconds=0.01,
    )
    first_result = first_process.run_once()
    assert first_result.sent == 1

    with db_session_factory() as db:
        checkpoint_after_first = db.get(SyncCheckpoint, "outbound")
        assert checkpoint_after_first is not None
        first_checkpoint_event = checkpoint_after_first.last_event_id
        assert first_checkpoint_event in {str(first_event.event_id), str(second_event.event_id)}
        assert count_rows(db, SyncOutbox) == 2

    restarted_process = LocalSyncWorker(
        db_session_factory,
        transport=transport,
        batch_size=10,
        poll_interval_seconds=0.01,
    )
    second_result = restarted_process.run_once()
    assert second_result.sent == 1

    with db_session_factory() as db:
        rows = list(db.scalars(select(SyncOutbox).order_by(SyncOutbox.created_at)).all())
        assert [row.status for row in rows] == ["sent", "sent"]
        checkpoint = db.get(SyncCheckpoint, "outbound")
        assert checkpoint is not None
        assert checkpoint.last_event_id in {str(first_event.event_id), str(second_event.event_id)}
        assert checkpoint.last_event_id != first_checkpoint_event

    assert sorted(transport.event_ids) == sorted([str(first_event.event_id), str(second_event.event_id)])


def test_future_aggregate_version_waits_then_applies_in_order(
    db_session_factory: sessionmaker[Session],
) -> None:
    applied_versions: list[int] = []

    def handler(db: Session, event: SyncEventEnvelope) -> dict[str, object]:
        applied_versions.append(event.aggregate_version)
        db.add(AuditLog(action=f"version_{event.aggregate_version}", entity_type="test"))
        return {"version": event.aggregate_version}

    version_two = make_envelope(aggregate_id="ordered", aggregate_version=2)
    waiting = consume_event_transactionally(db_session_factory, version_two, handler)
    assert waiting.status == "waiting_for_prior_version"
    assert applied_versions == []

    with db_session_factory() as db:
        dead_letter = db.scalar(
            select(SyncDeadLetter).where(SyncDeadLetter.event_id == str(version_two.event_id))
        )
        assert dead_letter is not None
        assert dead_letter.status == "waiting"
        assert dead_letter.reason_code == "aggregate_version_gap"

    version_one = make_envelope(aggregate_id="ordered", aggregate_version=1)
    assert consume_event_transactionally(db_session_factory, version_one, handler).status == "applied"
    assert consume_event_transactionally(db_session_factory, version_two, handler).status == "applied"
    assert applied_versions == [1, 2]

    with db_session_factory() as db:
        dead_letter = db.scalar(
            select(SyncDeadLetter).where(SyncDeadLetter.event_id == str(version_two.event_id))
        )
        assert dead_letter is not None
        assert dead_letter.status == "resolved"


def test_dead_letter_retry_is_audited(db_session_factory: sessionmaker[Session]) -> None:
    bad_event = make_envelope(aggregate_id="bad-schema", schema_version=99)

    def should_not_run(_db: Session, _event: SyncEventEnvelope) -> dict[str, object]:
        raise AssertionError("unsupported schema event must not execute its handler")

    result = consume_event_transactionally(db_session_factory, bad_event, should_not_run)
    assert result.status == "attention_required"

    with db_session_factory() as db:
        dead_letter = db.scalar(
            select(SyncDeadLetter).where(SyncDeadLetter.event_id == str(bad_event.event_id))
        )
        assert dead_letter is not None
        dead_letter_id = dead_letter.id

    with db_session_factory() as db:
        with db.begin():
            retried = request_dead_letter_retry(db, dead_letter_id=dead_letter_id)
            assert retried.retry_count == 1
            assert retried.status == "retry_requested"

    with db_session_factory() as db:
        audit = db.scalar(
            select(AuditLog).where(AuditLog.action == "sync_dead_letter_retry_requested")
        )
        assert audit is not None
        assert audit.entity_id == dead_letter_id
        assert audit.new_value_json is not None
        assert audit.new_value_json["event_id"] == str(bad_event.event_id)


def test_retry_backoff_is_bounded_and_retry_after_is_honored(
    db_session_factory: sessionmaker[Session],
) -> None:
    assert compute_retry_delay_seconds(
        20,
        base_delay_seconds=2,
        max_delay_seconds=30,
        rng=random.Random(1),
    ) <= 30

    envelope = make_envelope(aggregate_id="retry")
    now = datetime(2026, 8, 11, tzinfo=UTC)
    with db_session_factory() as db:
        with db.begin():
            row = enqueue_outbox(db, envelope)
            delay = schedule_outbox_retry(
                row,
                error="429 rate limited",
                base_delay_seconds=2,
                max_delay_seconds=30,
                retry_after_seconds=7,
                now=now,
            )
            assert delay == 7
            assert row.next_attempt_at is not None
            assert row.status == "retry"


def test_device_identity_persists_and_secret_is_not_stored(
    db_session_factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch,
) -> None:
    identity_file = tmp_path / "device-id"
    store = FileDeviceIdentityStore(identity_file)
    first = store.load_or_create()
    second = FileDeviceIdentityStore(identity_file).load_or_create()
    assert first == second

    monkeypatch.setenv("SYNC_DEVICE_SECRET", "test-secret-that-must-not-enter-db")
    provider = EnvironmentDeviceCredentialProvider()
    assert provider.get_secret("SYNC_DEVICE_SECRET") == "test-secret-that-must-not-enter-db"

    with db_session_factory() as db:
        with db.begin():
            device = get_or_create_device_identity(
                db,
                device_id=first,
                credential_ref="SYNC_DEVICE_SECRET",
            )
            assert device.credential_ref == "SYNC_DEVICE_SECRET"

    with db_session_factory() as db:
        device = db.scalar(select(SyncDevice).where(SyncDevice.device_id == first))
        assert device is not None
        persisted_text = repr({key: value for key, value in device.__dict__.items() if key != "_sa_instance_state"})
        assert "test-secret-that-must-not-enter-db" not in persisted_text
