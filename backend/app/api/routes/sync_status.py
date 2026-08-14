from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_scope_context, require_roles
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import (
    SyncDeadLetter,
    SyncDeadLetterStatus,
    SyncDevice,
    SyncInbox,
    SyncInboxStatus,
    SyncOutbox,
    SyncOutboxStatus,
    User,
    UserRole,
)
from app.schemas.hc3 import SyncStatusRead

router = APIRouter(prefix="/sync", tags=["sync-status"])
Database = Annotated[Session, Depends(get_db)]
Scope = Annotated[ScopeContext, Depends(get_scope_context)]
SyncViewer = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ANALYST)),
]


def _scope_filters(model, scope: ScopeContext):
    filters = [model.business_group_id == str(scope.business_group_id)]
    if not scope.all_companies and scope.company_id is not None:
        filters.append(model.company_id == str(scope.company_id))
    if scope.branch_ids:
        filters.append(model.branch_id.in_([str(value) for value in scope.branch_ids]))
    return filters


def _dead_letter_in_scope(row: SyncDeadLetter, scope: ScopeContext) -> bool:
    envelope = row.event_envelope_json or {}
    if str(envelope.get("business_group_id")) != str(scope.business_group_id):
        return False
    if not scope.all_companies and scope.company_id is not None:
        if str(envelope.get("company_id")) != str(scope.company_id):
            return False
    if scope.branch_ids and str(envelope.get("branch_id")) not in {str(value) for value in scope.branch_ids}:
        return False
    return True


@router.get("/status", response_model=SyncStatusRead)
def sync_status(
    db: Database,
    scope: Scope,
    _viewer: SyncViewer,
) -> SyncStatusRead:
    inbox_filters = _scope_filters(SyncInbox, scope)
    outbox_filters = _scope_filters(SyncOutbox, scope)
    pending_inbox = db.scalar(
        select(func.count(SyncInbox.id)).where(
            *inbox_filters,
            SyncInbox.status.in_([SyncInboxStatus.PENDING, SyncInboxStatus.RETRY, SyncInboxStatus.BLOCKED]),
        )
    ) or 0
    pending_outbox = db.scalar(
        select(func.count(SyncOutbox.id)).where(
            *outbox_filters,
            SyncOutbox.status.in_([SyncOutboxStatus.PENDING, SyncOutboxStatus.RETRY]),
        )
    ) or 0
    oldest_inbox = db.scalar(
        select(func.min(SyncInbox.created_at)).where(
            *inbox_filters,
            SyncInbox.status.in_([SyncInboxStatus.PENDING, SyncInboxStatus.RETRY, SyncInboxStatus.BLOCKED]),
        )
    )
    oldest_outbox = db.scalar(
        select(func.min(SyncOutbox.created_at)).where(
            *outbox_filters,
            SyncOutbox.status.in_([SyncOutboxStatus.PENDING, SyncOutboxStatus.RETRY]),
        )
    )
    oldest = min([value for value in (oldest_inbox, oldest_outbox) if value is not None], default=None)
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    last_inbound = db.scalar(select(func.max(SyncInbox.processed_at)).where(*inbox_filters))
    last_outbound = db.scalar(select(func.max(SyncOutbox.sent_at)).where(*outbox_filters))
    dead_letters = [
        row
        for row in db.scalars(
            select(SyncDeadLetter).where(
                SyncDeadLetter.status.in_([SyncDeadLetterStatus.OPEN, SyncDeadLetterStatus.RETRY_PENDING])
            )
        ).all()
        if _dead_letter_in_scope(row, scope)
    ]
    device_last_seen = db.scalar(select(func.max(SyncDevice.last_seen_at)))
    age = None if oldest is None else max(0, int((datetime.now(UTC) - oldest).total_seconds()))
    return SyncStatusRead(
        company_id=None if scope.all_companies else scope.company_id,
        branch_ids=list(scope.branch_ids),
        pending_inbox=int(pending_inbox),
        pending_outbox=int(pending_outbox),
        dead_letters=len(dead_letters),
        oldest_pending_age_seconds=age,
        last_inbound_sync_at=last_inbound,
        last_outbound_sync_at=last_outbound,
        local_device_last_seen_at=device_last_seen,
    )
