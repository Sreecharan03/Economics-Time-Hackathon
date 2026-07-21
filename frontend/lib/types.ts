// Mirrors services/gateway/app/models.py's ReviewResponse and the SSE event
// shapes emitted by main.py's /review/submittal/stream. Kept as one file
// since the gateway is the only service this app ever talks to.

export type Stage = "reading" | "checking" | "calendar" | "memory" | "writing";

export const STAGES: { key: Stage; label: string; blurb: string }[] = [
  { key: "reading", label: "Reading document", blurb: "Pulling the numbers out of the submittal" },
  { key: "checking", label: "Checking against spec", blurb: "Comparing each value to the requirement" },
  { key: "calendar", label: "Checking schedule impact", blurb: "Does this actually delay anything?" },
  { key: "memory", label: "Finding similar cases", blurb: "Searching past projects for precedent" },
  { key: "writing", label: "Drafting response", blurb: "Composing a cited RFI for review" },
];

export type StageStatus = "pending" | "started" | "done" | "skipped" | "error";

export interface StageState {
  status: StageStatus;
  reason?: string;
  detail?: string;
}

export interface ExtractedAttribute {
  attribute: string;
  value: number | string;
  unit: string | null;
  source_span: string;
  confidence: number;
}

export interface ExtractionResult {
  equipment_id: string | null;
  extracted_attributes: ExtractedAttribute[];
  extraction_warnings: string[];
}

export type Verdict = "PASS" | "FAIL" | "CONFLICT";

export interface ConflictingClause {
  clause: string;
  required_value: number | string;
  unit?: string | null;
}

export interface ComplianceAttributeResult {
  attribute: string;
  submitted_value: number | string;
  required_value: number | string | null;
  unit: string | null;
  verdict: Verdict;
  spec_section: string;
  rationale: string;
  conflicting_clauses?: ConflictingClause[] | null;
}

export interface ComplianceResult {
  equipment_id: string;
  overall_verdict: Verdict;
  results: ComplianceAttributeResult[];
}

export interface MilestoneImpact {
  activity_id: string;
  activity_name: string;
  baseline_early_finish: number;
  new_early_finish: number;
  slip_days: number;
  critical: boolean;
}

export interface AffectedActivity {
  activity_id: string;
  activity_name: string;
  baseline_early_finish: number;
  new_early_finish: number;
  baseline_total_float: number;
  new_total_float: number;
}

export type Urgency = "CRITICAL" | "FLAGGED";

export interface ScheduleResult {
  triggering_activity: string;
  milestone_impact: MilestoneImpact;
  affected_activities: AffectedActivity[];
  urgency: Urgency;
}

export interface PrecedentRfi {
  rfi_id: string;
  source_project: string | null;
  subject: string;
  score: number;
  resolution: string | null;
}

export interface Citation {
  type: string;
  ref: string;
}

export interface DraftRfi {
  subject: string;
  body: string;
  citations: Citation[];
}

export interface ReviewResult {
  equipment_id: string;
  extraction: ExtractionResult;
  compliance: ComplianceResult | null;
  schedule: ScheduleResult | null;
  precedent: PrecedentRfi[];
  draft_rfi: DraftRfi | null;
  requires_human_approval: boolean;
  pipeline_warnings: string[];
}

export interface StreamEvent {
  stage: Stage | "complete" | "failed";
  status: StageStatus | "done" | "error";
  data?: unknown;
  reason?: string;
  detail?: string;
  status_code?: number;
}
