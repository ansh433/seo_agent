"""Single bounded LangGraph workflow for technical SEO audits."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel

from seo_agent.audit.errors import AuditError
from seo_agent.audit.extraction import extract_page_signals, parse_robots_txt, parse_sitemap_xml
from seo_agent.audit.models import (
    AuditState,
    CandidateSource,
    PageCandidate,
    PageSelectionResult,
    PageSignals,
    SelectedPage,
    SiteContext,
    SiteFileSignals,
    SitemapSignals,
    SiteSignals,
)
from seo_agent.audit.prompts import (
    SELECT_PAGES_SYSTEM_PROMPT,
    SELECT_PAGES_USER_PROMPT,
    UNDERSTAND_SITE_SYSTEM_PROMPT,
    UNDERSTAND_SITE_USER_PROMPT,
)
from seo_agent.audit.providers import AuditDependencies, FetchedResource
from seo_agent.audit.url_policy import UrlPolicy, UrlPolicyError, normalize_url

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
