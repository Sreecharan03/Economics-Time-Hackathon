"use client";

import { useState } from "react";
import { SAMPLES } from "@/lib/samples";

interface Props {
  onSubmit: (input: { equipmentId: string; specSection: string; text: string }) => void;
  disabled: boolean;
}

export function SubmittalForm({ onSubmit, disabled }: Props) {
  const [equipmentId, setEquipmentId] = useState("");
  const [specSection, setSpecSection] = useState("");
  const [text, setText] = useState("");
  const [activeSample, setActiveSample] = useState<string | null>(null);

  function loadSample(id: string) {
    const sample = SAMPLES.find((s) => s.equipmentId === id);
    if (!sample) return;
    setEquipmentId(sample.equipmentId);
    setSpecSection(sample.specSection);
    setText(sample.text);
    setActiveSample(id);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!equipmentId.trim() || !text.trim()) return;
    onSubmit({ equipmentId: equipmentId.trim(), specSection: specSection.trim(), text });
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-border bg-bg-raised p-6">
      <h2 className="text-base font-semibold text-text mb-1">Review a submittal</h2>
      <p className="text-sm text-text-muted mb-5">
        Paste a vendor spec sheet, or try one of the examples below.
      </p>

      <div className="flex flex-wrap gap-2 mb-6">
        {SAMPLES.map((s) => (
          <button
            key={s.equipmentId}
            type="button"
            onClick={() => loadSample(s.equipmentId)}
            disabled={disabled}
            className={`text-left rounded-xl border px-3.5 py-2.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer ${
              activeSample === s.equipmentId
                ? "border-accent-border bg-accent-soft"
                : "border-border bg-bg-inset hover:border-border-subtle hover:bg-bg-raised-hover"
            }`}
          >
            <div className="text-sm font-medium text-text">{s.label}</div>
            <div className="text-xs text-text-muted mt-0.5">{s.outcome}</div>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <Field label="Equipment ID">
          <input
            value={equipmentId}
            onChange={(e) => {
              setEquipmentId(e.target.value);
              setActiveSample(null);
            }}
            placeholder="e.g. XFMR-01"
            disabled={disabled}
            className="w-full rounded-lg border border-border bg-bg-inset px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent-border disabled:opacity-50 font-mono"
          />
        </Field>
        <Field label="Spec section (optional)">
          <input
            value={specSection}
            onChange={(e) => setSpecSection(e.target.value)}
            placeholder="e.g. 26 12 00"
            disabled={disabled}
            className="w-full rounded-lg border border-border bg-bg-inset px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent-border disabled:opacity-50 font-mono"
          />
        </Field>
      </div>

      <Field label="Submittal text">
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setActiveSample(null);
          }}
          disabled={disabled}
          rows={10}
          placeholder="Paste the vendor's spec sheet text here…"
          className="w-full resize-y rounded-lg border border-border bg-bg-inset px-3 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent-border disabled:opacity-50 font-mono leading-relaxed"
        />
      </Field>

      <button
        type="submit"
        disabled={disabled || !equipmentId.trim() || !text.trim()}
        className="mt-5 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-bg transition-colors hover:bg-accent-strong disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
      >
        {disabled ? "Reviewing…" : "Review submittal"}
      </button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-text-secondary mb-1.5">{label}</span>
      {children}
    </label>
  );
}
