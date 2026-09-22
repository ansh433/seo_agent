import {
  ChartLineUp,
  CheckCircle,
  ClipboardText,
  Copy,
  Gauge,
  GlobeSimple,
  Info,
  LinkSimple,
  Robot,
  WarningCircle,
} from "@phosphor-icons/react";
import { useState } from "react";

import type {
  AuditScope,
  PageSpeedMetric,
  PageSpeedSummary,
  RemediationBrief,
} from "../types/audit";

interface SectionHeadingProps {
  icon: React.ReactNode;
  introduction?: string;
  title: string;
  tone?: "canvas" | "coral" | "sand" | "warm";
}

const toneClasses: Record<NonNullable<SectionHeadingProps["tone"]>, string> = {
  canvas: "bg-[var(--canvas)] text-[var(--ink)]",
  coral: "bg-[var(--signal)] text-[var(--ink)]",
  sand: "bg-[var(--surface-warm)] text-[var(--ink)]",
  warm: "bg-[var(--surface-warm)] text-[var(--ink)]",
};

export function SectionHeading({
  icon,
  introduction,
  title,
  tone = "canvas",
}: SectionHeadingProps): React.JSX.Element {
  return (
    <div className="mb-6 sm:mb-7">
      <div className="flex items-center gap-3.5">
        <span className={`grid size-11 shrink-0 place-items-center rounded-xl border border-[var(--line)] ${toneClasses[tone]}`} aria-hidden="true">
          {icon}
        </span>
        <h2 className="font-display text-[1.85rem] font-extrabold leading-tight text-[var(--ink)] sm:text-[2.1rem]">
          {title}
        </h2>
      </div>
      {introduction && (
        <p className="mt-3 max-w-[52rem] text-base leading-7 text-[var(--ink-muted)] sm:ml-[3.4rem]">
          {introduction}
        </p>
      )}
    </div>
  );
}

interface PerformanceSectionProps {
  observations: string[];
  performance: Record<string, PageSpeedSummary>;
}

export function PerformanceSection({
  observations,
  performance,
}: PerformanceSectionProps): React.JSX.Element {
  const results = Object.values(performance);

  return (
    <section id="performance" className="report-section scroll-mt-24">
      <SectionHeading
        icon={<ChartLineUp size={23} weight="duotone" />}
        title="Performance"
        tone="sand"
        introduction="Measured page results from PageSpeed. Lab and field signals are shown separately and unavailable data stays unavailable."
      />

      {results.length === 0 ? (
        <EmptyState text="No PageSpeed result was included in this audit." />
      ) : (
        <div className="grid items-start gap-5 xl:grid-cols-2">
          {results.map((result) => (
            <PerformanceCard key={`${result.url}-${result.strategy}`} result={result} />
          ))}
        </div>
      )}

      {observations.length > 0 && (
        <ObservationList title="Performance observations" items={observations} tone="sand" />
      )}
    </section>
  );
}

