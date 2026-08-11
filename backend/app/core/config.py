import enum
from functools import lru_cache

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class DeploymentMode(str, enum.Enum):
    LOCAL_HUB = "local_hub"
    CLOUD_GATEWAY = "cloud_gateway"


def database_target_identity(database_url: str) -> tuple[str | None, int | None, str | None]:
    """Return a password-free identity used only for target-boundary checks."""
    url = make_url(database_url)
    return (url.host, url.port, url.database)


class Settings(BaseSettings):
    app_name: str = "Hybrid Retail BI API"
    environment: str = Field(default="development")
    deployment_mode: DeploymentMode = DeploymentMode.LOCAL_HUB
    api_prefix: str = "/api"
    frontend_origin: str = "http://localhost:5173"
    frontend_extra_origins: str = "http://127.0.0.1:5173"
    api_docs_enabled: bool | None = None
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi"
    )
    local_database_url: str | None = None
    cloud_runtime_database_url: str | None = None
    cloud_migration_database_url: str | None = None
    secret_key: str = Field(default="change-me-in-development")
    access_token_expire_minutes: int = 60
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_deployment_database_configuration(self) -> "Settings":
        if self.deployment_mode == DeploymentMode.CLOUD_GATEWAY and not self.cloud_runtime_database_url:
            raise ValueError(
                "CLOUD_RUNTIME_DATABASE_URL is required when DEPLOYMENT_MODE=cloud_gateway."
            )

        local_target = database_target_identity(self.local_runtime_database_url)
        for name, cloud_url in (
            ("CLOUD_RUNTIME_DATABASE_URL", self.cloud_runtime_database_url),
            ("CLOUD_MIGRATION_DATABASE_URL", self.cloud_migration_database_url),
        ):
            if cloud_url and database_target_identity(cloud_url) == local_target:
                raise ValueError(f"{name} must not target the Local Hub database.")
        return self

    @property
    def local_runtime_database_url(self) -> str:
        """Resolve the explicit local URL while preserving the legacy setting."""
        return self.local_database_url or self.database_url

    @property
    def runtime_database_url(self) -> str:
        if self.deployment_mode == DeploymentMode.CLOUD_GATEWAY:
            if not self.cloud_runtime_database_url:
                raise RuntimeError("Cloud runtime database is not configured.")
            return self.cloud_runtime_database_url
        return self.local_runtime_database_url

    @property
    def local_migration_database_url(self) -> str:
        return self.local_runtime_database_url

    @property
    def required_cloud_migration_database_url(self) -> str:
        if not self.cloud_migration_database_url:
            raise RuntimeError(
                "CLOUD_MIGRATION_DATABASE_URL is required for cloud migrations."
            )
        return self.cloud_migration_database_url

    @property
    def resolved_api_docs_enabled(self) -> bool:
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return self.environment.lower() not in {"production", "prod"}

    @property
    def cors_origins(self) -> list[str]:
        origins: list[str] = []
        for raw_origins in (self.frontend_origin, self.frontend_extra_origins):
            for origin in raw_origins.split(","):
                cleaned = origin.strip()
                if cleaned and cleaned not in origins:
                    origins.append(cleaned)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
