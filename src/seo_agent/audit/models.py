"""Domain models shared by the SEO audit workflow."""

from enum import StrEnum
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class AuditModel(BaseModel):
    """Strict base model for internal and API audit contracts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class AuditLimits(AuditModel):
    """Central resource limits for one audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_candidates: PositiveInt = 30
    max_selected_pages: PositiveInt = 5
    max_pagespeed_pages: NonNegativeInt = 2
    max_investigation_rounds: NonNegativeInt = 1
    max_investigation_fetches: NonNegativeInt = 2
    max_sitemap_files: PositiveInt = 3
    max_sitemap_urls: PositiveInt = 500
    max_redirects: NonNegativeInt = 5
    max_retries: NonNegativeInt = 2
    request_timeout_seconds: Annotated[float, Field(gt=0.0)] = 10.0
    pagespeed_timeout_seconds: Annotated[float, Field(gt=0.0)] = 45.0
    max_response_bytes: PositiveInt = 2 * 1024 * 1024

    @model_validator(mode="after")
    def selected_pages_fit_candidates(self) -> "AuditLimits":
        """Keep the deep-inspection sample within the discovery sample."""
        if self.max_selected_pages > self.max_candidates:
            msg = "max_selected_pages cannot exceed max_candidates"
            raise ValueError(msg)
        return self


class SiteScope(AuditModel):
    """Normalized public-site boundary applied to every fetch."""

    requested_url: str = Field(min_length=1)
    homepage_url: str = Field(min_length=1)
    allowed_hosts: list[str] = Field(min_length=1)
    allowed_port: Annotated[int, Field(ge=1, le=65535)]


class SiteContext(AuditModel):
    """Compact contextual interpretation derived from homepage evidence."""

    summary: str
    business_name: str | None = None
    products_or_services: list[str] = Field(default_factory=list)
    audiences: list[str] = Field(default_factory=list)


class CandidateSource(StrEnum):
    """Where a page candidate was observed."""

    HOMEPAGE = "homepage"
    NAVIGATION = "navigation"
    SITEMAP = "sitemap"


class PageCandidate(AuditModel):
    """Lightweight discovered URL offered for page selection."""

    url: str = Field(min_length=1)
    title: str | None = None
    navigation_label: str | None = None
    inferred_page_type: str | None = None
    sources: list[CandidateSource] = Field(default_factory=list)


class SelectedPage(AuditModel):
    """A page selected for deep inspection with an auditable rationale."""

    url: str = Field(min_length=1)
    page_category: str = Field(min_length=1)
    selection_reason: str = Field(min_length=1)


class PageSelectionResult(AuditModel):
    """Structured output returned by the page-selection LLM task."""

    selected_pages: list[SelectedPage] = Field(default_factory=list)


class RobotsDirective(StrEnum):
    """Supported robots.txt rule directives."""

    ALLOW = "allow"
    DISALLOW = "disallow"


class RobotsRule(AuditModel):
    """One parsed robots.txt rule."""

    user_agent: str = Field(min_length=1)
    directive: RobotsDirective
    path: str


class RobotsSignals(AuditModel):
    """Compact robots.txt collection and parsing result."""

    url: str = Field(min_length=1)
    available: bool | None
    status_code: int | None = None
    rules: list[RobotsRule] = Field(default_factory=list)
    sitemap_urls: list[str] = Field(default_factory=list)
    collection_error: str | None = None
    parse_error: str | None = None


class SitemapSignals(AuditModel):
    """Compact sitemap or sitemap-index collection result."""

    url: str = Field(min_length=1)
    available: bool | None
    status_code: int | None = None
    is_index: bool = False
    page_urls: list[str] = Field(default_factory=list)
    child_sitemap_urls: list[str] = Field(default_factory=list)
    truncated: bool = False
    collection_error: str | None = None
    parse_error: str | None = None


