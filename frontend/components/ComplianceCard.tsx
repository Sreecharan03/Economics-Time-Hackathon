import type { ComplianceResult, ExtractionResult } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

export function ComplianceCard({
  compliance,
  extraction,
}: {
  compliance: ComplianceResult;
  extraction: ExtractionResult;
}) {
  const checkedNames = new Set(compliance.results.map((r) => r.attribute));
  const unchecked = extraction.extracted_attributes.filter((a) => !checkedNames.has(a.attribute));

  return (
    <Card title="Spec compliance" eyebrow="Step 2 of 5">
      <div className="flex items-center justify-between mb-5">
        <p className="text-sm text-text-secondary">
          Found {extraction.extracted_attributes.length} value{extraction.extracted_attributes.length === 1 ? "" : "s"} in the
          document, {compliance.results.length} checkable against spec.
        </p>
        <StatusBadge verdict={compliance.overall_verdict} />
      </div>

      <div className="space-y-3">
        {compliance.results.map((r, i) => (
          <AttributeRow key={i} result={r} />
        ))}
      </div>

      {unchecked.length > 0 && (
        <p className="mt-4 text-xs text-text-muted">
          {unchecked.length} other value{unchecked.length === 1 ? "" : "s"} in the document didn&apos;t match a spec
          requirement to check ({unchecked.map((a) => a.attribute).join(", ")}) — noted, not a deviation.
        </p>
      )}
    </Card>
  );
}

function AttributeRow({ result }: { result: ComplianceResult["results"][number] }) {
  const isConflict = result.verdict === "CONFLICT";
  return (
    <div
      className={`rounded-xl border p-4 ${
        isConflict ? "border-conflict-border bg-conflict-soft" : result.verdict === "FAIL" ? "border-fail-border bg-fail-soft" : "border-border-subtle bg-bg-inset"
      }`}
    >
      <div className="flex items-center justify-between gap-3 mb-2">
        <span className="font-mono text-sm text-text">{result.attribute}</span>
        <StatusBadge verdict={result.verdict} />
      </div>

      {isConflict && result.conflicting_clauses ? (
        <div className="mt-2 space-y-1.5">
          {result.conflicting_clauses.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <span className="font-mono text-xs text-conflict">{c.clause}</span>
              <span className="text-text-secondary">
                requires {c.required_value}
                {c.unit ? ` ${c.unit}` : ""}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
          <span className="text-text-secondary">
            Submitted <span className="font-mono text-text">{result.submitted_value}{result.unit ? ` ${result.unit}` : ""}</span>
          </span>
          {result.required_value !== null && (
            <span className="text-text-secondary">
              Required <span className="font-mono text-text">{result.required_value}{result.unit ? ` ${result.unit}` : ""}</span>
            </span>
          )}
          <span className="font-mono text-xs text-text-muted">§ {result.spec_section}</span>
        </div>
      )}

      <p className="mt-2 text-sm text-text-secondary leading-relaxed">{result.rationale}</p>
    </div>
  );
}

export function Card({ title, eyebrow, children }: { title: string; eyebrow?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-bg-raised p-6 animate-fade-up">
      {eyebrow && <p className="text-xs font-medium text-accent mb-1 tracking-wide uppercase">{eyebrow}</p>}
      <h3 className="text-base font-semibold text-text mb-4">{title}</h3>
      {children}
    </section>
  );
}
