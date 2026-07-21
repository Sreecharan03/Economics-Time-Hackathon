import type { PrecedentRfi } from "@/lib/types";
import { Card } from "./ComplianceCard";

export function PrecedentCard({ precedent }: { precedent: PrecedentRfi[] }) {
  const top = precedent[0];

  return (
    <Card title="Similar past cases" eyebrow="Step 4 of 5">
      {!top ? (
        <p className="text-sm text-text-muted">No closely similar case found in past projects.</p>
      ) : (
        <div className="rounded-xl border border-border-subtle bg-bg-inset p-4">
          <div className="flex items-center justify-between gap-3 mb-1.5">
            <span className="font-mono text-xs text-accent">{top.rfi_id}</span>
            <span className="text-xs text-text-muted">{Math.round(top.score * 100)}% similar</span>
          </div>
          <p className="text-sm text-text mb-2">{top.subject}</p>
          {top.source_project && <p className="text-xs text-text-muted mb-2">From {top.source_project}</p>}
          {top.resolution && (
            <p className="text-sm text-text-secondary leading-relaxed border-t border-border-subtle pt-2 mt-2">
              <span className="text-text-muted">How it was resolved: </span>
              {top.resolution}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
