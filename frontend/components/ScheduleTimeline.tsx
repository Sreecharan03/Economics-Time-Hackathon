import type { ScheduleResult } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { Card } from "./ComplianceCard";

export function ScheduleCard({ schedule }: { schedule: ScheduleResult | null }) {
  if (!schedule) {
    return (
      <Card title="Schedule impact" eyebrow="Step 3 of 5">
        <p className="text-sm text-text-muted">No schedule activity is linked to this equipment yet, so impact can&apos;t be checked.</p>
      </Card>
    );
  }

  const { milestone_impact: m, urgency } = schedule;
  const isCritical = urgency === "CRITICAL";
  const triggering = schedule.affected_activities.find((a) => a.activity_id === schedule.triggering_activity);

  return (
    <Card title="Schedule impact" eyebrow="Step 3 of 5">
      <div className="flex items-center justify-between mb-5">
        <p className="text-sm text-text-secondary">
          Effect on <span className="text-text">{m.activity_name}</span>
        </p>
        <StatusBadge verdict={urgency} />
      </div>

      <Timeline baseline={m.baseline_early_finish} updated={m.new_early_finish} critical={isCritical} />

      <div className="mt-5 grid grid-cols-2 gap-4">
        <Stat
          label="Deadline moves by"
          value={m.slip_days > 0 ? `+${m.slip_days} days` : "No change"}
          tone={m.slip_days > 0 ? "fail" : "pass"}
        />
        {triggering ? (
          <Stat
            label="Buffer remaining"
            value={`${triggering.new_total_float} days`}
            tone="neutral"
          />
        ) : (
          <Stat label="On critical path" value={isCritical ? "Yes" : "No"} tone={isCritical ? "fail" : "pass"} />
        )}
      </div>

      <p className="mt-4 text-sm text-text-secondary leading-relaxed">
        {isCritical
          ? "This item has no buffer left — any delay in fixing it pushes the project's final test date back by the same amount."
          : "This item still has buffer days left, so fixing it won't push back the project deadline — but it should still get resolved."}
      </p>
    </Card>
  );
}

function Timeline({ baseline, updated, critical }: { baseline: number; updated: number; critical: boolean }) {
  const shifted = updated > baseline;
  // Scale the strip around whichever range we actually need to show, with padding.
  const span = Math.max(updated - baseline, 20);
  const start = baseline - span * 0.4;
  const end = updated + span * 0.4;
  const pct = (day: number) => ((day - start) / (end - start)) * 100;

  return (
    <div className="relative pt-2 pb-7">
      <div className="h-1.5 rounded-full bg-bg-inset overflow-hidden relative">
        {shifted && (
          <div
            className="absolute top-0 h-full bg-fail-soft"
            style={{ left: `${pct(baseline)}%`, width: `${pct(updated) - pct(baseline)}%` }}
          />
        )}
      </div>
      <Marker pct={pct(baseline)} label="Planned" day={baseline} tone="neutral" />
      {shifted && <Marker pct={pct(updated)} label="Now expected" day={updated} tone={critical ? "fail" : "flagged"} />}
    </div>
  );
}

function Marker({ pct, label, day, tone }: { pct: number; label: string; day: number; tone: "neutral" | "fail" | "flagged" }) {
  const dot = tone === "fail" ? "bg-fail" : tone === "flagged" ? "bg-flagged" : "bg-text-muted";
  return (
    <div className="absolute top-0 -translate-x-1/2" style={{ left: `${pct}%` }}>
      <div className={`h-3.5 w-3.5 rounded-full border-2 border-bg-raised ${dot}`} />
      <div className="mt-1.5 whitespace-nowrap text-[11px] text-text-muted">
        {label} <span className="font-mono text-text-secondary">day {day}</span>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: "pass" | "fail" | "neutral" }) {
  const color = tone === "pass" ? "text-pass" : tone === "fail" ? "text-fail" : "text-text";
  return (
    <div className="rounded-xl border border-border-subtle bg-bg-inset px-4 py-3">
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className={`text-lg font-semibold font-mono ${color}`}>{value}</p>
    </div>
  );
}
