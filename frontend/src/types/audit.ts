export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type CandidateSource = "homepage" | "navigation" | "sitemap";
export type FindingStatus =
  | "observed"
  | "verified"
  | "needs_review"
  | "dismissed";
export type Severity =
  | "informational"
  | "low"
  | "medium"
  | "high"
  | "critical";
export type PageSpeedStrategy = "mobile" | "desktop";

export interface SiteContext {
  summary: string;
  business_name: string | null;
  products_or_services: string[];
  audiences: string[];
}

export interface SelectedPage {
  url: string;
  page_category: string;
  selection_reason: string;
}

export interface PageSpeedMetric {
  name: string;
  value: number;
  unit: string;
}

export interface PageSpeedSummary {
  url: string;
  strategy: PageSpeedStrategy;
  available: boolean;
  performance_score: number | null;
  lab_metrics: PageSpeedMetric[];
  field_metrics: PageSpeedMetric[];
  diagnostics: string[];
  collection_error: string | null;
}

export interface Evidence {
  source_url: string;
  signal: string;
  observed_value: JsonValue;
}

export interface Finding {
  id: string;
  issue_type: string;
  title: string;
  observation: string;
  affected_urls: string[];
  evidence: Evidence[];
  explanation: string | null;
  potential_impact: string | null;
  recommendation: string | null;
  missing_information: string[];
  status: FindingStatus;
  severity: Severity | null;
  confidence: number | null;
  evaluation_reason: string | null;
}

export interface RemediationBrief {
  finding_id: string;
  title: string;
  affected_urls: string[];
  recommended_changes: string[];
  verification_steps: string[];
  implementation_notes: string[];
}

export interface AuditScope {
  candidate_count: number;
  selected_pages: SelectedPage[];
  inspected_urls: string[];
  pagespeed_urls: string[];
  investigation_rounds_used: number;
  investigation_fetches_used: number;
}

export interface AuditReport {
  website_url: string;
  site_context: SiteContext | null;
  scope: AuditScope;
  summary: string;
  findings: Finding[];
  performance: Record<string, PageSpeedSummary>;
  performance_observations: string[];
  ai_discoverability_observations: string[];
  remediation_briefs: RemediationBrief[];
  unresolved_finding_ids: string[];
  collection_warnings: string[];
  limitations: string[];
}

export interface AuditRequest {
  website_url: string;
}

export interface AuditResponse {
  report: AuditReport;
}
