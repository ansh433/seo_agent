import { afterEach, describe, expect, it, vi } from "vitest";

import { AuditApiError, createAudit } from "./audits";

const validReport = {
  website_url: "https://example.com",
  site_context: null,
  scope: {
    candidate_count: 0,
    selected_pages: [],
    inspected_urls: [],
    pagespeed_urls: [],
    investigation_rounds_used: 0,
    investigation_fetches_used: 0,
  },
  summary: "No issues were found in the sampled pages.",
  findings: [],
  performance: {},
  performance_observations: [],
  ai_discoverability_observations: [],
  remediation_briefs: [],
  unresolved_finding_ids: [],
  collection_warnings: [],
  limitations: [],
};

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("createAudit", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns a schema-shaped audit report", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ report: validReport }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createAudit("https://example.com")).resolves.toEqual(validReport);
    expect(fetchMock).toHaveBeenCalledWith(
      "/audits",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ website_url: "https://example.com" }),
      }),
    );
  });

  it.each([
    ["invalid_website_url", 422],
    ["provider_not_configured", 503],
    ["audit_failed", 502],
  ] as const)("preserves the %s backend error", async (code, status) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code, message: `Backend message for ${code}` } }, status),
      ),
    );

    const request = createAudit("https://example.com");
    await expect(request).rejects.toMatchObject({
      name: "AuditApiError",
      code,
      message: `Backend message for ${code}`,
    });
  });

  it("maps native FastAPI validation detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { detail: [{ loc: ["body", "website_url"], msg: "Field required", type: "missing" }] },
          422,
        ),
      ),
    );

    await expect(createAudit("https://example.com")).rejects.toMatchObject({
      code: "validation_error",
      message: "Field required",
    });
  });

  it("maps network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(createAudit("https://example.com")).rejects.toMatchObject({
      code: "network_error",
    });
  });

  it("rejects unexpected success payloads", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ report: { summary: "partial" } })));

    await expect(createAudit("https://example.com")).rejects.toEqual(
      expect.objectContaining<Partial<AuditApiError>>({ code: "unexpected_response" }),
    );
  });
});
