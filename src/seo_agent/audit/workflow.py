"""Single bounded LangGraph workflow for technical SEO audits."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable, Mapping
from typing import Literal, cast
from urllib.parse import urlsplit, urlunsplit

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, JsonValue

from seo_agent.audit.checks import (
    apply_evaluation_safeguards,
    build_remediation_briefs,
    consolidate_findings,
    prioritize_findings,
    run_deterministic_checks,
)
from seo_agent.audit.errors import AuditError
from seo_agent.audit.extraction import (
    extract_page_signals,
    parse_robots_txt,
    parse_sitemap_xml,
)
from seo_agent.audit.models import (
    AnalysisResult,
    AuditLimits,
    AuditReport,
    AuditScope,
    AuditState,
    CandidateSource,
    CollectionStatus,
    EvaluationResult,
    Evidence,
    Finding,
    FindingEvaluation,
    FindingStatus,
    Investigation,
    PageCandidate,
    PageSelectionResult,
    PageSignals,
    PageSpeedStrategy,
    PageSpeedSummary,
    ReportResult,
    RobotsDirective,
    RobotsSignals,
    SelectedPage,
    SiteContext,
    SiteFileSignals,
    SitemapSignals,
    SiteSignals,
)
from seo_agent.audit.prompts import (
    ANALYZE_FINDINGS_SYSTEM_PROMPT,
    ANALYZE_FINDINGS_USER_PROMPT,
    EVALUATE_FINDINGS_SYSTEM_PROMPT,
    EVALUATE_FINDINGS_USER_PROMPT,
    REPORT_SYSTEM_PROMPT,
    REPORT_USER_PROMPT,
    SELECT_PAGES_SYSTEM_PROMPT,
    SELECT_PAGES_USER_PROMPT,
    UNDERSTAND_SITE_SYSTEM_PROMPT,
    UNDERSTAND_SITE_USER_PROMPT,
)
from seo_agent.audit.providers import AuditDependencies, FetchedResource
from seo_agent.audit.url_policy import UrlPolicy, UrlPolicyError, normalize_url

AuditGraph = CompiledStateGraph[AuditState, None, AuditState, AuditState]
StateUpdate = dict[str, object]


class AuditWorkflowNodes:
    """Domain-named graph nodes sharing injected provider capabilities."""

    def __init__(self, dependencies: AuditDependencies) -> None:
        self._dependencies = dependencies

    async def scope_and_discover(self, state: AuditState) -> StateUpdate:
        """Collect the homepage and bounded public site-level resources."""
        limits = state["limits"]
        website_url, policy = await UrlPolicy.for_url(
            state["website_url"], resolver=self._dependencies.resolver
        )
        homepage = await self._dependencies.fetcher.fetch(website_url, policy)
        homepage_signals = _extract_resource(homepage, policy)
        homepage_url = homepage.final_url

        robots_url = _root_url(homepage_url, "/robots.txt")
        default_sitemap_url = _root_url(homepage_url, "/sitemap.xml")
        llms_url = _root_url(homepage_url, "/llms.txt")
        robots_result, llms_result = await asyncio.gather(
            _optional_fetch(self._dependencies, robots_url, policy),
            _optional_fetch(self._dependencies, llms_url, policy),
        )
        warnings: list[str] = []

        robots_resource, robots_error = robots_result
        if robots_resource is None:
            robots = parse_robots_txt(
                None,
                url=robots_url,
                status_code=None,
                collection_error=robots_error,
            )
            if robots_error:
                warnings.append(f"robots.txt: {robots_error}")
        else:
            robots = parse_robots_txt(
                robots_resource.body,
                url=robots_resource.final_url,
                status_code=robots_resource.status_code,
                max_sitemaps=limits.max_sitemap_files,
            )

        sitemap_queue = list(robots.sitemap_urls) or [default_sitemap_url]
        sitemap_signals: list[SitemapSignals] = []
        sitemap_pages: list[str] = []
        seen_sitemaps: set[str] = set()
        while sitemap_queue and len(sitemap_signals) < limits.max_sitemap_files:
            sitemap_url = sitemap_queue.pop(0)
            try:
                normalized_sitemap = normalize_url(sitemap_url)
            except UrlPolicyError:
                warnings.append("Ignored an invalid sitemap URL")
                continue
            if normalized_sitemap in seen_sitemaps:
                continue
            seen_sitemaps.add(normalized_sitemap)
            resource, error = await _optional_fetch(self._dependencies, normalized_sitemap, policy)
            if resource is None:
                sitemap = parse_sitemap_xml(
                    None,
                    url=normalized_sitemap,
                    status_code=None,
                    collection_error=error,
                    max_urls=max(limits.max_sitemap_urls - len(sitemap_pages), 0),
                )
                if error:
                    warnings.append(f"Sitemap {normalized_sitemap}: {error}")
            else:
                sitemap = parse_sitemap_xml(
                    resource.body,
                    url=resource.final_url,
                    status_code=resource.status_code,
                    max_urls=max(limits.max_sitemap_urls - len(sitemap_pages), 0),
                )
            sitemap_signals.append(sitemap)
            for child_url in sitemap.child_sitemap_urls:
                if len(sitemap_signals) + len(sitemap_queue) < limits.max_sitemap_files:
                    sitemap_queue.append(child_url)
            for page_url in sitemap.page_urls:
                if len(sitemap_pages) >= limits.max_sitemap_urls:
                    break
                if page_url not in sitemap_pages:
                    sitemap_pages.append(page_url)

        llms_resource, llms_error = llms_result
        if llms_resource is None:
            llms_signals = SiteFileSignals(
                url=llms_url,
                available=None,
                collection_error=llms_error,
            )
            if llms_error:
                warnings.append(f"llms.txt: {llms_error}")
        else:
            llms_signals = SiteFileSignals(
                url=llms_resource.final_url,
                available=200 <= llms_resource.status_code < 300,
                status_code=llms_resource.status_code,
            )

        site_signals = SiteSignals(
            robots=robots,
            sitemaps=sitemap_signals,
            llms_txt=llms_signals,
        )
        candidates = _build_candidates(
            homepage_url,
            homepage_signals,
            sitemap_pages,
            limits.max_candidates,
        )
        site_context = _build_site_context(homepage_signals)
        try:
            site_context = await self._understand_site_context(homepage_signals, site_context)
        except AuditError as exc:
            warnings.append(f"Site context used a deterministic fallback ({exc})")
        if len(candidates) < limits.max_selected_pages:
            warnings.append(f"Only {len(candidates)} in-scope page candidate(s) were discovered")
        return {
            "website_url": homepage_url,
            "site_context": site_context,
            "candidates": candidates,
            "site_signals": site_signals,
            "page_signals": {homepage_url: homepage_signals},
            "collection_warnings": _merge_strings(state["collection_warnings"], warnings),
        }

    async def _understand_site_context(
        self,
        homepage: PageSignals,
        fallback: SiteContext,
    ) -> SiteContext:
        """Summarize compact homepage evidence for representative-page selection."""
        prompt = UNDERSTAND_SITE_USER_PROMPT.format(
            homepage_evidence=_json_data(_homepage_evidence(homepage)),
        )
        result = await self._dependencies.llm.generate(
            SiteContext,
            task="understand_site",
            system_prompt=UNDERSTAND_SITE_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
        return _bounded_site_context(result, fallback)

    async def select_pages(self, state: AuditState) -> StateUpdate:
        """Ask Gemini for representative pages and enforce the discovered allowlist."""
        homepage_url = state["website_url"]
        limits = state["limits"]
        mandatory_homepage = SelectedPage(
            url=homepage_url,
            page_category="homepage",
            selection_reason="Mandatory homepage coverage",
        )
        additional_limit = max(limits.max_selected_pages - 1, 0)
        candidates = [
            candidate for candidate in state["candidates"] if candidate.url != homepage_url
        ]
        if not candidates or additional_limit == 0:
            return {"selected_pages": [mandatory_homepage]}

        prompt = SELECT_PAGES_USER_PROMPT.format(
            site_context=_json_data(state["site_context"]),
            candidates=_json_data(candidates),
            additional_page_limit=min(additional_limit, len(candidates)),
        )
        warning: str | None = None
        for _attempt in range(2):
            try:
                result = await self._dependencies.llm.generate(
                    PageSelectionResult,
                    task="select_pages",
                    system_prompt=SELECT_PAGES_SYSTEM_PROMPT,
                    user_prompt=prompt,
                )
                selected = _validate_page_selection(
                    result,
                    candidates,
                    homepage_url=homepage_url,
                    limit=additional_limit,
                )
                return {"selected_pages": [mandatory_homepage, *selected]}
            except (AuditError, ValueError) as exc:
                warning = f"Page selection used a deterministic fallback ({type(exc).__name__})"

        fallback = [
            SelectedPage(
                url=candidate.url,
                page_category=candidate.inferred_page_type or "representative_page",
                selection_reason="Conservative fallback from the discovered candidate order",
            )
            for candidate in candidates[:additional_limit]
        ]
        return {
            "selected_pages": [mandatory_homepage, *fallback],
            "collection_warnings": _merge_strings(
                state["collection_warnings"], [warning] if warning else []
            ),
        }

    async def fetch_and_extract(self, state: AuditState) -> StateUpdate:
        """Fetch selected pages once and retain only compact signals."""
        _, policy = await UrlPolicy.for_url(
            state["website_url"], resolver=self._dependencies.resolver
        )
        page_signals = dict(state["page_signals"])
        warnings: list[str] = []

        async def collect(page: SelectedPage) -> tuple[str, PageSignals | None, str | None]:
            if page.url in page_signals:
                return page.url, page_signals[page.url], None
            robots = state["site_signals"].robots if state["site_signals"] else None
            if not _robots_permits(page.url, robots):
                blocked = PageSignals(
                    url=page.url,
                    collection_status=CollectionStatus.FAILED,
                    collection_error="Collection skipped because robots.txt disallows this URL",
                )
                return page.url, blocked, f"Page {page.url}: blocked by robots.txt"
            try:
                resource = await self._dependencies.fetcher.fetch(page.url, policy)
                signals = _extract_resource(resource, policy)
                if (
                    signals.status_code is not None
                    and 200 <= signals.status_code < 300
                    and not signals.page_context
                ):
                    rendered = await self._dependencies.renderer.render(page.url, policy)
                    if rendered:
                        signals = extract_page_signals(
                            url=resource.requested_url,
                            html=rendered,
                            status_code=resource.status_code,
                            headers=resource.headers,
                            final_url=resource.final_url,
                            redirect_chain=resource.redirect_chain,
                            scope=policy.scope,
                        )
                return page.url, signals, None
            except (AuditError, UrlPolicyError) as exc:
                failed = PageSignals(
                    url=page.url,
                    collection_status=CollectionStatus.FAILED,
                    collection_error="Selected page collection failed",
                )
                return page.url, failed, f"Page {page.url}: {type(exc).__name__}"

        results = await asyncio.gather(*(collect(page) for page in state["selected_pages"]))
        for page_url, signals, warning in results:
            if signals is not None:
                page_signals[page_url] = signals
            if warning:
                warnings.append(warning)
        return {
            "page_signals": page_signals,
            "collection_warnings": _merge_strings(state["collection_warnings"], warnings),
        }

    async def run_technical_audit(self, state: AuditState) -> StateUpdate:
        """Apply deterministic checks and collect bounded performance evidence."""
        page_signals = _attach_verified_link_statuses(state["page_signals"])
        limits = state["limits"]
        _, policy = await UrlPolicy.for_url(
            state["website_url"], resolver=self._dependencies.resolver
        )
        performance: dict[str, PageSpeedSummary] = {}
        warnings: list[str] = []
        robots = state["site_signals"].robots if state["site_signals"] else None
        pagespeed_pages = [
            page for page in state["selected_pages"] if _robots_permits(page.url, robots)
        ][: limits.max_pagespeed_pages]

        async def measure(page: SelectedPage) -> tuple[str, PageSpeedSummary]:
            summary = await self._dependencies.pagespeed.measure(
                page.url, policy, PageSpeedStrategy.MOBILE
            )
            return page.url, summary

        results = await asyncio.gather(*(measure(page) for page in pagespeed_pages))
        for page_url, summary in results:
            performance[page_url] = summary
            if not summary.available:
                warnings.append(
                    f"PageSpeed unavailable for {page_url}: "
                    f"{summary.collection_error or 'unknown provider error'}"
                )

        findings = run_deterministic_checks(page_signals, state["site_signals"])
        return {
            "page_signals": page_signals,
            "performance": performance,
            "findings": findings,
            "collection_warnings": _merge_strings(state["collection_warnings"], warnings),
        }

    def consolidate(self, state: AuditState) -> StateUpdate:
        """Combine technically identical observations before LLM reasoning."""
        return {"findings": consolidate_findings(state["findings"])}

    async def analyze_findings(self, state: AuditState) -> StateUpdate:
        """Add contextual interpretation without changing evidence."""
        if not state["findings"]:
            return {"findings": []}
        prompt = ANALYZE_FINDINGS_USER_PROMPT.format(
            site_context=_json_data(state["site_context"]),
            findings=_json_data(state["findings"]),
            performance=_json_data(state["performance"]),
        )
        try:
            result = await self._dependencies.llm.generate(
                AnalysisResult,
                task="analyze_findings",
                system_prompt=ANALYZE_FINDINGS_SYSTEM_PROMPT,
                user_prompt=prompt,
            )
        except AuditError as exc:
            return {
                "collection_warnings": _merge_strings(
                    state["collection_warnings"],
                    [f"Finding analysis was unavailable ({exc})"],
                )
            }
        analyses = {analysis.finding_id: analysis for analysis in result.analyses}
        findings: list[Finding] = []
        for finding in state["findings"]:
            analysis = analyses.get(finding.id)
            if analysis is None:
                findings.append(finding)
                continue
            findings.append(
                finding.model_copy(
                    update={
                        "explanation": analysis.explanation,
                        "potential_impact": analysis.potential_impact,
                        "recommendation": analysis.recommendation,
                        "missing_information": analysis.missing_information,
                    }
                )
            )
        return {"findings": findings}

    async def evaluate_findings(self, state: AuditState) -> StateUpdate:
        """Validate model conclusions and request only bounded useful evidence."""
        if not state["findings"]:
            return {"findings": [], "investigation_requests": []}
        limits = state["limits"]
        remaining_rounds = max(limits.max_investigation_rounds - state["investigation_count"], 0)
        remaining_fetches = limits.max_investigation_fetches if remaining_rounds else 0
        prompt = EVALUATE_FINDINGS_USER_PROMPT.format(
            findings=_json_data(state["findings"]),
            remaining_investigation_rounds=remaining_rounds,
            remaining_investigation_fetches=remaining_fetches,
        )
        warnings: list[str] = []
        try:
            result = await self._dependencies.llm.generate(
                EvaluationResult,
                task="evaluate_findings",
                system_prompt=EVALUATE_FINDINGS_SYSTEM_PROMPT,
                user_prompt=prompt,
            )
        except AuditError as exc:
            result = EvaluationResult()
            warnings.append(f"Finding evaluation was unavailable ({exc})")

        known_ids = {finding.id for finding in state["findings"]}
        evaluations = [
            evaluation for evaluation in result.evaluations if evaluation.finding_id in known_ids
        ]
        evaluated_ids = {evaluation.finding_id for evaluation in evaluations}
        evaluations.extend(
            FindingEvaluation(
                finding_id=finding.id,
                status=FindingStatus.NEEDS_REVIEW,
                confidence=0.3,
                rationale="No supported evaluator decision was available.",
            )
            for finding in state["findings"]
            if finding.id not in evaluated_ids
        )
        findings = apply_evaluation_safeguards(state["findings"], evaluations)
        requests: list[Investigation] = []
        if remaining_rounds and remaining_fetches:
            _, policy = await UrlPolicy.for_url(
                state["website_url"], resolver=self._dependencies.resolver
            )
            for request in result.investigation_requests:
                if request.finding_id not in known_ids or len(requests) >= remaining_fetches:
                    continue
                try:
                    normalized = await policy.validate_for_fetch(request.url)
                except UrlPolicyError:
                    warnings.append("Ignored an unsafe or out-of-scope investigation request")
                    continue
                requests.append(request.model_copy(update={"url": normalized}))
        return {
            "findings": findings,
            "investigation_requests": requests,
            "collection_warnings": _merge_strings(state["collection_warnings"], warnings),
        }

    async def investigate(self, state: AuditState) -> StateUpdate:
        """Perform one allowlisted, finding-specific evidence round."""
        limits = state["limits"]
        requests = state["investigation_requests"][: limits.max_investigation_fetches]
        _, policy = await UrlPolicy.for_url(
            state["website_url"], resolver=self._dependencies.resolver
        )
        evidence_by_id: dict[str, list[Evidence]] = {}
        page_signals = dict(state["page_signals"])
        warnings: list[str] = []
        for request in requests:
            robots = state["site_signals"].robots if state["site_signals"] else None
            if not _robots_permits(request.url, robots):
                warnings.append(
                    f"Investigation for {request.finding_id} was skipped due to robots.txt"
                )
                continue
            try:
                resource = await self._dependencies.fetcher.fetch(request.url, policy)
                signals = _extract_resource(resource, policy)
                page_signals[request.url] = signals
                evidence_by_id.setdefault(request.finding_id, []).append(
                    Evidence(
                        source_url=request.url,
                        signal=f"investigation.{request.operation.value}",
                        observed_value=cast(
                            JsonValue,
                            {
                                "status_code": signals.status_code,
                                "final_url": signals.final_url,
                                "canonical_url": signals.canonical_url,
                                "meta_robots": signals.meta_robots,
                                "x_robots_tag": signals.x_robots_tag,
                                "collection_status": signals.collection_status.value,
                            },
                        ),
                    )
                )
            except (AuditError, UrlPolicyError) as exc:
                warnings.append(
                    f"Investigation for {request.finding_id} was unavailable ({type(exc).__name__})"
                )
        findings = [
            finding.model_copy(
                update={"evidence": [*finding.evidence, *evidence_by_id.get(finding.id, [])]}
            )
            for finding in state["findings"]
        ]
        return {
            "findings": findings,
            "page_signals": page_signals,
            "investigation_requests": [],
            "investigation_count": state["investigation_count"] + 1,
            "collection_warnings": _merge_strings(state["collection_warnings"], warnings),
        }

    async def prioritize_and_report(self, state: AuditState) -> StateUpdate:
        """Produce the final sampled report and verified remediation briefs."""
        findings = prioritize_findings(state["findings"])
        scope = _audit_scope(state, findings)
        fallback_briefs = build_remediation_briefs(findings)
        performance_observations = _performance_observations(state)
        ai_observations = _ai_discoverability_observations(state)
        default_limitations = [
            "This is a representative sampled audit, not an exhaustive crawl of the website.",
            "Observed technical eligibility does not prove search-engine indexing or ranking.",
            (
                "Missing or inaccessible information was not treated as proof that an "
                "element does not exist."
            ),
        ]
        prompt = REPORT_USER_PROMPT.format(
            site_context=_json_data(state["site_context"]),
            scope=_json_data(scope),
            findings=_json_data(findings),
            performance=_json_data(state["performance"]),
            collection_warnings=_json_data(state["collection_warnings"]),
        )
        warnings = list(state["collection_warnings"])
        try:
            generated = await self._dependencies.llm.generate(
                ReportResult,
                task="report",
                system_prompt=REPORT_SYSTEM_PROMPT,
                user_prompt=prompt,
            )
        except AuditError as exc:
            generated = ReportResult(
                summary=_fallback_summary(findings),
                performance_observations=performance_observations,
                ai_discoverability_observations=ai_observations,
                remediation_briefs=fallback_briefs,
                limitations=default_limitations,
            )
            warnings = _merge_strings(
                warnings, [f"Report narrative generation was unavailable ({exc})"]
            )

        known_findings = {finding.id: finding for finding in findings}
        narratives = {
            narrative.finding_id: narrative
            for narrative in generated.finding_narratives
            if narrative.finding_id in known_findings
        }
        report_findings: list[Finding] = []
        for finding in findings:
            narrative = narratives.get(finding.id)
            if narrative is None:
                report_findings.append(finding)
                continue
            report_findings.append(
                finding.model_copy(
                    update={
                        "explanation": narrative.explanation,
                        "potential_impact": narrative.potential_impact,
                        "recommendation": narrative.recommended_action,
                    }
                )
            )
        verified_ids = {
            finding.id for finding in report_findings if finding.status is FindingStatus.VERIFIED
        }
        generated_briefs = [
            brief for brief in generated.remediation_briefs if brief.finding_id in verified_ids
        ]
        report = AuditReport(
            website_url=state["website_url"],
            site_context=state["site_context"],
            scope=scope,
            summary=generated.summary or _fallback_summary(report_findings),
            findings=report_findings,
            performance=state["performance"],
            performance_observations=generated.performance_observations or performance_observations,
            ai_discoverability_observations=generated.ai_discoverability_observations
            or ai_observations,
            remediation_briefs=generated_briefs or fallback_briefs,
            unresolved_finding_ids=[
                finding.id
                for finding in report_findings
                if finding.status in {FindingStatus.NEEDS_REVIEW, FindingStatus.OBSERVED}
            ],
            collection_warnings=warnings,
            limitations=_merge_strings(default_limitations, generated.limitations),
        )
        return {"findings": report_findings, "report": report}


def route_after_evaluation(state: AuditState) -> Literal["investigate", "report"]:
    """Route once to targeted investigation only while its round budget remains."""
    if (
        state["investigation_requests"]
        and state["investigation_count"] < state["limits"].max_investigation_rounds
    ):
        return "investigate"
    return "report"


def compile_audit_graph(dependencies: AuditDependencies) -> AuditGraph:
    """Compile the reusable audit graph without persistence or checkpointing."""
    nodes = AuditWorkflowNodes(dependencies)
    builder = StateGraph(AuditState)
    builder.add_node("scope_and_discover", nodes.scope_and_discover)
    builder.add_node("select_pages", nodes.select_pages)
    builder.add_node("fetch_and_extract", nodes.fetch_and_extract)
    builder.add_node("technical_audit", nodes.run_technical_audit)
    builder.add_node("consolidate", nodes.consolidate)
    builder.add_node("analyze", nodes.analyze_findings)
    builder.add_node("evaluate", nodes.evaluate_findings)
    builder.add_node("investigate", nodes.investigate)
    builder.add_node("report", nodes.prioritize_and_report)
    builder.add_edge(START, "scope_and_discover")
    builder.add_edge("scope_and_discover", "select_pages")
    builder.add_edge("select_pages", "fetch_and_extract")
    builder.add_edge("fetch_and_extract", "technical_audit")
    builder.add_edge("technical_audit", "consolidate")
    builder.add_edge("consolidate", "analyze")
    builder.add_edge("analyze", "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluation,
        {"investigate": "investigate", "report": "report"},
    )
    builder.add_edge("investigate", "evaluate")
    builder.add_edge("report", END)
    return builder.compile(name="technical-seo-audit")


def initial_audit_state(website_url: str, limits: AuditLimits) -> AuditState:
    """Create a complete initial state so nodes only return explicit updates."""
    return AuditState(
        website_url=website_url,
        limits=limits,
        site_context=None,
        candidates=[],
        selected_pages=[],
        site_signals=None,
        page_signals={},
        performance={},
        findings=[],
        investigation_requests=[],
        investigation_count=0,
        collection_warnings=[],
        report=None,
    )


async def _optional_fetch(
    dependencies: AuditDependencies,
    url: str,
    policy: UrlPolicy,
) -> tuple[FetchedResource | None, str | None]:
    try:
        return await dependencies.fetcher.fetch(url, policy), None
    except (AuditError, UrlPolicyError) as exc:
        return None, type(exc).__name__


def _extract_resource(resource: FetchedResource, policy: UrlPolicy) -> PageSignals:
    return extract_page_signals(
        url=resource.requested_url,
        html=resource.body,
        status_code=resource.status_code,
        headers=resource.headers,
        final_url=resource.final_url,
        redirect_chain=resource.redirect_chain,
        scope=policy.scope,
    )


def _root_url(url: str, path: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _build_site_context(homepage: PageSignals) -> SiteContext:
    pieces = [piece for piece in [homepage.title, homepage.meta_description] if piece]
    if not pieces and homepage.page_context:
        pieces.append(homepage.page_context[:300])
    return SiteContext(
        summary=" — ".join(pieces) or "Homepage context was unavailable.",
        business_name=homepage.title,
    )


def _homepage_evidence(homepage: PageSignals) -> dict[str, object]:
    """Prepare compact, raw-HTML-free evidence for site-context reasoning."""
    return {
        "homepage_url": homepage.final_url or homepage.url,
        "title": homepage.title,
        "meta_description": homepage.meta_description,
        "headings": [heading.model_dump(mode="json") for heading in homepage.headings[:6]],
        "json_ld_identity": [
            {
                "types": block.schema_types,
                "name": block.entity_name,
                "url": block.entity_url,
            }
            for block in homepage.json_ld[:6]
            if block.valid and (block.entity_name or block.entity_url)
        ],
        "page_context": homepage.page_context,
    }


def _bounded_site_context(result: SiteContext, fallback: SiteContext) -> SiteContext:
    """Keep model-produced context compact and fall back when its summary is blank."""
    summary = result.summary.strip()[:600] or fallback.summary
    return SiteContext(
        summary=summary,
        business_name=_bounded_text(result.business_name, 160),
        products_or_services=_bounded_context_items(result.products_or_services),
        audiences=_bounded_context_items(result.audiences),
    )


def _bounded_context_items(items: Iterable[str]) -> list[str]:
    """Deduplicate model context labels within the selection-prompt budget."""
    return list(
        dict.fromkeys(
            bounded for item in items if (bounded := _bounded_text(item, 160)) is not None
        )
    )[:5]


def _bounded_text(value: str | None, maximum_length: int) -> str | None:
    """Return compact non-empty text or None."""
    if not value:
        return None
    compact = " ".join(value.split())[:maximum_length]
    return compact or None


def _build_candidates(
    homepage_url: str,
    homepage: PageSignals,
    sitemap_urls: Iterable[str],
    limit: int,
) -> list[PageCandidate]:
    by_url: dict[str, PageCandidate] = {
        homepage_url: PageCandidate(
            url=homepage_url,
            title=homepage.title,
            inferred_page_type="homepage",
            sources=[CandidateSource.HOMEPAGE],
        )
    }
    for link in homepage.internal_links:
        if len(by_url) >= limit:
            break
        source = CandidateSource.NAVIGATION
        existing = by_url.get(link.url)
        if existing is not None:
            if source not in existing.sources:
                existing.sources.append(source)
            continue
        by_url[link.url] = PageCandidate(
            url=link.url,
            navigation_label=link.anchor_text,
            inferred_page_type=_infer_page_type(link.url),
            sources=[source],
        )
    for sitemap_url in sitemap_urls:
        if len(by_url) >= limit:
            break
        existing = by_url.get(sitemap_url)
        if existing is not None:
            if CandidateSource.SITEMAP not in existing.sources:
                existing.sources.append(CandidateSource.SITEMAP)
            continue
        by_url[sitemap_url] = PageCandidate(
            url=sitemap_url,
            inferred_page_type=_infer_page_type(sitemap_url),
            sources=[CandidateSource.SITEMAP],
        )
    return list(by_url.values())[:limit]


def _infer_page_type(url: str) -> str:
    path = urlsplit(url).path.lower()
    labels = {
        "pricing": "pricing",
        "product": "product",
        "features": "product",
        "solutions": "solution",
        "services": "service",
        "blog": "article",
        "resources": "resource",
        "about": "about",
    }
    return next((label for token, label in labels.items() if token in path), "other")


def _validate_page_selection(
    result: PageSelectionResult,
    candidates: Iterable[PageCandidate],
    *,
    homepage_url: str,
    limit: int,
) -> list[SelectedPage]:
    allowed = {candidate.url for candidate in candidates}
    selected: list[SelectedPage] = []
    seen: set[str] = {homepage_url}
    if len(result.selected_pages) > limit:
        raise ValueError("Model selected more pages than allowed")
    for page in result.selected_pages:
        normalized = normalize_url(page.url)
        if normalized not in allowed or normalized in seen:
            raise ValueError("Model selected an unknown or duplicate URL")
        selected.append(page.model_copy(update={"url": normalized}))
        seen.add(normalized)
    return selected


def _attach_verified_link_statuses(
    page_signals: Mapping[str, PageSignals],
) -> dict[str, PageSignals]:
    statuses: dict[str, int] = {}
    for key, page in page_signals.items():
        if page.status_code is None:
            continue
        statuses[key] = page.status_code
        statuses[page.url] = page.status_code
        if page.final_url:
            statuses[page.final_url] = page.status_code
    updated: dict[str, PageSignals] = {}
    for key, page in page_signals.items():
        links = [
            link.model_copy(update={"target_status_code": statuses.get(link.url)})
            if link.url in statuses
            else link
            for link in page.internal_links
        ]
        updated[key] = page.model_copy(update={"internal_links": links})
    return updated


def _robots_permits(url: str, robots: RobotsSignals | None) -> bool:
    """Apply the most specific observed wildcard/Googlebot robots rule."""
    if robots is None or robots.available is not True:
        return True
    path = urlsplit(url).path or "/"
    matching_rules = []
    for rule in robots.rules:
        if rule.user_agent not in {"*", "googlebot", "technicalseoauditagent"}:
            continue
        if not rule.path:
            continue
        expression = re.escape(rule.path).replace(r"\*", ".*")
        if expression.endswith(r"\$"):
            expression = f"{expression[:-2]}$"
        if re.match(expression, path):
            matching_rules.append(rule)
    if not matching_rules:
        return True
    longest = max(len(rule.path) for rule in matching_rules)
    most_specific = [rule for rule in matching_rules if len(rule.path) == longest]
    return any(rule.directive is RobotsDirective.ALLOW for rule in most_specific)


def _audit_scope(state: AuditState, findings: Iterable[Finding]) -> AuditScope:
    investigation_fetches = sum(
        1
        for finding in findings
        for evidence in finding.evidence
        if evidence.signal.startswith("investigation.")
    )
    return AuditScope(
        candidate_count=len(state["candidates"]),
        selected_pages=state["selected_pages"],
        inspected_urls=sorted(state["page_signals"]),
        pagespeed_urls=sorted(state["performance"]),
        investigation_rounds_used=state["investigation_count"],
        investigation_fetches_used=investigation_fetches,
    )


def _performance_observations(state: AuditState) -> list[str]:
    observations: list[str] = []
    for url, summary in state["performance"].items():
        if not summary.available:
            observations.append(
                f"Performance data was unavailable for {url}: "
                f"{summary.collection_error or 'unknown provider error'}."
            )
        elif summary.performance_score is not None:
            observations.append(
                f"{url} received a mobile Lighthouse performance score of "
                f"{summary.performance_score:.2f}; this is laboratory evidence."
            )
        if summary.field_metrics:
            observations.append(f"Real-user field metrics were available for {url}.")
    return observations


def _ai_discoverability_observations(state: AuditState) -> list[str]:
    observations: list[str] = []
    identity_urls = sorted(
        {
            page.url
            for page in state["page_signals"].values()
            for block in page.json_ld
            if block.valid and {"Organization", "WebSite"}.intersection(block.schema_types)
        }
    )
    if identity_urls:
        observations.append(
            "Public Organization or WebSite JSON-LD identity signals were observed on: "
            + ", ".join(identity_urls)
            + "."
        )
    else:
        observations.append(
            "No Organization or WebSite JSON-LD identity signal was observed in the sampled "
            "pages; this does not prove site-wide absence or imply a ranking effect."
        )

    site_signals = state["site_signals"]
    llms = site_signals.llms_txt if site_signals else None
    if llms is None or llms.available is None:
        observations.append(
            "llms.txt availability could not be determined; this is not a ranking conclusion."
        )
    elif llms.available:
        observations.append("A public llms.txt file was observed; no ranking effect is inferred.")
    else:
        observations.append(
            "No llms.txt file was observed. This is informational because llms.txt is an "
            "experimental convention, not an established ranking requirement."
        )
    return observations


def _fallback_summary(findings: Iterable[Finding]) -> str:
    findings_list = list(findings)
    verified = sum(finding.status is FindingStatus.VERIFIED for finding in findings_list)
    unresolved = sum(
        finding.status in {FindingStatus.NEEDS_REVIEW, FindingStatus.OBSERVED}
        for finding in findings_list
    )
    return (
        f"The sampled audit produced {verified} verified finding(s) and "
        f"{unresolved} unresolved finding(s)."
    )


def _merge_strings(existing: Iterable[str], additions: Iterable[str]) -> list[str]:
    return list(dict.fromkeys([*existing, *(item for item in additions if item)]))


def _json_data(value: object) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
