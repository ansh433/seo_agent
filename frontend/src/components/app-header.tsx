import { GlobeHemisphereWest, ShieldCheck } from "@phosphor-icons/react";

interface AppHeaderProps {
  compact?: boolean;
}

/** SiteIntel brand header shared by both application states. */
export function AppHeader({ compact = false }: AppHeaderProps): React.JSX.Element {
  return (
    <header
      className={`border-b border-[#dde3e0] bg-[#fbfcf9] ${compact ? "print:hidden" : ""}`}
    >
      <div className="mx-auto flex h-[4.5rem] w-full max-w-[76rem] items-center justify-between px-5 sm:px-8">
        <a
          href="/"
          aria-label="SiteIntel home"
          className="group flex min-h-11 items-center gap-3 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-[#0b63f6] focus-visible:ring-offset-2"
        >
          <span className="grid size-10 place-items-center rounded-xl border border-[#cbd8f7] bg-[#edf3ff] text-[#075ee5] transition-transform duration-200 group-hover:-rotate-3">
            <GlobeHemisphereWest size={23} weight="duotone" aria-hidden="true" />
          </span>
          <span className="font-display text-[1.55rem] font-bold tracking-[-0.035em] text-[#0d1933]">
            SiteIntel
          </span>
        </a>

        {!compact && (
          <p className="hidden items-center gap-2 text-sm font-medium text-[#53617a] sm:flex">
            <ShieldCheck size={18} weight="duotone" className="text-[#09864a]" />
            Evidence-backed website audits
          </p>
        )}
      </div>
    </header>
  );
}
