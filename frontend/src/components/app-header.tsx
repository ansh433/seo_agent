import { ArrowDown, GlobeHemisphereWest, ShieldCheck } from "@phosphor-icons/react";

interface AppHeaderProps {
  compact?: boolean;
}

/** SiteIntel brand header shared by both application states. */
export function AppHeader({ compact = false }: AppHeaderProps): React.JSX.Element {
  return (
    <header
      className={`border-b border-[var(--line)] bg-[var(--canvas)] ${compact ? "print:hidden" : ""}`}
    >
      <div className="mx-auto flex h-[4.5rem] w-full max-w-[76rem] items-center justify-between px-5 sm:px-8">
        <a
          href="/"
          aria-label="SiteIntel home"
          className="pressable group flex min-h-11 items-center gap-3 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--canvas)]"
        >
          <span className="grid size-10 place-items-center rounded-lg border border-[var(--line-strong)] bg-white text-[var(--ink)] transition-transform duration-200 group-hover:-rotate-3">
            <GlobeHemisphereWest size={23} weight="duotone" aria-hidden="true" />
          </span>
          <span>
            <span className="font-display block text-[1.3rem] font-extrabold leading-5 text-[var(--ink)]">
              SiteIntel
            </span>
            <span className="hidden text-[0.68rem] font-bold leading-4 text-[var(--ink-muted)] sm:block">
              Technical audit agent
            </span>
          </span>
        </a>

        {compact ? (
          <p className="flex items-center gap-2 text-sm font-semibold text-[var(--ink-muted)]">
            <ShieldCheck size={18} weight="duotone" className="text-[var(--ink)]" />
            <span className="hidden sm:inline">Evidence-backed report</span>
            <span className="sm:hidden">Report</span>
          </p>
        ) : (
          <div className="flex items-center gap-2 sm:gap-5">
            <nav aria-label="Landing page" className="hidden items-center gap-5 md:flex">
              <a className="header-link" href="#report-preview">
                Report preview
              </a>
              <a className="header-link" href="#what-it-checks">
                What it checks
              </a>
            </nav>
            <a
              href="#audit-form"
              className="pressable flex min-h-11 items-center gap-2 rounded-lg border border-[var(--ink)] bg-[var(--ink)] px-3.5 text-sm font-bold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--canvas)] sm:px-4"
            >
              Run audit
              <ArrowDown size={16} weight="bold" aria-hidden="true" />
            </a>
          </div>
        )}
      </div>
    </header>
  );
}
