"""Compact, deterministic extraction from fetched website resources."""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Mapping, Sequence
from typing import Protocol, cast
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, ParseError

from bs4 import BeautifulSoup, Tag
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring as safe_xml_fromstring
from pydantic import JsonValue

from seo_agent.audit.models import (
    CollectionStatus,
    HeadingSignal,
    InternalLinkSignal,
    JsonLdSignal,
    PageSignals,
    RedirectHop,
    RobotsDirective,
    RobotsRule,
    RobotsSignals,
    SitemapSignals,
    SiteScope,
)
from seo_agent.audit.url_policy import UrlPolicyError, is_in_scope, normalize_url

_WHITESPACE = re.compile(r"\s+")
_DEFAULT_MAX_INTERNAL_LINKS = 100
_DEFAULT_MAX_CONTEXT_CHARS = 1_200
_DEFAULT_MAX_ROBOTS_RULES = 500
_DEFAULT_MAX_SITEMAP_URLS = 500
_MAX_JSON_LD_PROPERTIES = 12
_MAX_JSON_LD_OBJECTS = 500
_JSON_LD_PROPERTIES = frozenset(
    {
        "applicationCategory",
        "articleSection",
        "brand",
        "category",
        "dateModified",
        "datePublished",
        "inLanguage",
        "isAccessibleForFree",
        "operatingSystem",
        "priceRange",
        "sameAs",
    }
)


