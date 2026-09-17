"""Small asynchronous boundaries for external audit providers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from seo_agent.audit.errors import (
    CollectionError,
    ProviderResponseError,
    ResourceTooLargeError,
)
from seo_agent.audit.models import (
    AuditLimits,
    PageSpeedMetric,
    PageSpeedStrategy,
    PageSpeedSummary,
    RedirectHop,
)
from seo_agent.audit.url_policy import DnsResolver, UrlPolicy, UrlPolicyError, normalize_url

ModelT = TypeVar("ModelT", bound=BaseModel)


_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_LAB_AUDITS = {
    "first-contentful-paint": ("first_contentful_paint", "ms"),
    "largest-contentful-paint": ("largest_contentful_paint", "ms"),
    "cumulative-layout-shift": ("cumulative_layout_shift", "score"),
    "speed-index": ("speed_index", "ms"),
    "total-blocking-time": ("total_blocking_time", "ms"),
}


@dataclass(frozen=True, slots=True)
class FetchedResource:
    """Transient response data that must not be stored in graph state."""

    requested_url: str
    final_url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    redirect_chain: tuple[RedirectHop, ...] = ()

    @property
    def content_type(self) -> str | None:
        """Return the media type without optional charset parameters."""
        value = self.headers.get("content-type")
        return value.split(";", maxsplit=1)[0].strip().lower() if value else None

    def text(self) -> str:
        """Decode text conservatively without propagating raw bytes beyond collection."""
        content_type = self.headers.get("content-type", "")
        charset = "utf-8"
        for part in content_type.split(";")[1:]:
            name, separator, value = part.strip().partition("=")
            if separator and name.lower() == "charset" and value:
                charset = value.strip("\"'")
                break
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


class Fetcher(Protocol):
    """Fetch public in-scope resources with redirect safety."""

    async def fetch(self, url: str, policy: UrlPolicy) -> FetchedResource:
        """Fetch one bounded resource."""
        ...


class RenderedPageProvider(Protocol):
    """Optionally retrieve rendered HTML for an already validated target."""

    async def render(self, url: str, policy: UrlPolicy) -> str | None:
        """Return rendered HTML or None when rendering is not configured."""
        ...


class PerformanceProvider(Protocol):
    """Measure one validated public page."""

    async def measure(
        self,
        url: str,
        policy: UrlPolicy,
        strategy: PageSpeedStrategy = PageSpeedStrategy.MOBILE,
    ) -> PageSpeedSummary:
        """Return compact PageSpeed evidence."""
        ...


class StructuredLlm(Protocol):
    """Generate validated structured output for one named workflow task."""

    async def generate(
        self,
        output_model: type[ModelT],
        *,
        task: str,
        system_prompt: str,
        user_prompt: str,
    ) -> ModelT:
        """Generate a response conforming to output_model."""
        ...


@dataclass(frozen=True, slots=True)
class AuditDependencies:
    """External capabilities injected into workflow nodes."""

    fetcher: Fetcher
    renderer: RenderedPageProvider
    pagespeed: PerformanceProvider
    llm: StructuredLlm
    resolver: DnsResolver | None = None


class SafeHttpFetcher:
    """HTTPX fetcher that revalidates scope and DNS on every redirect hop."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        limits: AuditLimits,
        *,
        user_agent: str,
    ) -> None:
        self._client = client
        self._limits = limits
        self._headers = {
            "accept": "text/html,application/xhtml+xml,application/xml,text/plain;q=0.9,*/*;q=0.1",
            "user-agent": user_agent,
        }

    async def fetch(self, url: str, policy: UrlPolicy) -> FetchedResource:
        """Fetch a bounded response while validating every hop."""
        requested_url = await policy.validate_for_fetch(url)
        current_url = requested_url
        redirects: list[RedirectHop] = []

        for redirect_index in range(self._limits.max_redirects + 1):
            current_url = await policy.validate_for_fetch(current_url)
            response, body = await self._request_with_retries(current_url)
            if response.status_code not in _REDIRECT_STATUSES:
                return FetchedResource(
                    requested_url=requested_url,
                    final_url=current_url,
                    status_code=response.status_code,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=body,
                    redirect_chain=tuple(redirects),
                )

            location = response.headers.get("location")
            if not location:
                return FetchedResource(
                    requested_url=requested_url,
                    final_url=current_url,
                    status_code=response.status_code,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=body,
                    redirect_chain=tuple(redirects),
                )
            if redirect_index == self._limits.max_redirects:
                raise CollectionError("Redirect limit exceeded")

            try:
                destination = normalize_url(urljoin(current_url, location))
                destination = await policy.validate_for_fetch(destination)
            except UrlPolicyError as exc:
                raise CollectionError("Redirect destination is unsafe or out of scope") from exc
            redirects.append(
                RedirectHop(
                    source_url=current_url,
                    status_code=response.status_code,
                    destination_url=destination,
                )
            )
            current_url = destination

        raise CollectionError("Redirect limit exceeded")

    async def _request_with_retries(self, url: str) -> tuple[httpx.Response, bytes]:
        last_error: httpx.RequestError | None = None
        for attempt in range(self._limits.max_retries + 1):
            try:
                request = self._client.build_request(
                    "GET",
                    url,
                    headers=self._headers,
                    timeout=self._limits.request_timeout_seconds,
                )
                response = await self._client.send(request, stream=True, follow_redirects=False)
                try:
                    body = await self._read_bounded_body(response)
                finally:
                    await response.aclose()
            except httpx.RequestError as exc:
                last_error = exc
                if attempt == self._limits.max_retries:
                    break
                await asyncio.sleep(0.05 * (attempt + 1))
                continue
            if (
                response.status_code not in _RETRYABLE_STATUSES
                or attempt == self._limits.max_retries
            ):
                return response, body
            await asyncio.sleep(0.05 * (attempt + 1))
        raise CollectionError("Website request failed after bounded retries") from last_error

    async def _read_bounded_body(self, response: httpx.Response) -> bytes:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._limits.max_response_bytes:
                    raise ResourceTooLargeError(
                        "Website response exceeded the configured size limit"
                    )
            except ValueError:
                pass
        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > self._limits.max_response_bytes:
                raise ResourceTooLargeError("Website response exceeded the configured size limit")
            body.extend(chunk)
        return bytes(body)


