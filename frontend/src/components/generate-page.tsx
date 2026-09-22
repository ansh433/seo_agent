import {
  ArrowRight,
  ChartLineUp,
  CheckCircle,
  Code,
  FileMagnifyingGlass,
  GlobeSimple,
  Lightning,
  MagnifyingGlass,
  Robot,
  ShieldCheck,
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
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <AppHeader />
      <main>
        <section className="relative overflow-hidden border-b border-[var(--line)]">
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-[34rem] opacity-45"
            aria-hidden="true"
            style={{
              backgroundImage:
                "radial-gradient(circle at 50% 0%, rgba(255,176,176,0.9), transparent 44%), linear-gradient(rgba(13,25,51,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(13,25,51,0.06) 1px, transparent 1px)",
              backgroundSize: "auto, 32px 32px, 32px 32px",
              maskImage: "linear-gradient(to bottom, black, transparent)",
            }}
          />

          <div className="relative mx-auto w-full max-w-[76rem] px-5 pb-14 pt-16 sm:px-8 sm:pb-20 sm:pt-24 lg:pt-28">
            <div className="mx-auto max-w-[58rem] text-center">
              <p className="mx-auto mb-5 flex w-fit items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--surface-warm)] px-3.5 py-2 text-sm font-bold text-[var(--ink)]">
                <MagnifyingGlass size={17} weight="bold" aria-hidden="true" />
                Technical SEO &amp; AI discoverability
              </p>
              <h1 className="font-display text-[clamp(2.8rem,7.4vw,6rem)] font-extrabold leading-[0.93] text-[var(--ink)]">
                Find what blocks your site from being found.
              </h1>
              <p className="mx-auto mt-7 max-w-[43rem] text-[1.05rem] leading-7 text-[var(--ink-muted)] sm:text-xl sm:leading-8">
                SiteIntel turns a representative sample of your website into traceable
                findings, PageSpeed evidence, and developer-ready fixes—without hiding
                uncertainty behind a made-up score.
              </p>
            </div>

            <form
              id="audit-form"
              onSubmit={handleSubmit}
              className="mx-auto mt-9 max-w-[46rem] scroll-mt-6"
              noValidate
            >
              <label htmlFor="website-url" className="sr-only">
                Website URL
              </label>
              <div className="flex flex-col gap-2 rounded-xl border border-[var(--line)] bg-white p-2 shadow-[0_18px_50px_rgba(13,25,51,0.12)] sm:flex-row">
                <div className="flex min-h-14 min-w-0 flex-1 items-center gap-3 rounded-lg px-3 focus-within:ring-2 focus-within:ring-[var(--ink)]">
                  <GlobeSimple
                    size={21}
                    className="shrink-0 text-[var(--ink-muted)]"
                    aria-hidden="true"
                  />
                  <input
                    id="website-url"
                    name="website_url"
                    type="url"
                    inputMode="url"
                    autoComplete="url"
                    placeholder="yourwebsite.com"
                    value={websiteUrl}
                    onChange={(event) => {
                      setWebsiteUrl(event.target.value);
                      if (localError) setLocalError(null);
                    }}
                    disabled={isLoading}
                    aria-describedby={shownError ? "url-error audit-note" : "audit-note"}
                    aria-invalid={Boolean(shownError)}
                    className="min-w-0 flex-1 bg-transparent py-3 text-base text-[var(--ink)] outline-none placeholder:text-[#69758a] disabled:cursor-not-allowed"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isLoading || websiteUrl.trim().length === 0}
                  className="pressable flex min-h-14 shrink-0 items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-6 text-base font-bold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:translate-y-0"
                >
                  {isLoading ? (
                    <>
                      <SpinnerGap size={21} className="animate-spin" aria-hidden="true" />
                      Running audit…
                    </>
                  ) : (
                    <>
                      Audit my site
                      <ArrowRight size={20} weight="bold" aria-hidden="true" />
                    </>
                  )}
                </button>
              </div>

              {shownError && (
                <div
                  id="url-error"
                  role="alert"
                  className="mt-3 flex items-start gap-2 rounded-lg border border-[var(--ink)] bg-[var(--signal)] px-3.5 py-3 text-left text-sm leading-5 text-[var(--ink)]"
                >
                  <WarningCircle size={20} weight="fill" className="mt-px shrink-0" />
                  <span>{shownError}</span>
                </div>
              )}

              <p id="audit-note" className="mt-3 text-center text-xs leading-5 text-[var(--ink-muted)]">
                No account or configuration. Audits run synchronously and can take a few minutes.
              </p>
            </form>

            <ul className="mx-auto mt-8 flex max-w-[45rem] flex-wrap justify-center gap-x-6 gap-y-2 text-sm font-semibold text-[var(--ink-muted)]" aria-label="Audit qualities">
              <li className="flex items-center gap-2"><CheckCircle size={17} weight="fill" aria-hidden="true" /> Evidence attached</li>
              <li className="flex items-center gap-2"><CheckCircle size={17} weight="fill" aria-hidden="true" /> Scope disclosed</li>
              <li className="flex items-center gap-2"><CheckCircle size={17} weight="fill" aria-hidden="true" /> JSON export</li>
            </ul>

            <AuditPreview />
          </div>
        </section>

        <section aria-label="Audit coverage summary" className="border-b border-[var(--line)] bg-white">
          <dl className="mx-auto grid w-full max-w-[76rem] grid-cols-2 px-5 sm:px-8 lg:grid-cols-4">
            <CoverageStat value="Technical" label="crawl, index & markup checks" />
            <CoverageStat value="Measured" label="PageSpeed data when available" />
            <CoverageStat value="Qualified" label="public AI discoverability signals" />
            <CoverageStat value="Actionable" label="fixes with verification steps" />
          </dl>
        </section>

        <section id="what-it-checks" aria-labelledby="audit-anatomy" className="scroll-mt-6 border-b border-[var(--line)] bg-[var(--surface-warm)]">
          <div className="mx-auto grid w-full max-w-[76rem] gap-12 px-5 py-16 sm:px-8 sm:py-24 lg:grid-cols-[0.8fr_1.2fr] lg:gap-24">
            <div className="lg:sticky lg:top-8 lg:self-start">
              <h2 id="audit-anatomy" className="font-display max-w-[12ch] text-[clamp(2.35rem,5vw,4.4rem)] font-extrabold leading-[0.98] text-[var(--ink)]">
                An audit you can actually use.
              </h2>
              <p className="mt-6 max-w-[32rem] text-base leading-7 text-[var(--ink-muted)] sm:text-lg sm:leading-8">
                Every conclusion stays close to the page, signal, and collection state that
                produced it. The report is designed for handoff, not just presentation.
              </p>
              <div className="mt-8 rounded-xl border border-[var(--line)] bg-[var(--canvas)] p-5">
                <p className="text-sm font-bold text-[var(--ink)]">Honest by design</p>
                <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
                  Missing provider data is shown as unavailable. Experimental AI-facing
                  conventions are described as observations, not ranking requirements.
                </p>
              </div>
            </div>

            <div className="border-y border-[var(--line)]">
              <AuditLayer
                icon={<FileMagnifyingGlass size={26} weight="duotone" />}
                title="Find the technical blockers"
                text="Review crawlability, indexability, metadata, canonicals, links, and structured data across the selected sample."
                note="Observed evidence remains attached to every finding."
                tone="bg-[var(--canvas)]"
              />
              <AuditLayer
                icon={<ChartLineUp size={26} weight="duotone" />}
                title="Separate performance fact from guesswork"
                text="Keep mobile or desktop PageSpeed results, lab metrics, field data, and collection warnings in their proper context."
                note="Unavailable data never silently becomes a zero."
                tone="bg-white"
              />
              <AuditLayer
                icon={<Robot size={26} weight="duotone" />}
                title="Inspect public AI-facing signals"
                text="See how accessible the site's public product information is to AI systems, with careful language around experimental conventions."
                note="No invented AI-readiness score."
                tone="bg-[var(--signal)]"
              />
              <AuditLayer
                icon={<Code size={26} weight="duotone" />}
                title="Hand developers a plan"
                text="Move from finding to affected URL, recommended change, implementation note, and a concrete verification step."
                note="Remediation briefs link back to the evidence that produced them."
                tone="bg-[var(--canvas)]"
              />
            </div>
          </div>
        </section>

        <section aria-labelledby="workflow-title" className="bg-[var(--ink)] text-white">
          <div className="mx-auto w-full max-w-[76rem] px-5 py-16 sm:px-8 sm:py-24">
            <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-end lg:gap-20">
              <div>
                <h2 id="workflow-title" className="font-display max-w-[10ch] text-[clamp(2.4rem,5vw,4.5rem)] font-extrabold leading-[0.98] text-white">
                  From public page to verifiable fix.
                </h2>
              </div>
              <p className="max-w-[36rem] text-base leading-7 text-[#d7dded] sm:text-lg sm:leading-8">
                SiteIntel follows one visible chain of reasoning. That makes the report
                easier to challenge, prioritize, and turn into work.
              </p>
            </div>

            <ol className="mt-12 grid border-y border-white/20 sm:grid-cols-2 lg:grid-cols-4">
              <WorkflowStep number="01" title="Sample" text="Select representative public pages." />
              <WorkflowStep number="02" title="Observe" text="Collect HTTP, HTML, and available provider data." />
              <WorkflowStep number="03" title="Evaluate" text="Run deterministic checks and qualified analysis." />
              <WorkflowStep number="04" title="Remediate" text="Map findings to changes and verification." />
            </ol>

            <div className="mt-12 grid overflow-hidden rounded-xl border border-white/20 bg-white text-[var(--ink)] lg:grid-cols-[0.75fr_1.25fr]">
              <div className="bg-[var(--signal)] p-6 sm:p-8">
                <div className="flex items-center gap-2 text-sm font-bold">
                  <Lightning size={20} weight="fill" aria-hidden="true" />
                  Example finding
                </div>
                <h3 className="font-display mt-5 text-3xl font-extrabold leading-tight">
                  Product pages are missing product structured data.
                </h3>
                <p className="mt-4 text-sm leading-6 text-[var(--ink-muted)]">
                  Verified · High priority · 4 affected URLs
                </p>
              </div>
              <div className="grid sm:grid-cols-2">
                <EvidenceCell label="Evidence" text="No Product or SoftwareApplication JSON-LD was observed on sampled product pages." />
                <EvidenceCell label="Recommended change" text="Add supported product markup with only visible, verifiable properties." />
                <EvidenceCell label="Verification" text="Validate the rendered block, then re-run the audit and confirm the entity is detected." />
                <EvidenceCell label="Implementation note" text="Keep prices, ratings, and availability out unless the page visibly supports them." />
              </div>
            </div>
          </div>
        </section>

        <section className="bg-[var(--canvas)]">
          <div className="mx-auto flex w-full max-w-[76rem] flex-col items-start justify-between gap-8 px-5 py-16 sm:px-8 sm:py-20 lg:flex-row lg:items-center">
            <div>
              <h2 className="font-display max-w-[14ch] text-4xl font-extrabold leading-[1.02] text-[var(--ink)] sm:text-5xl">
                Start with the site you have.
              </h2>
              <p className="mt-4 max-w-[38rem] text-base leading-7 text-[var(--ink-muted)]">
                Get a focused report that tells you what was checked, what was found,
                and what your team can verify next.
              </p>
            </div>
            <a
              href="#audit-form"
              className="pressable flex min-h-14 shrink-0 items-center gap-2 rounded-lg bg-[var(--ink)] px-6 text-base font-bold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--canvas)]"
            >
              Audit a website
              <ArrowRight size={20} weight="bold" aria-hidden="true" />
            </a>
          </div>
        </section>
      </main>
    </div>
  );
}

