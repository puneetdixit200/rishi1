# P1 Phase Report: Ownership, Venture, And Data-Scope Schema

## Status

- Phase: P1
- Status: Verification in progress
- Date: 2026-08-11
- Base: HC1-complete `main` at `198db73607e4dbb2c348285ad5597db20b4dc10c`
- Local Alembic revision: `20260811_0008`
- Cloud Alembic history: unchanged and separate

## Scope Implemented

- Added `BusinessGroup -> Company -> Branch` ownership hierarchy.
- Added Retail/Cafe venture type, stable slug, demo flag, and ownership group to companies.
- Added business-group/company scope and token-version/security fields to users.
- Added roles: Super Admin, Venture Admin, Store Manager, Staff, Order Taker, Kitchen, Analyst.
- Added company scope to operational/confidential roots required by the multi-venture TRD.
- Converted branch, category, supplier, SKU, barcode, sale number, PO number, customer identity, and invoice number uniqueness to company-aware constraints.
- Added expand/backfill/validate PostgreSQL migration preserving legacy IDs, financial totals, and business identifiers.
- Promoted the legacy global Admin to Super Admin during migration while temporarily preserving old global-admin capabilities until P2 installs ScopeContext authorization.
- Added a multi-venture-safe development seed entry point that creates one Business Group, one Retail venture, and a minimal Cafe venture/branch before generating existing Retail demo data.
- Preserved HC1 sync tables and separate cloud migration history.

## Verification Gates

The P1 GitHub Actions workflow must pass all of the following before merge:

1. Upgrade a PostgreSQL 16 database only through HC1 (`20260811_0007`).
2. Insert a legacy Retail fixture with known sale/invoice identifiers and totals.
3. Apply P1 migration `20260811_0008`.
4. Verify the legacy identifiers, IDs, and totals are unchanged and all rows are company-scoped.
5. Verify local/cloud Alembic heads remain separated.
6. Run P1 schema, migration-contract, scope-constraint, HC1, deployment, and Retail regression tests.
7. Run the multi-venture development reseed against PostgreSQL.
8. Run the complete backend test suite and backend compile check.
9. Run frontend dependency install, typecheck, and production build.

## P2 Boundary

P1 establishes durable ownership and database scope but does not claim route-level cross-venture isolation. P2 remains mandatory and will replace branch-only authorization with shared `ScopeContext`, enforce company/branch predicates on every service/query, add token-version revocation checks, and add release-blocking Retail/Cafe isolation tests.
