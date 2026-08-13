# P5 Phase Report: Cafe Menu, Tables, And Secure QR Foundation

## Status

- Phase: P5
- Status: Verification in progress
- Date: 2026-08-13
- Base: verified P4 `main`
- Local Alembic target: `20260813_0011`
- Cloud Alembic history: unchanged and separate

## Implemented Scope

- Added company/branch-scoped Cafe menu categories and menu items with optional same-company product linkage, customer display prices, preparation area, availability, activation, display order, and optimistic versioning.
- Added company/branch-scoped Cafe tables with branch-unique table codes, capacity/area metadata, activation, and optimistic versioning.
- Added hash-only table QR credentials with 256-bit secret randomness, opaque public reference, non-secret prefix, expiry, revocation, last-used tracking, creator, and audit trail.
- Raw QR secrets are returned only by generation/rotation and are never written to database rows or audit payloads.
- Added authenticated local SVG QR rendering so table credentials are not sent to third-party QR services.
- Added table sessions with opaque public IDs, dine-in/takeaway/counter type, required lifecycle states, actor/timestamps, and optimistic versioning.
- Added a PostgreSQL partial unique index plus service conflict handling to guarantee at most one active session for a table.
- Added Cafe menu/category/item, table, QR rotation/revocation/render/status, and table-session APIs in Local Hub mode only.
- Added a public QR resolver that validates the credential and returns only Cafe/table display identity; it explicitly does not accept an order or create a table session.
- Extended P2 company/branch scope enforcement and same-company foreign-object checks to all P5 Cafe records.
- Added deterministic P5 development seed: six required categories, 24 menu items, eight Cafe-owned product links, and 12 Cafe tables. QR secrets are intentionally not seeded or logged.
- Added Cafe Menu Management and Tables/QR frontend pages with role-aware administration, availability controls, session controls, one-time QR preview/print, and explicit ordering-disabled messaging.

## Security Invariants

- Retail users cannot access Cafe administration APIs.
- Non-admin Cafe roles cannot change menu/table/QR administration.
- Linked products must belong to the same Cafe Company.
- QR secrets use 32 cryptographically random bytes (256 bits) and only SHA-256 hashes are persisted.
- `token_hash` is never part of a response schema.
- Rotation revokes previous active table QR credentials.
- Revoked, expired, malformed, cross-table, and mismatched credentials fail closed.
- Raw QR credentials exist only in one-time generation response/UI state and are cleared when the preview is dismissed.
- Customer-facing QR resolution does not open a session, accept items, or create financial records.
- Database-level partial uniqueness protects against concurrent duplicate active table sessions.

## Verification Gate

P5 may merge only after:

1. PostgreSQL migration reaches `20260813_0011` and cloud history remains separate.
2. Canonical P5 seed succeeds without generating QR secrets.
3. Required Cafe menu/table/QR/session security tests pass.
4. PostgreSQL concurrent-session probe proves exactly one active session can commit.
5. Cross-venture, auth, Retail inventory/catalog, HC1 sync, and deployment-mode regressions pass.
6. Complete backend regression and compile pass.
7. Frontend portal-boundary verifier, typecheck, and production build pass.
8. Inherited HC1/P1/P2/P3/P4 workflows remain green on the exact P5 head.

## Boundary To HC2 / Later Ordering

P5 is administration and credential foundation only. It does not publish Cafe snapshots to Supabase and does not accept customer order submissions. HC2 owns cloud coordination schema, RLS, publication, and cloud gateway isolation. Later ordering phases own customer order lifecycle.
