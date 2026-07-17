# frontend

Not yet started. Planned: Next.js/React, talks only to `gateway`
(`POST /review/submittal`), never to the other five services directly.

Minimum viable screens for the one end-to-end thread (see top-level README):

1. Submittal upload/paste (text for now; PDF upload once
   `extraction-service`'s PDF parsing path exists).
2. Compliance result view — verdict, spec citation, submitted vs. required
   value, with a clear visual distinction between `PASS`, `FAIL`, and
   `CONFLICT` (conflict is not the same severity as a vendor deviation and
   should not be styled identically to one).
3. Schedule impact view — timeline/Gantt-style rendering distinguishing
   "CRITICAL, milestone slips N days" from "FLAGGED, N days float remaining"
   (see `services/schedule-service/README.md` — these are deliberately
   different urgency levels, not the same alert styled differently).
4. Drafted RFI view — the draft text, its citations, and an explicit
   human-approval action (approve/edit/reject) — never an auto-send path.

Not building a graph-database-backed visualization; a simple table/timeline
view of the Postgres data is sufficient (see top-level README's non-goals).
