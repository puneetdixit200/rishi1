# P2 Phase Report: Venture Scope Enforcement, Roles, And Security Context

## Status

- Phase: P2
- Status: Verification in progress
- Date: 2026-08-11
- Base: P1-complete `main`
- Local Alembic revision: `20260811_0009`
- Cloud Alembic history: unchanged and separate

## Scope Implemented

- Added server-derived `ScopeContext` with business-group, company, branch, role, and permission data.
- Added request-bound `ScopedSession` enforcement for company and branch ORM reads.
- Added write-time company/branch checks and same-company foreign-object validation.
- Added scope coverage for inventory batches, serial numbers, and product price history.
- Added persistent `token_version` access-token claims and database validation so role/company/logout revocation survives process restarts and multiple API instances.
- Added persistent step-up authentication timestamp and `/auth/step-up` foundation.
- Added active business-group/company validation during login and authenticated requests.
- Added non-disclosing 404 handling for cross-company write/reference violations.
- Made audit writes company-scope aware.
- Extended frontend auth typing for business group, company, branch, permissions, and expanded roles without altering the legacy portal structure before P3.

## Required Security Tests

P2 adds release-blocking tests for:

- Cafe Admin receiving only Cafe company scope from `/auth/me`.
- Existing access token rejection after persisted `token_version` changes.
- Logout incrementing token version and invalidating the current token.
- Deactivated company login failing closed.
- Step-up authentication success/failure and persisted timestamp.
- Cafe Admin inability to list/fetch Retail products, categories, suppliers, branches, inventory, customers, sales, invoices, purchase orders, forecasts, business profile, dashboard counts, exports, or AI sessions.
- Retail Admin inability to discover Cafe rows.
- Branch user inability to list a different same-company branch.
- Cross-company category/supplier IDs failing without disclosing the Retail object.
- Super Admin remaining the only global scope.

## Verification Gate

The P2 GitHub Actions workflow must pass PostgreSQL migration through `20260811_0009`, migration-history separation, P2 security tests, HC1 regression tests, the ownership-aware demo reseed, complete backend regression, backend compile, frontend typecheck, and frontend production build before P2 may merge.

## P3 Boundary

P2 deliberately does not build the separate Super Admin, Retail, and Cafe portal shells. P3 owns portal routing, venture labels/selectors, venture user management, and Cafe staff seed accounts after this backend isolation gate is proven.
