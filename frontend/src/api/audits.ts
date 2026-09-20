import type { AuditReport, AuditRequest, AuditResponse } from "../types/audit";

type AuditErrorCode =
  | "invalid_website_url"
  | "provider_not_configured"
  | "audit_failed"
  | "validation_error"
  | "network_error"
  | "unexpected_response";

interface ErrorDetail {
  code: AuditErrorCode;
  message: string;
}

export class AuditApiError extends Error {
  public readonly code: AuditErrorCode;

  public constructor(detail: ErrorDetail) {
    super(detail.message);
    this.name = "AuditApiError";
    this.code = detail.code;
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isAuditReport = (value: unknown): value is AuditReport => {
  if (!isRecord(value) || !isRecord(value.scope)) {
    return false;
  }

  return (
    typeof value.website_url === "string" &&
    typeof value.summary === "string" &&
    Array.isArray(value.findings) &&
    isRecord(value.performance) &&
    Array.isArray(value.performance_observations) &&
    Array.isArray(value.ai_discoverability_observations) &&
    Array.isArray(value.remediation_briefs) &&
    Array.isArray(value.unresolved_finding_ids) &&
    Array.isArray(value.collection_warnings) &&
    Array.isArray(value.limitations) &&
    typeof value.scope.candidate_count === "number" &&
    Array.isArray(value.scope.selected_pages) &&
    Array.isArray(value.scope.inspected_urls) &&
    Array.isArray(value.scope.pagespeed_urls)
  );
};

const validationMessage = (payload: unknown): string | null => {
  if (!isRecord(payload) || !Array.isArray(payload.detail)) {
    return null;
  }

  const messages = payload.detail
    .filter(isRecord)
    .map((item) => (typeof item.msg === "string" ? item.msg : null))
    .filter((message): message is string => message !== null);

  return messages.length > 0 ? messages.join(" ") : null;
};

const responseError = (status: number, payload: unknown): AuditApiError => {
  if (isRecord(payload) && isRecord(payload.error)) {
    const code = payload.error.code;
    const message = payload.error.message;
    if (
      (code === "invalid_website_url" ||
        code === "provider_not_configured" ||
        code === "audit_failed") &&
      typeof message === "string"
    ) {
      return new AuditApiError({ code, message });
    }
  }

  if (status === 422) {
    return new AuditApiError({
      code: "validation_error",
      message:
        validationMessage(payload) ??
        "The website URL could not be validated. Check it and try again.",
    });
  }

  return new AuditApiError({
    code: "unexpected_response",
    message: "The audit service returned an unexpected error. Please try again.",
  });
};

/** Run a synchronous, bounded website audit through the backend API. */
export async function createAudit(
  websiteUrl: string,
  signal?: AbortSignal,
): Promise<AuditReport> {
  const request: AuditRequest = { website_url: websiteUrl };
  let response: Response;

  try {
    response = await fetch("/audits", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new AuditApiError({
      code: "network_error",
      message:
        "We could not reach the audit service. Check your connection and try again.",
    });
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new AuditApiError({
      code: "unexpected_response",
      message: "The audit service returned a response we could not read.",
    });
  }

  if (!response.ok) {
    throw responseError(response.status, payload);
  }

  if (!isRecord(payload) || !isAuditReport(payload.report)) {
    throw new AuditApiError({
      code: "unexpected_response",
      message: "The audit completed, but its report format was unexpected.",
    });
  }

  return (payload as unknown as AuditResponse).report;
}
