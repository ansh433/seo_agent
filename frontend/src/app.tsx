import { useState } from "react";

import { AuditApiError, createAudit } from "./api/audits";
import { GeneratePage } from "./components/generate-page";
import { ReportPage } from "./components/report-page";
import type { AuditReport } from "./types/audit";

/** Root application state for generating and reading one audit report. */
export function App(): React.JSX.Element {
  const [report, setReport] = useState<AuditReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (websiteUrl: string): Promise<void> => {
    if (isLoading) return;

    setError(null);
    setIsLoading(true);
    try {
      const auditReport = await createAudit(websiteUrl);
      setReport(auditReport);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (requestError: unknown) {
      setError(
        requestError instanceof AuditApiError
          ? requestError.message
          : "Something unexpected happened while running the audit. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartOver = (): void => {
    setReport(null);
    setError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return report ? (
    <ReportPage report={report} onStartOver={handleStartOver} />
  ) : (
    <GeneratePage error={error} isLoading={isLoading} onSubmit={(url) => void handleSubmit(url)} />
  );
}
