"""Deterministic, evidence-backed technical SEO checks."""

# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from pydantic import JsonValue

from seo_agent.audit.models import (
    CollectionStatus,
    Evidence,
    Finding,
    FindingEvaluation,
    FindingStatus,
    PageSignals,
    RemediationBrief,
    RobotsDirective,
    RobotsRule,
    RobotsSignals,
    Severity,
    SiteSignals,
)

HTTP_RESPONSE_ERROR = "http_response_error"
HTTP_REDIRECT = "http_redirect"
ROBOTS_BLOCKED = "robots_blocked"
NOINDEX_DIRECTIVE = "noindex_directive"
MISSING_CANONICAL = "missing_canonical"
CANONICAL_MISMATCH = "canonical_mismatch"
SITEMAP_UNAVAILABLE = "sitemap_unavailable"
SITEMAP_INVALID = "sitemap_invalid"
PAGE_MISSING_FROM_SITEMAP = "page_missing_from_sitemap"
SITEMAP_RESPONSE_INCONSISTENCY = "sitemap_response_inconsistency"
SITEMAP_INDEXING_INCONSISTENCY = "sitemap_indexing_inconsistency"
SITEMAP_CANONICAL_INCONSISTENCY = "sitemap_canonical_inconsistency"
SITEMAP_ROBOTS_INCONSISTENCY = "sitemap_robots_inconsistency"
MISSING_TITLE = "missing_title"
DUPLICATE_TITLE = "duplicate_title"
MISSING_META_DESCRIPTION = "missing_meta_description"
DUPLICATE_META_DESCRIPTION = "duplicate_meta_description"
MISSING_H1 = "missing_h1"
MULTIPLE_H1 = "multiple_h1"
INVALID_JSON_LD = "invalid_json_ld"
BROKEN_INTERNAL_LINK = "broken_internal_link"
MISSING_LLMS_TXT = "missing_llms_txt"

type PageSignalCollection = Mapping[str, PageSignals] | Iterable[PageSignals]

_ISSUE_DETAILS: dict[str, tuple[str, str]] = {
    HTTP_RESPONSE_ERROR: (
        "Unsuccessful HTTP response",
        "The sampled URL returned an unsuccessful HTTP status.",
    ),
    HTTP_REDIRECT: (
        "Redirect observed",
        "The requested sampled URL redirected before reaching its final response.",
    ),
    ROBOTS_BLOCKED: (
        "Page blocked by robots.txt",
        "A robots.txt rule applicable to Googlebot disallows the sampled URL.",
    ),
    NOINDEX_DIRECTIVE: (
        "Noindex directive observed",
        "The sampled URL contains an explicit noindex directive.",
    ),
    MISSING_CANONICAL: (
        "Canonical URL missing",
        "No canonical link was extracted from the complete page response.",
    ),
    CANONICAL_MISMATCH: (
        "Canonical URL differs from the fetched URL",
        "The declared canonical URL does not match the page's final fetched URL.",
    ),
    SITEMAP_UNAVAILABLE: (
        "Sitemap unavailable",
        "A discovered sitemap was explicitly observed as unavailable.",
    ),
    SITEMAP_INVALID: (
        "Sitemap could not be parsed",
        "A retrieved sitemap has a recorded parsing error.",
    ),
    PAGE_MISSING_FROM_SITEMAP: (
        "Sampled page absent from sitemap",
        "The sampled page was not present in the complete collected sitemap set.",
    ),
    SITEMAP_RESPONSE_INCONSISTENCY: (
        "Sitemap contains an unsuccessful URL",
        "A URL listed in a sitemap returned an unsuccessful response.",
    ),
    SITEMAP_INDEXING_INCONSISTENCY: (
        "Sitemap URL has a noindex directive",
        "A URL listed in a sitemap contains an explicit noindex directive.",
    ),
    SITEMAP_CANONICAL_INCONSISTENCY: (
        "Sitemap URL canonicalizes elsewhere",
        "A URL listed in a sitemap declares a different canonical URL.",
    ),
    SITEMAP_ROBOTS_INCONSISTENCY: (
        "Sitemap URL is blocked by robots.txt",
        "A URL listed in a sitemap is disallowed by an applicable robots.txt rule.",
    ),
    MISSING_TITLE: (
        "Page title missing",
        "No non-empty title was extracted from the complete page response.",
    ),
    DUPLICATE_TITLE: (
        "Duplicate page title",
        "Multiple sampled pages use the same normalized title.",
    ),
    MISSING_META_DESCRIPTION: (
        "Meta description missing",
        "No non-empty meta description was extracted from the complete page response.",
    ),
    DUPLICATE_META_DESCRIPTION: (
        "Duplicate meta description",
        "Multiple sampled pages use the same normalized meta description.",
    ),
    MISSING_H1: (
        "H1 heading missing",
        "No non-empty H1 heading was extracted from the complete page response.",
    ),
    MULTIPLE_H1: (
        "Multiple H1 headings",
        "The sampled page contains more than one non-empty H1 heading.",
    ),
    INVALID_JSON_LD: (
        "Invalid JSON-LD",
        "At least one JSON-LD block has an explicit parsing or validation error.",
    ),
    BROKEN_INTERNAL_LINK: (
        "Verified broken internal link",
        "An internal link target returned a verified unsuccessful HTTP status.",
    ),
    MISSING_LLMS_TXT: (
        "llms.txt not found",
        "The optional llms.txt file was explicitly observed as unavailable.",
    ),
}

