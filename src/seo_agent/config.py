"""Typed runtime configuration loaded from environment variables."""

from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from seo_agent.audit.models import AuditLimits


class Settings(BaseSettings):
    """Application configuration with credential-safe representations."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SEO_AGENT_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    gemini_api_key: Annotated[SecretStr, Field(min_length=1)]
    gemini_model: str = Field(default="gemini-2.5-flash", min_length=1)
    pagespeed_api_key: SecretStr | None = None
    firecrawl_api_key: SecretStr | None = None
    limits: AuditLimits = Field(default_factory=AuditLimits)

    @field_validator("pagespeed_api_key", "firecrawl_api_key", mode="before")
    @classmethod
    def empty_optional_secret_is_unset(cls, value: object) -> object:
        """Treat blank optional variables in a copied environment template as unset."""
        return None if value == "" else value
