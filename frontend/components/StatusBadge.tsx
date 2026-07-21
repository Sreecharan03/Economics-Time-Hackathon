const STYLES = {
  pass: "text-pass bg-pass-soft border-pass-border",
  fail: "text-fail bg-fail-soft border-fail-border",
  conflict: "text-conflict bg-conflict-soft border-conflict-border",
  flagged: "text-flagged bg-flagged-soft border-flagged-border",
  neutral: "text-text-secondary bg-bg-raised border-border",
} as const;

type Tone = keyof typeof STYLES;

const LABELS: Record<string, { label: string; tone: Tone }> = {
  PASS: { label: "Meets spec", tone: "pass" },
  FAIL: { label: "Fails spec", tone: "fail" },
  CONFLICT: { label: "Spec conflict", tone: "conflict" },
  CRITICAL: { label: "Deadline at risk", tone: "fail" },
  FLAGGED: { label: "Flagged, not urgent", tone: "flagged" },
};

export function StatusBadge({ verdict }: { verdict: string }) {
  const cfg = LABELS[verdict] ?? { label: verdict, tone: "neutral" as Tone };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium ${STYLES[cfg.tone]}`}
    >
      <Dot tone={cfg.tone} />
      {cfg.label}
    </span>
  );
}

function Dot({ tone }: { tone: Tone }) {
  const colors: Record<Tone, string> = {
    pass: "bg-pass",
    fail: "bg-fail",
    conflict: "bg-conflict",
    flagged: "bg-flagged",
    neutral: "bg-text-muted",
  };
  return <span className={`h-1.5 w-1.5 rounded-full ${colors[tone]}`} />;
}
