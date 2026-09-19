"""End-to-end offline tests for both bounded graph routes."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TypeVar, cast

import httpx
import pytest
from pydantic import BaseModel

from seo_agent.audit.errors import CollectionError
from seo_agent.audit.models import (
    AnalysisResult,
    AuditLimits,
    EvaluationResult,
    FindingAnalysis,
    FindingEvaluation,
    FindingStatus,
    Investigation,
    InvestigationOperation,
    PageSelectionResult,
    PageSpeedStrategy,
    PageSpeedSummary,
    ReportResult,
    SelectedPage,
    Severity,
    SiteContext,
)
from seo_agent.audit.providers import AuditDependencies, FetchedResource
from seo_agent.audit.service import AuditService
from seo_agent.audit.url_policy import UrlPolicy, normalize_url
from seo_agent.audit.workflow import compile_audit_graph, initial_audit_state
from seo_agent.main import create_app

ModelT = TypeVar("ModelT", bound=BaseModel)


async def public_resolver(_hostname: str, _port: int) -> Sequence[str]:
    return ["93.184.216.34"]


class FixtureFetcher:
    """Record validated requests and serve saved byte fixtures."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.resources = {
            "https://example.com/": _resource(
                "https://example.com/",
                """<!doctype html><html><head>
                <title>Example SaaS</title>
                <meta name="description" content="Automation for teams">
                <link rel="canonical" href="https://example.com/">
                </head><body><nav><a href="/about">About</a></nav>
                <main><h1>Example SaaS</h1><p>Automation for teams.</p></main>
                <!-- RAW-HTML-SENTINEL --></body></html>""",
            ),
            "https://example.com/about": _resource(
                "https://example.com/about",
                """<html><head><title>About Example</title>
                <link rel="canonical" href="https://example.com/about">
                </head><body><main><h1>About us</h1><p>Company details.</p></main></body></html>""",
            ),
            "https://example.com/robots.txt": _resource(
                "https://example.com/robots.txt",
                "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n",
                content_type="text/plain",
            ),
            "https://example.com/sitemap.xml": _resource(
                "https://example.com/sitemap.xml",
                """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://example.com/</loc></url>
                <url><loc>https://example.com/about</loc></url></urlset>""",
                content_type="application/xml",
            ),
            "https://example.com/llms.txt": _resource(
                "https://example.com/llms.txt",
                "not found",
                status_code=404,
                content_type="text/plain",
            ),
        }

    async def fetch(self, url: str, policy: UrlPolicy) -> FetchedResource:
        normalized = await policy.validate_for_fetch(url)
        self.calls.append(normalized)
        resource = self.resources.get(normalized)
        if resource is None:
            raise CollectionError("Fixture resource is unavailable")
        return resource


class NoRenderer:
    async def render(self, url: str, policy: UrlPolicy) -> str | None:
        await policy.validate_for_fetch(url)
        return None


class NoPageSpeed:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def measure(
        self,
        url: str,
        policy: UrlPolicy,
        strategy: PageSpeedStrategy = PageSpeedStrategy.MOBILE,
    ) -> PageSpeedSummary:
        target = await policy.validate_for_fetch(url)
        self.calls.append(target)
        return PageSpeedSummary(
            url=target,
            strategy=strategy,
            available=False,
            collection_error="disabled in fixture",
        )


class FixtureLlm:
    """Return schema-valid decisions grounded in IDs parsed from each prompt."""

    def __init__(self, *, investigate_once: bool = False) -> None:
        self.investigate_once = investigate_once
        self.tasks: list[str] = []
        self.evaluation_count = 0

    async def generate(
        self,
        output_model: type[ModelT],
        *,
        task: str,
        system_prompt: str,
        user_prompt: str,
    ) -> ModelT:
        del system_prompt
        self.tasks.append(task)
        if output_model is SiteContext:
            result: BaseModel = SiteContext(
                summary="Example SaaS provides workflow automation for operations teams.",
                business_name="Example SaaS",
                products_or_services=["workflow automation"],
                audiences=["operations teams"],
            )
        elif output_model is PageSelectionResult:
            result = PageSelectionResult(
                selected_pages=[
                    SelectedPage(
                        url="https://example.com/about",
                        page_category="about",
                        selection_reason="Representative company information",
                    )
                ]
            )
        elif output_model is AnalysisResult:
            findings = _tagged_json(user_prompt, "findings")
            result = AnalysisResult(
                analyses=[
                    FindingAnalysis(
                        finding_id=_finding_id(item),
                        explanation=(
                            "The observation is supported by the supplied technical evidence."
                        ),
                        potential_impact="The condition may reduce clarity for crawlers or users.",
                        recommendation=(
                            "Confirm intent and correct the sampled page where applicable."
                        ),
                        appears_actionable=True,
                    )
                    for item in findings
                ]
            )
        elif output_model is EvaluationResult:
            self.evaluation_count += 1
            findings = _tagged_json(user_prompt, "findings")
            requests: list[Investigation] = []
            if self.investigate_once and self.evaluation_count == 1 and findings:
                first = findings[0]
                requests.append(
                    Investigation(
                        finding_id=_finding_id(first),
                        url=_first_affected_url(first),
                        question="Does a fresh bounded fetch confirm the observation?",
                        operation=InvestigationOperation.FETCH_URL,
                    )
                )
            result = EvaluationResult(
                evaluations=[
                    FindingEvaluation(
                        finding_id=_finding_id(item),
                        status=FindingStatus.VERIFIED
                        if not requests
                        else FindingStatus.NEEDS_REVIEW,
                        severity=Severity.LOW if not requests else None,
                        confidence=0.9 if not requests else 0.5,
                        rationale="The status follows from the source-linked evidence.",
                    )
                    for item in findings
                ],
                investigation_requests=requests,
            )
        elif output_model is ReportResult:
            result = ReportResult(summary="Fixture audit completed from sampled evidence.")
        else:
            raise AssertionError(f"Unexpected output model: {output_model}")
        return cast(ModelT, result)


