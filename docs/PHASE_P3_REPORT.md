# P3 Phase Report: Shared Login, Isolated Portals, And Venture User Management

## Status

- Phase: P3
- Status: Verification in progress
- Date: 2026-08-11
- Base: P2-complete `main`
- Local Alembic head: `20260811_0009` (no new local schema migration required by P3)
- Cloud Alembic history: unchanged and separate

## Scope Implemented

- Extended `/auth/me` with safe current venture name, slug, business type, company ID, branch ID, server role, and permissions.
- Added current-venture and Super Admin venture-list APIs.
- Added Super Admin-only venture user list/create/reassignment APIs.
- Enforced one company assignment for normal users and no company/branch assignment for Super Admin.
- Validated every user branch assignment against the selected company.
- Incremented `token_version` whenever a user role/company/branch/active assignment changes so old sessions fail closed.
- Added server-enforced Super Admin venture selection using `X-Venture-Id`; the selected venture is converted into the same P2 `ScopeContext` used by business queries.
- Added deterministic Cafe Partner Admin, Manager, Order Taker, Kitchen, and Analyst seed accounts.
- Added authoritative frontend portal routing from backend `server_role` and `company_business_type`.
- Added isolated `/super-admin/*`, `/retail/*`, and `/cafe/*` portal surfaces.
- Added a Super Admin venture selector that can enter Retail or Cafe with server-enforced selected scope, while the Super Admin home remains all-venture.
- Added role-aware Cafe placeholder navigation; Kitchen receives preparation-only navigation and Order Taker receives order-only navigation.
- Preserved the existing Retail application inside the `/retail` shell rather than rewriting its operational modules in P3.
- Kept `/order/:qrToken` separate from authenticated portals but intentionally disabled actual ordering until P5, HC2, and P6 gates pass.

## Verification Gate

P3 cannot merge until GitHub Actions proves:

1. PostgreSQL migrations remain at local head `20260811_0009` with cloud history separate.
2. Multi-venture demo seed and all five Cafe role seeds succeed.
3. Cafe users receive only their Cafe venture context.
4. Cafe Partner cannot discover Super Admin venture/user APIs.
5. Super Admin can select Retail, Cafe, or all-venture scope without client-side authority bypass.
6. User creation/reassignment validates company/branch ownership and invalidates old tokens.
7. P2/P1/HC1 isolation, migration, sync, and regression workflows remain green.
8. Portal static boundary checks, frontend typecheck, and production build pass.
9. Complete backend regression passes.

## P4 Boundary

P4 owns Non-GST-default behavior, registration/effective-date state, controlled Super Admin GST activation with recent step-up authentication, customer-output privacy, and non-retroactive tax-mode rules. P3 does not alter tax calculation behavior.