class FetchedResourceLike(Protocol):
    """Minimal structural interface accepted from HTTP provider boundaries."""

    @property
    def requested_url(self) -> str: ...

    @property
    def final_url(self) -> str: ...

    @property
    def status_code(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...

    @property
    def redirect_chain(self) -> Sequence[RedirectHop]: ...

    def text(self) -> str:
        """Return the decoded response body."""
        ...


def extract_page_signals(
    resource: FetchedResourceLike | None = None,
    *,
    url: str | None = None,
    html: str | bytes | None = None,
    status_code: int | None = None,
    headers: Mapping[str, str] | None = None,
    final_url: str | None = None,
    redirect_chain: Sequence[RedirectHop] | None = None,
    scope: SiteScope | None = None,
    collection_error: str | None = None,
    body_truncated: bool = False,
    max_internal_links: int = _DEFAULT_MAX_INTERNAL_LINKS,
    max_context_chars: int = _DEFAULT_MAX_CONTEXT_CHARS,
) -> PageSignals:
    """Extract bounded page evidence without retaining the full response body."""
    if max_internal_links < 0 or max_context_chars < 0:
        raise ValueError("Extraction limits must not be negative")

    if resource is not None:
        url = url or resource.requested_url
        final_url = final_url or resource.final_url
        status_code = resource.status_code if status_code is None else status_code
        headers = resource.headers if headers is None else headers
        html = resource.text() if html is None else html
        redirect_chain = resource.redirect_chain if redirect_chain is None else redirect_chain

    if url is None:
        raise ValueError("A source URL is required")
    source_url = _best_effort_normalize(url)
    normalized_final_url = _best_effort_normalize(final_url or source_url)
    normalized_redirect_chain = list(redirect_chain or ())
    header_values = _lowercase_headers(headers or {})
    content_type = _header_value(header_values, "content-type")
    x_robots_tag = _parse_directives(_header_value(header_values, "x-robots-tag") or "")

    if isinstance(html, bytes):
        html_text = html.decode("utf-8", errors="replace")
    else:
        html_text = html

    extraction_notes: list[str] = []
    if collection_error:
        extraction_notes.append(collection_error)
    if body_truncated:
        extraction_notes.append("Response body was truncated before extraction")
    if html_text is None or not html_text.strip():
        if html_text is not None:
            extraction_notes.append("Response contained no HTML content")
        status = (
            CollectionStatus.FAILED
            if collection_error or html_text is None
            else CollectionStatus.PARTIAL
        )
        return PageSignals(
            url=source_url,
            status_code=status_code,
            final_url=normalized_final_url,
            redirect_chain=normalized_redirect_chain,
            content_type=content_type,
            x_robots_tag=x_robots_tag,
            collection_status=status,
            collection_error=_join_notes(extraction_notes),
        )

    soup = BeautifulSoup(html_text, "html.parser")
    title = _tag_text(soup.find("title"))
    description = _meta_content(soup, "description")
    canonical_url = _canonical_url(soup, normalized_final_url, extraction_notes)
    meta_robots = _meta_robots(soup)
    headings = _headings(soup)
    internal_links = _internal_links(
        soup,
        normalized_final_url,
        scope=scope,
        limit=max_internal_links,
    )
    json_ld = _json_ld_signals(soup)
    page_context = _meaningful_context(soup, max_chars=max_context_chars)

    status = CollectionStatus.COMPLETE
    if extraction_notes or (content_type is not None and "html" not in content_type.lower()):
        status = CollectionStatus.PARTIAL
        if content_type is not None and "html" not in content_type.lower():
            extraction_notes.append("Response content type was not HTML")

    return PageSignals(
        url=source_url,
        status_code=status_code,
        final_url=normalized_final_url,
        redirect_chain=normalized_redirect_chain,
        content_type=content_type,
        title=title,
        meta_description=description,
        canonical_url=canonical_url,
        meta_robots=meta_robots,
        x_robots_tag=x_robots_tag,
        headings=headings,
        internal_links=internal_links,
        json_ld=json_ld,
        page_context=page_context,
        collection_status=status,
        collection_error=_join_notes(extraction_notes),
    )


def parse_robots_txt(
    text: str | bytes | None,
    *,
    url: str,
    status_code: int | None = 200,
    collection_error: str | None = None,
    max_rules: int = _DEFAULT_MAX_ROBOTS_RULES,
    max_sitemaps: int = 20,
) -> RobotsSignals:
    """Parse bounded robots rules and sitemap declarations."""
    if max_rules < 0 or max_sitemaps < 0:
        raise ValueError("Robots limits must not be negative")
    source_url = _best_effort_normalize(url)
    available = _resource_available(status_code, collection_error)
    if text is None or available is not True:
        return RobotsSignals(
            url=source_url,
            available=available,
            status_code=status_code,
            collection_error=collection_error,
        )

    robots_text = text.decode("utf-8-sig", errors="replace") if isinstance(text, bytes) else text
    current_agents: list[str] = []
    group_has_rules = False
    rules: list[RobotsRule] = []
    sitemap_urls: list[str] = []
    parse_notes: list[str] = []

    for raw_line in robots_text.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip()
        if not line:
            current_agents = []
            group_has_rules = False
            continue
        if ":" not in line:
            continue
        field, raw_value = line.split(":", maxsplit=1)
        directive = field.strip().lower()
        value = raw_value.strip()

        if directive == "user-agent":
            if not value:
                continue
            if group_has_rules:
                current_agents = []
                group_has_rules = False
            normalized_agent = value.lower()
            if normalized_agent not in current_agents:
                current_agents.append(normalized_agent)
            continue

        if directive in {RobotsDirective.ALLOW.value, RobotsDirective.DISALLOW.value}:
            if not current_agents:
                continue
            group_has_rules = True
            if len(rules) >= max_rules:
                if "Robots rules were truncated" not in parse_notes:
                    parse_notes.append("Robots rules were truncated")
                continue
            rule_directive = RobotsDirective(directive)
            for user_agent in current_agents:
                if len(rules) >= max_rules:
                    if "Robots rules were truncated" not in parse_notes:
                        parse_notes.append("Robots rules were truncated")
                    break
                rules.append(
                    RobotsRule(
                        user_agent=user_agent,
                        directive=rule_directive,
                        path=value,
                    )
                )
            continue

        if directive == "sitemap" and value:
            try:
                sitemap_url = normalize_url(value, base_url=source_url)
            except UrlPolicyError:
                parse_notes.append("Ignored an invalid sitemap URL")
                continue
            if sitemap_url not in sitemap_urls:
                if len(sitemap_urls) < max_sitemaps:
                    sitemap_urls.append(sitemap_url)
                elif "Sitemap declarations were truncated" not in parse_notes:
                    parse_notes.append("Sitemap declarations were truncated")

    return RobotsSignals(
        url=source_url,
        available=True,
        status_code=status_code,
        rules=rules,
        sitemap_urls=sitemap_urls,
        collection_error=collection_error,
        parse_error=_join_notes(parse_notes),
    )


def parse_sitemap_xml(
    xml: str | bytes | None,
    *,
    url: str,
    status_code: int | None = 200,
    collection_error: str | None = None,
    max_urls: int = _DEFAULT_MAX_SITEMAP_URLS,
) -> SitemapSignals:
    """Safely parse one bounded XML sitemap or sitemap index."""
    if max_urls < 0:
        raise ValueError("Sitemap limit must not be negative")
    source_url = _best_effort_normalize(url)
    available = _resource_available(status_code, collection_error)
    if xml is None or available is not True:
        return SitemapSignals(
            url=source_url,
            available=available,
            status_code=status_code,
            collection_error=collection_error,
        )

    try:
        root = safe_xml_fromstring(xml)
    except (DefusedXmlException, ParseError, ValueError) as exc:
        return SitemapSignals(
            url=source_url,
            available=True,
            status_code=status_code,
            collection_error=collection_error,
            parse_error=f"Sitemap XML could not be parsed ({type(exc).__name__})",
        )

    root_name = _local_name(root.tag).lower()
    if root_name not in {"urlset", "sitemapindex"}:
        return SitemapSignals(
            url=source_url,
            available=True,
            status_code=status_code,
            collection_error=collection_error,
            parse_error="XML root is not urlset or sitemapindex",
        )

    is_index = root_name == "sitemapindex"
    expected_entry = "sitemap" if is_index else "url"
    extracted_urls: list[str] = []
    invalid_locations = 0
    truncated = False

    for entry in root:
        if _local_name(entry.tag).lower() != expected_entry:
            continue
        location = _direct_child_text(entry, "loc")
        if location is None:
            continue
        try:
            normalized_location = normalize_url(location, base_url=source_url)
        except UrlPolicyError:
            invalid_locations += 1
            continue
        if normalized_location in extracted_urls:
            continue
        if len(extracted_urls) >= max_urls:
            truncated = True
            continue
        extracted_urls.append(normalized_location)

    parse_error = None
    if invalid_locations:
        parse_error = f"Ignored {invalid_locations} invalid sitemap location(s)"
    return SitemapSignals(
        url=source_url,
        available=True,
        status_code=status_code,
        is_index=is_index,
        page_urls=[] if is_index else extracted_urls,
        child_sitemap_urls=extracted_urls if is_index else [],
        truncated=truncated,
        collection_error=collection_error,
        parse_error=parse_error,
    )


def _lowercase_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(name).lower(): str(value).strip() for name, value in headers.items()}


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    value = headers.get(name)
    return value or None