function PerformanceCard({ result }: { result: PageSpeedSummary }): React.JSX.Element {
  const score = result.performance_score === null ? null : Math.round(result.performance_score * 100);
  const scoreTone =
    score === null
      ? "bg-[var(--canvas)] text-[var(--ink-muted)]"
      : score >= 90
        ? "bg-[var(--surface-warm)] text-[var(--ink)]"
        : score >= 50
          ? "bg-[var(--surface-warm)] text-[var(--ink)]"
          : "bg-[var(--signal)] text-[var(--ink)]";

  return (
    <article className="overflow-hidden rounded-2xl border border-[var(--line)] bg-white">
      <div className="flex items-start gap-4 border-b border-[var(--line)] p-5 sm:p-6">
        <span className={`grid size-16 shrink-0 place-items-center rounded-xl text-2xl font-extrabold ${scoreTone}`}>
          {score ?? "—"}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-[var(--canvas)] px-2.5 py-1 text-xs font-bold capitalize text-[var(--ink-muted)]">
              {result.strategy}
            </span>
            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${result.available ? "bg-[var(--surface-warm)]" : "bg-[var(--signal)]"} text-[var(--ink)]`}>
              {result.available ? "Collected" : "Unavailable"}
            </span>
          </div>
          <p className="mt-3 break-words font-mono text-xs leading-6 text-[var(--ink)] sm:text-sm">{result.url}</p>
        </div>
      </div>

      {result.available ? (
        <div className="p-5 sm:p-6">
          <MetricGroup title="Lab metrics" metrics={result.lab_metrics} />
          <div className="my-6 h-px bg-[var(--line)]" />
          <MetricGroup title="Field metrics" metrics={result.field_metrics} />
          {result.diagnostics.length > 0 && (
            <div className="mt-6 rounded-xl bg-[var(--canvas)] p-4 sm:p-5">
              <p className="text-sm font-extrabold text-[var(--ink)]">Diagnostics</p>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 text-base leading-7 text-[var(--ink-muted)]">
                {result.diagnostics.map((diagnostic) => (
                  <li key={diagnostic}>{diagnostic}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <div className="flex min-h-32 items-start gap-3 bg-[var(--signal)] p-5 text-base leading-7 text-[var(--ink)] sm:p-6">
          <WarningCircle size={20} weight="fill" className="mt-0.5 shrink-0 text-[var(--ink)]" />
          <p>{result.collection_error ?? "PageSpeed did not return data for this page."}</p>
        </div>
      )}
    </article>
  );
}

function MetricGroup({ title, metrics }: { metrics: PageSpeedMetric[]; title: string }): React.JSX.Element {
  return (
    <div>
      <p className="text-sm font-extrabold text-[var(--ink)]">{title}</p>
      {metrics.length === 0 ? (
        <p className="mt-2 text-base text-[var(--ink-muted)]">Not available</p>
      ) : (
        <dl className="mt-3 grid grid-cols-2 overflow-hidden rounded-xl border border-[var(--line)] sm:grid-cols-3">
          {metrics.map((metric) => (
            <div key={`${metric.name}-${metric.unit}`} className="min-w-0 border-b border-r border-[var(--line)] bg-white p-3.5 sm:p-4">
              <dt className="break-words text-xs leading-5 text-[var(--ink-muted)] sm:text-[0.8rem]">{formatMetricName(metric.name)}</dt>
              <dd className="mt-1 text-lg font-extrabold text-[var(--ink)]">
                {Number.isInteger(metric.value) ? metric.value : metric.value.toFixed(2)}{" "}
                <span className="text-[0.8rem] font-semibold text-[var(--ink-muted)]">{metric.unit}</span>
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

const formatMetricName = (name: string): string => {
  const label = name.replaceAll("_", " ");
  return label.replace(/\b(lcp|cls|tbt|fcp)\b/gi, (token) => token.toUpperCase());
};

interface AiSectionProps {
  observations: string[];
}

export function AiSection({ observations }: AiSectionProps): React.JSX.Element {
  return (
    <section id="ai-discoverability" className="report-section scroll-mt-24">
      <SectionHeading
        icon={<Robot size={23} weight="duotone" />}
        title="AI discoverability"
        tone="warm"
        introduction="Observed signals about how accessible the site’s public information may be to AI systems. No readiness score is inferred."
      />
      {observations.length === 0 ? (
        <EmptyState text="No AI discoverability observations were included in this audit." />
      ) : (
        <ObservationList title="Public information observations" items={observations} tone="warm" />
      )}
    </section>
  );
}

interface RemediationSectionProps {
  briefs: RemediationBrief[];
}

export function RemediationSection({ briefs }: RemediationSectionProps): React.JSX.Element {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = async (brief: RemediationBrief): Promise<void> => {
    const text = [
      brief.title,
      "",
      "Affected URLs",
      ...brief.affected_urls.map((url) => `- ${url}`),
      "",
      "Recommended changes",
      ...brief.recommended_changes.map((item) => `- ${item}`),
      "",
      "Verification steps",
      ...brief.verification_steps.map((item) => `- ${item}`),
      ...(brief.implementation_notes.length > 0
        ? ["", "Implementation notes", ...brief.implementation_notes.map((item) => `- ${item}`)]
        : []),
    ].join("\n");

    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(brief.finding_id);
      window.setTimeout(() => setCopiedId(null), 1800);
    } catch {
      setCopiedId("unavailable");
      window.setTimeout(() => setCopiedId(null), 1800);
    }
  };

  return (
    <section id="remediation" className="report-section scroll-mt-24">
      <SectionHeading
        icon={<ClipboardText size={23} weight="duotone" />}
        title="Remediation briefs"
        tone="canvas"
        introduction="Implementation-ready guidance linked directly to the finding that produced it."
      />

      {briefs.length === 0 ? (
        <EmptyState text="No remediation briefs were generated for this audit." />
      ) : (
        <div className="space-y-4">
          {briefs.map((brief, index) => (
            <article key={`${brief.finding_id}-${index}`} className="overflow-hidden rounded-2xl border border-[var(--line)] bg-white">
              <div className="flex items-start gap-3 bg-[var(--surface-warm)] p-5 sm:p-6">
                <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-[var(--ink)] text-sm font-extrabold text-white">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-[var(--ink-muted)]">
                    Finding {brief.finding_id}
                  </p>
                  <h3 className="mt-1 font-display text-xl font-extrabold leading-7 text-[var(--ink)] sm:text-2xl">{brief.title}</h3>
                </div>
                <button
                  type="button"
                  onClick={() => void handleCopy(brief)}
                  className="pressable print:hidden flex min-h-11 shrink-0 items-center gap-2 rounded-lg border border-[var(--line)] bg-white px-3 text-sm font-bold text-[var(--ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)]"
                  aria-label={`Copy remediation brief: ${brief.title}`}
                >
                  {copiedId === brief.finding_id ? <CheckCircle size={18} weight="fill" /> : <Copy size={18} />}
                  <span className="hidden sm:inline">
                    {copiedId === brief.finding_id ? "Copied" : copiedId === "unavailable" ? "Unavailable" : "Copy"}
                  </span>
                </button>
              </div>

              <div className="grid gap-7 p-5 sm:p-6 lg:grid-cols-2">
                <BriefList title="Recommended changes" items={brief.recommended_changes} ordered />
                <BriefList title="Verification steps" items={brief.verification_steps} ordered />
                {brief.affected_urls.length > 0 && <BriefList title="Affected URLs" items={brief.affected_urls} isCode />}
                {brief.implementation_notes.length > 0 && <BriefList title="Implementation notes" items={brief.implementation_notes} />}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function BriefList({
  isCode = false,
  items,
  ordered = false,
  title,
}: {
  isCode?: boolean;
  items: string[];
  ordered?: boolean;
  title: string;
}): React.JSX.Element {
  const List = ordered ? "ol" : "ul";
  return (
    <div>
      <h4 className="text-sm font-extrabold text-[var(--ink)]">{title}</h4>
      <List className={`${ordered ? "list-decimal" : "list-disc"} mt-2.5 space-y-2 pl-5 text-base leading-7 text-[var(--ink-muted)] ${isCode ? "break-all font-mono text-xs leading-6" : ""}`}>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </List>
    </div>
  );
}

interface ScopeSectionProps {
  scope: AuditScope;
}

export function ScopeSection({ scope }: ScopeSectionProps): React.JSX.Element {
  return (
    <section id="scope" className="report-section scroll-mt-24">
      <SectionHeading
        icon={<GlobeSimple size={23} weight="duotone" />}
        title="Audit scope"
        tone="sand"
        introduction="This is representative sampling, not an exhaustive crawl. The selected pages and investigation usage are listed for transparency."
      />

      <div className="overflow-hidden rounded-2xl border border-[var(--line)] bg-white">
        <dl className="grid grid-cols-2 gap-px bg-[var(--line)] sm:grid-cols-4">
          <ScopeMetric label="Candidates" value={scope.candidate_count} />
          <ScopeMetric label="Selected pages" value={scope.selected_pages.length} />
          <ScopeMetric label="Investigation rounds" value={scope.investigation_rounds_used} />
          <ScopeMetric label="Investigation fetches" value={scope.investigation_fetches_used} />
        </dl>

        {scope.selected_pages.length > 0 && (
          <div className="border-t border-[var(--line)] p-5 sm:p-6">
            <h3 className="text-base font-extrabold text-[var(--ink)]">Selected pages</h3>
            <div className="mt-3 divide-y divide-[var(--line)] border-y border-[var(--line)]">
              {scope.selected_pages.map((page) => (
                <div key={page.url} className="grid gap-2 py-4 sm:grid-cols-[9rem_1fr] sm:gap-5">
                  <span className="text-xs font-extrabold text-[var(--ink)]">{page.page_category}</span>
                  <div>
                    <p className="break-all font-mono text-xs leading-6 text-[var(--ink)]">{page.url}</p>
                    <p className="mt-1 text-base leading-7 text-[var(--ink-muted)]">{page.selection_reason}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-6 border-t border-[var(--line)] p-5 sm:p-6 lg:grid-cols-2">
          <UrlList title="Inspected URLs" urls={scope.inspected_urls} icon={<LinkSimple size={18} />} />
          <UrlList title="PageSpeed URLs" urls={scope.pagespeed_urls} icon={<Gauge size={18} />} />
        </div>
      </div>
    </section>
  );
}

function ScopeMetric({ label, value }: { label: string; value: number }): React.JSX.Element {
  return (
    <div className="bg-[var(--surface-warm)] p-4 sm:p-5">
      <dt className="text-sm font-semibold leading-5 text-[var(--ink-muted)]">{label}</dt>
      <dd className="mt-1 font-display text-3xl font-extrabold text-[var(--ink)]">{value}</dd>
    </div>
  );
}

function UrlList({ icon, title, urls }: { icon: React.ReactNode; title: string; urls: string[] }): React.JSX.Element {
  return (
    <div>
      <h3 className="flex items-center gap-2 text-sm font-extrabold text-[var(--ink)]">
        {icon}
        {title}
      </h3>
      {urls.length === 0 ? (
        <p className="mt-2 text-base text-[var(--ink-muted)]">None recorded</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {urls.map((url) => (
            <li key={url} className="break-all rounded-lg bg-[var(--canvas)] px-3 py-2.5 font-mono text-xs leading-6 text-[var(--ink-muted)]">{url}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function WarningSection({
  limitations,
  unresolvedIds,
  warnings,
}: {
  limitations: string[];
  unresolvedIds: string[];
  warnings: string[];
}): React.JSX.Element | null {
  if (limitations.length === 0 && unresolvedIds.length === 0 && warnings.length === 0) {
    return null;
  }

  return (
    <section id="limitations" className="report-section scroll-mt-24">
      <SectionHeading icon={<Info size={23} weight="duotone" />} title="Warnings & limitations" tone="coral" />
      <div className="grid gap-5 lg:grid-cols-2">
        {warnings.length > 0 && <NoticeCard title="Collection warnings" items={warnings} tone="warning" />}
        {unresolvedIds.length > 0 && <NoticeCard title="Unresolved findings" items={unresolvedIds} tone="review" />}
        {limitations.length > 0 && <NoticeCard title="Limitations" items={limitations} tone="neutral" />}
      </div>
    </section>
  );
}

function NoticeCard({ items, title, tone }: { items: string[]; title: string; tone: "neutral" | "review" | "warning" }): React.JSX.Element {
  const classes = {
    neutral: "border-[var(--line)] bg-white text-[var(--ink-muted)]",
    review: "border-[var(--line)] bg-[var(--surface-warm)] text-[var(--ink)]",
    warning: "border-[var(--signal)] bg-[var(--signal)] text-[var(--ink)]",
  }[tone];
  return (
    <article className={`rounded-xl border p-5 sm:p-6 ${classes}`}>
      <h3 className="font-display text-xl font-extrabold text-[var(--ink)]">{title}</h3>
      <ul className="mt-3 list-disc space-y-2 pl-5 text-base leading-7">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </article>
  );
}

function ObservationList({ items, title, tone }: { items: string[]; title: string; tone: "sand" | "warm" }): React.JSX.Element {
  const accent = tone === "sand" ? "bg-[var(--surface-warm)] text-[var(--ink)]" : "bg-[var(--canvas)] text-[var(--ink)]";
  return (
    <div className="mt-5 overflow-hidden rounded-2xl border border-[var(--line)] bg-white">
      <h3 className="border-b border-[var(--line)] px-5 py-4 text-base font-extrabold text-[var(--ink)] sm:px-6">{title}</h3>
      <ol className="divide-y divide-[var(--line)]">
        {items.map((item, index) => (
          <li key={`${item}-${index}`} className="flex items-start gap-4 px-5 py-4 sm:px-6 sm:py-5">
            <span className={`grid size-8 shrink-0 place-items-center rounded-lg text-xs font-extrabold ${accent}`}>{index + 1}</span>
            <p className="text-base leading-7 text-[var(--ink-muted)]">{item}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function EmptyState({ text }: { text: string }): React.JSX.Element {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-dashed border-[var(--line)] bg-white p-5 text-base leading-7 text-[var(--ink-muted)]">
      <Info size={20} weight="duotone" className="shrink-0" />
      <p>{text}</p>
    </div>
  );
}
