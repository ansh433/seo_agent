/** Temporary application shell; replaced by the audit flow in commit 18. */
export function App(): React.JSX.Element {
  return (
    <div className="min-h-screen bg-[#f6f7f3] text-[#0d1933]">
      <main className="mx-auto w-full max-w-[76rem] px-5 py-16 sm:px-8">
        <h1 className="font-display text-4xl font-bold tracking-[-0.035em]">
          SiteIntel
        </h1>
        <p className="mt-3 text-base leading-7 text-[#5b6880]">
          Evidence-backed technical SEO audits.
        </p>
      </main>
    </div>
  );
}
