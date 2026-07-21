# Meridian — Project Explained (Video Script & Docs)

This document is written to help you explain this project in a **3-minute
video** — in simple English, with no jargon. It has everything you need:
what the project is, how it works, the tech used, what each button on the
screen does, and a full worked example you can read from while recording.

---

## 1. The one-line pitch

> **Meridian reads a vendor's equipment spec sheet, checks it against what
> the project actually requires, tells you whether the problem will
> actually delay the project, and writes a ready-to-send email about it —
> all in under a minute, with a person approving it at the end.**

---

## 2. The problem, in plain English

When a company builds a data centre, they buy equipment from vendors —
transformers, generators, backup batteries, cooling units. Every vendor
sends a document ("submittal") describing exactly what they are shipping.

Someone on the project has to manually check: **does this match what was
asked for?** That check is slow (hours per document), easy to get wrong
(the one bad number is often buried on page 40 of a 70-page PDF), and even
when someone does catch a mistake, nobody connects it to the real
question: **does this actually push back the opening date?**

Not every mistake matters equally. Some genuinely delay the whole project.
Others don't matter at all because there's enough spare time in the
schedule to fix them quietly. A tool that treats every problem as
"URGENT!!" gets ignored. The hard, valuable part is telling the two apart
— using real project-scheduling math, not guesswork.

**That is exactly what this project does.**

---

## 3. How it works — five steps, one after another

Every submittal goes through five steps. Think of it as five specialists,
each doing one job, handing off to the next:

| Step | Plain name | What it actually does |
|---|---|---|
| 1 | **Reading document** | An AI reads the vendor's document and pulls out the numbers that matter (e.g. "impedance = 7.0%"). |
| 2 | **Checking against spec** | Plain math — no AI — compares that number to what the spec requires. Pass or fail, no guessing. |
| 3 | **Checking schedule impact** | Plain math — no AI — figures out if this failure actually delays the project's final test date, using the real project schedule. |
| 4 | **Finding similar cases** | Searches past, similar problems from other projects so the response isn't written from scratch. |
| 5 | **Drafting response** | An AI writes a clear, cited email about the problem — but it never gets sent automatically. A person must approve it. |

**Why steps 2 and 3 don't use AI:** you never want a computer *guessing*
whether something legally/technically passes or fails, or guessing at
schedule math. Those are done with plain, checkable arithmetic instead —
the same math a scheduler would do by hand, just instant. AI is only used
where it's actually good at something: reading messy documents (step 1)
and writing clear text (step 5).

**Steps 3 and 4 run at the same time** (not one after another) — the
system checks the schedule and searches for similar cases simultaneously,
to save time. You can literally watch this happen live in the UI: both
light up together.

**If everything passes spec (step 2), the tool stops there.** No schedule
check, no search, nothing to draft — because there's nothing wrong. This
saves time and avoids wasting AI calls on documents that are already fine.

---

## 4. The codebase — how the project is organised

The project is not one big program. It's **seven small pieces**, each
doing exactly one job. This is deliberate: it's much easier to trust and
test seven small, focused things than one giant thing that tries to do
everything.

```
epc-ai-platform/
├── services/
│   ├── extraction-service/    Step 1: reads the document (uses AI)
│   ├── compliance-service/    Step 2: checks against spec (plain math)
│   ├── schedule-service/      Step 3: checks schedule impact (plain math)
│   ├── retrieval-service/     Step 4: finds similar past cases
│   ├── drafting-service/      Step 5: writes the draft email (uses AI)
│   └── gateway/                The "front desk" — calls the other five
│                                in the right order and combines the result
├── frontend/                   The website you actually look at and click
├── dataset/                    A realistic example project used for testing
│                                (fake data centre, real equipment values)
└── infra/                      Docker setup that runs all seven pieces together
```

Each of the six backend pieces is its own small web service with its own
tests. The **gateway** is the only one the website talks to — it calls the
other five in order and stitches their answers together into one result.

### Why split it up this way?

- If step 1 (reading a document) breaks, steps 2–5 still work fine for
  anything already read.
- Each piece can be tested completely on its own before trusting it as
  part of the whole.
