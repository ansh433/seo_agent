"""Offline tests for deterministic technical audit checks."""

import pytest

from seo_agent.audit.checks import (
    BROKEN_INTERNAL_LINK,
    CANONICAL_MISMATCH,
    DUPLICATE_META_DESCRIPTION,
    DUPLICATE_TITLE,
    HTTP_REDIRECT,
    HTTP_RESPONSE_ERROR,
    INVALID_JSON_LD,
    MISSING_CANONICAL,
    MISSING_H1,
    MISSING_LLMS_TXT,
    MISSING_META_DESCRIPTION,
    MISSING_TITLE,
    MULTIPLE_H1,
    NOINDEX_DIRECTIVE,
    ROBOTS_BLOCKED,
    apply_evaluation_safeguards,
    build_remediation_briefs,
    consolidate_findings,
    prioritize_findings,
    run_deterministic_checks,
    stable_finding_id,
    validate_finding_evidence,
)
from seo_agent.audit.models import (
    CollectionStatus,
    Evidence,
    Finding,
    FindingEvaluation,
    FindingStatus,
    HeadingSignal,
    InternalLinkSignal,
    JsonLdSignal,
    PageSignals,
    RedirectHop,
    RobotsDirective,
    RobotsRule,
    RobotsSignals,
    Severity,
    SiteFileSignals,
    SitemapSignals,
    SiteSignals,
)

pytestmark = pytest.mark.unit


def _page(url: str, **updates: object) -> PageSignals:
    values: dict[str, object] = {
        "url": url,
        "status_code": 200,
        "final_url": url,
        "title": f"Title for {url}",
        "meta_description": f"Description for {url}",
        "canonical_url": url,
        "headings": [HeadingSignal(level=1, text="Primary heading")],
        "collection_status": CollectionStatus.COMPLETE,
    }
    values.update(updates)
    return PageSignals.model_validate(values)


def _healthy_site(page_urls: list[str]) -> SiteSignals:
    return SiteSignals(
        robots=RobotsSignals(
            url="https://example.com/robots.txt",
            available=True,
            status_code=200,
        ),
        sitemaps=[
            SitemapSignals(
                url="https://example.com/sitemap.xml",
                available=True,
                status_code=200,
                page_urls=page_urls,
            )
        ],
        llms_txt=SiteFileSignals(
            url="https://example.com/llms.txt",
            available=True,
            status_code=200,
        ),
    )


def _finding(issue_type: str, url: str = "https://example.com/a") -> Finding:
    return Finding(
        id=stable_finding_id(issue_type, [url]),
        issue_type=issue_type,
        title="Test finding",
        observation="Observed by a deterministic check.",
        affected_urls=[url],
        evidence=[Evidence(source_url=url, signal="http.status_code", observed_value=500)],
    )


def test_healthy_page_has_no_actionable_or_structured_data_findings() -> None:
    url = "https://example.com/"

    findings = run_deterministic_checks([_page(url)], _healthy_site([url]))

    assert findings == []


def test_single_permanent_slash_redirect_is_not_an_audit_finding() -> None:
    source_url = "https://example.com/blog/"
    page = _page(
        source_url,
        final_url="https://example.com/blog",
        redirect_chain=[
            RedirectHop(
                source_url=source_url,
                status_code=308,
                destination_url="https://example.com/blog",
            )
        ],
    )

    findings = run_deterministic_checks([page], _healthy_site([source_url]))

    assert HTTP_REDIRECT not in {finding.issue_type for finding in findings}


def test_path_changing_or_temporary_redirects_remain_findings() -> None:
    permanent_move = _page(
        "https://example.com/old-page",
        final_url="https://example.com/new-page",
        redirect_chain=[
            RedirectHop(
                source_url="https://example.com/old-page",
                status_code=301,
                destination_url="https://example.com/new-page",
            )
        ],
    )
    temporary_move = _page(
        "https://example.com/pricing/",
        final_url="https://example.com/pricing",
        redirect_chain=[
            RedirectHop(
                source_url="https://example.com/pricing/",
                status_code=302,
                destination_url="https://example.com/pricing",
            )
        ],
    )

    findings = run_deterministic_checks([permanent_move, temporary_move])

    redirect = next(finding for finding in findings if finding.issue_type == HTTP_REDIRECT)
    assert redirect.affected_urls == [
        "https://example.com/old-page",
        "https://example.com/pricing/",
    ]