@pytest.mark.integration
async def test_compiled_workflow_reports_without_investigation() -> None:
    fetcher = FixtureFetcher()
    llm = FixtureLlm()
    pagespeed = NoPageSpeed()
    limits = AuditLimits(max_selected_pages=2, max_pagespeed_pages=0)
    graph = compile_audit_graph(
        AuditDependencies(
            fetcher=fetcher,
            renderer=NoRenderer(),
            pagespeed=pagespeed,
            llm=llm,
            resolver=public_resolver,
        )
    )

    result = await graph.ainvoke(initial_audit_state("https://example.com", limits))

    report = result["report"]
    assert report is not None
    assert report.scope.candidate_count == 2
    assert [page.url for page in report.scope.selected_pages] == [
        "https://example.com/",
        "https://example.com/about",
    ]
    assert report.scope.investigation_rounds_used == 0
    assert report.site_context is not None
    assert report.site_context.products_or_services == ["workflow automation"]
    assert report.site_context.audiences == ["operations teams"]
    assert report.findings
    assert all(finding.status is FindingStatus.VERIFIED for finding in report.findings)
    assert fetcher.calls.count("https://example.com/") == 1
    assert pagespeed.calls == []
    assert llm.tasks == [
        "understand_site",
        "select_pages",
        "analyze_findings",
        "evaluate_findings",
        "report",
    ]
    assert "RAW-HTML-SENTINEL" not in json.dumps(_serializable_state(result), sort_keys=True)


@pytest.mark.integration
async def test_compiled_workflow_investigates_once_then_terminates() -> None:
    fetcher = FixtureFetcher()
    llm = FixtureLlm(investigate_once=True)
    limits = AuditLimits(max_selected_pages=2, max_pagespeed_pages=0)
    graph = compile_audit_graph(
        AuditDependencies(
            fetcher=fetcher,
            renderer=NoRenderer(),
            pagespeed=NoPageSpeed(),
            llm=llm,
            resolver=public_resolver,
        )
    )

    result = await graph.ainvoke(initial_audit_state("https://example.com", limits))

    report = result["report"]
    assert report is not None
    assert report.scope.investigation_rounds_used == 1
    assert report.scope.investigation_fetches_used == 1
    assert llm.evaluation_count == 2
    assert llm.tasks == [
        "understand_site",
        "select_pages",
        "analyze_findings",
        "evaluate_findings",
        "evaluate_findings",
        "report",
    ]
    assert fetcher.calls.count("https://example.com/") == 1
    assert len(fetcher.calls) == 6  # Home, three site files, selected page, one investigation.


@pytest.mark.integration
async def test_api_returns_schema_and_sanitizes_unsafe_input() -> None:
    limits = AuditLimits(max_selected_pages=2, max_pagespeed_pages=0)
    graph = compile_audit_graph(
        AuditDependencies(
            fetcher=FixtureFetcher(),
            renderer=NoRenderer(),
            pagespeed=NoPageSpeed(),
            llm=FixtureLlm(),
            resolver=public_resolver,
        )
    )
    app = create_app(audit_service=AuditService(graph, limits))

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post("/audits", json={"website_url": "https://example.com"})
            unsafe = await client.post("/audits", json={"website_url": "http://127.0.0.1"})
            invalid = await client.post("/audits", json={})

    assert response.status_code == 200
    assert response.json()["report"]["website_url"] == "https://example.com/"
    assert "RAW-HTML-SENTINEL" not in response.text
    assert unsafe.status_code == 422
    assert unsafe.json() == {
        "error": {
            "code": "invalid_website_url",
            "message": (
                "The website URL is invalid, unsafe, or outside the permitted public scope."
            ),
        }
    }
    assert invalid.status_code == 422


def _resource(
    url: str,
    body: str,
    *,
    status_code: int = 200,
    content_type: str = "text/html; charset=utf-8",
) -> FetchedResource:
    normalized = normalize_url(url)
    return FetchedResource(
        requested_url=normalized,
        final_url=normalized,
        status_code=status_code,
        headers={"content-type": content_type},
        body=body.encode(),
    )


def _tagged_json(prompt: str, tag: str) -> list[dict[str, object]]:
    start = prompt.index(f"<{tag}>") + len(tag) + 2
    end = prompt.index(f"</{tag}>")
    value = json.loads(prompt[start:end].strip())
    if not isinstance(value, list):
        raise AssertionError(f"Expected a list in <{tag}>")
    return cast(list[dict[str, object]], value)


def _finding_id(item: dict[str, object]) -> str:
    value = item.get("id")
    if not isinstance(value, str):
        raise AssertionError("Finding fixture is missing a string ID")
    return value


def _first_affected_url(item: dict[str, object]) -> str:
    value = item.get("affected_urls")
    if not isinstance(value, list) or not value or not isinstance(value[0], str):
        raise AssertionError("Finding fixture is missing an affected URL")
    return value[0]


def _serializable_state(state: object) -> object:
    if isinstance(state, BaseModel):
        return state.model_dump(mode="json")
    if isinstance(state, dict):
        return {str(key): _serializable_state(value) for key, value in state.items()}
    if isinstance(state, list):
        return [_serializable_state(value) for value in state]
    return state
