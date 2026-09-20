import {
  ArrowRight,
  ChartLineUp,
  Code,
  FileMagnifyingGlass,
  GlobeSimple,
  MagnifyingGlass,
  Robot,
  SpinnerGap,
  WarningCircle,
} from "@phosphor-icons/react";
import { useState } from "react";

import { AppHeader } from "./app-header";

interface GeneratePageProps {
  error: string | null;
  isLoading: boolean;
  onSubmit: (websiteUrl: string) => void;
}

const normalizeWebsiteUrl = (value: string): string => {
  const trimmed = value.trim();
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
};

const validWebsiteUrl = (value: string): boolean => {
  try {
    const url = new URL(normalizeWebsiteUrl(value));
    return (url.protocol === "http:" || url.protocol === "https:") && url.hostname.includes(".");
  } catch {
    return false;
  }
};

/** URL entry experience for starting a real audit. */
export function GeneratePage({
  error,
  isLoading,
  onSubmit,
}: GeneratePageProps): React.JSX.Element {
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!validWebsiteUrl(websiteUrl)) {
      setLocalError("Enter a public website address, such as https://example.com.");
      return;
    }
    setLocalError(null);
    onSubmit(normalizeWebsiteUrl(websiteUrl));
  };

  const shownError = localError ?? error;

  return (
    <div className="min-h-screen bg-[#f6f7f3] text-[#0d1933]">
      <AppHeader />
      <main>
        <section className="relative overflow-hidden border-b border-[#dde3e0] bg-[#fbfcf9]">
          <div className="mx-auto grid w-full max-w-[76rem] gap-12 px-5 py-16 sm:px-8 sm:py-20 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:gap-20 lg:py-28">
            <div>
              <p className="mb-5 flex items-center gap-2 text-sm font-bold text-[#075ee5]">
                <MagnifyingGlass size={18} weight="bold" aria-hidden="true" />
                Technical SEO &amp; AI discoverability
              </p>
              <h1 className="font-display max-w-[12ch] text-[clamp(2.75rem,7vw,5.5rem)] font-bold leading-[0.94] tracking-[-0.055em] text-[#0d1933]">
                See what search engines see.
              </h1>
              <p className="mt-7 max-w-[39rem] text-[1.06rem] leading-7 text-[#53617a] sm:text-lg sm:leading-8">
                Generate an evidence-backed report across crawlability, indexability,
                performance, structured data, and public AI discoverability signals.
              </p>
            </div>

            <div>
              <form
                onSubmit={handleSubmit}
                className="rounded-[1.65rem] border border-[#d9dfdc] bg-white p-5 shadow-[0_24px_60px_rgba(19,35,56,0.10)] sm:p-8"
                noValidate
              >
                <div className="mb-7 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="font-display text-[1.65rem] font-bold tracking-[-0.025em] text-[#0d1933]">
                      Generate your report
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-[#66728a]">
                      One URL. No configuration required.
                    </p>
                  </div>
                  <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-[#edf3ff] text-[#075ee5]">
                    <GlobeSimple size={23} weight="duotone" aria-hidden="true" />
                  </span>
                </div>

                <label htmlFor="website-url" className="text-sm font-bold text-[#25334d]">
                  Website URL
                </label>
                <div className="mt-2 flex min-h-14 items-center gap-2 rounded-xl border border-[#b8c2cf] bg-white px-4 shadow-[inset_0_1px_2px_rgba(13,25,51,0.04)] focus-within:border-[#0b63f6] focus-within:ring-4 focus-within:ring-[#dfeaff]">
                  <GlobeSimple size={20} className="shrink-0 text-[#63718a]" aria-hidden="true" />
                  <input
                    id="website-url"
                    name="website_url"
                    type="url"
                    inputMode="url"
                    autoComplete="url"
                    placeholder="https://example.com"
                    value={websiteUrl}
                    onChange={(event) => {
                      setWebsiteUrl(event.target.value);
                      if (localError) setLocalError(null);
                    }}
                    disabled={isLoading}
                    aria-describedby={shownError ? "url-error audit-note" : "audit-note"}
                    aria-invalid={Boolean(shownError)}
                    className="min-w-0 flex-1 bg-transparent py-3 text-base text-[#0d1933] outline-none placeholder:text-[#66728a] disabled:cursor-not-allowed"
                  />
                </div>

                {shownError && (
                  <div
                    id="url-error"
                    role="alert"
                    className="mt-3 flex items-start gap-2 rounded-xl border border-[#f3b7b6] bg-[#fff1f0] px-3.5 py-3 text-sm leading-5 text-[#a92523]"
                  >
                    <WarningCircle size={20} weight="fill" className="mt-px shrink-0" />
                    <span>{shownError}</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isLoading || websiteUrl.trim().length === 0}
                  className="mt-4 flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-[#075ee5] px-5 text-base font-bold text-white shadow-[0_10px_24px_rgba(7,94,229,0.22)] transition-[background-color,transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:bg-[#064fc1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0b63f6] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:translate-y-0"
                >
                  {isLoading ? (
                    <>
                      <SpinnerGap size={21} className="animate-spin" aria-hidden="true" />
                      Running the audit…
                    </>
                  ) : (
                    <>
                      Generate report
                      <ArrowRight size={20} weight="bold" aria-hidden="true" />
                    </>
                  )}
                </button>

                <p id="audit-note" className="mt-4 text-center text-xs leading-5 text-[#66728a]">
                  The audit runs synchronously and may take a few minutes. We inspect a
                  representative sample—not an exhaustive crawl.
                </p>
              </form>
            </div>
          </div>
        </section>

        <section aria-labelledby="audit-includes" className="mx-auto w-full max-w-[76rem] px-5 py-14 sm:px-8 sm:py-20">
          <div className="grid gap-10 lg:grid-cols-[0.7fr_1.3fr] lg:gap-20">
            <div>
              <h2 id="audit-includes" className="font-display text-4xl font-bold tracking-[-0.035em] text-[#0d1933]">
                A useful audit, not a wall of warnings.
              </h2>
              <p className="mt-4 text-base leading-7 text-[#5b6880]">
                SiteIntel connects every recommendation to observed evidence and makes
                uncertainty visible.
              </p>
            </div>

            <div className="divide-y divide-[#d9dfdc] border-y border-[#d9dfdc]">
              <FeatureRow
                icon={<FileMagnifyingGlass size={24} weight="duotone" />}
                title="Technical findings"
                text="Crawlability, indexability, metadata, canonicals, links, and structured data."
                tone="blue"
              />
              <FeatureRow
                icon={<ChartLineUp size={24} weight="duotone" />}
                title="Performance"
                text="Page-level mobile or desktop PageSpeed results, with lab and field data kept separate."
                tone="green"
              />
              <FeatureRow
                icon={<Robot size={24} weight="duotone" />}
                title="AI discoverability"
                text="Plain-language observations about public information accessibility—without invented scores."
                tone="violet"
              />
              <FeatureRow
                icon={<Code size={24} weight="duotone" />}
                title="Remediation briefs"
                text="Copy-ready technical changes and verification steps for developers."
                tone="amber"
              />
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

interface FeatureRowProps {
  icon: React.ReactNode;
  text: string;
  title: string;
  tone: "amber" | "blue" | "green" | "violet";
}

const toneClasses: Record<FeatureRowProps["tone"], string> = {
  amber: "bg-[#fff4dc] text-[#b65e00]",
  blue: "bg-[#eaf1ff] text-[#075ee5]",
  green: "bg-[#e5f8ec] text-[#078649]",
  violet: "bg-[#f0ebff] text-[#6842c2]",
};

function FeatureRow({ icon, text, title, tone }: FeatureRowProps): React.JSX.Element {
  return (
    <article className="grid gap-3 py-6 sm:grid-cols-[3.25rem_11rem_1fr] sm:items-center sm:gap-5">
      <span className={`grid size-11 place-items-center rounded-xl ${toneClasses[tone]}`} aria-hidden="true">
        {icon}
      </span>
      <h3 className="font-display text-xl font-bold text-[#14203a]">{title}</h3>
      <p className="text-sm leading-6 text-[#5b6880] sm:text-base">{text}</p>
    </article>
  );
}