def test_defective_pages_produce_evidence_backed_findings() -> None:
    first_url = "https://example.com/a"
    second_url = "https://example.com/b"
    pages = [
        _page(
            first_url,
            status_code=500,
            title="Repeated title",
            meta_description="Repeated description",
            canonical_url="https://example.com/preferred",
            meta_robots=["noindex, follow"],
            headings=[],
            json_ld=[JsonLdSignal(block_index=0, valid=False, error="invalid JSON")],
            internal_links=[
                InternalLinkSignal(url="https://example.com/dead", target_status_code=404),
                InternalLinkSignal(
                    url="https://example.com/unverified",
                    verification_error="timeout",
                ),
            ],
        ),
        _page(
            second_url,
            title=" repeated   TITLE ",
            meta_description=" repeated description ",
            canonical_url=None,
            headings=[HeadingSignal(level=1, text="One"), HeadingSignal(level=1, text="Two")],
        ),
    ]
    site = _healthy_site([first_url, second_url])
    site = site.model_copy(
        update={
            "robots": RobotsSignals(
                url="https://example.com/robots.txt",
                available=True,
                status_code=200,
                rules=[
                    RobotsRule(
                        user_agent="*",
                        directive=RobotsDirective.DISALLOW,
                        path="/a",
                    )
                ],
            )
        }
    )

    findings = run_deterministic_checks(pages, site)
    issue_types = {finding.issue_type for finding in findings}

    assert {
        HTTP_RESPONSE_ERROR,
        ROBOTS_BLOCKED,
        NOINDEX_DIRECTIVE,
        CANONICAL_MISMATCH,
        MISSING_CANONICAL,
        DUPLICATE_TITLE,
        DUPLICATE_META_DESCRIPTION,
        MISSING_H1,
        MULTIPLE_H1,
        INVALID_JSON_LD,
        BROKEN_INTERNAL_LINK,
    } <= issue_types
    assert all(finding.evidence for finding in findings)
    assert all(validate_finding_evidence(finding) for finding in findings)
    broken = next(finding for finding in findings if finding.issue_type == BROKEN_INTERNAL_LINK)
    assert broken.affected_urls == [first_url]
    assert broken.evidence[0].observed_value == {
        "target_url": "https://example.com/dead",
        "status_code": 404,
    }


def test_failed_collection_is_not_treated_as_element_absence() -> None:
    url = "https://example.com/failed"
    page = _page(
        url,
        status_code=None,
        title=None,
        meta_description=None,
        canonical_url=None,
        headings=[],
        collection_status=CollectionStatus.FAILED,
        collection_error="timeout",
    )
    site = SiteSignals(
        llms_txt=SiteFileSignals(
            url="https://example.com/llms.txt",
            available=False,
            collection_error="timeout",
        ),
        sitemaps=[
            SitemapSignals(
                url="https://example.com/sitemap.xml",
                available=False,
                collection_error="timeout",
            )
        ],
    )

    findings = run_deterministic_checks([page], site)

    assert findings == []


def test_absent_structured_data_is_not_actionable_and_missing_llms_is_informational() -> None:
    url = "https://example.com/"
    site = _healthy_site([url]).model_copy(
        update={
            "llms_txt": SiteFileSignals(
                url="https://example.com/llms.txt",
                available=False,
                status_code=404,
            )
        }
    )

    findings = run_deterministic_checks([_page(url, json_ld=[])], site)

    assert [finding.issue_type for finding in findings] == [MISSING_LLMS_TXT]
    verified = apply_evaluation_safeguards(
        findings,
        [
            FindingEvaluation(
                finding_id=findings[0].id,
                status=FindingStatus.VERIFIED,
                severity=Severity.CRITICAL,
                confidence=1.0,
                rationale="The 404 response verifies absence.",
            )
        ],
    )
    assert verified[0].severity is Severity.INFORMATIONAL
    assert build_remediation_briefs(verified) == []


