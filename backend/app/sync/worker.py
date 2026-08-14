from __future__ import annotations

import logging
import signal
import threading
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.services.cloud_transport import CloudGatewaySyncTransport, pull_cloud_commands
from app.sync.cafe_orders import make_cloud_order_handler
from app.sync.device import DeviceIdentityStore, SettingsCredentialStore
from app.sync.service import (
    BatchResult,
    SyncHandler,
    SyncProcessingError,
    SyncTransport,
    process_inbox_batch,
    process_outbox_batch,
    stage_inbox_event,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerCycleResult:
    inbound: BatchResult
    outbound: BatchResult


class LocalSyncWorker:
    """Durable Local Hub worker. PostgreSQL owns all queue/checkpoint state."""

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
        self.credential_store = SettingsCredentialStore(configured_settings)
        self._command_puller: Callable[[int], list] | None = None
        self._stop_event = threading.Event()
        self.device_id: str | None = None

    def initialize(self) -> str:
        with self.session_factory() as db:
            with db.begin():
                identity = self.device_store.get_or_create(db)
                self.device_id = identity.device_id

        assert self.device_id is not None
        self.handlers.setdefault("cafe.order.submitted", make_cloud_order_handler(self.device_id))
        gateway = (self.settings.cloud_gateway_base_url or "").strip()
        proof = self.credential_store.get_secret()
        if gateway and proof:
            if self.transport is None:
                self.transport = CloudGatewaySyncTransport(
                    gateway_base_url=gateway,
                    device_id=self.device_id,
                    installation_proof=proof,
                )
            if self._command_puller is None:
                self._command_puller = lambda limit: pull_cloud_commands(
                    gateway_base_url=gateway,
                    device_id=self.device_id or "",
                    installation_proof=proof,
                    limit=limit,
                )
        logger.info("Local sync worker initialized for device %s", self.device_id)
        return self.device_id

    def _pull_and_stage_commands(self) -> int:
        if self._command_puller is None:
            return 0
        try:
            events = self._command_puller(self.settings.sync_batch_size)
        except SyncProcessingError as exc:
            logger.warning("Cloud command pull deferred: %s", exc)
            return 0
        if not events:
            return 0
        with self.session_factory() as db:
            with db.begin():
                for event in events:
                    stage_inbox_event(db, event)
        return len(events)

    def run_once(self) -> WorkerCycleResult:
        if self.device_id is None:
            self.initialize()

        pulled = self._pull_and_stage_commands()
        if pulled:
            logger.info("Staged %s cloud synchronization command(s).", pulled)

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
            # Without cloud configuration, durable local queues remain untouched.
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
