# HC1 Local Synchronization Worker

## Purpose

HC1 adds the durable Local Hub synchronization substrate. It does **not** enable Supabase QR order intake. The worker is intentionally transport-disabled until HC2 supplies an approved cloud transport and HC3 supplies cloud order import.

Local PostgreSQL remains authoritative. Queue state, inbox receipts, aggregate versions, dead letters, device identity metadata, and checkpoints are durable database records. No normal recovery step depends on process memory.

## Durable State

HC1 adds these local tables:

- `sync_devices`: stable installation identity and credential reference only; no credential secret.
- `sync_outbox`: events written in the same SQL transaction as their originating domain change.
- `sync_inbox`: committed event receipts used for idempotent redelivery.
- `sync_checkpoints`: durable progress markers.
- `sync_aggregate_versions`: monotonic per-aggregate apply version.
- `sync_dead_letters`: visible permanent failures and version gaps.

The event envelope is versioned and carries scope, aggregate identity/version, correlation/causation IDs, timestamps, and a minimal payload.

## Transaction Rules

1. A domain write and its required outbox event must share one SQLAlchemy transaction.
2. `enqueue_outbox()` flushes but never commits.
3. A consumer checks the durable inbox before applying a handler.
4. The business effect, inbox receipt, and aggregate-version advance share one transaction.
5. A lost acknowledgment therefore causes a safe retry: the existing receipt is returned and the business effect is not repeated.
6. Future aggregate versions are held visibly until missing earlier versions are applied.
7. Unknown schema versions and permanent failures remain durable in `sync_dead_letters`.
8. Manual dead-letter retry requests are audit logged.

## Device Identity And Credentials

`SYNC_DEVICE_ID` may be supplied explicitly. When it is blank, the Local Hub creates a non-secret UUID in `SYNC_DEVICE_ID_FILE` (default `.sync-device-id`). That file is gitignored and survives worker restarts.

`SYNC_DEVICE_CREDENTIAL_ENV` stores only the **name** of the environment variable that contains the secret. Default:

```text
SYNC_DEVICE_CREDENTIAL_ENV=SYNC_DEVICE_SECRET
```

The secret itself is read only from the process environment or a future OS secret provider. It is not written to the local sync tables, queue payloads, logs, or Git.

## Development Startup And Restart

Prepare the backend and apply the local migration first:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
cd ..
```

Run the development crash-restart wrapper:

```powershell
.\scripts\run_sync_worker_dev.ps1
```

The wrapper restarts the worker after a non-zero crash. A graceful Ctrl+C exits cleanly instead of entering a restart loop.

The worker currently starts with no cloud transport in HC1. That is deliberate. It may persist local outbox work, but it must not send QR/order traffic to Supabase until the later cloud phases open their gates.

## Production Automatic Restart

Production must run PostgreSQL, the Local Hub API, the sync worker, local frontend, and backup jobs under managed startup/restart policies. On Windows, use a service manager such as NSSM, WinSW, or an equivalent enterprise service wrapper.

Example NSSM shape, run from an elevated shell after installing NSSM and preparing the backend virtual environment:

```powershell
nssm install KalpvrikSyncWorker "C:\path\to\repo\backend\.venv\Scripts\python.exe" "-m app.workers.sync_worker"
nssm set KalpvrikSyncWorker AppDirectory "C:\path\to\repo\backend"
nssm set KalpvrikSyncWorker Start SERVICE_AUTO_START
nssm set KalpvrikSyncWorker AppExit Default Restart
nssm start KalpvrikSyncWorker
```

Do not put device secrets in the command line. Supply them through protected service environment configuration or an OS secret mechanism.

Required startup dependency order remains:

1. PostgreSQL starts and passes a database health check.
2. Approved local migrations run as a controlled deployment step.
3. Local Hub API starts.
4. Sync device identity and checkpoints are loaded.
5. Sync worker starts and drains only work that is due.
6. Local frontend and backup monitoring remain available.

## Retry Behavior

HC1 provides bounded exponential backoff with jitter and a configurable maximum delay. A supplied `Retry-After` delay takes precedence, still capped by the configured maximum. Permanent failures do not retry forever and move to visible attention/dead-letter state.

Configuration:

```text
SYNC_BATCH_SIZE=50
SYNC_POLL_INTERVAL_SECONDS=5
SYNC_RETRY_BASE_DELAY_SECONDS=2
SYNC_MAX_RETRY_DELAY_SECONDS=300
```

## Crash Semantics

- Crash before local commit: neither the domain change nor its outbox event exists.
- Crash after local commit: the outbox event remains pending and is selected after restart.
- Crash after remote send but before local sent/checkpoint commit: the event is sent again. The remote consumer must use the same `event_id`; inbox/idempotency semantics prevent duplicate business effects.
- Crash during inbound processing before commit: no receipt or business effect is acknowledged.
- Crash after inbound commit but before response delivery: redelivery returns the durable prior receipt.

## HC1 Exit Gate

No customer QR order may be accepted through Supabase in HC1. The local idempotent consumer and crash-recovery tests must pass first. Cloud schema/publication is HC2; cloud order intake and local convergence are later gated phases.
