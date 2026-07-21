"use client";

import { useState } from "react";
import type { DraftRfi } from "@/lib/types";
import { Card } from "./ComplianceCard";

type Decision = "none" | "approved" | "rejected";

const CITATION_LABELS: Record<string, string> = {
  spec_clause: "Spec clause",
  submittal: "Submittal",
  schedule_activity: "Schedule item",
  precedent_rfi: "Past case",
};

export function DraftRfiCard({ draft }: { draft: DraftRfi }) {
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(draft.body);
  const [decision, setDecision] = useState<Decision>("none");

  return (
    <Card title="Drafted response" eyebrow="Step 5 of 5">
      <p className="text-sm text-text-muted mb-4">
        Every fact in this draft traces back to a step above — nothing here was invented. It goes nowhere until a
        person approves it.
      </p>

      <div className="rounded-xl border border-border-subtle bg-bg-inset p-4">
        <p className="text-sm font-semibold text-text mb-3">{draft.subject}</p>

        {editing ? (
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={7}
            className="w-full resize-y rounded-lg border border-border bg-bg-raised px-3 py-2.5 text-sm text-text leading-relaxed focus:outline-none focus:border-accent-border"
          />
        ) : (
          <p className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">{body}</p>
        )}

        {draft.citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-4 pt-3 border-t border-border-subtle">
            {draft.citations.map((c, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 rounded-md border border-border bg-bg-raised px-2 py-1 text-[11px] text-text-secondary"
              >
                <span className="text-text-muted">{CITATION_LABELS[c.type] ?? c.type}:</span>
                <span className="font-mono text-text">{c.ref}</span>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mt-5 flex items-center gap-2.5">
        {decision === "none" ? (
          <>
            <button
              onClick={() => setDecision("approved")}
              className="rounded-lg bg-pass px-4 py-2 text-sm font-semibold text-bg hover:opacity-90 cursor-pointer transition-opacity"
            >
              Approve
            </button>
            <button
              onClick={() => setEditing((v) => !v)}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text hover:bg-bg-raised-hover cursor-pointer transition-colors"
            >
              {editing ? "Done editing" : "Edit"}
            </button>
            <button
              onClick={() => setDecision("rejected")}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-bg-raised-hover cursor-pointer transition-colors"
            >
              Reject
            </button>
          </>
        ) : (
          <div
            className={`flex items-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-medium ${
              decision === "approved" ? "border-pass-border bg-pass-soft text-pass" : "border-border bg-bg-inset text-text-secondary"
            }`}
          >
            {decision === "approved" ? "Approved — ready to send" : "Rejected"}
            <button onClick={() => setDecision("none")} className="text-xs underline decoration-dotted opacity-70 hover:opacity-100 cursor-pointer">
              undo
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}