def _tag_text(tag: Tag | None) -> str | None:
    if tag is None:
        return None
    return _clean_text(tag.get_text(" ", strip=True)) or None


def _meta_content(soup: BeautifulSoup, name: str) -> str | None:
    for tag in soup.find_all("meta"):
        tag_name = tag.get("name")
        if isinstance(tag_name, str) and tag_name.lower() == name:
            content = tag.get("content")
            if isinstance(content, str):
                return _clean_text(content) or None
    return None


def _canonical_url(
    soup: BeautifulSoup,
    base_url: str,
    extraction_notes: list[str],
) -> str | None:
    for tag in soup.find_all("link"):
        rel = tag.get("rel")
        rel_values = [rel] if isinstance(rel, str) else rel
        if not isinstance(rel_values, list) or "canonical" not in {
            str(value).lower() for value in rel_values
        }:
            continue
        href = tag.get("href")
        if not isinstance(href, str) or not href.strip():
            return None
        try:
            return normalize_url(href, base_url=base_url)
        except UrlPolicyError:
            extraction_notes.append("Canonical URL was invalid")
            return None
    return None


def _meta_robots(soup: BeautifulSoup) -> list[str]:
    directives: list[str] = []
    for tag in soup.find_all("meta"):
        name = tag.get("name")
        content = tag.get("content")
        if (
            isinstance(name, str)
            and name.lower() in {"robots", "googlebot", "bingbot"}
            and isinstance(content, str)
        ):
            directives.extend(_parse_directives(content))
    return list(dict.fromkeys(directives))


