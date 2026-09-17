"""Provider contract tests using only in-process transports."""

from collections.abc import Sequence

import httpx
import pytest

from seo_agent.audit.errors import CollectionError, ResourceTooLargeError
from seo_agent.audit.models import AuditLimits
from seo_agent.audit.providers import PageSpeedClient, SafeHttpFetcher
from seo_agent.audit.url_policy import UrlPolicy


async def public_resolver(_hostname: str, _port: int) -> Sequence[str]:
    return ["93.184.216.34"]


@pytest.mark.unit
async def test_fetcher_follows_only_validated_redirects() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/":
            return httpx.Response(301, headers={"location": "/about"}, content=b"")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<h1>About</h1>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = SafeHttpFetcher(client, AuditLimits(), user_agent="seo-agent-test")
        _, policy = await UrlPolicy.for_url("https://example.com", resolver=public_resolver)
        resource = await fetcher.fetch("https://example.com", policy)

    assert requests == ["https://example.com/", "https://example.com/about"]
    assert resource.final_url == "https://example.com/about"
    assert resource.status_code == 200
    assert len(resource.redirect_chain) == 1
    assert resource.text() == "<h1>About</h1>"


@pytest.mark.unit
async def test_fetcher_rejects_unsafe_redirect_before_second_request() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = SafeHttpFetcher(client, AuditLimits(), user_agent="seo-agent-test")
        _, policy = await UrlPolicy.for_url("https://example.com", resolver=public_resolver)
        with pytest.raises(CollectionError, match="unsafe or out of scope"):
            await fetcher.fetch("https://example.com", policy)

    assert requests == ["https://example.com/"]


@pytest.mark.unit
async def test_fetcher_enforces_response_limit() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"too large")

    limits = AuditLimits(max_response_bytes=3)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = SafeHttpFetcher(client, limits, user_agent="seo-agent-test")
        _, policy = await UrlPolicy.for_url("https://example.com", resolver=public_resolver)
        with pytest.raises(ResourceTooLargeError):
            await fetcher.fetch("https://example.com", policy)


@pytest.mark.unit
async def test_fetcher_retries_only_to_configured_bound() -> None:
    request_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(503, content=b"unavailable")

    limits = AuditLimits(max_retries=2)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = SafeHttpFetcher(client, limits, user_agent="seo-agent-test")
        _, policy = await UrlPolicy.for_url("https://example.com", resolver=public_resolver)
        resource = await fetcher.fetch("https://example.com", policy)

    assert request_count == 3
    assert resource.status_code == 503


@pytest.mark.unit
async def test_pagespeed_client_discards_full_payload_and_keeps_compact_metrics() -> None:
    payload = {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.81}},
            "audits": {
                "first-contentful-paint": {
                    "numericValue": 1200.0,
                    "title": "First Contentful Paint",
                },
                "unused-javascript": {
                    "title": "Reduce unused JavaScript",
                    "details": {"overallSavingsMs": 450},
                },
            },
        },
        "loadingExperience": {"metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2300}}},
        "largeUnusedProviderField": "must not enter the model",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["url"] == "https://example.com/"
        assert request.url.params["strategy"] == "mobile"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PageSpeedClient(client, api_key=None, timeout_seconds=10)
        _, policy = await UrlPolicy.for_url("https://example.com", resolver=public_resolver)
        result = await provider.measure("https://example.com", policy)

    assert result.available is True
    assert result.performance_score == 0.81
    assert result.lab_metrics[0].name == "first_contentful_paint"
    assert result.field_metrics[0].name == "largest_contentful_paint_ms"
    assert result.diagnostics == ["Reduce unused JavaScript"]
    assert "largeUnusedProviderField" not in result.model_dump_json()


@pytest.mark.unit
async def test_pagespeed_client_keeps_safe_http_failure_status() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "quota details"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PageSpeedClient(client, api_key="test-key", timeout_seconds=10)
        _, policy = await UrlPolicy.for_url("https://example.com", resolver=public_resolver)
        result = await provider.measure("https://example.com", policy)

    assert result.available is False
    assert result.collection_error == "PageSpeed request failed (HTTP 429)"


@pytest.mark.unit
async def test_pagespeed_client_distinguishes_timeout_from_other_failures() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PageSpeedClient(client, api_key="test-key", timeout_seconds=45)
        _, policy = await UrlPolicy.for_url("https://example.com", resolver=public_resolver)
        result = await provider.measure("https://example.com", policy)

    assert result.available is False
    assert result.collection_error == "PageSpeed request timed out after 45 seconds"
