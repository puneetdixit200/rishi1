from __future__ import annotations

import httpx

from app.schemas.cloud import MenuPublicationInput, MenuPublicationRead


def push_menu_publication(
    *,
    gateway_base_url: str,
    device_id: str,
    installation_proof: str,
    payload: MenuPublicationInput,
    timeout_seconds: float = 15.0,
) -> MenuPublicationRead:
    url = f"{gateway_base_url.rstrip('/')}/api/cloud/publications/menu"
    response = httpx.post(
        url,
        headers={
            "X-Device-Id": device_id,
            "X-Device-Proof": installation_proof,
            "Content-Type": "application/json",
        },
        json=payload.model_dump(mode="json"),
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return MenuPublicationRead.model_validate(response.json())
