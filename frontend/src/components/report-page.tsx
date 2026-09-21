import {
  ArrowCounterClockwise,
  CheckCircle,
  DownloadSimple,
  FileMagnifyingGlass,
  Printer,
  ShieldCheck,
} from "@phosphor-icons/react";
import { useMemo, useState } from "react";

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
  const orderedFindings = useMemo(() => sortedFindings(report.findings), [report.findings]);
  const priorityFindings = orderedFindings.filter((finding) => finding.status !== "dismissed").slice(0, 3);
  const visibleFindings = showAllFindings ? orderedFindings : priorityFindings;
  const verifiedCount = report.findings.filter((finding) => finding.status === "verified").length;
  const domain = hostnameFor(report.website_url);

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
    <div className="min-h-screen bg-[#f5f7f4] text-[#0d1933]">
      <AppHeader compact />

      <main>
        <header className="border-b border-[#dbe1df] bg-[#fbfcf9]">
          <div className="mx-auto w-full max-w-[76rem] px-5 py-7 sm:px-8 sm:py-10">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="min-w-0">
                <p className="mb-3 flex items-center gap-2 text-sm font-bold text-[#087d45]">
                  <CheckCircle size={19} weight="fill" aria-hidden="true" />
                  Audit complete
                </p>
                <h1 className="font-display text-[clamp(2.4rem,6vw,4.8rem)] font-bold leading-[0.95] tracking-[-0.05em] text-[#0d1933]">
                  {domain}
                </h1>
                <p className="mt-3 break-all font-mono text-xs leading-5 text-[#627087] sm:text-sm">
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

          <nav aria-label="Report sections" className="print:hidden overflow-x-auto border-t border-[#e2e6e4] bg-white">
            <div className="mx-auto flex min-w-max max-w-[76rem] px-3 sm:px-6">
              {reportSections.map(([id, label]) => (
                <a
                  key={id}
                  href={`#${id}`}
                  className="flex min-h-12 items-center border-b-2 border-transparent px-3 text-sm font-semibold text-[#58667d] transition-colors hover:border-[#075ee5] hover:text-[#075ee5] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0b63f6] sm:px-4"
                >
                  {label}
                </a>
              ))}
            </div>
          </nav>
        </header>

        <div className="mx-auto grid w-full max-w-[76rem] gap-8 px-5 py-8 sm:px-8 sm:py-12 lg:grid-cols-[12rem_minmax(0,1fr)] lg:gap-12">
          <aside className="print:hidden hidden lg:block">
            <nav aria-label="Report table of contents" className="sticky top-6">
              <p className="mb-3 text-xs font-bold uppercase tracking-[0.12em] text-[#5f6c81]">On this report</p>
              <ul className="space-y-1">
                {reportSections.map(([id, label]) => (
                  <li key={id}>
                    <a
                      href={`#${id}`}
                      className="flex min-h-10 items-center rounded-lg px-3 text-sm font-semibold text-[#59677e] transition-colors hover:bg-white hover:text-[#075ee5] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0b63f6]"
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
              <p className="mt-6 rounded-xl border border-[#d7dfdc] bg-white p-3 text-xs leading-5 text-[#657189]">
                Representative sampling keeps this audit focused. Scope details are included below.
              </p>
            </nav>
          </aside>

          <div className="min-w-0 space-y-14 sm:space-y-16">
            <section id="overview" className="scroll-mt-24">
              <div className="overflow-hidden rounded-[1.4rem] border border-[#cfe4d8] bg-[#f2fbf5] shadow-[0_14px_40px_rgba(18,70,44,0.055)]">
                <div className="p-5 sm:p-8 lg:p-10">
                  <div className="flex items-center gap-2 text-sm font-bold text-[#087d45]">
                    <ShieldCheck size={20} weight="duotone" />
                    Executive summary
                  </div>
                  <p className="font-display mt-5 max-w-[48rem] text-[1.65rem] font-bold leading-[1.15] tracking-[-0.025em] text-[#14203a] sm:text-3xl lg:text-[2.2rem]">
                    {report.summary || "No executive summary was provided."}
                  </p>
                  {report.site_context && (
                    <div className="mt-6 max-w-[48rem] border-t border-[#cee1d5] pt-5">
                      {report.site_context.business_name && (
                        <p className="text-sm font-bold text-[#284834]">{report.site_context.business_name}</p>
                      )}
                      <p className="mt-1 text-sm leading-6 text-[#4c6656] sm:text-base">{report.site_context.summary}</p>
                    </div>
                  )}
                </div>

                <dl className="grid grid-cols-2 border-t border-[#cfe4d8] bg-white/70 sm:grid-cols-4">
                  <SummaryMetric label="Total findings" value={report.findings.length} />
                  <SummaryMetric label="Verified" value={verifiedCount} />
                  <SummaryMetric label="Unresolved" value={report.unresolved_finding_ids.length} />
                  <SummaryMetric label="Pages selected" value={report.scope.selected_pages.length} />
                </dl>
              </div>
            </section>

            <section id="findings" className="report-section scroll-mt-24">
              <div className="flex items-end justify-between gap-4">
                <SectionHeading
                  icon={<FileMagnifyingGlass size={23} weight="duotone" />}
                  title="Findings"
                  introduction="Priority is based on the reported severity and evaluation status. Open a finding to inspect its reasoning and evidence."
                />
                {report.findings.length > priorityFindings.length && (
                  <button
                    type="button"
                    onClick={() => setShowAllFindings((current) => !current)}
                    className="print:hidden mb-6 hidden min-h-11 shrink-0 items-center rounded-xl border border-[#c8d2df] px-4 text-sm font-bold text-[#075ee5] hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0b63f6] sm:flex"
                  >
                    {showAllFindings ? "Show priority" : `View all ${report.findings.length}`}
                  </button>
                )}
              </div>

              {visibleFindings.length === 0 ? (
                <div className="flex items-center gap-3 rounded-2xl border border-[#cae3d4] bg-[#f1faf4] p-5 text-sm leading-6 text-[#326146]">
                  <CheckCircle size={21} weight="fill" className="shrink-0 text-[#087d45]" />
                  <p>No non-dismissed findings were reported for the sampled pages.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {visibleFindings.map((finding, index) => (
                    <FindingCard key={finding.id} finding={finding} rank={index + 1} />
                  ))}
                </div>
              )}

              {report.findings.length > priorityFindings.length && (
                <button
                  type="button"
                  onClick={() => setShowAllFindings((current) => !current)}
                  className="print:hidden mt-4 flex min-h-12 w-full items-center justify-center rounded-xl border border-[#c8d2df] bg-white px-4 text-sm font-bold text-[#075ee5] hover:bg-[#f8fafc] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0b63f6] sm:hidden"
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

      <footer className="border-t border-[#dbe1df] bg-[#fbfcf9] px-5 py-6 text-center text-xs leading-5 text-[#5e6a80]">
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
      className={`flex min-h-11 items-center gap-2 rounded-xl border px-3.5 text-sm font-bold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0b63f6] focus-visible:ring-offset-2 sm:px-4 ${
        primary
          ? "border-[#075ee5] bg-[#075ee5] text-white hover:bg-[#064fc1]"
          : "border-[#c8d2df] bg-white text-[#33445f] hover:border-[#91a4be] hover:bg-[#f7f9fb]"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function SummaryMetric({ label, value }: { label: string; value: number }): React.JSX.Element {
  return (
    <div className="border-b border-[#dfe6e2] p-4 even:border-l sm:border-b-0 sm:border-l sm:first:border-l-0 sm:p-5">
      <dt className="text-xs font-semibold leading-4 text-[#637088]">{label}</dt>
      <dd className="font-display mt-1 text-2xl font-bold text-[#14203a]">{value}</dd>
    </div>
  );
}
