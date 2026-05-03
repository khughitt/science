<!--
core/decisions.md — load-bearing decisions and the reasoning behind them.
Loaded at session start via AGENTS.md.

Length cap: ~150 lines. When the file outgrows that, move older entries
to doc/decisions/ and keep only the still-load-bearing ones here.

This file is APPEND-ONLY for individual decisions. Do not rewrite a
decision when it is later superseded — add a new entry that references and
supersedes the old one, and update the "Status" line on the original. The
historical record is part of the value: it explains why obvious-looking
alternatives were rejected.

Each entry follows the format below. Number entries sequentially.
-->

# Decisions

## D-001: <one-line decision>

- **Date:** YYYY-MM-DD
- **Status:** active | superseded by D-XXX | abandoned
- **Decision:** <what was decided, in one sentence>

**Why:**
<2-4 sentences. The constraints, evidence, or pressure that drove the call.
What hard requirement or value judgement made this the choice over the
alternatives?>

**Alternatives considered and rejected:**
- <alternative> — <why rejected>
- <alternative> — <why rejected>

**Implications:**
- <what is now load-bearing because of this decision>
- <what is foreclosed or made harder>

**Revisit if:**
- <signal or threshold that would justify reopening this decision>

---

<!--
Examples of what belongs here:

- "We chose Polars over Pandas for the workflow layer because the per-batch
  joins exceeded Pandas' memory budget on the 2026-Q1 cohort." — load-bearing
  technical choice with concrete trigger.

- "We treat 'high-confidence' findings as posterior P(sign) > 0.95 rather than
  frequentist p < 0.05 because two prior interpretations conflated the two."
  — load-bearing methodological choice rooted in a specific past failure.

- "Canonical citation key format is FirstAuthorYear; we will not retroactively
  rename existing keys." — convention with explicit non-migration boundary.

What does NOT belong here:

- Implementation notes ("we use httpx not requests") — that's code-level.
- Style preferences without consequence — those belong in AGENTS.md.
- One-time deliberations that no longer constrain anything — let them die in
  doc/discussions/.
- Recap of an entire research debate — link to the discussion doc, summarize
  the conclusion in this file.

When in doubt: if the decision will surprise a future contributor — or if
re-opening it would silently break downstream work — it belongs here.
-->