class SiteFileSignals(AuditModel):
    """Availability of a small public site-level file."""

    url: str = Field(min_length=1)
    available: bool | None
    status_code: int | None = None
    collection_error: str | None = None


class SiteSignals(AuditModel):
    """Compact site-wide evidence collected separately from sampled pages."""

    robots: RobotsSignals | None = None
    sitemaps: list[SitemapSignals] = Field(default_factory=list)
    llms_txt: SiteFileSignals | None = None


class RedirectHop(AuditModel):
    """One validated redirect hop observed during collection."""

    source_url: str = Field(min_length=1)
    status_code: int
    destination_url: str = Field(min_length=1)


class HeadingSignal(AuditModel):
    """One extracted HTML heading."""

    level: Annotated[int, Field(ge=1, le=6)]
    text: str


class InternalLinkSignal(AuditModel):
    """Normalized internal link and optional target verification result."""

    url: str = Field(min_length=1)
    anchor_text: str | None = None
    rel: list[str] = Field(default_factory=list)
    target_status_code: int | None = None
    verification_error: str | None = None


class JsonLdSignal(AuditModel):
    """Compact normalized information from one JSON-LD block."""

    block_index: NonNegativeInt
    valid: bool
    schema_types: list[str] = Field(default_factory=list)
    entity_id: str | None = None
    entity_name: str | None = None
    entity_url: str | None = None
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    error: str | None = None


class CollectionStatus(StrEnum):
    """Whether technical extraction produced a complete page record."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class PageSignals(AuditModel):
    """Normalized technical signals retained for one deeply inspected page."""

    url: str = Field(min_length=1)
    status_code: int | None = None
    final_url: str | None = None
    redirect_chain: list[RedirectHop] = Field(default_factory=list)
    content_type: str | None = None
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    meta_robots: list[str] = Field(default_factory=list)
    x_robots_tag: list[str] = Field(default_factory=list)
    headings: list[HeadingSignal] = Field(default_factory=list)
    internal_links: list[InternalLinkSignal] = Field(default_factory=list)
    json_ld: list[JsonLdSignal] = Field(default_factory=list)
    page_context: str | None = None
    collection_status: CollectionStatus
    collection_error: str | None = None


class PageSpeedStrategy(StrEnum):
    """Supported PageSpeed device strategies."""

    MOBILE = "mobile"
    DESKTOP = "desktop"


class PageSpeedMetric(AuditModel):
    """One compact PageSpeed metric."""

    name: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)


class PageSpeedSummary(AuditModel):
    """Compact lab and optional field performance evidence for one URL."""

    url: str = Field(min_length=1)
    strategy: PageSpeedStrategy = PageSpeedStrategy.MOBILE
    available: bool
    performance_score: Probability | None = None
    lab_metrics: list[PageSpeedMetric] = Field(default_factory=list)
    field_metrics: list[PageSpeedMetric] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    collection_error: str | None = None


class FindingStatus(StrEnum):
    """Evidence-evaluation lifecycle for a finding."""

    OBSERVED = "observed"
    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    DISMISSED = "dismissed"


class Severity(StrEnum):
    """Prioritization assigned only after contextual evaluation."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Evidence(AuditModel):
    """One source-linked observation supporting a finding."""

    source_url: str = Field(min_length=1)
    signal: str = Field(min_length=1)
    observed_value: JsonValue


class Finding(AuditModel):
    """Consolidated observation, interpretation, and evaluation result."""

    id: str = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    observation: str = Field(min_length=1)
    affected_urls: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    explanation: str | None = None
    potential_impact: str | None = None
    recommendation: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    status: FindingStatus = FindingStatus.OBSERVED
    severity: Severity | None = None
    confidence: Probability | None = None
    evaluation_reason: str | None = None


class InvestigationOperation(StrEnum):
    """Allowlisted operations available to targeted investigation."""

    FETCH_URL = "fetch_url"
    INSPECT_REDIRECT = "inspect_redirect"
    INSPECT_CANONICAL = "inspect_canonical"
    CHECK_INTERNAL_LINK = "check_internal_link"
    RENDER_PAGE = "render_page"


