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
  tone?: "amber" | "blue" | "green" | "violet";
}

const toneClasses: Record<NonNullable<SectionHeadingProps["tone"]>, string> = {
  amber: "bg-[#fff1d7] text-[#ae5c00]",
  blue: "bg-[#eaf1ff] text-[#075ee5]",
  green: "bg-[#e3f7eb] text-[#087d45]",
  violet: "bg-[#eee8ff] text-[#6842c2]",
};

export function SectionHeading({
  icon,
  introduction,
  title,
  tone = "blue",
}: SectionHeadingProps): React.JSX.Element {
  return (
    <div className="mb-5 sm:mb-6">
      <div className="flex items-center gap-3">
        <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${toneClasses[tone]}`} aria-hidden="true">
          {icon}
        </span>
        <h2 className="font-display text-[1.7rem] font-bold tracking-[-0.025em] text-[#14203a] sm:text-3xl">
          {title}
        </h2>
      </div>
      {introduction && (
        <p className="mt-3 max-w-[48rem] text-sm leading-6 text-[#647088] sm:ml-[3.25rem] sm:text-base">
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
        tone="green"
        introduction="Measured page results from PageSpeed. Lab and field signals are shown separately and unavailable data stays unavailable."
      />

      {results.length === 0 ? (
        <EmptyState text="No PageSpeed result was included in this audit." />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {results.map((result) => (
            <PerformanceCard key={`${result.url}-${result.strategy}`} result={result} />
          ))}
        </div>
      )}

      {observations.length > 0 && (
        <ObservationList title="Performance observations" items={observations} tone="green" />
      )}
    </section>
  );
}

function PerformanceCard({ result }: { result: PageSpeedSummary }): React.JSX.Element {
  const score = result.performance_score === null ? null : Math.round(result.performance_score * 100);
  const scoreTone =
    score === null
      ? "bg-[#f0f2f4] text-[#526078]"
      : score >= 90
        ? "bg-[#e5f7eb] text-[#087d45]"
        : score >= 50
          ? "bg-[#fff3dc] text-[#a35b00]"
          : "bg-[#ffebea] text-[#ae2725]";

  return (
    <article className="overflow-hidden rounded-2xl border border-[#d9dfdc] bg-white shadow-[0_8px_30px_rgba(18,31,52,0.04)]">
      <div className="flex items-start gap-3 border-b border-[#e0e5e2] p-4 sm:p-5">
        <span className={`grid size-14 shrink-0 place-items-center rounded-2xl text-xl font-extrabold ${scoreTone}`}>
          {score ?? "—"}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-[#eef1f4] px-2.5 py-1 text-xs font-bold capitalize text-[#4e5c73]">
              {result.strategy}
            </span>
            <span className={`text-xs font-bold ${result.available ? "text-[#087d45]" : "text-[#a92523]"}`}>
              {result.available ? "Collected" : "Unavailable"}
            </span>
          </div>
          <p className="mt-2 break-all text-sm font-semibold leading-5 text-[#26344e]">{result.url}</p>
        </div>
      </div>

      {result.available ? (
        <div className="p-4 sm:p-5">
          <MetricGroup title="Lab metrics" metrics={result.lab_metrics} />
          <div className="my-5 h-px bg-[#e0e5e2]" />
          <MetricGroup title="Field metrics" metrics={result.field_metrics} />
          {result.diagnostics.length > 0 && (
            <div className="mt-5 rounded-xl bg-[#f5f7f6] p-4">
              <p className="text-sm font-bold text-[#26344e]">Diagnostics</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[#5b6880]">
                {result.diagnostics.map((diagnostic) => (
                  <li key={diagnostic}>{diagnostic}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <div className="flex items-start gap-3 p-4 text-sm leading-6 text-[#6b4d21] sm:p-5">
          <WarningCircle size={20} weight="fill" className="mt-0.5 shrink-0 text-[#bd6900]" />
          <p>{result.collection_error ?? "PageSpeed did not return data for this page."}</p>
        </div>
      )}
    </article>
  );
}

function MetricGroup({ title, metrics }: { metrics: PageSpeedMetric[]; title: string }): React.JSX.Element {
  return (
    <div>
      <p className="text-xs font-bold uppercase tracking-[0.11em] text-[#637088]">{title}</p>
      {metrics.length === 0 ? (
        <p className="mt-2 text-sm text-[#69758b]">Not available</p>
      ) : (
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {metrics.map((metric) => (
            <div key={`${metric.name}-${metric.unit}`} className="rounded-xl border border-[#e0e5e2] p-3">
              <dt className="text-xs leading-4 text-[#637088]">{metric.name}</dt>
              <dd className="mt-1 text-base font-extrabold text-[#14203a]">
                {Number.isInteger(metric.value) ? metric.value : metric.value.toFixed(2)}{" "}
                <span className="text-xs font-semibold text-[#627087]">{metric.unit}</span>
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

interface AiSectionProps {
  observations: string[];
}

export function AiSection({ observations }: AiSectionProps): React.JSX.Element {
  return (
    <section id="ai-discoverability" className="report-section scroll-mt-24">
      <SectionHeading
        icon={<Robot size={23} weight="duotone" />}
        title="AI discoverability"
        tone="violet"
        introduction="Observed signals about how accessible the site’s public information may be to AI systems. No readiness score is inferred."
      />
      {observations.length === 0 ? (
        <EmptyState text="No AI discoverability observations were included in this audit." />
      ) : (
        <ObservationList title="Public information observations" items={observations} tone="violet" />
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
        tone="blue"
        introduction="Implementation-ready guidance linked directly to the finding that produced it."
      />

      {briefs.length === 0 ? (
        <EmptyState text="No remediation briefs were generated for this audit." />
      ) : (
        <div className="space-y-4">
          {briefs.map((brief, index) => (
            <article key={`${brief.finding_id}-${index}`} className="rounded-2xl border border-[#d9dfdc] bg-white p-4 shadow-[0_8px_30px_rgba(18,31,52,0.04)] sm:p-6">
              <div className="flex items-start gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[#eaf1ff] text-sm font-extrabold text-[#075ee5]">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold uppercase tracking-[0.1em] text-[#66728a]">
                    Finding {brief.finding_id}
                  </p>
                  <h3 className="mt-1 font-display text-xl font-bold leading-7 text-[#14203a]">{brief.title}</h3>
                </div>
                <button
                  type="button"
                  onClick={() => void handleCopy(brief)}
                  className="print:hidden flex min-h-11 shrink-0 items-center gap-2 rounded-xl border border-[#c9d2de] px-3 text-sm font-bold text-[#33445f] transition-colors hover:border-[#8ea6c8] hover:bg-[#f4f7fb] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0b63f6]"
                  aria-label={`Copy remediation brief: ${brief.title}`}
                >
                  {copiedId === brief.finding_id ? <CheckCircle size={18} weight="fill" className="text-[#087d45]" /> : <Copy size={18} />}
                  <span className="hidden sm:inline">
                    {copiedId === brief.finding_id ? "Copied" : copiedId === "unavailable" ? "Unavailable" : "Copy"}
                  </span>
                </button>
              </div>

              <div className="mt-5 grid gap-5 lg:grid-cols-2">
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
      <h4 className="text-sm font-bold text-[#26344e]">{title}</h4>
      <List className={`${ordered ? "list-decimal" : "list-disc"} mt-2 space-y-1.5 pl-5 text-sm leading-6 text-[#5b6880] ${isCode ? "font-mono text-xs break-all" : ""}`}>
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
        tone="amber"
        introduction="This is representative sampling, not an exhaustive crawl. The selected pages and investigation usage are listed for transparency."
      />

      <div className="rounded-2xl border border-[#d9dfdc] bg-white p-4 shadow-[0_8px_30px_rgba(18,31,52,0.04)] sm:p-6">
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <ScopeMetric label="Candidates" value={scope.candidate_count} />
          <ScopeMetric label="Selected pages" value={scope.selected_pages.length} />
          <ScopeMetric label="Investigation rounds" value={scope.investigation_rounds_used} />
          <ScopeMetric label="Investigation fetches" value={scope.investigation_fetches_used} />
        </dl>

        {scope.selected_pages.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-bold text-[#26344e]">Selected pages</h3>
            <div className="mt-3 divide-y divide-[#e1e5e3] border-y border-[#e1e5e3]">
              {scope.selected_pages.map((page) => (
                <div key={page.url} className="grid gap-1 py-4 sm:grid-cols-[10rem_1fr] sm:gap-4">
                  <span className="text-xs font-extrabold uppercase tracking-[0.08em] text-[#58677f]">{page.page_category}</span>
                  <div>
                    <p className="break-all font-mono text-xs leading-5 text-[#26344e]">{page.url}</p>
                    <p className="mt-1 text-sm leading-6 text-[#66728a]">{page.selection_reason}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          <UrlList title="Inspected URLs" urls={scope.inspected_urls} icon={<LinkSimple size={18} />} />
          <UrlList title="PageSpeed URLs" urls={scope.pagespeed_urls} icon={<Gauge size={18} />} />
        </div>
      </div>
    </section>
  );
}

function ScopeMetric({ label, value }: { label: string; value: number }): React.JSX.Element {
  return (
    <div className="rounded-xl bg-[#f5f7f6] p-3 sm:p-4">
      <dt className="text-xs font-semibold leading-4 text-[#627087]">{label}</dt>
      <dd className="mt-1 font-display text-2xl font-bold text-[#14203a]">{value}</dd>
    </div>
  );
}

function UrlList({ icon, title, urls }: { icon: React.ReactNode; title: string; urls: string[] }): React.JSX.Element {
  return (
    <div>
      <h3 className="flex items-center gap-2 text-sm font-bold text-[#26344e]">
        {icon}
        {title}
      </h3>
      {urls.length === 0 ? (
        <p className="mt-2 text-sm text-[#69758b]">None recorded</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {urls.map((url) => (
            <li key={url} className="break-all rounded-lg bg-[#f5f7f6] px-3 py-2 font-mono text-xs leading-5 text-[#40506a]">{url}</li>
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
      <SectionHeading icon={<Info size={23} weight="duotone" />} title="Warnings & limitations" tone="amber" />
      <div className="grid gap-4 lg:grid-cols-2">
        {warnings.length > 0 && <NoticeCard title="Collection warnings" items={warnings} tone="warning" />}
        {unresolvedIds.length > 0 && <NoticeCard title="Unresolved findings" items={unresolvedIds} tone="review" />}
        {limitations.length > 0 && <NoticeCard title="Limitations" items={limitations} tone="neutral" />}
      </div>
    </section>
  );
}

function NoticeCard({ items, title, tone }: { items: string[]; title: string; tone: "neutral" | "review" | "warning" }): React.JSX.Element {
  const classes = {
    neutral: "border-[#d9dfdc] bg-white text-[#53617a]",
    review: "border-[#ead1a3] bg-[#fff8e9] text-[#6e4a16]",
    warning: "border-[#edc2c0] bg-[#fff3f2] text-[#7f302e]",
  }[tone];
  return (
    <article className={`rounded-2xl border p-4 sm:p-5 ${classes}`}>
      <h3 className="font-display text-lg font-bold text-[#25334d]">{title}</h3>
      <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </article>
  );
}

function ObservationList({ items, title, tone }: { items: string[]; title: string; tone: "green" | "violet" }): React.JSX.Element {
  const accent = tone === "green" ? "bg-[#e3f7eb] text-[#087d45]" : "bg-[#eee8ff] text-[#6842c2]";
  return (
    <div className="mt-4 overflow-hidden rounded-2xl border border-[#d9dfdc] bg-white shadow-[0_8px_30px_rgba(18,31,52,0.04)]">
      <h3 className="border-b border-[#e1e5e3] px-4 py-3 text-sm font-bold text-[#26344e] sm:px-5">{title}</h3>
      <ol className="divide-y divide-[#e1e5e3]">
        {items.map((item, index) => (
          <li key={`${item}-${index}`} className="flex items-start gap-3 px-4 py-4 sm:px-5">
            <span className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-extrabold ${accent}`}>{index + 1}</span>
            <p className="text-sm leading-6 text-[#53617a]">{item}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function EmptyState({ text }: { text: string }): React.JSX.Element {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-dashed border-[#cbd3d0] bg-[#fafbf9] p-5 text-sm leading-6 text-[#657189]">
      <Info size={20} weight="duotone" className="shrink-0" />
      <p>{text}</p>
    </div>
  );
}
