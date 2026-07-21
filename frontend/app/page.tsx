"use client";

import { useRef, useState } from "react";
import { type Stage, type StageState, type ReviewResult, type StreamEvent } from "@/lib/types";
import { streamReview } from "@/lib/api";
import { SubmittalForm } from "@/components/SubmittalForm";
import { PipelineSidebar } from "@/components/PipelineSidebar";
import { ComplianceCard, Card } from "@/components/ComplianceCard";
import { ScheduleCard } from "@/components/ScheduleTimeline";
import { PrecedentCard } from "@/components/PrecedentCard";
import { DraftRfiCard } from "@/components/DraftRfiCard";
import { StatusBadge } from "@/components/StatusBadge";

const INITIAL_STAGES: Record<Stage, StageState> = {
  reading: { status: "pending" },
  checking: { status: "pending" },
  calendar: { status: "pending" },
  memory: { status: "pending" },
  writing: { status: "pending" },
};

type Phase = "idle" | "running" | "done" | "error";

export default function Home() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [stageStates, setStageStates] = useState<Record<Stage, StageState>>(INITIAL_STAGES);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function handleSubmit(input: { equipmentId: string; specSection: string; text: string }) {
    setPhase("running");
    setStageStates(INITIAL_STAGES);
    setResult(null);
    setErrorMessage(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamReview(
        {
          equipment_id_hint: input.equipmentId,
          raw_submittal_text: input.text,
          spec_section_hint: input.specSection || undefined,
        },
        (event: StreamEvent) => {
          if (event.stage === "complete") {
            setResult(event.data as ReviewResult);
            setPhase("done");
            return;
          }
          if (event.stage === "failed") {
            setErrorMessage((event.detail as string) ?? "Something went wrong.");
            setPhase("error");
            return;
          }
          setStageStates((prev) => ({
            ...prev,
            [event.stage as Stage]: {
              status: event.status as StageState["status"],
              reason: event.reason,
              detail: event.detail,
            },
          }));
        },
        controller.signal
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Couldn't reach the review service.");
      setPhase("error");
    }
  }

  function reset() {
    abortRef.current?.abort();
    setPhase("idle");
    setStageStates(INITIAL_STAGES);
    setResult(null);
    setErrorMessage(null);
  }

  const showResults = phase !== "idle";
  const compliance = result?.compliance ?? null;
  const isPass = compliance?.overall_verdict === "PASS";

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 pb-24">
        <div className="flex flex-col lg:flex-row gap-6 items-start">
          <div className="flex-1 min-w-0 w-full space-y-5">
            {!showResults && <SubmittalForm onSubmit={handleSubmit} disabled={false} />}

            {showResults && (
              <>
                {phase === "running" && !result && <ThinkingNotice />}

                {phase === "error" && <ErrorCard message={errorMessage} onRetry={reset} />}

                {compliance && <ComplianceCard compliance={compliance} extraction={result!.extraction} />}

                {compliance && !isPass && <ScheduleCard schedule={result!.schedule} />}
                {compliance && !isPass && <PrecedentCard precedent={result!.precedent} />}
                {result?.draft_rfi && <DraftRfiCard draft={result.draft_rfi} />}

                {phase === "done" && isPass && <PassNotice />}
                {phase === "done" && !compliance && <NoComplianceNotice warnings={result?.pipeline_warnings ?? []} />}

                {phase === "done" && (
                  <button
                    onClick={reset}
                    className="w-full rounded-xl border border-border bg-bg-raised px-4 py-3 text-sm font-medium text-text-secondary hover:bg-bg-raised-hover hover:text-text transition-colors cursor-pointer"
                  >
                    Review another submittal
                  </button>
                )}
              </>
            )}
          </div>

          <PipelineSidebar stageStates={stageStates} active={phase === "running"} />
        </div>
      </main>
    </div>
  );
}

function Header() {
  return (
    <header className="border-b border-border-subtle">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <div className="flex items-center gap-2.5 mb-2">
          <Mark />
          <span className="text-sm font-semibold tracking-wide text-text">MERIDIAN</span>
        </div>
        <h1 className="text-2xl font-semibold text-text mb-2">Submittal review</h1>
        <p className="text-sm text-text-secondary max-w-xl leading-relaxed">
          Check a vendor&apos;s equipment spec against project requirements, see whether any issue actually
          threatens the deadline, and get a cited draft response — reviewed by a person before anything goes out.
        </p>
      </div>
    </header>
  );
}

function Mark() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M2 15L7 5L10 12L13 5L18 15" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ThinkingNotice() {
  return (
    <div className="rounded-2xl border border-border bg-bg-raised p-6 flex items-center gap-3">
      <span className="h-2 w-2 rounded-full bg-accent animate-pulse-dot" />
      <p className="text-sm text-text-secondary">Working through the document — results will appear here as each step finishes.</p>
    </div>
  );
}

function PassNotice() {
  return (
    <Card title="All clear">
      <div className="flex items-center gap-3">
        <StatusBadge verdict="PASS" />
        <p className="text-sm text-text-secondary">
          Everything checked out. No schedule risk, no precedent search, nothing to draft — the deadline check and the
          rest of the review only run when something actually needs attention.
        </p>
      </div>
    </Card>
  );
}

function NoComplianceNotice({ warnings }: { warnings: string[] }) {
  return (
    <Card title="Couldn't assess compliance">
      <p className="text-sm text-text-secondary mb-3">
        The document was read, but nothing in it matched a spec requirement to check for this equipment.
      </p>
      {warnings.length > 0 && (
        <ul className="space-y-1">
          {warnings.map((w, i) => (
            <li key={i} className="text-xs text-text-muted font-mono">
              {w}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ErrorCard({ message, onRetry }: { message: string | null; onRetry: () => void }) {
  return (
    <div className="rounded-2xl border border-fail-border bg-fail-soft p-6">
      <p className="text-sm font-semibold text-fail mb-1.5">Couldn&apos;t complete the review</p>
      <p className="text-sm text-text-secondary mb-4">{message ?? "An unexpected error occurred."}</p>
      <button
        onClick={onRetry}
        className="rounded-lg border border-border bg-bg-raised px-3.5 py-2 text-sm font-medium text-text hover:bg-bg-raised-hover cursor-pointer transition-colors"
      >
        Try again
      </button>
    </div>
  );
}