class Investigation(AuditModel):
    """A narrow evidence request tied to an existing finding."""

    finding_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    question: str = Field(min_length=1)
    operation: InvestigationOperation


class FindingAnalysis(AuditModel):
    """Contextual LLM interpretation for one observed finding."""

    finding_id: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    potential_impact: str | None = None
    recommendation: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    appears_actionable: bool


class AnalysisResult(AuditModel):
    """Structured output from the finding-analysis LLM task."""

    analyses: list[FindingAnalysis] = Field(default_factory=list)


class FindingEvaluation(AuditModel):
    """Evidence-grounded evaluator decision for one finding."""

    finding_id: str = Field(min_length=1)
    status: Literal[
        FindingStatus.VERIFIED,
        FindingStatus.NEEDS_REVIEW,
        FindingStatus.DISMISSED,
    ]
    severity: Severity | None = None
    confidence: Probability
    rationale: str = Field(min_length=1)


class EvaluationResult(AuditModel):
    """Structured output from evaluation, including bounded evidence requests."""

    evaluations: list[FindingEvaluation] = Field(default_factory=list)
    investigation_requests: list[Investigation] = Field(default_factory=list)


class RemediationBrief(AuditModel):
    """Implementation-oriented remediation guidance for a verified finding."""

    finding_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    affected_urls: list[str] = Field(default_factory=list)
    recommended_changes: list[str] = Field(min_length=1)
    verification_steps: list[str] = Field(min_length=1)
    implementation_notes: list[str] = Field(default_factory=list)


class ReportFindingNarrative(AuditModel):
    """Report prose keyed to an existing, evidence-backed finding."""

    finding_id: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    potential_impact: str | None = None
    recommended_action: str | None = None


class ReportResult(AuditModel):
    """Structured prose returned by the report-generation LLM task."""

    summary: str
    finding_narratives: list[ReportFindingNarrative] = Field(default_factory=list)
    performance_observations: list[str] = Field(default_factory=list)
    ai_discoverability_observations: list[str] = Field(default_factory=list)
    remediation_briefs: list[RemediationBrief] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AuditScope(AuditModel):
    """Transparent description of the sampled audit coverage."""

    candidate_count: NonNegativeInt
    selected_pages: list[SelectedPage] = Field(default_factory=list)
    inspected_urls: list[str] = Field(default_factory=list)
    pagespeed_urls: list[str] = Field(default_factory=list)
    investigation_rounds_used: NonNegativeInt = 0
    investigation_fetches_used: NonNegativeInt = 0


class AuditReport(AuditModel):
    """Final API-safe technical audit and developer handoff."""

    website_url: str = Field(min_length=1)
    site_context: SiteContext | None = None
    scope: AuditScope
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    performance: dict[str, PageSpeedSummary] = Field(default_factory=dict)
    performance_observations: list[str] = Field(default_factory=list)
    ai_discoverability_observations: list[str] = Field(default_factory=list)
    remediation_briefs: list[RemediationBrief] = Field(default_factory=list)
    unresolved_finding_ids: list[str] = Field(default_factory=list)
    collection_warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AuditRequest(AuditModel):
    """Public API request for one website audit."""

    website_url: str = Field(min_length=1)


class AuditResponse(AuditModel):
    """Public API response wrapper."""

    report: AuditReport


class AuditState(TypedDict):
    """Exact compact state shared by all LangGraph nodes."""

    website_url: str
    limits: AuditLimits
    site_context: SiteContext | None
    candidates: list[PageCandidate]
    selected_pages: list[SelectedPage]
    site_signals: SiteSignals | None
    page_signals: dict[str, PageSignals]
    performance: dict[str, PageSpeedSummary]
    findings: list[Finding]
    investigation_requests: list[Investigation]
    investigation_count: int
    collection_warnings: list[str]
    report: AuditReport | None
