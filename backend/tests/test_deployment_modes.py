from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import DeploymentMode, Settings
from app.main import create_app


LOCAL_URL = "postgresql+psycopg://local_user:local_password@localhost:5432/local_hub"
CLOUD_RUNTIME_URL = (
    "postgresql+psycopg://cloud_user:cloud_password@region.pooler.supabase.com:6543/postgres"
)
CLOUD_MIGRATION_URL = (
    "postgresql+psycopg://cloud_user:cloud_password@db.project.supabase.co:5432/postgres"
)


def build_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "deployment_mode": DeploymentMode.LOCAL_HUB,
        "database_url": LOCAL_URL,
        "local_database_url": LOCAL_URL,
        "api_docs_enabled": False,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def route_paths(app) -> set[str]:
    return {route.path for route in app.routes}


def test_local_hub_registers_existing_operational_routes() -> None:
    app = create_app(build_settings())
    paths = route_paths(app)

    assert "/api/health" in paths
    assert "/api/auth/login" in paths
    assert "/api/inventory/adjustments" in paths
    assert "/api/invoices/{invoice_id}/issue" in paths
    assert "/api/purchase-orders/{purchase_order_id}/receive" in paths


def test_cloud_gateway_fails_closed_to_health_only() -> None:
    app = create_app(
        build_settings(
            deployment_mode=DeploymentMode.CLOUD_GATEWAY,
            cloud_runtime_database_url=CLOUD_RUNTIME_URL,
            cloud_migration_database_url=CLOUD_MIGRATION_URL,
        )
    )
    paths = route_paths(app)

    assert paths == {"/api/health"}

    with TestClient(app) as client:
        health = client.get("/api/health")
        inventory_write = client.post("/api/inventory/adjustments", json={})
        invoice_write = client.post("/api/invoices/1/issue", json={})

    assert health.status_code == 200
    assert health.json()["deployment_mode"] == "cloud_gateway"
    assert health.json()["database_configured"] is True
    assert inventory_write.status_code == 404
    assert invoice_write.status_code == 404


def test_cloud_gateway_requires_explicit_runtime_database() -> None:
    with pytest.raises(ValidationError, match="CLOUD_RUNTIME_DATABASE_URL is required"):
        build_settings(deployment_mode=DeploymentMode.CLOUD_GATEWAY)


def test_cloud_database_cannot_identify_local_target() -> None:
    same_target_with_different_credentials = (
        "postgresql+psycopg://other_user:other_password@localhost:5432/local_hub"
    )

    with pytest.raises(ValidationError, match="must not target the Local Hub database"):
        build_settings(cloud_migration_database_url=same_target_with_different_credentials)


def test_local_runtime_preserves_legacy_url_and_allows_explicit_override() -> None:
    legacy = Settings(database_url=LOCAL_URL, _env_file=None)
    explicit_url = "postgresql+psycopg://local_user:password@localhost:5432/explicit_local"
    explicit = Settings(
        database_url=LOCAL_URL,
        local_database_url=explicit_url,
        _env_file=None,
    )

    assert legacy.local_runtime_database_url == LOCAL_URL
    assert legacy.runtime_database_url == LOCAL_URL
    assert explicit.local_runtime_database_url == explicit_url
    assert explicit.local_migration_database_url == explicit_url


def test_cloud_migration_url_is_explicit_and_separate() -> None:
    settings = build_settings(cloud_migration_database_url=CLOUD_MIGRATION_URL)
    assert settings.required_cloud_migration_database_url == CLOUD_MIGRATION_URL

    without_cloud_migration = build_settings()
    with pytest.raises(RuntimeError, match="CLOUD_MIGRATION_DATABASE_URL is required"):
        _ = without_cloud_migration.required_cloud_migration_database_url


def test_production_disables_api_docs_by_default() -> None:
    app = create_app(build_settings(environment="production", api_docs_enabled=None))
    paths = route_paths(app)

    assert "/docs" not in paths
    assert "/redoc" not in paths
    assert "/openapi.json" not in paths


def test_cloud_alembic_history_is_independent() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    local_env = (backend_root / "alembic" / "env.py").read_text(encoding="utf-8")
    cloud_env = (backend_root / "alembic_cloud" / "env.py").read_text(encoding="utf-8")

    assert "local_migration_database_url" in local_env
    assert "alembic_version_cloud" not in local_env
    assert "required_cloud_migration_database_url" in cloud_env
    assert 'version_table="alembic_version_cloud"' in cloud_env
    assert (backend_root / "alembic_cloud.ini").exists()

