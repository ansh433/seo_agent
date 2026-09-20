import type { AuditReport } from "../types/audit";
import { AppHeader } from "./app-header";

interface ReportPageProps {
  onStartOver: () => void;
  report: AuditReport;
}

/** Temporary report shell; replaced by the full report UI in commit 19. */
export function ReportPage({ onStartOver, report }: ReportPageProps): React.JSX.Element {
  return (
    <div className="min-h-screen bg-[#f5f7f4] text-[#0d1933]">
      <AppHeader compact />
      <main className="mx-auto w-full max-w-[76rem] px-5 py-12 sm:px-8">
        <p className="text-sm font-bold text-[#087d45]">Audit complete</p>
        <h1 className="mt-2 break-all font-display text-3xl font-bold">{report.website_url}</h1>
        <p className="mt-4 max-w-[48rem] text-base leading-7 text-[#53617a]">{report.summary}</p>
        <button
          type="button"
          onClick={onStartOver}
          className="mt-6 min-h-11 rounded-xl border border-[#c8d2df] bg-white px-4 text-sm font-bold text-[#075ee5]"
        >
          New audit
        </button>
      </main>
    </div>
  );
}
