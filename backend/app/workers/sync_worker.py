from __future__ import annotations

import logging
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.sync import SyncOutbox
from app.schemas.sync import SyncEventEnvelope
from app.services.sync import (
    PermanentSyncError,
    RetryableSyncError,
    dead_letter_outbox,
    envelope_from_outbox,
    get_or_create_device_identity,
    mark_outbox_sent,
    pending_outbox_batch,
    schedule_outbox_retry,
    update_checkpoint,
)

logger = logging.getLogger("local_sync_worker")


class OutboundTransport(Protocol):
    def send(self, envelope: SyncEventEnvelope) -> dict[str, object] | None:
        ...


class DeviceIdentityStore(Protocol):
    def load_or_create(self) -> str:
        ...


class FileDeviceIdentityStore:
    """Persist a non-secret device UUID locally; credentials remain external."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load_or_create(self) -> str:
        if self.path.exists():
            value = self.path.read_text(encoding="utf-8").strip()
            if value:
                return value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        value = str(uuid4())
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(value + "\n", encoding="utf-8")
        temporary.replace(self.path)
        return value


@dataclass(frozen=True)
class WorkerRunResult:
    selected: int = 0
    sent: int = 0
    retried: int = 0
    dead_lettered: int = 0


class LocalSyncWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        transport: OutboundTransport | None = None,
        batch_size: int = 50,
        base_retry_delay_seconds: float = 2.0,
        max_retry_delay_seconds: float = 300.0,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self.session_factory = session_factory
        self.transport = transport
        self.batch_size = max(1, batch_size)
        self.base_retry_delay_seconds = max(0.1, base_retry_delay_seconds)
        self.max_retry_delay_seconds = max(self.base_retry_delay_seconds, max_retry_delay_seconds)
        self.poll_interval_seconds = max(0.1, poll_interval_seconds)
        self.shutdown_event = Event()

    def request_shutdown(self) -> None:
        self.shutdown_event.set()

    def _select_batch(self) -> list[SyncEventEnvelope]:
        with self.session_factory() as db:
            rows = pending_outbox_batch(db, limit=self.batch_size)
            return [envelope_from_outbox(row) for row in rows]

    def _record_success(self, envelope: SyncEventEnvelope) -> None:
        with self.session_factory() as db:
            with db.begin():
                row = db.get(SyncOutbox, str(envelope.event_id))
                if row is None or row.status == "sent":
                    return
                mark_outbox_sent(row)
                update_checkpoint(
                    db,
                    name="outbound",
                    cursor=str(envelope.recorded_at.timestamp()),
                    last_event_id=str(envelope.event_id),
                )

    def _record_retry(self, envelope: SyncEventEnvelope, exc: RetryableSyncError) -> None:
        with self.session_factory() as db:
            with db.begin():
                row = db.get(SyncOutbox, str(envelope.event_id))
                if row is None or row.status == "sent":
                    return
                schedule_outbox_retry(
                    row,
                    error=str(exc),
                    base_delay_seconds=self.base_retry_delay_seconds,
                    max_delay_seconds=self.max_retry_delay_seconds,
                    retry_after_seconds=exc.retry_after_seconds,
                )

    def _record_permanent_failure(self, envelope: SyncEventEnvelope, exc: Exception) -> None:
        with self.session_factory() as db:
            with db.begin():
                row = db.get(SyncOutbox, str(envelope.event_id))
                if row is None or row.status == "sent":
                    return
                dead_letter_outbox(
                    db,
                    row,
                    reason_code="permanent_transport_failure",
                    diagnostic=str(exc),
                )

    def run_once(self) -> WorkerRunResult:
        if self.transport is None:
            return WorkerRunResult()

        envelopes = self._select_batch()
        sent = retried = dead_lettered = 0
        for envelope in envelopes:
            if self.shutdown_event.is_set():
                break
            try:
                self.transport.send(envelope)
            except RetryableSyncError as exc:
                self._record_retry(envelope, exc)
                retried += 1
            except PermanentSyncError as exc:
                self._record_permanent_failure(envelope, exc)
                dead_lettered += 1
            else:
                self._record_success(envelope)
                sent += 1

        return WorkerRunResult(
            selected=len(envelopes),
            sent=sent,
            retried=retried,
            dead_lettered=dead_lettered,
        )

    def run_forever(self) -> None:
        while not self.shutdown_event.is_set():
            result = self.run_once()
            if result.selected:
                logger.info(
                    "sync batch selected=%s sent=%s retried=%s dead_lettered=%s",
                    result.selected,
                    result.sent,
                    result.retried,
                    result.dead_lettered,
                )
            self.shutdown_event.wait(self.poll_interval_seconds)


def install_signal_handlers(worker: LocalSyncWorker) -> None:
    def _request_shutdown(signum: int, _frame: object) -> None:
        logger.info("received signal %s; requesting graceful sync worker shutdown", signum)
        worker.request_shutdown()

    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), _request_shutdown)


def bootstrap_device(session_factory: sessionmaker[Session]) -> str:
    if settings.sync_device_id:
        device_id = settings.sync_device_id
    else:
        identity_store = FileDeviceIdentityStore(Path(settings.sync_device_id_file))
        device_id = identity_store.load_or_create()

    with session_factory() as db:
        with db.begin():
            get_or_create_device_identity(
                db,
                device_id=device_id,
                credential_ref=settings.sync_device_credential_env,
            )
    return device_id


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    device_id = bootstrap_device(SessionLocal)
    logger.info("Local sync worker starting for device %s", device_id)
    worker = LocalSyncWorker(
        SessionLocal,
        transport=None,
        batch_size=settings.sync_batch_size,
        base_retry_delay_seconds=settings.sync_retry_base_delay_seconds,
        max_retry_delay_seconds=settings.sync_max_retry_delay_seconds,
        poll_interval_seconds=settings.sync_poll_interval_seconds,
    )
    install_signal_handlers(worker)
    worker.run_forever()


if __name__ == "__main__":
    main()
