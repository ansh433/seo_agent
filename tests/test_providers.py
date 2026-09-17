"""Provider contract tests using only in-process transports."""

from collections.abc import Sequence

import httpx
import pytest

from seo_agent.audit.errors import CollectionError, ResourceTooLargeError
from seo_agent.audit.models import AuditLimits
from seo_agent.audit.providers import SafeHttpFetcher
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