- It mirrors how a real team would work: one person reads the document,
  another checks it against the rulebook, another checks the calendar,
  another checks precedent, another writes the email.

---

## 5. Tech stack — what's used, and why

| Layer | Technology | Why this one |
|---|---|---|
| AI (reading + writing) | **Groq** (running Llama 3.3 70B) | Free/cheap, very fast responses — good for the two jobs that genuinely need an AI: reading messy text and writing clear sentences. |
| Compliance & schedule math | **Plain Python** — no AI at all | Legal/engineering decisions must be exact and repeatable. Math doesn't hallucinate; an AI might. |
| Finding similar past cases | **sentence-transformers** (a small, free, local AI model) + **pgvector** | Turns text into a "fingerprint" so the computer can find similar-meaning text, not just matching keywords. Runs locally, no extra cost. |
| Database | **PostgreSQL** (with the `pgvector` add-on) | Stores equipment, spec rules, and the project schedule; the `pgvector` add-on is what makes "finding similar text" possible. |
| Backend services | **Python + FastAPI** | Simple, fast, well-tested framework for building the six small web services described above. |
| Website (frontend) | **Next.js + React + TypeScript** | Modern, fast website framework; TypeScript catches mistakes before the page even loads. |
| Styling | **Tailwind CSS** | Lets the whole app share one consistent, custom look (see section 7) without extra design tools. |
| Running everything together | **Docker + Docker Compose** | Packages all seven pieces so they start up together with one command, on any machine. |
| Testing | **pytest** (Python) + **Playwright** (browser testing) | Every piece has its own automated tests; the website is tested by literally driving a real browser through it. |

---

## 6. The website — what each part of the screen does

When you open the app, you see two things: a form on the left, and a
progress panel on the right.

### The input form

| Field | What it's for |
|---|---|
| **Example buttons** (4 of them) | Instantly fill the form with a real example, so you don't need your own document to try it. Each one shows a different outcome: a critical failure, a non-urgent failure, a spec that contradicts itself, and a clean pass. |
| **Equipment ID** | The tag of the equipment being reviewed, e.g. `XFMR-01` (a transformer). This tells the system which spec rules to check against. |
| **Spec section** (optional) | The specific rulebook section this equipment falls under, e.g. `26 12 00`. Optional — the system can often work it out. |
| **Submittal text** | Where you paste the vendor's actual document — the spec sheet text the AI will read in Step 1. |
| **Review submittal button** | Starts the whole 5-step process. |

### The progress panel (right side)

Shows the five steps from Section 3, live, as they actually happen — not a
fake loading animation. Each step shows:

- A grey empty circle = not started yet
- A pulsing orange circle = happening right now
- An orange checkmark = done
- A grey dash = skipped (e.g. because the equipment already passed)

### The results (appear one at a time, as each step finishes)

1. **Spec compliance** — pass/fail/conflict badge, the exact number
   submitted vs. required, and the spec rule it's checked against.
2. **Schedule impact** — a timeline showing the planned date vs. the new
   expected date, and whether the deadline is actually at risk.
3. **Similar past cases** — the closest matching past problem, and how it
   was resolved last time.
4. **Drafted response** — the actual email text, what it's based on
   (citations), and three buttons: **Approve**, **Edit**, **Reject**.
   Nothing is ever sent automatically — a person must click Approve.

---

## 7. A full dry run — the exact example to use in your video

This is the single best example to demo, because it shows the tool
catching a real, deadline-threatening problem. All numbers below are real
outputs from the actual running system — not made up for the video.

**Setup:** click the first example button, **"Transformer — service
entrance A."** This loads a real (synthetic) vendor spec sheet for a
transformer called `XFMR-01`, then click **Review submittal**.

**What happens, step by step:**

1. **Reading document** — the AI reads the vendor's spec sheet and pulls
   out 17 different values (power rating, voltage, weight, etc.).

