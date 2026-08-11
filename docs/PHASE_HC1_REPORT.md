# HC1 Phase Report: Durable Local Synchronization Foundation

## Status

- Phase: HC1
- Status: Verification in progress
- Date: 2026-08-11
- Base: HC0 commit `70068c6`
- Local Alembic revision: `20260811_0007`
- Cloud Alembic history: unchanged and separate

## Scope Implemented

HC1 establishes the crash-safe Local Business Hub synchronization substrate. It intentionally does not implement Supabase QR order acceptance, cloud business tables, Cafe order intake, writer leases, continuity financial processing, or HC2+ behavior.

Implemented:

- durable local `sync_devices`, `sync_outbox`, `sync_inbox`, `sync_checkpoints`, `sync_dead_letters`, and `sync_aggregate_versions` tables;
- versioned event envelopes with event, correlation, causation, scope, aggregate, idempotency, and UTC timestamp metadata;
- transactional outbox helper that never commits independently;
- durable inbox receipts and idempotent redelivery behavior;
- per-aggregate monotonic version checks with visible blocked/dead-letter states;
- persisted inbound/outbound checkpoints;
- bounded batch processing;
- exponential retry with jitter, maximum delay, and Retry-After support;
- graceful worker shutdown and disposable process-memory design;
- persistent device identity with credential-reference storage only;
- development restart supervisor and documented production service policy;
- audited dead-letter retry using the existing audit ledger;
- release-blocking HC1 and HC0 regression tests.

## Failure And Recovery Evidence

Automated tests cover:

1. Domain change and outbox event commit together.
2. Domain rollback removes the outbox row with the domain change.
3. Duplicate delivery creates exactly one business effect.
4. Lost acknowledgment followed by redelivery returns the durable prior receipt.
5. Worker recreation against the same database resumes pending inbox work and advances the persisted checkpoint.
6. Future aggregate versions remain visibly blocked until the missing version commits.
7. Dead-letter retry is durable and writes an audit record.
8. Unknown future event schema versions remain durable and visible.
9. Raw device secret values are not persisted.
10. Retry delay is bounded and honors explicit Retry-After values.

## Queue And Checkpoint State In Tests

The HC1 tests use isolated database fixtures. Each test begins with no synchronization rows and tears down its database after verification, so no persistent CI queue, dead-letter, or reconciliation state remains after the suite. Restart tests explicitly verify checkpoint persistence across new worker instances using the same test database.

## Security Boundary

- Local PostgreSQL remains the operational system of record.
- No raw device secret is stored in PostgreSQL or committed environment templates.
- No Supabase service-role key or cloud credential was added.
- No public/cloud QR write route was added.
- HC0 cloud fail-closed route registration remains part of the required regression suite.
- RLS is not applicable in HC1 because the Supabase coordination schema is an HC2 deliverable.

## Verification

GitHub Actions runs HC1 against PostgreSQL 16 and also performs frontend regression verification.

The first verification run proved:

- PostgreSQL service startup: passed;
- local Alembic upgrade through `20260811_0007`: passed;
- local migration head: `20260811_0007`;
- independent cloud migration-head check: passed;
- frontend dependency install, typecheck, and production build: passed;
- HC1 + deployment targeted suite: 17 passed, 1 failed because workflow-level `LOCAL_DATABASE_URL` polluted an HC0 settings-isolation test.

The failing test was a CI environment-scoping issue, not an application failure. The workflow was corrected so PostgreSQL connection variables are scoped only to Alembic steps. A clean rerun is required before HC1 is marked complete.

## Exit Gate

**Closed until the clean verification rerun passes.** No QR order may be accepted through Supabase while this report remains in verification status.

## Known Deferred Work

- Supabase coordination schema and RLS: HC2.
- Vercel cloud sync/QR gateway: HC2.
- Cloud order intake and local convergence: HC3.
- Heartbeats, writer leases, fencing, automatic continuity reconciliation: HC4.
- Venture/Cafe feature work continues according to the integrated dependency order rather than being pulled into HC1.