_EXPECTED_SIGNALS: dict[str, frozenset[str]] = {
    HTTP_RESPONSE_ERROR: frozenset({"http.status_code"}),
    HTTP_REDIRECT: frozenset({"http.redirect_chain"}),
    ROBOTS_BLOCKED: frozenset({"robots.rule"}),
    NOINDEX_DIRECTIVE: frozenset({"html.meta_robots", "http.x_robots_tag"}),
    MISSING_CANONICAL: frozenset({"html.canonical"}),
    CANONICAL_MISMATCH: frozenset({"html.canonical"}),
    SITEMAP_UNAVAILABLE: frozenset({"sitemap.availability"}),
    SITEMAP_INVALID: frozenset({"sitemap.parse_error"}),
    PAGE_MISSING_FROM_SITEMAP: frozenset({"sitemap.membership"}),
    SITEMAP_RESPONSE_INCONSISTENCY: frozenset({"sitemap.http_status"}),
    SITEMAP_INDEXING_INCONSISTENCY: frozenset({"sitemap.indexing_directive"}),
    SITEMAP_CANONICAL_INCONSISTENCY: frozenset({"sitemap.canonical"}),
    SITEMAP_ROBOTS_INCONSISTENCY: frozenset({"sitemap.robots_rule"}),
    MISSING_TITLE: frozenset({"html.title"}),
    DUPLICATE_TITLE: frozenset({"html.title"}),
    MISSING_META_DESCRIPTION: frozenset({"html.meta_description"}),
    DUPLICATE_META_DESCRIPTION: frozenset({"html.meta_description"}),
    MISSING_H1: frozenset({"html.h1"}),
    MULTIPLE_H1: frozenset({"html.h1"}),
    INVALID_JSON_LD: frozenset({"html.json_ld"}),
    BROKEN_INTERNAL_LINK: frozenset({"link.target_status_code"}),
    MISSING_LLMS_TXT: frozenset({"llms_txt.availability"}),
}

_DEFAULT_SEVERITY: dict[str, Severity] = {
    HTTP_RESPONSE_ERROR: Severity.HIGH,
    HTTP_REDIRECT: Severity.LOW,
    ROBOTS_BLOCKED: Severity.HIGH,
    NOINDEX_DIRECTIVE: Severity.HIGH,
    MISSING_CANONICAL: Severity.LOW,
    CANONICAL_MISMATCH: Severity.MEDIUM,
    SITEMAP_UNAVAILABLE: Severity.LOW,
    SITEMAP_INVALID: Severity.MEDIUM,
    PAGE_MISSING_FROM_SITEMAP: Severity.LOW,
    SITEMAP_RESPONSE_INCONSISTENCY: Severity.HIGH,
    SITEMAP_INDEXING_INCONSISTENCY: Severity.HIGH,
    SITEMAP_CANONICAL_INCONSISTENCY: Severity.MEDIUM,
    SITEMAP_ROBOTS_INCONSISTENCY: Severity.HIGH,
    MISSING_TITLE: Severity.MEDIUM,
    DUPLICATE_TITLE: Severity.MEDIUM,
    MISSING_META_DESCRIPTION: Severity.LOW,
    DUPLICATE_META_DESCRIPTION: Severity.LOW,
    MISSING_H1: Severity.LOW,
    MULTIPLE_H1: Severity.LOW,
    INVALID_JSON_LD: Severity.LOW,
    BROKEN_INTERNAL_LINK: Severity.MEDIUM,
    MISSING_LLMS_TXT: Severity.INFORMATIONAL,
}

