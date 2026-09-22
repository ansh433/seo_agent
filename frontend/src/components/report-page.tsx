import {
  ArrowCounterClockwise,
  CheckCircle,
  DownloadSimple,
  FileMagnifyingGlass,
  Printer,
  ShieldCheck,
} from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "react";

import type { AuditReport, Finding, FindingStatus, Severity } from "../types/audit";
import { AppHeader } from "./app-header";
import { FindingCard } from "./finding-card";
import {
  AiSection,
  PerformanceSection,
  RemediationSection,
  ScopeSection,
  SectionHeading,
  WarningSection,
} from "./report-sections";

interface ReportPageProps {
  onStartOver: () => void;
  report: AuditReport;
}

const severityRank: Record<Severity | "unrated", number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  informational: 4,
  unrated: 5,
};

const statusRank: Record<FindingStatus, number> = {
  verified: 0,
  needs_review: 1,
  observed: 2,
  dismissed: 3,
};

const reportSections = [
  ["overview", "Overview"],
  ["findings", "Findings"],
  ["performance", "Performance"],
  ["ai-discoverability", "AI discoverability"],
  ["remediation", "Remediation"],
  ["scope", "Scope"],
] as const;

const limitationsSection = ["limitations", "Limitations"] as const;

const sortedFindings = (findings: Finding[]): Finding[] =>
  [...findings].sort((left, right) => {
    const statusDifference = statusRank[left.status] - statusRank[right.status];
    if (statusDifference !== 0) return statusDifference;
    return severityRank[left.severity ?? "unrated"] - severityRank[right.severity ?? "unrated"];
  });

const hostnameFor = (websiteUrl: string): string => {
  try {
    return new URL(websiteUrl).hostname.replace(/^www\./, "");
  } catch {
    return websiteUrl;
  }
};