class FirecrawlRenderer:
    """Selective Firecrawl v2 renderer; ordinary HTTP remains the evidence source."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes

    async def render(self, url: str, policy: UrlPolicy) -> str | None:
        """Return rendered HTML only when Firecrawl is configured."""
        if not self._api_key:
            return None
        target_url = await policy.validate_for_fetch(url)
        try:
            response = await self._client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers={"authorization": f"Bearer {self._api_key}"},
                json={"url": target_url, "formats": ["html"], "onlyMainContent": False},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderResponseError("Rendered-page provider request failed") from exc
        if len(response.content) > self._max_response_bytes:
            raise ResourceTooLargeError("Rendered-page response exceeded the configured size limit")
        try:
            payload = response.json()
            html = payload["data"]["html"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderResponseError("Rendered-page provider returned invalid data") from exc
        if not isinstance(html, str):
            raise ProviderResponseError("Rendered-page provider returned invalid HTML")
        return html


class PageSpeedClient:
    """Compact PageSpeed Insights v5 client."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str | None,
        timeout_seconds: float,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    async def measure(
        self,
        url: str,
        policy: UrlPolicy,
        strategy: PageSpeedStrategy = PageSpeedStrategy.MOBILE,
    ) -> PageSpeedSummary:
        """Measure a validated URL and discard the full API response."""
        target_url = await policy.validate_for_fetch(url)
        params: dict[str, str] = {
            "url": target_url,
            "strategy": strategy.value,
            "category": "performance",
        }
        if self._api_key:
            params["key"] = self._api_key
        try:
            response = await self._client.get(
                "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed",
                params=params,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return _parse_pagespeed(target_url, strategy, payload)
        except httpx.TimeoutException:
            return PageSpeedSummary(
                url=target_url,
                strategy=strategy,
                available=False,
                collection_error=(
                    f"PageSpeed request timed out after {self._timeout_seconds:g} seconds"
                ),
            )
        except httpx.HTTPStatusError as exc:
            return PageSpeedSummary(
                url=target_url,
                strategy=strategy,
                available=False,
                collection_error=f"PageSpeed request failed (HTTP {exc.response.status_code})",
            )
        except (httpx.HTTPError, TypeError, ValueError, KeyError):
            return PageSpeedSummary(
                url=target_url,
                strategy=strategy,
                available=False,
                collection_error="PageSpeed measurement was unavailable",
            )


def _parse_pagespeed(
    url: str,
    strategy: PageSpeedStrategy,
    payload: object,
) -> PageSpeedSummary:
    if not isinstance(payload, dict):
        raise TypeError("PageSpeed payload must be an object")
    lighthouse = payload.get("lighthouseResult")
    if not isinstance(lighthouse, dict):
        raise KeyError("lighthouseResult")
    categories = lighthouse.get("categories")
    audits = lighthouse.get("audits")
    if not isinstance(categories, dict) or not isinstance(audits, dict):
        raise KeyError("PageSpeed categories or audits")
    performance = categories.get("performance")
    score: float | None = None
    if isinstance(performance, dict) and isinstance(performance.get("score"), int | float):
        score = float(performance["score"])

    lab_metrics: list[PageSpeedMetric] = []
    for audit_key, (name, unit) in _LAB_AUDITS.items():
        audit = audits.get(audit_key)
        if not isinstance(audit, dict):
            continue
        value = audit.get("numericValue")
        if isinstance(value, int | float):
            lab_metrics.append(PageSpeedMetric(name=name, value=float(value), unit=unit))

    field_metrics: list[PageSpeedMetric] = []
    loading_experience = payload.get("loadingExperience")
    if isinstance(loading_experience, dict):
        metrics = loading_experience.get("metrics")
        if isinstance(metrics, dict):
            for name, metric in metrics.items():
                if not isinstance(name, str) or not isinstance(metric, dict):
                    continue
                percentile = metric.get("percentile")
                if isinstance(percentile, int | float):
                    field_metrics.append(
                        PageSpeedMetric(
                            name=name.lower(), value=float(percentile), unit="percentile"
                        )
                    )

    diagnostics: list[str] = []
    for audit in audits.values():
        if not isinstance(audit, dict):
            continue
        details = audit.get("details")
        savings = details.get("overallSavingsMs") if isinstance(details, dict) else None
        title = audit.get("title")
        if isinstance(savings, int | float) and savings > 100 and isinstance(title, str):
            diagnostics.append(title)
        if len(diagnostics) == 5:
            break

    return PageSpeedSummary(
        url=url,
        strategy=strategy,
        available=True,
        performance_score=score,
        lab_metrics=lab_metrics,
        field_metrics=field_metrics,
        diagnostics=diagnostics,
    )
