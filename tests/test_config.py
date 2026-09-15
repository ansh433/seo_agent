"""Tests for typed, credential-safe runtime settings."""

import pytest
from pydantic import SecretStr, ValidationError

from seo_agent.audit.models import AuditLimits
from seo_agent.config import Settings

pytestmark = pytest.mark.unit


def test_settings_use_documented_defaults() -> None:
    settings = Settings(
        gemini_api_key=SecretStr("gemini-secret"),
        _env_file=None,  # pyright: ignore[reportCallIssue]
    )

    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.pagespeed_api_key is None
    assert settings.firecrawl_api_key is None
    assert settings.limits == AuditLimits()
    assert settings.limits.pagespeed_timeout_seconds == 45.0


def test_settings_load_prefixed_nested_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEO_AGENT_GEMINI_API_KEY", "environment-secret")
    monkeypatch.setenv("SEO_AGENT_PAGESPEED_API_KEY", "")
    monkeypatch.setenv("SEO_AGENT_LIMITS__MAX_CANDIDATES", "12")
    monkeypatch.setenv("SEO_AGENT_LIMITS__MAX_SELECTED_PAGES", "4")
    monkeypatch.setenv("SEO_AGENT_LIMITS__REQUEST_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("SEO_AGENT_LIMITS__PAGESPEED_TIMEOUT_SECONDS", "25")

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.gemini_api_key.get_secret_value() == "environment-secret"
    assert settings.pagespeed_api_key is None
    assert settings.limits.max_candidates == 12
    assert settings.limits.max_selected_pages == 4
    assert settings.limits.request_timeout_seconds == 3.5
    assert settings.limits.pagespeed_timeout_seconds == 25.0


def test_settings_do_not_expose_credentials() -> None:
    secret = "never-print-this-value"
    settings = Settings(
        gemini_api_key=SecretStr(secret),
        _env_file=None,  # pyright: ignore[reportCallIssue]
    )

    assert secret not in repr(settings)
    assert secret not in settings.model_dump_json()


def test_audit_limits_reject_selected_pages_above_candidate_budget() -> None:
    with pytest.raises(ValidationError, match="cannot exceed max_candidates"):
        AuditLimits(max_candidates=2, max_selected_pages=3)