def _parse_directives(value: str) -> list[str]:
    directives: list[str] = []
    for raw_directive in value.split(","):
        directive = _clean_text(raw_directive).lower()
        if not directive:
            continue
        if ": " in directive:
            prefix, remainder = directive.split(": ", maxsplit=1)
            if prefix.endswith("bot") or prefix in {"robots", "*"}:
                directive = remainder
        if ":" in directive:
            directives.append(re.sub(r"\s*:\s*", ":", directive))
        else:
            directives.extend(directive.split())
    return list(dict.fromkeys(directives))


def _headings(soup: BeautifulSoup) -> list[HeadingSignal]:
    headings: list[HeadingSignal] = []
    for tag in soup.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE)):
        text = _tag_text(tag)
        if text:
            headings.append(HeadingSignal(level=int(tag.name[1]), text=text))
    return headings


def _internal_links(
    soup: BeautifulSoup,
    base_url: str,
    *,
    scope: SiteScope | None,
    limit: int,
) -> list[InternalLinkSignal]:
    links: list[InternalLinkSignal] = []
    seen: set[str] = set()
    base_parts = urlsplit(base_url)
    base_hostname = base_parts.hostname

    for tag in soup.find_all("a"):
        if len(links) >= limit:
            break
        href = tag.get("href")
        if not isinstance(href, str) or not href.strip() or href.lstrip().startswith("#"):
            continue
        try:
            target_url = normalize_url(href, base_url=base_url)
        except UrlPolicyError:
            continue
        target_hostname = urlsplit(target_url).hostname
        if scope is not None:
            internal = is_in_scope(target_url, scope)
        else:
            internal = target_hostname == base_hostname
        if not internal or target_url in seen:
            continue

        rel_value = tag.get("rel")
        if isinstance(rel_value, str):
            rel = rel_value.lower().split()
        elif isinstance(rel_value, list):
            rel = [str(value).lower() for value in rel_value]
        else:
            rel = []
        links.append(
            InternalLinkSignal(
                url=target_url,
                anchor_text=_tag_text(tag),
                rel=list(dict.fromkeys(rel)),
            )
        )
        seen.add(target_url)
    return links


def _json_ld_signals(soup: BeautifulSoup) -> list[JsonLdSignal]:
    signals: list[JsonLdSignal] = []
    block_index = 0
    for tag in soup.find_all("script"):
        script_type = tag.get("type")
        if not isinstance(script_type, str) or script_type.split(";", maxsplit=1)[
            0
        ].strip().lower() != ("application/ld+json"):
            continue
        current_block_index = block_index
        block_index += 1
        raw_json = tag.string if tag.string is not None else tag.get_text()
        try:
            value = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError) as exc:
            error = "Invalid JSON-LD"
            if isinstance(exc, json.JSONDecodeError):
                error = f"Invalid JSON-LD at line {exc.lineno}, column {exc.colno}"
            signals.append(JsonLdSignal(block_index=current_block_index, valid=False, error=error))
            continue
        if not isinstance(value, (dict, list)):
            signals.append(
                JsonLdSignal(
                    block_index=current_block_index,
                    valid=False,
                    error="JSON-LD root must be an object or array",
                )
            )
            continue

        objects = list(_json_ld_objects(value))
        primary = next((item for item in objects if "@type" in item), objects[0] if objects else {})
        signals.append(
            JsonLdSignal(
                block_index=current_block_index,
                valid=True,
                schema_types=_schema_types(objects),
                entity_id=_json_string(primary.get("@id")),
                entity_name=_json_string(primary.get("name")),
                entity_url=_json_string(primary.get("url")),
                properties=_compact_json_ld_properties(primary),
            )
        )
    return signals


