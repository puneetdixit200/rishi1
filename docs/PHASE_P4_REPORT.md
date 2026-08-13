# P4 Phase Report: GST-Ready, Non-GST-Default Configuration

## Status

- Phase: P4
- Status: Verification in progress
- Date: 2026-08-13
- Base: verified P3 `main`
- Local Alembic target: `20260813_0010`
- Cloud Alembic history: unchanged and separate

## Implemented Scope

- Added venture tax registration state, effective date, customer-detail privacy mode, B2B GST flag, and GST-report customer flag.
- Changed current operational defaults to unregistered / Non-GST for Retail and Cafe.
- Preserved HSN/SAC and reference tax metadata internally while marking demo GST registrations inactive/reference-only.
- Added Non-GST invoice sequences/templates for active ventures without creating a separate Cafe billing engine.
- Added server-derived tax-operation API and Super Admin-only settings/activation controls.
- Added recent step-up, registration, GSTIN format, legal identity, state, effective-date, invoice-sequence, invoice-template, and explicit professional-review prerequisites for GST activation.
- Added effective-date enforcement so a client cannot force GST before activation or force Non-GST after the effective date.
- Protected the legacy business-profile endpoint from changing tax mode outside the guarded workflow.
- Added owner-only combined BusinessGroup turnover monitoring explicitly labelled as a review aid, not legal advice.
- Added canonical P4 development seed wrapper that leaves both ventures operating Non-GST.

## Verification Gate

P4 may merge only after:

1. PostgreSQL migration and separate cloud migration history checks pass.
2. Canonical P4 seed succeeds for Retail and Cafe.
3. Required P4 tests prove Non-GST zero tax/privacy, forced-GST denial, guarded activation, effective dating, historical immutability, and owner-only turnover.
4. Existing business-settings, invoice-tax, invoice, POS, auth, venture-isolation, HC1 sync, and deployment-mode tests pass.
5. Complete backend regression and compile pass.
6. Frontend portal boundary check, typecheck, and production build pass.

## Boundaries

- No hard-coded GST registration threshold or automatic legal determination.
- No retroactive conversion of historical Non-GST invoices.
- No live GST portal, e-invoice, or e-way integration.
- P5 owns Cafe menu, tables, QR tokens, and table sessions. P4 does not accept public customer orders.
