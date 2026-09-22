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
  critical: "border-[var(--signal)] bg-[var(--signal)] text-[var(--ink)]",
  high: "border-[var(--line)] bg-[var(--surface-warm)] text-[var(--ink)]",
  medium: "border-[var(--line)] bg-[var(--surface-warm)] text-[var(--ink)]",
  low: "border-[var(--line)] bg-[var(--canvas)] text-[var(--ink)]",
  informational: "border-[var(--line)] bg-white text-[var(--ink-muted)]",
  unrated: "border-[var(--line)] bg-white text-[var(--ink-muted)]",
};

const statusClasses: Record<FindingStatus, string> = {
  verified: "bg-[var(--surface-warm)] text-[var(--ink)]",
  observed: "bg-[var(--canvas)] text-[var(--ink)]",
  needs_review: "bg-[var(--signal)] text-[var(--ink)]",
  dismissed: "border border-[var(--line)] bg-white text-[var(--ink-muted)]",
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
    <article className="overflow-hidden rounded-xl border border-[var(--line)] bg-white">
      <details className="group" open={rank === 1}>
        <summary className="flex min-h-[7rem] cursor-pointer list-none items-start gap-3 p-5 outline-none marker:hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--ink)] sm:gap-5 sm:p-6">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-[var(--ink)] text-sm font-extrabold text-white">
            {rank}
          </span>
          <span className="min-w-0 flex-1">
            <span className="mb-3 flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${statusClasses[finding.status]}`}>
                {statusIcons[finding.status]}
                {titleCase(finding.status)}
              </span>
              <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${severityClasses[severity]}`}>
                {titleCase(severity)}
              </span>
            </span>
            <span className="block font-display text-xl font-extrabold leading-7 text-[var(--ink)] sm:text-[1.4rem] sm:leading-8">
              {finding.title}
            </span>
            <span className="mt-2 block text-sm font-medium leading-5 text-[var(--ink-muted)]">
              {finding.affected_urls.length === 0
                ? "No affected URLs listed"
                : `${finding.affected_urls.length} affected ${finding.affected_urls.length === 1 ? "URL" : "URLs"}`}
              <span aria-hidden="true"> · </span>
              {titleCase(finding.issue_type)}
            </span>
          </span>
          <CaretDown
            size={20}
            weight="bold"
            className="mt-2 shrink-0 rounded-full bg-[var(--canvas)] p-1 text-[var(--ink)] transition-transform duration-200 group-open:rotate-180"
            aria-hidden="true"
          />
        </summary>

        <div className="border-t border-[var(--line)] bg-[var(--canvas)] px-5 pb-6 pt-6 sm:px-6 sm:pb-7">
          <div className="grid gap-x-8 gap-y-6 lg:grid-cols-2">
            <FindingField title="What we observed" text={finding.observation} />
            <FindingField title="Why it matters" text={finding.explanation} />
            <FindingField title="Potential impact" text={finding.potential_impact} />
            <FindingField title="Recommended action" text={finding.recommendation} />
          </div>

          {finding.affected_urls.length > 0 && (
            <div className="mt-7 border-t border-[var(--line)] pt-6">
              <h4 className="text-base font-extrabold text-[var(--ink)]">Affected URLs</h4>
              <ul className="mt-2 space-y-2">
                {finding.affected_urls.map((url) => (
                  <li key={url} className="break-all rounded-lg border border-[var(--line)] bg-white px-3 py-2.5 font-mono text-xs leading-5 text-[var(--ink-muted)]">
                    {url}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {finding.evidence.length > 0 && (
            <div className="mt-7 border-t border-[var(--line)] pt-6">
              <h4 className="text-base font-extrabold text-[var(--ink)]">Evidence</h4>
              <p className="mt-1 text-sm leading-6 text-[var(--ink-muted)]">Raw observed values retained for verification.</p>
              <div className="mt-3 space-y-3">
                {finding.evidence.map((evidence, index) => (
                  <div key={`${evidence.source_url}-${evidence.signal}-${index}`} className="overflow-hidden rounded-lg border border-[var(--ink)] bg-[var(--ink)]">
                    <div className="border-b border-white/15 px-4 py-3 text-xs leading-5 text-[#d7dded]">
                      <span className="font-bold text-white">{evidence.signal}</span>
                      <span aria-hidden="true"> · </span>
                      <span className="break-all">{evidence.source_url}</span>
                    </div>
                    <pre className="max-h-72 overflow-auto p-4 font-mono text-xs leading-5 text-white">
                      {JSON.stringify(evidence.observed_value, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(finding.evaluation_reason || finding.confidence !== null) && (
            <div className="mt-6 rounded-lg border border-[var(--line)] bg-[var(--surface-warm)] p-5">
              <div className="flex items-center gap-2 text-sm font-bold text-[var(--ink)]">
                <CheckCircle size={18} weight="duotone" />
                Evaluation
              </div>
              {finding.evaluation_reason && (
                <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">{finding.evaluation_reason}</p>
              )}
              {finding.confidence !== null && (
                <p className="mt-2 text-xs font-bold text-[var(--ink)]">
                  Confidence: {Math.round(finding.confidence * 100)}%
                </p>
              )}
            </div>
          )}

          {finding.missing_information.length > 0 && (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-[var(--signal)] bg-[var(--signal)] p-4 text-sm leading-6 text-[var(--ink)]">
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
    <div className="border-t border-[var(--line)] pt-4">
      <h4 className="text-sm font-extrabold text-[var(--ink)]">{title}</h4>
      <p className="mt-2 text-base leading-7 text-[var(--ink-muted)]">
        {text ?? "No additional information was provided."}
      </p>
    </div>
  );
}