/** Complete audit report mapped directly from the backend report contract. */
export function ReportPage({ onStartOver, report }: ReportPageProps): React.JSX.Element {
  const [showAllFindings, setShowAllFindings] = useState(false);
  const [activeSection, setActiveSection] = useState("overview");
  const orderedFindings = useMemo(() => sortedFindings(report.findings), [report.findings]);
  const priorityFindings = orderedFindings.filter((finding) => finding.status !== "dismissed").slice(0, 3);
  const visibleFindings = showAllFindings ? orderedFindings : priorityFindings;
  const verifiedCount = report.findings.filter((finding) => finding.status === "verified").length;
  const unavailablePerformanceCount = Object.values(report.performance).filter(
    (result) => !result.available,
  ).length;
  const dataGapCount = report.collection_warnings.length + unavailablePerformanceCount;
  const domain = hostnameFor(report.website_url);
  const reviewTarget =
    report.limitations.length > 0 ||
    report.unresolved_finding_ids.length > 0 ||
    report.collection_warnings.length > 0
      ? "limitations"
      : "performance";
  const navigableSections = useMemo(
    () =>
      report.limitations.length > 0 ||
      report.unresolved_finding_ids.length > 0 ||
      report.collection_warnings.length > 0
        ? [...reportSections, limitationsSection]
        : reportSections,
    [report.collection_warnings.length, report.limitations.length, report.unresolved_finding_ids.length],
  );

  useEffect(() => {
    const sections = navigableSections
      .map(([id]) => document.getElementById(id))
      .filter((section): section is HTMLElement => section !== null);

    if (sections.length === 0) return undefined;

    const updateActiveSection = (): void => {
      const readingLine = window.scrollY + window.innerHeight * 0.28;
      const currentSection = sections.reduce((active, section) => {
        return section.offsetTop <= readingLine ? section.id : active;
      }, sections[0].id);

      setActiveSection(currentSection);
    };

    updateActiveSection();
    window.addEventListener("scroll", updateActiveSection, { passive: true });
    window.addEventListener("resize", updateActiveSection);

    return () => {
      window.removeEventListener("scroll", updateActiveSection);
      window.removeEventListener("resize", updateActiveSection);
    };
  }, [navigableSections]);

  const handleDownload = (): void => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `${domain.replace(/[^a-z0-9.-]+/gi, "-")}-siteintel-audit.json`;
    anchor.click();
    URL.revokeObjectURL(objectUrl);
  };

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <AppHeader compact />

      <main>
        <header className="bg-[var(--ink)] text-white">
          <div className="mx-auto w-full max-w-[82rem] px-5 py-9 sm:px-8 sm:py-12 lg:py-14">
            <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
              <div className="min-w-0">
                <p className="mb-4 inline-flex items-center gap-2 rounded-full bg-[var(--surface-warm)] px-3 py-1.5 text-sm font-bold text-[var(--ink)]">
                  <CheckCircle size={19} weight="fill" aria-hidden="true" />
                  Audit complete
                </p>
                <h1 className="font-display max-w-[18ch] break-words text-[clamp(2.65rem,7vw,5.25rem)] font-extrabold leading-[0.92] text-white">
                  {domain}
                </h1>
                <p className="mt-4 break-all font-mono text-sm leading-6 text-[#d7dded]">
                  {report.website_url}
                </p>
              </div>

              <div className="print:hidden flex flex-wrap gap-2">
                <ActionButton icon={<ArrowCounterClockwise size={18} />} label="New audit" onClick={onStartOver} />
                <ActionButton icon={<DownloadSimple size={18} />} label="JSON" onClick={handleDownload} />
                <ActionButton icon={<Printer size={18} />} label="Print" onClick={() => window.print()} primary />
              </div>
            </div>
          </div>

          <nav aria-label="Report sections" className="print:hidden overflow-x-auto border-t border-white/15 bg-white text-[var(--ink)] lg:hidden">
            <div className="mx-auto flex min-w-max max-w-[82rem] px-3 sm:px-6">
              {navigableSections.map(([id, label]) => (
                <a
                  key={id}
                  href={`#${id}`}
                  aria-current={activeSection === id ? "location" : undefined}
                  onClick={() => setActiveSection(id)}
                  className={`pressable flex min-h-14 items-center border-b-2 px-3 text-sm font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--ink)] sm:px-4 ${
                    activeSection === id
                      ? "border-[var(--ink)] text-[var(--ink)]"
                      : "border-transparent text-[var(--ink-muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
                  }`}
                >
                  {label}
                </a>
              ))}
            </div>
          </nav>
        </header>

        <div className="mx-auto grid w-full max-w-[82rem] gap-8 px-5 py-10 sm:px-8 sm:py-14 lg:grid-cols-[13.5rem_minmax(0,1fr)] lg:gap-14 lg:py-16">
          <aside className="print:hidden hidden lg:block">
            <nav aria-label="Report table of contents" className="sticky top-6 overflow-hidden rounded-xl border border-[var(--line)] bg-white">
              <p className="border-b border-[var(--line)] px-4 py-3 text-sm font-extrabold text-[var(--ink)]">Report index</p>
              <ul className="p-2">
                {navigableSections.map(([id, label]) => (
                  <li key={id}>
                    <a
                      href={`#${id}`}
                      aria-current={activeSection === id ? "location" : undefined}
                      onClick={() => setActiveSection(id)}
                      className={`pressable flex min-h-11 items-center rounded-lg px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)] ${
                        activeSection === id
                          ? "bg-[var(--ink)] text-white"
                          : "text-[var(--ink-muted)] hover:bg-[var(--canvas)] hover:text-[var(--ink)]"
                      }`}
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
              <p className="border-t border-[var(--line)] bg-[var(--surface-warm)] p-4 text-sm leading-6 text-[var(--ink)]">
                Representative sampling keeps this audit focused. Scope details are included below.
              </p>
            </nav>
          </aside>

          <div className="min-w-0 space-y-16 sm:space-y-20">
            <section id="overview" className="scroll-mt-24">
              <div className="overflow-hidden rounded-2xl border border-[var(--line)] bg-white">
                <div className="grid lg:grid-cols-[minmax(0,1.6fr)_minmax(18rem,0.65fr)]">
                  <div className="bg-[var(--surface-warm)] p-6 sm:p-8 lg:p-10">
                  <div className="flex items-center gap-2 text-sm font-extrabold text-[var(--ink)]">
                    <ShieldCheck size={20} weight="duotone" />
                    Executive summary
                  </div>
                  <p className="font-display mt-6 max-w-[48rem] text-[1.75rem] font-extrabold leading-[1.15] text-[var(--ink)] sm:text-[2rem] lg:text-[2.35rem]">
                    {report.summary || "No executive summary was provided."}
                  </p>
                  {report.site_context && (
                    <div className="mt-7 max-w-[48rem] border-t border-[var(--line)] pt-5">
                      {report.site_context.business_name && (
                        <p className="text-base font-extrabold text-[var(--ink)]">{report.site_context.business_name}</p>
                      )}
                      <p className="mt-2 text-base leading-7 text-[var(--ink-muted)]">{report.site_context.summary}</p>
                    </div>
                  )}
                  </div>

                  <dl className="grid grid-cols-2 bg-[var(--ink)] text-white lg:grid-cols-1">
                    <SummaryMetric label="Findings" value={report.findings.length} />
                    <SummaryMetric label="Verified" value={verifiedCount} />
                    <SummaryMetric label="Needs review" value={report.unresolved_finding_ids.length} />
                    <SummaryMetric label="Pages sampled" value={report.scope.selected_pages.length} />
                    <SummaryMetric label="Fix briefs" value={report.remediation_briefs.length} />
                    <SummaryMetric label="Data gaps" value={dataGapCount} />
                  </dl>
                </div>

                {(report.unresolved_finding_ids.length > 0 || dataGapCount > 0) && (
                  <div className="flex flex-col gap-2 border-t border-[var(--line)] bg-[var(--signal)] px-5 py-4 text-sm leading-6 text-[var(--ink)] sm:flex-row sm:items-center sm:justify-between sm:px-7">
                    <p className="font-bold">Some conclusions still need human review or additional data.</p>
                    <a href={`#${reviewTarget}`} className="print:hidden font-extrabold underline underline-offset-4">
                      Review data gaps
                    </a>
                  </div>
                )}
              </div>
            </section>

            <section id="findings" className="report-section scroll-mt-24">
              <div className="flex items-end justify-between gap-5">
                <SectionHeading
                  icon={<FileMagnifyingGlass size={23} weight="duotone" />}
                  title="Findings"
                  introduction="Start with the highest-priority issues. Each finding keeps the observation, evidence, impact, and recommended action together."
                />
                {report.findings.length > priorityFindings.length && (
                  <button
                    type="button"
                    onClick={() => setShowAllFindings((current) => !current)}
                    className="pressable print:hidden mb-6 hidden min-h-11 shrink-0 items-center rounded-lg border border-[var(--ink)] bg-[var(--ink)] px-4 text-sm font-bold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--canvas)] sm:flex"
                  >
                    {showAllFindings ? "Show priority" : `View all ${report.findings.length}`}
                  </button>
                )}
              </div>

              {visibleFindings.length === 0 ? (
                <div className="flex items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-warm)] p-5 text-sm leading-6 text-[var(--ink)]">
                  <CheckCircle size={21} weight="fill" className="shrink-0 text-[var(--ink)]" />
                  <p>No non-dismissed findings were reported for the sampled pages.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {visibleFindings.map((finding, index) => (
                    <FindingCard key={finding.id} finding={finding} rank={index + 1} />
                  ))}
                </div>
              )}

              {report.findings.length > priorityFindings.length && (
                <button
                  type="button"
                  onClick={() => setShowAllFindings((current) => !current)}
                  className="pressable print:hidden mt-4 flex min-h-12 w-full items-center justify-center rounded-lg border border-[var(--line)] bg-white px-4 text-sm font-bold text-[var(--ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)] sm:hidden"
                >
                  {showAllFindings ? "Show priority findings" : `View all ${report.findings.length} findings`}
                </button>
              )}
            </section>

            <PerformanceSection performance={report.performance} observations={report.performance_observations} />
            <AiSection observations={report.ai_discoverability_observations} />
            <RemediationSection briefs={report.remediation_briefs} />
            <ScopeSection scope={report.scope} />
            <WarningSection
              limitations={report.limitations}
              unresolvedIds={report.unresolved_finding_ids}
              warnings={report.collection_warnings}
            />
          </div>
        </div>
      </main>

      <footer className="border-t border-[var(--line)] bg-[var(--surface-warm)] px-5 py-7 text-center text-sm leading-6 text-[var(--ink-muted)]">
        SiteIntel reports are based on a representative sample, public data, and available third-party services.
      </footer>
    </div>
  );
}

interface ActionButtonProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  primary?: boolean;
}

function ActionButton({ icon, label, onClick, primary = false }: ActionButtonProps): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`pressable flex min-h-11 items-center gap-2 rounded-lg border px-3.5 text-sm font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--canvas)] sm:px-4 ${
        primary
          ? "border-[var(--surface-warm)] bg-[var(--surface-warm)] text-[var(--ink)]"
          : "border-white/25 bg-transparent text-white hover:border-white/50 hover:bg-white/10"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function SummaryMetric({ label, value }: { label: string; value: number }): React.JSX.Element {
  return (
    <div className="flex min-h-24 flex-col justify-center border-b border-white/15 p-5 even:border-l even:border-white/15 lg:min-h-0 lg:flex-row lg:items-center lg:justify-between lg:border-l-0 lg:px-6 lg:py-5">
      <dt className="text-sm font-semibold leading-5 text-[#d7dded]">{label}</dt>
      <dd className="font-display mt-1 text-3xl font-extrabold text-white lg:mt-0">{value}</dd>
    </div>
  );
}
