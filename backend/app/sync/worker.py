from __future__ import annotations

import logging
import signal
import threading
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.sync.device import DeviceIdentityStore
from app.sync.service import BatchResult, SyncHandler, SyncTransport, process_inbox_batch, process_outbox_batch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerCycleResult:
    inbound: BatchResult
    outbound: BatchResult


class LocalSyncWorker:
    """Small durable worker. Queue state lives in PostgreSQL; process memory is disposable."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] = SessionLocal,
        configured_settings: Settings = settings,
        handlers: dict[str, SyncHandler] | None = None,
        transport: SyncTransport | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = configured_settings
        self.handlers = handlers or {}
        self.transport = transport
        self.device_store = DeviceIdentityStore(configured_settings)
        self._stop_event = threading.Event()
        self.device_id: str | None = None

    def initialize(self) -> str:
        with self.session_factory() as db:
            with db.begin():
                identity = self.device_store.get_or_create(db)
                self.device_id = identity.device_id
        logger.info("Local sync worker initialized for device %s", self.device_id)
        return self.device_id

    def run_once(self) -> WorkerCycleResult:
        if self.device_id is None:
            self.initialize()

        inbound = process_inbox_batch(
            self.session_factory,
            self.handlers,
            limit=self.settings.sync_batch_size,
            max_attempts=self.settings.sync_max_attempts,
            base_delay_seconds=self.settings.sync_base_retry_delay_seconds,
            max_delay_seconds=self.settings.sync_max_retry_delay_seconds,
            jitter_ratio=self.settings.sync_retry_jitter_ratio,
        )

        if self.transport is None:
            # HC1 intentionally has no cloud transport. Pending outbox rows stay durable and untouched.
            outbound = BatchResult()
        else:
            outbound = process_outbox_batch(
                self.session_factory,
                self.transport,
                limit=self.settings.sync_batch_size,
                max_attempts=self.settings.sync_max_attempts,
                base_delay_seconds=self.settings.sync_base_retry_delay_seconds,
                max_delay_seconds=self.settings.sync_max_retry_delay_seconds,
                jitter_ratio=self.settings.sync_retry_jitter_ratio,
            )

        if self.device_id is not None:
            with self.session_factory() as db:
                with db.begin():
                    self.device_store.touch(db, self.device_id)

        return WorkerCycleResult(inbound=inbound, outbound=outbound)

    def stop(self) -> None:
        self._stop_event.set()

    def run_forever(self) -> None:
        self.initialize()
        logger.info("Local sync worker started; durable queues will resume after process restarts.")
        while not self._stop_event.is_set():
            try:
                cycle = self.run_once()
                if cycle.inbound.attempted or cycle.outbound.attempted:
                    logger.info(
                        "Sync cycle inbound=%s outbound=%s",
                        cycle.inbound,
                        cycle.outbound,
                    )
            except Exception:
                # Database/network outages must not destroy the supervisor process or queue state.
                logger.exception("Synchronization cycle failed; committed queue state remains durable.")
            self._stop_event.wait(self.settings.sync_poll_interval_seconds)
        logger.info("Local sync worker stopped gracefully.")


def _install_signal_handlers(worker: LocalSyncWorker) -> None:
    def request_shutdown(signum: int, _frame: object) -> None:
        logger.info("Received signal %s; requesting graceful worker shutdown.", signum)
        worker.stop()

    for signal_name in ("SIGINT", "SIGTERM"):
        signal_value = getattr(signal, signal_name, None)
        if signal_value is not None:
            signal.signal(signal_value, request_shutdown)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    worker = LocalSyncWorker()
    _install_signal_handlers(worker)
    worker.run_forever()


if __name__ == "__main__":
    main()
