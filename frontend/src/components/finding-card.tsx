import {
  CaretDown,
  CheckCircle,
  Eye,
  Question,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react";

import type { Finding, FindingStatus, Severity } from "../types/audit";

interface FindingCardProps {
  finding: Finding;
  rank: number;
}

const severityClasses: Record<Severity | "unrated", string> = {
  critical: "border-[#e69a99] bg-[#fde8e7] text-[#a61f1d]",
  high: "border-[#f0b6b5] bg-[#fff0ef] text-[#b62523]",
  medium: "border-[#f1d39c] bg-[#fff5df] text-[#9a5500]",
  low: "border-[#b9d0f8] bg-[#edf3ff] text-[#1554ae]",
  informational: "border-[#cad2dd] bg-[#f2f4f7] text-[#4b5a70]",
  unrated: "border-[#cad2dd] bg-[#f2f4f7] text-[#4b5a70]",
};

const statusClasses: Record<FindingStatus, string> = {
  verified: "text-[#087a43]",
  observed: "text-[#1554ae]",
  needs_review: "text-[#9a5500]",
  dismissed: "text-[#647188]",
};

const statusIcons: Record<FindingStatus, React.ReactNode> = {
  verified: <CheckCircle size={17} weight="fill" aria-hidden="true" />,
  observed: <Eye size={17} weight="fill" aria-hidden="true" />,
  needs_review: <Question size={17} weight="fill" aria-hidden="true" />,
  dismissed: <XCircle size={17} weight="fill" aria-hidden="true" />,
};

const titleCase = (value: string): string =>
  value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());

/** Expandable, evidence-backed audit finding. */
export function FindingCard({ finding, rank }: FindingCardProps): React.JSX.Element {
  const severity = finding.severity ?? "unrated";

  return (
    <article className="rounded-2xl border border-[#dbe1df] bg-white shadow-[0_8px_30px_rgba(18,31,52,0.045)]">
      <details className="group">
        <summary className="flex min-h-[7.25rem] cursor-pointer list-none items-start gap-3 p-4 outline-none marker:hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0b63f6] sm:gap-4 sm:p-5">
          <span className="grid size-9 shrink-0 place-items-center rounded-full border border-[#cdd5df] bg-[#f8f9f8] text-sm font-bold text-[#25334d]">
            {rank}
          </span>
          <span className="min-w-0 flex-1">
            <span className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 text-xs font-bold ${statusClasses[finding.status]}`}>
                {statusIcons[finding.status]}
                {titleCase(finding.status)}
              </span>
              <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${severityClasses[severity]}`}>
                {titleCase(severity)}
              </span>
            </span>
            <span className="block font-display text-[1.15rem] font-bold leading-6 text-[#14203a] sm:text-xl">
              {finding.title}
            </span>
            <span className="mt-1.5 block text-sm leading-5 text-[#657189]">
              {finding.affected_urls.length === 0
                ? "No affected URLs listed"
                : `${finding.affected_urls.length} affected ${finding.affected_urls.length === 1 ? "URL" : "URLs"}`}
              <span aria-hidden="true"> · </span>
              {titleCase(finding.issue_type)}
            </span>
          </span>
          <CaretDown
            size={19}
            weight="bold"
            className="mt-1 shrink-0 text-[#5c6b83] transition-transform duration-200 group-open:rotate-180"
            aria-hidden="true"
          />
        </summary>

        <div className="border-t border-[#e2e6e4] px-4 pb-5 pt-5 sm:px-5 sm:pb-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <FindingField title="What we observed" text={finding.observation} />
            <FindingField title="Why it matters" text={finding.explanation} />
            <FindingField title="Potential impact" text={finding.potential_impact} />
            <FindingField title="Recommended action" text={finding.recommendation} />
          </div>

          {finding.affected_urls.length > 0 && (
            <div className="mt-6">
              <h4 className="text-sm font-bold text-[#25334d]">Affected URLs</h4>
              <ul className="mt-2 space-y-2">
                {finding.affected_urls.map((url) => (
                  <li key={url} className="break-all rounded-lg bg-[#f5f7f6] px-3 py-2 font-mono text-xs leading-5 text-[#40506a]">
                    {url}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {finding.evidence.length > 0 && (
            <div className="mt-6">
              <h4 className="text-sm font-bold text-[#25334d]">Evidence</h4>
              <div className="mt-2 space-y-3">
                {finding.evidence.map((evidence, index) => (
                  <div key={`${evidence.source_url}-${evidence.signal}-${index}`} className="overflow-hidden rounded-xl border border-[#d9dfdc] bg-[#f7f8f7]">
                    <div className="border-b border-[#d9dfdc] px-3 py-2 text-xs leading-5 text-[#526078]">
                      <span className="font-bold text-[#26344e]">{evidence.signal}</span>
                      <span aria-hidden="true"> · </span>
                      <span className="break-all">{evidence.source_url}</span>
                    </div>
                    <pre className="max-h-72 overflow-auto p-3 font-mono text-xs leading-5 text-[#25334d]">
                      {JSON.stringify(evidence.observed_value, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(finding.evaluation_reason || finding.confidence !== null) && (
            <div className="mt-6 rounded-xl border border-[#cddaf0] bg-[#f1f5fb] p-4">
              <div className="flex items-center gap-2 text-sm font-bold text-[#263b62]">
                <CheckCircle size={18} weight="duotone" />
                Evaluation
              </div>
              {finding.evaluation_reason && (
                <p className="mt-2 text-sm leading-6 text-[#485a76]">{finding.evaluation_reason}</p>
              )}
              {finding.confidence !== null && (
                <p className="mt-2 text-xs font-bold text-[#3f5270]">
                  Confidence: {Math.round(finding.confidence * 100)}%
                </p>
              )}
            </div>
          )}

          {finding.missing_information.length > 0 && (
            <div className="mt-4 flex items-start gap-2 rounded-xl border border-[#ead1a3] bg-[#fff7e7] p-4 text-sm leading-6 text-[#745018]">
              <WarningCircle size={19} weight="fill" className="mt-0.5 shrink-0" />
              <div>
                <p className="font-bold">Missing information</p>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  {finding.missing_information.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </details>
    </article>
  );
}

interface FindingFieldProps {
  text: string | null;
  title: string;
}

function FindingField({ text, title }: FindingFieldProps): React.JSX.Element {
  return (
    <div>
      <h4 className="text-sm font-bold text-[#25334d]">{title}</h4>
      <p className="mt-1.5 text-sm leading-6 text-[#5c6880]">
        {text ?? "No additional information was provided."}
      </p>
    </div>
  );
}