_SEVERITY_SCORE = {
    Severity.INFORMATIONAL: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def stable_finding_id(issue_type: str, affected_urls: Iterable[str]) -> str:
    """Create a reproducible ID that does not depend on evidence ordering."""
    normalized_urls = sorted({_normalize_url(url) for url in affected_urls})
    identity = json.dumps([issue_type, normalized_urls], separators=(",", ":"))
    digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
    return f"{issue_type}-{digest}"


def run_deterministic_checks(
    page_signals: PageSignalCollection,
    site_signals: SiteSignals | None = None,
) -> list[Finding]:
    """Return consolidated findings derived only from collected technical signals."""
    pages = sorted(_page_values(page_signals), key=lambda page: page.url)
    findings: list[Finding] = []

    for page in pages:
        findings.extend(_check_page(page, site_signals))

    findings.extend(_check_duplicate_metadata(pages, "title", DUPLICATE_TITLE))
    findings.extend(
        _check_duplicate_metadata(
            pages,
            "meta_description",
            DUPLICATE_META_DESCRIPTION,
        )
    )
    findings.extend(_check_site_files(site_signals))
    findings.extend(_check_sitemap_membership(pages, site_signals))
    return consolidate_findings(findings)


def consolidate_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Group repeated issue types without discarding affected URLs or evidence."""
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.issue_type].append(finding)

    consolidated: list[Finding] = []
    for issue_type, group in sorted(grouped.items()):
        affected_urls = sorted({url for finding in group for url in finding.affected_urls})
        evidence = _deduplicate_evidence(item for finding in group for item in finding.evidence)
        first = group[0]
        status = _consolidated_status(group)
        severities = [finding.severity for finding in group if finding.severity is not None]
        severity = max(severities, key=lambda item: _SEVERITY_SCORE[item]) if severities else None
        confidences = [finding.confidence for finding in group if finding.confidence is not None]
        consolidated.append(
            first.model_copy(
                update={
                    "id": stable_finding_id(issue_type, affected_urls),
                    "affected_urls": affected_urls,
                    "evidence": evidence,
                    "missing_information": sorted(
                        {item for finding in group for item in finding.missing_information}
                    ),
                    "status": status,
                    "severity": severity,
                    "confidence": min(confidences) if confidences else None,
                    "explanation": _first_present(group, "explanation"),
                    "potential_impact": _first_present(group, "potential_impact"),
                    "recommendation": _first_present(group, "recommendation"),
                    "evaluation_reason": _first_present(group, "evaluation_reason"),
                }
            )
        )
    return consolidated


def validate_finding_evidence(finding: Finding) -> bool:
    """Return whether evidence is non-empty, source-linked, and relevant to the issue."""
    if not finding.affected_urls or not finding.evidence:
        return False
    affected_urls = {_normalize_url(url) for url in finding.affected_urls if _is_http_url(url)}
    if len(affected_urls) != len(set(finding.affected_urls)):
        return False
    evidence_urls: set[str] = set()
    signals: set[str] = set()
    for evidence in finding.evidence:
        if not _is_http_url(evidence.source_url) or _is_empty_json_value(evidence.observed_value):
            return False
        evidence_urls.add(_normalize_url(evidence.source_url))
        signals.add(evidence.signal)
    if not affected_urls.issubset(evidence_urls):
        return False
    expected_signals = _EXPECTED_SIGNALS.get(finding.issue_type)
    return expected_signals is None or bool(signals & expected_signals)


def apply_evaluation_safeguards(
    findings: Iterable[Finding],
    evaluations: Iterable[FindingEvaluation] = (),
) -> list[Finding]:
    """Apply evaluator decisions without allowing unsupported verified conclusions."""
    evaluations_by_id = {evaluation.finding_id: evaluation for evaluation in evaluations}
    safeguarded: list[Finding] = []
    for finding in findings:
        evaluation = evaluations_by_id.get(finding.id)
        if evaluation is None:
            safeguarded.append(_enforce_existing_status(finding))
            continue

        status = evaluation.status
        severity = evaluation.severity
        confidence = evaluation.confidence
        reason = evaluation.rationale
        if status is FindingStatus.VERIFIED and not validate_finding_evidence(finding):
            status = FindingStatus.NEEDS_REVIEW
            severity = None
            confidence = min(confidence, 0.5)
            reason = f"{reason} Verification was prevented because evidence validation failed."
        elif status is FindingStatus.VERIFIED:
            severity = _bounded_severity(finding.issue_type, severity)
        else:
            severity = None

        safeguarded.append(
            finding.model_copy(
                update={
                    "status": status,
                    "severity": severity,
                    "confidence": confidence,
                    "evaluation_reason": reason,
                }
            )
        )
    return safeguarded


def prioritize_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Assign safe defaults to verified findings and return a stable priority order."""
    prepared = [_assign_default_severity(_enforce_existing_status(finding)) for finding in findings]
    status_order = {
        FindingStatus.VERIFIED: 0,
        FindingStatus.NEEDS_REVIEW: 1,
        FindingStatus.OBSERVED: 2,
        FindingStatus.DISMISSED: 3,
    }
    return sorted(
        prepared,
        key=lambda finding: (
            status_order[finding.status],
            -_SEVERITY_SCORE.get(finding.severity or Severity.INFORMATIONAL, 0),
            -len(finding.affected_urls),
            finding.id,
        ),
    )


def build_remediation_briefs(findings: Iterable[Finding]) -> list[RemediationBrief]:
    """Create implementation briefs only for verified, actionable findings."""
    briefs: list[RemediationBrief] = []
    for finding in prioritize_findings(findings):
        if finding.status is not FindingStatus.VERIFIED:
            continue
        if finding.severity is Severity.INFORMATIONAL:
            continue
        recommended_change, verification_step = _remediation_text(finding.issue_type)
        if finding.recommendation:
            recommended_change = finding.recommendation
        briefs.append(
            RemediationBrief(
                finding_id=finding.id,
                title=finding.title,
                affected_urls=finding.affected_urls,
                recommended_changes=[recommended_change],
                verification_steps=[verification_step],
                implementation_notes=[
                    "Confirm the intended indexing and canonical behavior before deployment."
                ]
                if finding.issue_type in {ROBOTS_BLOCKED, NOINDEX_DIRECTIVE, CANONICAL_MISMATCH}
                else [],
            )
        )
    return briefs


def _check_page(page: PageSignals, site_signals: SiteSignals | None) -> list[Finding]:
    findings: list[Finding] = []
    if page.status_code is not None and not 200 <= page.status_code < 400:
        findings.append(
            _finding(
                HTTP_RESPONSE_ERROR,
                [page.url],
                [
                    Evidence(
                        source_url=page.url,
                        signal="http.status_code",
                        observed_value=page.status_code,
                    )
                ],
            )
        )
    if page.redirect_chain and not _is_benign_slash_redirect(page):
        findings.append(
            _finding(
                HTTP_REDIRECT,
                [page.url],
                [
                    Evidence(
                        source_url=page.url,
                        signal="http.redirect_chain",
                        observed_value=[hop.model_dump(mode="json") for hop in page.redirect_chain],
                    )
                ],
            )
        )

    robots = site_signals.robots if site_signals else None
    blocking_rule = _blocking_robots_rule(page.url, robots)
    if blocking_rule is not None and robots is not None:
        findings.append(
            _finding(
                ROBOTS_BLOCKED,
                [page.url],
                [
                    Evidence(
                        source_url=page.url,
                        signal="robots.rule",
                        observed_value={
                            "robots_url": robots.url,
                            "user_agent": blocking_rule.user_agent,
                            "directive": blocking_rule.directive.value,
                            "path": blocking_rule.path,
                        },
                    )
                ],
            )
        )

    noindex_evidence = _noindex_evidence(page)
    if noindex_evidence:
        findings.append(_finding(NOINDEX_DIRECTIVE, [page.url], noindex_evidence))

    if page.collection_status is CollectionStatus.COMPLETE:
        canonical_url = page.canonical_url
        if not _has_text(canonical_url):
            findings.append(
                _finding(
                    MISSING_CANONICAL,
                    [page.url],
                    [
                        Evidence(
                            source_url=page.url, signal="html.canonical", observed_value="absent"
                        )
                    ],
                )
            )
        elif canonical_url is not None and not _same_url(canonical_url, page.final_url or page.url):
            findings.append(
                _finding(
                    CANONICAL_MISMATCH,
                    [page.url],
                    [
                        Evidence(
                            source_url=page.url,
                            signal="html.canonical",
                            observed_value={
                                "declared": canonical_url,
                                "fetched": page.final_url or page.url,
                            },
                        )
                    ],
                )
            )
        if not _has_text(page.title):
            findings.append(
                _finding(
                    MISSING_TITLE,
                    [page.url],
                    [Evidence(source_url=page.url, signal="html.title", observed_value="absent")],
                )
            )
        if not _has_text(page.meta_description):
            findings.append(
                _finding(
                    MISSING_META_DESCRIPTION,
                    [page.url],
                    [
                        Evidence(
                            source_url=page.url,
                            signal="html.meta_description",
                            observed_value="absent",
                        )
                    ],
                )
            )
        h1_texts = [
            heading.text
            for heading in page.headings
            if heading.level == 1 and _has_text(heading.text)
        ]
        if not h1_texts:
            findings.append(
                _finding(
                    MISSING_H1,
                    [page.url],
                    [Evidence(source_url=page.url, signal="html.h1", observed_value="absent")],
                )
            )
        elif len(h1_texts) > 1:
            findings.append(
                _finding(
                    MULTIPLE_H1,
                    [page.url],
                    [
                        Evidence(
                            source_url=page.url,
                            signal="html.h1",
                            observed_value=_json_strings(h1_texts),
                        )
                    ],
                )
            )

    invalid_blocks = [block for block in page.json_ld if not block.valid]
    if invalid_blocks:
        findings.append(
            _finding(
                INVALID_JSON_LD,
                [page.url],
                [
                    Evidence(
                        source_url=page.url,
                        signal="html.json_ld",
                        observed_value={
                            "block_index": block.block_index,
                            "error": block.error or "invalid",
                        },
                    )
                    for block in invalid_blocks
                ],
            )
        )

    broken_links = [
        link
        for link in page.internal_links
        if link.target_status_code is not None and link.target_status_code >= 400
    ]
    if broken_links:
        findings.append(
            _finding(
                BROKEN_INTERNAL_LINK,
                [page.url],
                [
                    Evidence(
                        source_url=page.url,
                        signal="link.target_status_code",
                        observed_value={
                            "target_url": link.url,
                            "status_code": link.target_status_code,
                        },
                    )
                    for link in broken_links
                ],
            )
        )
    return findings


def _check_duplicate_metadata(
    pages: Sequence[PageSignals],
    attribute: str,
    issue_type: str,
) -> list[Finding]:
    values: dict[str, list[tuple[PageSignals, str]]] = defaultdict(list)
    for page in pages:
        if page.collection_status is not CollectionStatus.COMPLETE:
            continue
        value = getattr(page, attribute)
        if not isinstance(value, str) or not value.strip():
            continue
        values[_normalize_text(value)].append((page, value))

    signal = f"html.{attribute}"
    findings: list[Finding] = []
    for duplicate_pages in values.values():
        if len(duplicate_pages) < 2:
            continue
        findings.append(
            _finding(
                issue_type,
                [page.url for page, _ in duplicate_pages],
                [
                    Evidence(source_url=page.url, signal=signal, observed_value=value)
                    for page, value in duplicate_pages
                ],
            )
        )
    return findings


def _check_site_files(site_signals: SiteSignals | None) -> list[Finding]:
    if site_signals is None:
        return []
    findings: list[Finding] = []
    for sitemap in site_signals.sitemaps:
        if sitemap.available is False and sitemap.collection_error is None:
            findings.append(
                _finding(
                    SITEMAP_UNAVAILABLE,
                    [sitemap.url],
                    [
                        Evidence(
                            source_url=sitemap.url,
                            signal="sitemap.availability",
                            observed_value={"available": False, "status_code": sitemap.status_code},
                        )
                    ],
                )
            )
        if sitemap.available is True and sitemap.parse_error:
            findings.append(
                _finding(
                    SITEMAP_INVALID,
                    [sitemap.url],
                    [
                        Evidence(
                            source_url=sitemap.url,
                            signal="sitemap.parse_error",
                            observed_value=sitemap.parse_error,
                        )
                    ],
                )
            )

    llms_txt = site_signals.llms_txt
    if llms_txt is not None and llms_txt.available is False and llms_txt.collection_error is None:
        findings.append(
            _finding(
                MISSING_LLMS_TXT,
                [llms_txt.url],
                [
                    Evidence(
                        source_url=llms_txt.url,
                        signal="llms_txt.availability",
                        observed_value={"available": False, "status_code": llms_txt.status_code},
                    )
                ],
            )
        )
    return findings


def _check_sitemap_membership(
    pages: Sequence[PageSignals],
    site_signals: SiteSignals | None,
) -> list[Finding]:
    if site_signals is None:
        return []
    usable_sitemaps = [
        sitemap
        for sitemap in site_signals.sitemaps
        if sitemap.available is True and sitemap.parse_error is None
    ]
    if not usable_sitemaps:
        return []

    sitemap_urls = {_normalize_url(url) for sitemap in usable_sitemaps for url in sitemap.page_urls}
    sitemap_source = usable_sitemaps[0].url
    membership_is_complete = (
        any(not sitemap.is_index for sitemap in usable_sitemaps)
        and all(not sitemap.truncated for sitemap in usable_sitemaps)
        and all(
            not sitemap.is_index or not sitemap.child_sitemap_urls for sitemap in usable_sitemaps
        )
    )
    findings: list[Finding] = []
    for page in pages:
        page_url = _normalize_url(page.final_url or page.url)
        is_listed = page_url in sitemap_urls or _normalize_url(page.url) in sitemap_urls
        if (
            not is_listed
            and membership_is_complete
            and page.collection_status is CollectionStatus.COMPLETE
            and page.status_code is not None
            and 200 <= page.status_code < 300
        ):
            findings.append(
                _finding(
                    PAGE_MISSING_FROM_SITEMAP,
                    [page.url],
                    [
                        Evidence(
                            source_url=page.url,
                            signal="sitemap.membership",
                            observed_value={"listed": False, "sitemap_url": sitemap_source},
                        )
                    ],
                )
            )
        if not is_listed:
            continue
        if page.status_code is not None and not 200 <= page.status_code < 300:
            findings.append(
                _finding(
                    SITEMAP_RESPONSE_INCONSISTENCY,
                    [page.url],
                    [
                        Evidence(
                            source_url=page.url,
                            signal="sitemap.http_status",
                            observed_value={
                                "sitemap_url": sitemap_source,
                                "status_code": page.status_code,
                            },
                        )
                    ],
                )
            )
        noindex = _noindex_evidence(page)
        if noindex:
            findings.append(
                _finding(
                    SITEMAP_INDEXING_INCONSISTENCY,
                    [page.url],
                    [
                        Evidence(
                            source_url=page.url,
                            signal="sitemap.indexing_directive",
                            observed_value={
                                "sitemap_url": sitemap_source,
                                "directives": [item.observed_value for item in noindex],
                            },
                        )
                    ],
                )
            )
        if page.canonical_url and not _same_url(page.canonical_url, page.final_url or page.url):
            findings.append(
                _finding(
                    SITEMAP_CANONICAL_INCONSISTENCY,
                    [page.url],
                    [
                        Evidence(
                            source_url=page.url,
                            signal="sitemap.canonical",
                            observed_value={
                                "sitemap_url": sitemap_source,
                                "canonical_url": page.canonical_url,
                            },
                        )
                    ],
                )
            )
        robots = site_signals.robots
        blocking_rule = _blocking_robots_rule(page.url, robots)
        if blocking_rule is not None and robots is not None:
            findings.append(
                _finding(
                    SITEMAP_ROBOTS_INCONSISTENCY,
                    [page.url],
                    [
                        Evidence(
                            source_url=page.url,
                            signal="sitemap.robots_rule",
                            observed_value={
                                "sitemap_url": sitemap_source,
                                "robots_url": robots.url,
                                "rule": blocking_rule.path,
                            },
                        )
                    ],
                )
            )
    return findings


def _finding(issue_type: str, affected_urls: list[str], evidence: list[Evidence]) -> Finding:
    title, observation = _ISSUE_DETAILS[issue_type]
    unique_urls = sorted(set(affected_urls))
    return Finding(
        id=stable_finding_id(issue_type, unique_urls),
        issue_type=issue_type,
        title=title,
        observation=observation,
        affected_urls=unique_urls,
        evidence=evidence,
    )


def _noindex_evidence(page: PageSignals) -> list[Evidence]:
    evidence: list[Evidence] = []
    if _contains_noindex(page.meta_robots):
        evidence.append(
            Evidence(
                source_url=page.url,
                signal="html.meta_robots",
                observed_value=_json_strings(page.meta_robots),
            )
        )
    if _contains_noindex(page.x_robots_tag):
        evidence.append(
            Evidence(
                source_url=page.url,
                signal="http.x_robots_tag",
                observed_value=_json_strings(page.x_robots_tag),
            )
        )
    return evidence


def _contains_noindex(directives: Sequence[str]) -> bool:
    words = {
        word for directive in directives for word in re.findall(r"[a-z]+", directive.casefold())
    }
    return "noindex" in words or "none" in words


def _json_strings(values: Sequence[str]) -> list[JsonValue]:
    return list(values)


def _blocking_robots_rule(url: str, robots: RobotsSignals | None) -> RobotsRule | None:
    if robots is None or robots.available is not True or robots.parse_error:
        return None
    googlebot_rules = [rule for rule in robots.rules if rule.user_agent.casefold() == "googlebot"]
    applicable_rules = googlebot_rules or [
        rule for rule in robots.rules if rule.user_agent.casefold() == "*"
    ]
    path = urlsplit(url).path or "/"
    if urlsplit(url).query:
        path = f"{path}?{urlsplit(url).query}"
    matching = [rule for rule in applicable_rules if _robots_path_matches(path, rule.path)]
    if not matching:
        return None
    winning_rule = max(
        matching,
        key=lambda rule: (
            len(rule.path.rstrip("$")),
            rule.directive is RobotsDirective.ALLOW,
        ),
    )
    return winning_rule if winning_rule.directive is RobotsDirective.DISALLOW else None


def _robots_path_matches(url_path: str, rule_path: str) -> bool:
    if not rule_path:
        return False
    anchored = rule_path.endswith("$")
    pattern = re.escape(rule_path.removesuffix("$")).replace(r"\*", ".*")
    expression = f"^{pattern}{'$' if anchored else ''}"
    return re.search(expression, url_path) is not None


def _page_values(page_signals: PageSignalCollection) -> list[PageSignals]:
    if isinstance(page_signals, Mapping):
        return list(page_signals.values())
    return list(page_signals)


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalize_url(url: str) -> str:
    parsed = urlsplit(url)
    scheme = parsed.scheme.casefold()
    hostname = (parsed.hostname or "").casefold()
    port = parsed.port
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        hostname = f"{hostname}:{port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, hostname, path, parsed.query, ""))


def _same_url(left: str, right: str) -> bool:
    return _normalize_url(left) == _normalize_url(right)


def _is_benign_slash_redirect(page: PageSignals) -> bool:
    """Ignore one same-origin permanent redirect that only adds or removes one slash."""
    if len(page.redirect_chain) != 1:
        return False
    redirect = page.redirect_chain[0]
    if redirect.status_code not in {301, 308}:
        return False
    source = urlsplit(redirect.source_url)
    destination = urlsplit(redirect.destination_url)
    if (
        source.scheme.casefold() != destination.scheme.casefold()
        or (source.hostname or "").casefold() != (destination.hostname or "").casefold()
        or source.port != destination.port
        or source.query != destination.query
    ):
        return False
    if source.path == destination.path:
        return False
    return source.path.rstrip("/") == destination.path.rstrip("/")


def _has_text(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_http_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _is_empty_json_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False


def _deduplicate_evidence(evidence: Iterable[Evidence]) -> list[Evidence]:
    unique: dict[str, Evidence] = {}
    for item in evidence:
        key = json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        unique[key] = item
    return [unique[key] for key in sorted(unique)]


def _consolidated_status(group: Sequence[Finding]) -> FindingStatus:
    statuses = {finding.status for finding in group}
    if statuses == {FindingStatus.DISMISSED}:
        return FindingStatus.DISMISSED
    if statuses == {FindingStatus.VERIFIED}:
        return FindingStatus.VERIFIED
    if FindingStatus.NEEDS_REVIEW in statuses or FindingStatus.DISMISSED in statuses:
        return FindingStatus.NEEDS_REVIEW
    return FindingStatus.OBSERVED


def _first_present(group: Sequence[Finding], attribute: str) -> str | None:
    for finding in group:
        value = getattr(finding, attribute)
        if isinstance(value, str) and value:
            return value
    return None


def _enforce_existing_status(finding: Finding) -> Finding:
    if finding.status is FindingStatus.VERIFIED and not validate_finding_evidence(finding):
        return finding.model_copy(
            update={
                "status": FindingStatus.NEEDS_REVIEW,
                "severity": None,
                "confidence": min(finding.confidence or 0.5, 0.5),
                "evaluation_reason": "Verification was prevented because evidence validation failed.",
            }
        )
    if finding.status is not FindingStatus.VERIFIED and finding.severity is not None:
        return finding.model_copy(update={"severity": None})
    return finding


def _assign_default_severity(finding: Finding) -> Finding:
    if finding.status is not FindingStatus.VERIFIED:
        return finding
    severity = _bounded_severity(finding.issue_type, finding.severity)
    return finding.model_copy(update={"severity": severity})


def _bounded_severity(issue_type: str, requested: Severity | None) -> Severity:
    maximum = _DEFAULT_SEVERITY.get(issue_type, Severity.MEDIUM)
    if requested is None or _SEVERITY_SCORE[requested] > _SEVERITY_SCORE[maximum]:
        return maximum
    return requested


def _remediation_text(issue_type: str) -> tuple[str, str]:
    changes = {
        HTTP_RESPONSE_ERROR: "Restore a successful response or remove/update references to the URL.",
        HTTP_REDIRECT: "Update internal references to the final URL and remove unnecessary redirect hops.",
        ROBOTS_BLOCKED: "Adjust the applicable robots.txt rule if the page is intended to be crawled.",
        NOINDEX_DIRECTIVE: "Remove the noindex directive if the page is intended for search indexing.",
        MISSING_CANONICAL: "Add a single absolute canonical link that reflects the preferred URL.",
        CANONICAL_MISMATCH: "Align the canonical target with the intended preferred version of the page.",
        SITEMAP_UNAVAILABLE: "Publish a valid XML sitemap at the advertised location.",
        SITEMAP_INVALID: "Correct the sitemap XML so it can be parsed reliably.",
        PAGE_MISSING_FROM_SITEMAP: "Add the preferred indexable page URL to the appropriate sitemap.",
        SITEMAP_RESPONSE_INCONSISTENCY: "Remove or replace sitemap URLs that do not return success responses.",
        SITEMAP_INDEXING_INCONSISTENCY: "Align sitemap membership with the page's intended indexing directive.",
        SITEMAP_CANONICAL_INCONSISTENCY: "List the preferred canonical URL in the sitemap.",
        SITEMAP_ROBOTS_INCONSISTENCY: "Align sitemap membership with robots.txt crawl permissions.",
        MISSING_TITLE: "Add a concise, page-specific HTML title.",
        DUPLICATE_TITLE: "Give each affected page a distinct, descriptive HTML title.",
        MISSING_META_DESCRIPTION: "Add a page-specific meta description.",
        DUPLICATE_META_DESCRIPTION: "Give each affected page a distinct meta description.",
        MISSING_H1: "Add one descriptive primary H1 heading.",
        MULTIPLE_H1: "Use one primary H1 and demote subordinate headings where appropriate.",
        INVALID_JSON_LD: "Correct or remove each invalid JSON-LD block.",
        BROKEN_INTERNAL_LINK: "Update or remove links whose targets return unsuccessful responses.",
    }
    verifications = {
        HTTP_RESPONSE_ERROR: "Request every affected URL and confirm a successful final response.",
        HTTP_REDIRECT: "Request each original URL and confirm the intended redirect path.",
        ROBOTS_BLOCKED: "Test each affected URL against the deployed robots.txt rules.",
        NOINDEX_DIRECTIVE: "Inspect rendered HTML and response headers for the intended indexing directive.",
        MISSING_CANONICAL: "Inspect the final HTML and confirm one absolute canonical link is present.",
        CANONICAL_MISMATCH: "Confirm each deployed canonical resolves to the intended preferred URL.",
        SITEMAP_UNAVAILABLE: "Fetch the sitemap and validate a successful XML response.",
        SITEMAP_INVALID: "Parse the deployed sitemap with an XML validator.",
        PAGE_MISSING_FROM_SITEMAP: "Fetch the sitemap and confirm each preferred URL is listed once.",
        SITEMAP_RESPONSE_INCONSISTENCY: "Fetch every changed sitemap URL and confirm a successful response.",
        SITEMAP_INDEXING_INCONSISTENCY: "Confirm sitemap URLs no longer carry unintended noindex directives.",
        SITEMAP_CANONICAL_INCONSISTENCY: "Compare each sitemap URL with its deployed canonical link.",
        SITEMAP_ROBOTS_INCONSISTENCY: "Confirm listed URLs are allowed by deployed robots.txt rules.",
        MISSING_TITLE: "Inspect each final HTML response and confirm a non-empty title.",
        DUPLICATE_TITLE: "Re-audit titles and confirm the affected pages are distinct.",
        MISSING_META_DESCRIPTION: "Inspect each final HTML response and confirm a non-empty description.",
        DUPLICATE_META_DESCRIPTION: "Re-audit descriptions and confirm the affected pages are distinct.",
        MISSING_H1: "Inspect each page and confirm one non-empty primary H1.",
        MULTIPLE_H1: "Inspect the heading outline and confirm the intended H1 structure.",
        INVALID_JSON_LD: "Parse every deployed JSON-LD block and confirm it is valid JSON.",
        BROKEN_INTERNAL_LINK: "Follow each changed internal link and confirm a successful target response.",
    }
    return (
        changes.get(issue_type, "Implement the verified recommendation for every affected URL."),
        verifications.get(
            issue_type, "Re-run the audit and confirm the finding no longer appears."
        ),
    )
