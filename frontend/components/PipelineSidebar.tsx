import { STAGES, type Stage, type StageState } from "@/lib/types";

export function PipelineSidebar({ stageStates, active }: { stageStates: Record<Stage, StageState>; active: boolean }) {
  return (
    <aside className="w-full lg:w-72 shrink-0">
      <div className="lg:sticky lg:top-8 rounded-2xl border border-border bg-bg-raised p-5">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-sm font-semibold text-text">Working through it</h2>
          {active && <LiveDot />}
        </div>
        <p className="text-xs text-text-muted mb-5">Five separate checks run in order below.</p>

        <ol className="relative">
          {STAGES.map((s, i) => {
            const state = stageStates[s.key];
            const isLast = i === STAGES.length - 1;
            return (
              <li key={s.key} className="relative pb-7 last:pb-0">
                {!isLast && (
                  <span
                    className={`absolute left-[9px] top-6 w-px h-[calc(100%-0.5rem)] transition-colors duration-500 ${
                      state.status === "done" || state.status === "skipped" ? "bg-accent" : "bg-border"
                    }`}
                  />
                )}
                <div className="flex gap-3">
                  <StageIcon status={state.status} />
                  <div className="min-w-0 pt-[1px]">
                    <div className="flex items-baseline gap-2">
                      <span
                        className={`text-sm font-medium ${
                          state.status === "pending" ? "text-text-muted" : "text-text"
                        }`}
                      >
                        {s.label}
                      </span>
                    </div>
                    <p className="text-xs text-text-muted mt-0.5 leading-snug">
                      {state.status === "skipped"
                        ? state.reason || "Skipped"
                        : state.status === "error"
                          ? state.detail || "Ran into a problem"
                          : s.blurb}
                    </p>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </aside>
  );
}

function StageIcon({ status }: { status: StageState["status"] }) {
  if (status === "done") {
    return (
      <span className="relative z-10 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent text-bg">
        <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none">
          <path d="M2.5 6.2 5 8.7l4.5-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (status === "started") {
    return (
      <span className="relative z-10 grid h-5 w-5 shrink-0 place-items-center rounded-full border-2 border-accent">
        <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse-dot" />
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="relative z-10 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-fail text-bg">
        <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none">
          <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </span>
    );
  }
  if (status === "skipped") {
    return (
      <span className="relative z-10 grid h-5 w-5 shrink-0 place-items-center rounded-full border-2 border-border bg-bg-raised">
        <span className="h-1.5 w-1.5 rounded-full bg-text-muted" />
      </span>
    );
  }
  return <span className="relative z-10 h-5 w-5 shrink-0 rounded-full border-2 border-border bg-bg-raised" />;
}

function LiveDot() {
  return (
    <span className="flex items-center gap-1.5 text-[11px] font-medium text-accent">
      <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse-dot" />
      LIVE
    </span>
  );
}