2. **Checking against spec** — out of those 17 values, only one
   (`impedance_pct`) is something this project's spec actually has a rule
   for. The vendor's sheet says **7.0%**. The project spec requires
   **5.75%, with a tolerance of ±7.5%** — meaning anything from 5.32% to
   6.18% is acceptable. **7.0% is outside that range → FAILS spec.**
   (The other 16 values are noted but aren't deviations — they simply
   don't have a spec rule to check against.)

3. **Checking schedule impact** — this transformer sits on the most
   important path in the whole schedule (nothing else is more time-
   critical). Fixing this failure requires a "resubmit cycle," which
   costs about 14 days. Since this item has **zero spare days** in the
   schedule, the final test date (called the "Integrated Systems Test")
   **slips by exactly 14 days** — from day 745 to day 759 of the project.
   **This is marked CRITICAL — deadline at risk.**

4. **Finding similar cases** — the system searches 20 real historical RFIs
   (from past, similar projects) and finds one about the exact same kind
   of problem: a transformer's impedance being outside tolerance on a
   different project, resolved by ordering a custom low-impedance
   transformer.

5. **Drafting response** — the AI writes a short, professional email
   explaining: what failed, which spec rule it violates, that it causes a
   14-day delay to a critical milestone, and references the similar past
   case. It ends with "human engineer sign-off is required" — and stops
   there. A person then clicks **Approve**, **Edit**, or **Reject.**

**Total time for all 5 steps: a few seconds.** What would normally take an
engineer hours of manual cross-checking — and might still miss the
schedule connection — happens automatically, with every number traceable
back to a real source.

### The second example worth showing (optional, if you have time)

Click **"Switchgear — utility paralleling bus."** This item *also* fails
spec (25kA submitted vs. 40kA required) — but the schedule check shows
**249 days of spare time still available**, so the deadline does **not**
move. This proves the tool doesn't cry wolf on every failure — it tells
you which ones actually matter.

---

## 8. Suggested 3-minute video script

**0:00–0:25 — The problem**
> "Building a data centre means buying huge amounts of equipment from
> vendors. Every vendor sends a spec sheet, and someone has to manually
> check it matches what was asked for — and more importantly, figure out
> if a mistake will actually delay the project. That check is slow, and
> nobody today connects 'this part is wrong' to 'this pushes back opening
> day by two weeks.'"

**0:25–0:50 — What this does**
> "This tool automates that whole chain. It reads a vendor's document,
> checks it against the spec, checks whether it actually threatens the
> deadline using real project-schedule math, finds a similar past case,
> and drafts a response — ready for a person to approve."

**0:50–1:10 — How it's built**
> "It's built as seven small pieces, not one big AI. AI is only used for
> reading documents and writing text — the two jobs it's actually good at.
> Checking spec compliance and schedule impact is done with plain,
> deterministic math, because you never want a computer guessing on
> something with legal or engineering consequences."

**1:10–2:30 — Live demo** (use the dry run from Section 7)
> Walk through the 5-step live panel, narrating each step as it lights up:
> "Watch — it's reading the document now... found 17 values, but only one
> is spec-checked: impedance, submitted 7%, required 5.75%. Fails.
> Now it's checking the schedule — this transformer has zero float, so
> that 14-day fix delay pushes the final test date back by 14 days. Real
> risk. It's finding a similar past case... and now drafting the actual
> email, citing the spec clause and the schedule impact. Nothing sends
> automatically — a person approves it right here."

**2:30–3:00 — Wrap-up**
> "Every one of the six backend services and the website have their own
> automated tests — over 300 tests total — and everything you just saw is
> real output from the running system, not mocked. That's Meridian."

---

## 9. Quick answers to likely questions

**"Why not just use one big AI model for everything?"**
Because compliance and schedule decisions need to be exact and
repeatable — a single AI model can be inconsistent or simply wrong in a
way that's hard to catch. Splitting the "must be exact" parts (math) from
the "AI is genuinely good at this" parts (reading, writing) makes the
whole system both cheaper to run and easier to trust.

**"What happens if a step fails or a service is down?"**
Reading the document and checking spec compliance are required — without
them there's nothing to say. But the schedule check, the similar-case
search, and the draft email are treated as "best effort": if one of them
fails, the rest of the review still comes back with a clear note about
what didn't work, instead of the whole thing crashing.

**"Does anything get sent automatically?"**
No. The draft email is always just a draft. A person must click Approve
before it would ever be considered ready to send — the system does not
send anything itself.
