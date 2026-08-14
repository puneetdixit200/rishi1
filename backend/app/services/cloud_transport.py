from __future__ import annotations

import httpx

from app.schemas.cloud import MenuPublicationInput, MenuPublicationRead
from app.schemas.hc3 import CloudCommandBatch, CloudSyncPushRead
from app.schemas.sync import EventEnvelope
from app.sync.service import PermanentSyncError, RetryableSyncError, parse_retry_after


def _raise_sync_http(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    retry_after = parse_retry_after(response.headers.get("Retry-After"))
    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableSyncError(
            f"Cloud gateway returned HTTP {response.status_code}.",
            code=f"cloud_http_{response.status_code}",
            retry_after_seconds=retry_after,
        )
    raise PermanentSyncError(
        f"Cloud gateway rejected synchronization with HTTP {response.status_code}.",
        code=f"cloud_http_{response.status_code}",
    )


def _device_headers(device_id: str, installation_proof: str) -> dict[str, str]:
    return {
        "X-Device-Id": device_id,
        "X-Device-Proof": installation_proof,
        "Content-Type": "application/json",
    }


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
        headers=_device_headers(device_id, installation_proof),
        json=payload.model_dump(mode="json"),
        timeout=timeout_seconds,
    )
    _raise_sync_http(response)
    return MenuPublicationRead.model_validate(response.json())


def pull_cloud_commands(
    *,
    gateway_base_url: str,
    device_id: str,
    installation_proof: str,
    limit: int,
    timeout_seconds: float = 15.0,
) -> list[EventEnvelope]:
    url = f"{gateway_base_url.rstrip('/')}/api/cloud/sync/commands"
    try:
        response = httpx.get(
            url,
            headers=_device_headers(device_id, installation_proof),
            params={"limit": max(1, min(limit, 200))},
            timeout=timeout_seconds,
        )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise RetryableSyncError(str(exc), code="cloud_unreachable") from exc
    _raise_sync_http(response)
    return CloudCommandBatch.model_validate(response.json()).events


class CloudGatewaySyncTransport:
    def __init__(
        self,
        *,
        gateway_base_url: str,
        device_id: str,
        installation_proof: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.gateway_base_url = gateway_base_url.rstrip("/")
        self.device_id = device_id
        self.installation_proof = installation_proof
        self.timeout_seconds = timeout_seconds

    def send(self, event: EventEnvelope) -> dict[str, object]:
        url = f"{self.gateway_base_url}/api/cloud/sync/events"
        try:
            response = httpx.post(
                url,
                headers=_device_headers(self.device_id, self.installation_proof),
                json=event.model_dump(mode="json"),
                timeout=self.timeout_seconds,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise RetryableSyncError(str(exc), code="cloud_unreachable") from exc
        _raise_sync_http(response)
        return CloudSyncPushRead.model_validate(response.json()).model_dump(mode="json")