def test_intentional_or_ambiguous_directives_remain_observations() -> None:
    url = "https://example.com/private"
    page = _page(
        url,
        meta_robots=["noindex"],
        canonical_url="https://example.com/public",
    )
    site = _healthy_site([url]).model_copy(
        update={
            "robots": RobotsSignals(
                url="https://example.com/robots.txt",
                available=True,
                rules=[
                    RobotsRule(
                        user_agent="Googlebot",
                        directive=RobotsDirective.DISALLOW,
                        path="/private",
                    )
                ],
            )
        }
    )

    findings = run_deterministic_checks([page], site)

    assert {finding.issue_type for finding in findings} >= {
        ROBOTS_BLOCKED,
        NOINDEX_DIRECTIVE,
        CANONICAL_MISMATCH,
    }
    assert all(finding.status is FindingStatus.OBSERVED for finding in findings)
    assert all(finding.severity is None for finding in findings)
    assert build_remediation_briefs(findings) == []


def test_consolidation_preserves_urls_evidence_and_stable_ids() -> None:
    first = _finding(HTTP_RESPONSE_ERROR, "https://example.com/a")
    second = _finding(HTTP_RESPONSE_ERROR, "https://example.com/b")
    different_type = _finding(MISSING_TITLE, "https://example.com/a").model_copy(
        update={
            "evidence": [
                Evidence(
                    source_url="https://example.com/a",
                    signal="html.title",
                    observed_value="absent",
                )
            ]
        }
    )

    forward = consolidate_findings([first, different_type, second])
    reverse = consolidate_findings([second, first, different_type])

    assert [finding.issue_type for finding in forward] == [
        HTTP_RESPONSE_ERROR,
        MISSING_TITLE,
    ]
    assert [finding.id for finding in forward] == [finding.id for finding in reverse]
    response = forward[0]
    assert response.affected_urls == ["https://example.com/a", "https://example.com/b"]
    assert len(response.evidence) == 2


def test_evidence_safeguards_demote_unsupported_verification_and_cap_severity() -> None:
    valid = _finding(BROKEN_INTERNAL_LINK).model_copy(
        update={
            "evidence": [
                Evidence(
                    source_url="https://example.com/a",
                    signal="link.target_status_code",
                    observed_value={"target_url": "https://example.com/dead", "status_code": 404},
                )
            ]
        }
    )
    unsupported = _finding(MISSING_TITLE).model_copy(
        update={
            "evidence": [
                Evidence(
                    source_url="https://example.com/other",
                    signal="html.title",
                    observed_value="absent",
                )
            ]
        }
    )
    evaluations = [
        FindingEvaluation(
            finding_id=finding.id,
            status=FindingStatus.VERIFIED,
            severity=Severity.CRITICAL,
            confidence=0.95,
            rationale="Evaluator requested verification.",
        )
        for finding in [valid, unsupported]
    ]

    results = apply_evaluation_safeguards([valid, unsupported], evaluations)

    assert results[0].status is FindingStatus.VERIFIED
    assert results[0].severity is Severity.MEDIUM
    assert results[1].status is FindingStatus.NEEDS_REVIEW
    assert results[1].severity is None
    assert results[1].confidence == 0.5
    assert not validate_finding_evidence(unsupported)


def test_prioritization_and_remediation_only_use_verified_actionable_findings() -> None:
    high = _finding(HTTP_RESPONSE_ERROR).model_copy(
        update={"status": FindingStatus.VERIFIED, "confidence": 1.0}
    )
    low = _finding(MISSING_TITLE, "https://example.com/b").model_copy(
        update={
            "status": FindingStatus.VERIFIED,
            "confidence": 0.9,
            "evidence": [
                Evidence(
                    source_url="https://example.com/b",
                    signal="html.title",
                    observed_value="absent",
                )
            ],
        }
    )
    unresolved = _finding(MISSING_META_DESCRIPTION, "https://example.com/c").model_copy(
        update={
            "evidence": [
                Evidence(
                    source_url="https://example.com/c",
                    signal="html.meta_description",
                    observed_value="absent",
                )
            ]
        }
    )

    prioritized = prioritize_findings([unresolved, low, high])
    briefs = build_remediation_briefs(prioritized)

    assert [finding.issue_type for finding in prioritized] == [
        HTTP_RESPONSE_ERROR,
        MISSING_TITLE,
        MISSING_META_DESCRIPTION,
    ]
    assert [brief.finding_id for brief in briefs] == [high.id, low.id]
    assert all(brief.recommended_changes and brief.verification_steps for brief in briefs)