function AuditPreview(): React.JSX.Element {
  return (
    <article id="report-preview" className="relative mx-auto mt-12 max-w-[68rem] scroll-mt-6 overflow-hidden rounded-2xl border border-[var(--line)] bg-white shadow-[0_28px_80px_rgba(13,25,51,0.16)] sm:mt-16">
      <header className="flex flex-col gap-4 border-b border-[var(--line)] px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-[var(--surface-warm)]">
            <ShieldCheck size={22} weight="duotone" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-bold text-[#315f43]">Audit complete</p>
            <p className="truncate text-base font-extrabold">acme.com</p>
          </div>
        </div>
        <span className="w-fit rounded-full border border-[var(--line)] bg-[var(--canvas)] px-3 py-1.5 text-xs font-bold">
          Representative sample · 3 pages
        </span>
      </header>

      <div className="grid md:grid-cols-[10rem_minmax(0,1fr)]">
        <nav className="hidden border-r border-[var(--line)] bg-[#f8f7ef] p-4 text-xs font-semibold text-[var(--ink-muted)] md:block" aria-label="Example report sections">
          <p className="rounded-md bg-white px-3 py-2.5 text-[var(--ink)]">Overview</p>
          <p className="px-3 py-2.5">Findings</p>
          <p className="px-3 py-2.5">Performance</p>
          <p className="px-3 py-2.5">AI discoverability</p>
          <p className="px-3 py-2.5">Remediation</p>
          <p className="px-3 py-2.5">Scope</p>
        </nav>

        <div className="min-w-0 bg-[#fbfbf7] p-4 sm:p-6 lg:p-8">
          <section className="overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--surface-warm)]">
            <div className="p-5 sm:p-6">
              <p className="flex items-center gap-2 text-xs font-bold">
                <ShieldCheck size={17} weight="duotone" aria-hidden="true" /> Executive summary
              </p>
              <h2 className="font-display mt-3 max-w-[40rem] text-xl font-extrabold leading-tight sm:text-2xl">
                The sampled site is crawlable, with clear opportunities in structured data and mobile performance.
              </h2>
            </div>
            <dl className="grid grid-cols-3 border-t border-[var(--line)] bg-white">
              <PreviewMetric label="Findings" value="7" />
              <PreviewMetric label="Verified" value="4" />
              <PreviewMetric label="Needs review" value="2" />
            </dl>
          </section>

          <div className="mt-5 flex items-center justify-between gap-4">
            <h3 className="text-sm font-extrabold">Priority findings</h3>
            <span className="text-xs font-semibold text-[var(--ink-muted)]">Evidence attached</span>
          </div>
          <div className="mt-3 space-y-2">
            <PreviewFinding status="Verified" title="Product structured data is missing" meta="High · 4 affected URLs" tone="bg-[var(--signal)]" />
            <PreviewFinding status="Needs review" title="Mobile LCP exceeds the target" meta="Medium · PageSpeed lab data" tone="bg-[var(--surface-warm)]" />
            <PreviewFinding status="Observed" title="No llms.txt file was found" meta="Informational · Experimental convention" tone="bg-[var(--canvas)]" />
          </div>
        </div>
      </div>
    </article>
  );
}

function PreviewMetric({ label, value }: { label: string; value: string }): React.JSX.Element {
  return (
    <div className="border-l border-[var(--line)] p-3 first:border-l-0 sm:p-4">
      <dt className="text-[0.65rem] font-semibold text-[var(--ink-muted)] sm:text-xs">{label}</dt>
      <dd className="mt-1 text-lg font-extrabold sm:text-xl">{value}</dd>
    </div>
  );
}

interface PreviewFindingProps {
  meta: string;
  status: string;
  title: string;
  tone: string;
}

function PreviewFinding({ meta, status, title, tone }: PreviewFindingProps): React.JSX.Element {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-[var(--line)] bg-white p-3 sm:items-center sm:p-4">
      <span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-full ${tone} sm:mt-0`}>
        <CheckCircle size={17} weight="fill" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-bold text-[var(--ink-muted)]">{status}</p>
        <p className="mt-0.5 text-sm font-extrabold leading-5">{title}</p>
      </div>
      <p className="hidden shrink-0 text-xs font-semibold text-[var(--ink-muted)] sm:block">{meta}</p>
    </div>
  );
}

function CoverageStat({ label, value }: { label: string; value: string }): React.JSX.Element {
  return (
    <div className="border-b border-[var(--line)] py-6 odd:pr-4 even:border-l even:pl-4 sm:py-8 lg:border-b-0 lg:border-l lg:px-6 lg:first:border-l-0 lg:first:pl-0">
      <dt className="text-base font-extrabold text-[var(--ink)]">{value}</dt>
      <dd className="mt-1 text-xs leading-5 text-[var(--ink-muted)] sm:text-sm">{label}</dd>
    </div>
  );
}

interface AuditLayerProps {
  icon: React.ReactNode;
  note: string;
  text: string;
  title: string;
  tone: string;
}

function AuditLayer({ icon, note, text, title, tone }: AuditLayerProps): React.JSX.Element {
  return (
    <article className="grid gap-5 border-b border-[var(--line)] py-7 last:border-b-0 sm:grid-cols-[3.5rem_1fr] sm:py-9">
      <span className={`grid size-12 place-items-center rounded-lg border border-[var(--line)] text-[var(--ink)] ${tone}`} aria-hidden="true">
        {icon}
      </span>
      <div>
        <h3 className="text-xl font-extrabold tracking-[-0.03em] text-[var(--ink)] sm:text-2xl">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)] sm:text-base sm:leading-7">{text}</p>
        <p className="mt-4 text-sm font-bold leading-6 text-[var(--ink)]">{note}</p>
      </div>
    </article>
  );
}

function WorkflowStep({ number, text, title }: { number: string; text: string; title: string }): React.JSX.Element {
  return (
    <li className="border-b border-white/20 px-0 py-6 sm:border-l sm:px-6 sm:first:border-l-0 lg:border-b-0 lg:px-7">
      <p className="font-mono text-xs font-bold text-[#ffb0b0]">{number}</p>
      <h3 className="mt-4 text-lg font-extrabold text-white">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[#d7dded]">{text}</p>
    </li>
  );
}

function EvidenceCell({ label, text }: { label: string; text: string }): React.JSX.Element {
  return (
    <div className="border-b border-[var(--line)] p-5 odd:sm:border-r sm:p-6">
      <p className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--ink-muted)]">{label}</p>
      <p className="mt-2 text-sm leading-6 text-[var(--ink)]">{text}</p>
    </div>
  );
}
