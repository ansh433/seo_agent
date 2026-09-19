"""FastAPI application composition and provider lifecycle."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from seo_agent.audit.errors import (
    AuditError,
    ProviderConfigurationError,
)
from seo_agent.audit.providers import (
    AuditDependencies,
    FirecrawlRenderer,
    GeminiStructuredClient,
    PageSpeedClient,
    SafeHttpFetcher,
)
from seo_agent.audit.router import router as audit_router
from seo_agent.audit.service import AuditService
from seo_agent.audit.url_policy import UrlPolicyError
from seo_agent.audit.workflow import compile_audit_graph
from seo_agent.config import Settings

_USER_AGENT = "TechnicalSeoAuditAgent/0.1"


def create_app(
    *,
    settings: Settings | None = None,
    audit_service: AuditService | None = None,
) -> FastAPI:
    """Create the API, optionally injecting a complete service for tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        if audit_service is not None:
            app.state.audit_service = audit_service
            yield
            return

        runtime_settings = settings or Settings()  # pyright: ignore[reportCallIssue]
        async with httpx.AsyncClient() as http_client:
            gemini = GeminiStructuredClient(
                api_key=runtime_settings.gemini_api_key.get_secret_value(),
                model=runtime_settings.gemini_model,
            )
            dependencies = AuditDependencies(
                fetcher=SafeHttpFetcher(
                    http_client,
                    runtime_settings.limits,
                    user_agent=_USER_AGENT,
                ),
                renderer=FirecrawlRenderer(
                    http_client,
                    api_key=_secret_value(runtime_settings.firecrawl_api_key),
                    timeout_seconds=runtime_settings.limits.request_timeout_seconds,
                    max_response_bytes=runtime_settings.limits.max_response_bytes,
                ),
                pagespeed=PageSpeedClient(
                    http_client,
                    api_key=_secret_value(runtime_settings.pagespeed_api_key),
                    timeout_seconds=runtime_settings.limits.pagespeed_timeout_seconds,
                ),
                llm=gemini,
            )
            app.state.audit_service = AuditService(
                compile_audit_graph(dependencies), runtime_settings.limits
            )
            try:
                yield
            finally:
                await gemini.close()

    application = FastAPI(
        title="Technical SEO Audit Agent",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(audit_router)
    _register_exception_handlers(application)
    return application


def _register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(UrlPolicyError)
    async def invalid_url_handler(_request: Request, _exc: UrlPolicyError) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_website_url",
            "The website URL is invalid, unsafe, or outside the permitted public scope.",
        )

    @application.exception_handler(ProviderConfigurationError)
    async def provider_configuration_handler(
        _request: Request,
        _exc: ProviderConfigurationError,
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "provider_not_configured",
            "A required audit provider is not configured.",
        )

    @application.exception_handler(AuditError)
    async def audit_error_handler(_request: Request, _exc: AuditError) -> JSONResponse:
        return _error_response(
            status.HTTP_502_BAD_GATEWAY,
            "audit_failed",
            "The audit could not be completed with the available evidence.",
        )


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _secret_value(secret: object) -> str | None:
    get_secret_value = getattr(secret, "get_secret_value", None)
    return str(get_secret_value()) if callable(get_secret_value) else None


app = create_app()
