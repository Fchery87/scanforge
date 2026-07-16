from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_env_file() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        env_path = parent / ".env"
        if env_path.exists():
            return env_path
    return Path(".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(find_env_file()),
        extra="ignore",
    )

    DATABASE_URL: str
    APP_ENV: str = "development"
    APP_NAME: str = "repo-security-platform-api"
    APP_URL: str = "http://localhost:8000"

    CORS_ORIGINS: str = "http://localhost:3000"
    TRUSTED_PROXY_IPS: str = ""

    NEON_AUTH_ISSUER: str = ""
    NEON_AUTH_AUDIENCE: str = ""
    NEON_AUTH_JWKS_URL: str = ""

    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""

    R2_ENDPOINT: str = ""
    R2_BUCKET: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_PUBLIC_BASE_URL: str = ""

    GITHUB_APP_ID: str = ""
    GITHUB_APP_SLUG: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_PRIVATE_KEY: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_STATE_SIGNING_SECRET: str = ""

    INTERNAL_API_KEY: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    SLACK_WEBHOOK_URL: str | None = None

    TRIVY_BINARY: str = "trivy"
    GITLEAKS_BINARY: str = "gitleaks"
    OSV_SCANNER_BINARY: str = "osv-scanner"
    SYFT_BINARY: str = "syft"
    GRYPE_BINARY: str = "grype"

    @field_validator("SLACK_WEBHOOK_URL", mode="before")
    @classmethod
    def empty_to_none(cls, v):
        if v == "":
            return None
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def trusted_proxy_ips_set(self) -> set[str] | None:
        ips = [ip.strip() for ip in self.TRUSTED_PROXY_IPS.split(",") if ip.strip()]
        return set(ips) if ips else None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