def _json_ld_objects(value: object) -> Sequence[dict[str, object]]:
    objects: list[dict[str, object]] = []
    pending = [value]
    while pending and len(objects) < _MAX_JSON_LD_OBJECTS:
        current = pending.pop(0)
        if isinstance(current, dict):
            normalized = cast(dict[str, object], current)
            objects.append(normalized)
            pending.extend(normalized.values())
        elif isinstance(current, list):
            pending.extend(current)
    return objects


def _schema_types(objects: Sequence[dict[str, object]]) -> list[str]:
    schema_types: list[str] = []
    for item in objects:
        value = item.get("@type")
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate and candidate not in schema_types:
                schema_types.append(candidate)
    return schema_types


def _compact_json_ld_properties(value: Mapping[str, object]) -> dict[str, JsonValue]:
    properties: dict[str, JsonValue] = {}
    for name in sorted(_JSON_LD_PROPERTIES):
        if len(properties) >= _MAX_JSON_LD_PROPERTIES:
            break
        raw_value = value.get(name)
        compact_value = _compact_json_value(raw_value)
        if compact_value is not None:
            properties[name] = compact_value
    return properties


def _compact_json_value(value: object) -> JsonValue | None:
    if isinstance(value, (str, bool, int, float)):
        return value if not isinstance(value, str) else value[:300]
    if isinstance(value, list):
        scalars = [item[:300] if isinstance(item, str) else item for item in value[:20]]
        if all(isinstance(item, (str, bool, int, float)) or item is None for item in scalars):
            return scalars
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str):
            return {"name": name[:300]}
    return None


def _json_string(value: object) -> str | None:
    return value[:500] if isinstance(value, str) and value else None


def _meaningful_context(soup: BeautifulSoup, *, max_chars: int) -> str | None:
    if max_chars == 0:
        return None
    container = soup.find("main") or soup.find("article") or soup.body
    if not isinstance(container, Tag):
        return None
    for tag in container.find_all(
        [
            "script",
            "style",
            "noscript",
            "template",
            "svg",
            "header",
            "nav",
            "aside",
            "footer",
            "form",
        ]
    ):
        tag.decompose()
    chunks: list[str] = []
    for text in container.stripped_strings:
        cleaned = _clean_text(str(text))
        if cleaned and (not chunks or chunks[-1] != cleaned):
            chunks.append(cleaned)
    context = " ".join(chunks)
    if not context:
        return None
    if len(context) <= max_chars:
        return context
    if max_chars == 1:
        return "…"
    shortened = context[: max_chars - 1].rsplit(" ", maxsplit=1)[0]
    return f"{shortened}…" if shortened else f"{context[: max_chars - 1]}…"


def _resource_available(status_code: int | None, collection_error: str | None) -> bool | None:
    if collection_error is not None:
        return None
    if status_code is None:
        return None
    return 200 <= status_code < 300


def _direct_child_text(element: Element, child_name: str) -> str | None:
    for child in element:
        if _local_name(child.tag).lower() == child_name and child.text:
            cleaned = child.text.strip()
            return cleaned or None
    return None


def _local_name(name: str) -> str:
    return name.rsplit("}", maxsplit=1)[-1]


def _best_effort_normalize(url: str) -> str:
    try:
        return normalize_url(url)
    except UrlPolicyError:
        return url.strip()


def _clean_text(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


def _join_notes(notes: Collection[str]) -> str | None:
    unique_notes = list(dict.fromkeys(note for note in notes if note))
    return "; ".join(unique_notes) or None
