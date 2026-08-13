from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import insert, select, text, update
from sqlalchemy.orm import Session

from app.api.errors import raise_forbidden, raise_unauthorized
from app.cloud_db.schema import device_heartbeats, device_registrations
from app.db.session import get_db
from app.schemas.cloud import MenuPublicationInput, MenuPublicationRead, SafeMenuRead
from app.services.cloud_coordination import get_safe_menu, publish_menu_snapshot, resolve_published_table

router = APIRouter(prefix="/cloud", tags=["cloud-gateway"])
Database = Annotated[Session, Depends(get_db)]


def _active_device(
    db: Session,
    *,
    device_id: str,
    proof: str,
    purpose: str,
):
    row = db.execute(
        select(device_registrations).where(device_registrations.c.device_id == device_id)
    ).mappings().first()
    if row is None or row["status"] != "active" or row["revoked_at"] is not None:
        raise_unauthorized("Device authorization is not active.")
    candidate = hashlib.sha256(proof.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(candidate, row["credential_hash"]):
        raise_unauthorized("Device authorization is not active.")
    if purpose not in (row["allowed_purposes"] or []):
        raise_forbidden("Device is not authorized for this operation.")
    return row


def _require_scope(row, payload: MenuPublicationInput) -> None:
    if str(row["business_group_id"]) != payload.business_group_id:
        raise_forbidden("Publication scope is not authorized for this device.")
    if row["company_id"] is not None and str(row["company_id"]) != payload.company_id:
        raise_forbidden("Publication scope is not authorized for this device.")
    if row["branch_id"] is not None and str(row["branch_id"]) != payload.branch_id:
        raise_forbidden("Publication scope is not authorized for this device.")


@router.get("/readiness")
def readiness(db: Database, request: Request) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    return {
        "status": "ready",
        "deployment_mode": request.app.state.settings.deployment_mode.value,
        "database_ready": True,
        "cloud_schema_revision": "20260813_cloud_0001",
    }


@router.post("/devices/heartbeat")
def heartbeat(
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
    payload: dict[str, object],
) -> dict[str, object]:
    device = _active_device(
        db,
        device_id=x_device_id,
        proof=x_device_proof,
        purpose="heartbeat",
    )
    now = datetime.now(UTC)
    db.execute(
        insert(device_heartbeats).values(
            device_id=device["device_id"],
            business_group_id=device["business_group_id"],
            company_id=device["company_id"],
            branch_id=device["branch_id"],
            mode=str(payload.get("mode", "local_writer"))[:32],
            fencing_epoch=max(0, int(payload.get("fencing_epoch", 0))),
            software_version=(str(payload["software_version"])[:64] if payload.get("software_version") else None),
            event_schema_version=max(1, int(payload.get("event_schema_version", 1))),
            recorded_at=now,
        )
    )
    db.execute(
        update(device_registrations)
        .where(device_registrations.c.device_id == device["device_id"])
        .values(last_seen_at=now)
    )
    db.commit()
    return {"accepted": True, "device_id": device["device_id"], "recorded_at": now}


@router.post("/publications/menu", response_model=MenuPublicationRead)
def publish_menu(
    payload: MenuPublicationInput,
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
) -> MenuPublicationRead:
    device = _active_device(
        db,
        device_id=x_device_id,
        proof=x_device_proof,
        purpose="menu_publication",
    )
    _require_scope(device, payload)
    return publish_menu_snapshot(db, payload=payload, source_device_id=device["device_id"])


@router.get("/public/cafe/menu/{publication_id}", response_model=SafeMenuRead)
def public_menu(publication_id: UUID, db: Database) -> SafeMenuRead:
    return get_safe_menu(db, publication_id)


@router.post("/public/cafe/qr/resolve")
def public_qr_resolve(payload: dict[str, str], db: Database) -> dict[str, object]:
    value = str(payload.get("opaque_token", ""))
    return resolve_published_table(db, value)
