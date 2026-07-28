# `/curate-skills` — Design

**Status:** Approved

**Date:** 2026-07-28

**Goal:** Close the loop the `science skills coverage` scan opened — triage
portfolio skill-**corpus** coverage gaps into `science feedback`, report-first
with a human gate. Writes **no skill files**: authoring stays human.

## Context

`science skills coverage` (branch `skill-coverage-command`, merge `b0c6dfa7`)
scans the registered project portfolio and, per project enrolled in the
`molecular-measurement` domain, emits a `coverage-report` with three occurrence
states plus evidence-backed **candidates**:

- `uncovered` — a used `data-product` term that **no leaf skill covers**. Each
  becomes a `Candidate{proposed_scope, likely_archetype, score, evidence[]}`.
- `covered-not-loaded` — a covering skill exists but the plan did not load it.
- `unmapped` — analysis touches an owned dataset tagged against no term.

The scan is a pure detector: it produces the candidates but **nothing consumes
them**. The umbrella design
([`2026-07-23-data-product-vocabulary-and-skill-coverage-design.md`](2026-07-23-data-product-vocabulary-and-skill-coverage-design.md))
explicitly deferred the `covers:` **authoring** axis, and the follow-up vision
(skills program phase 5) named a `/curate-skills` surface with a report-first +
`--apply` human gate. This design is that surface.

### Grounding decisions

Four forks were settled before this design (brainstorming session 2026-07-28):

1. **Triage → backlog, not authoring.** A confirmed gap produces a *tracked
   record*, never a scaffolded or drafted skill file. All authoring judgment
   stays human. This is the anti-drift guardrail the vision memory names
   ("auto-generated skills without review = corpus drift").
2. **Records land in `science feedback`, not a new store.** `science feedback`
   is a **global** store at `~/.config/science/feedback` (or
   `$SCIENCE_FEEDBACK_DIR`) with built-in duplicate detection, occurrence-based
   recurrence, and a triage program — and it is the channel the autonomy
   envelope ([`2026-07-24-autonomy-envelope-design.md`](2026-07-24-autonomy-envelope-design.md) §6)
   already chose for sweep escalations. A skill-corpus gap ledger inside
   `skills/` would also collide with the churning generated-mirror /
   inventory-exclusion contract from
   [`2026-07-27-coding-agent-support-design.md`](2026-07-27-coding-agent-support-design.md).
3. **`uncovered` only.** `/curate-skills` files feedback only for `uncovered`
   candidates (the skill-**corpus** gap: "author a skill covering X"). The other
   two states are reported as context counts but not filed — they are
   project-side hygiene (`covered-not-loaded` → load an existing skill;
   `unmapped` → tag a dataset), with different remediations and audiences.
4. **Layered: a deterministic CLI wrapped by an agent command** — the
   `wander` / `explore-ideas` house pattern the autonomy envelope cites (§ below).

## Design

### Layer 1 — `science skills curate` CLI

A new command under `skills_group`, beside `coverage`
(`science/src/science_tool/skills_coverage/`). It runs **in-process** — no
shelling out — reusing the existing coverage scan and feedback APIs:

```bash
science skills curate                        # print the filing plan; write NOTHING (report-only tier)
science skills curate --apply                # execute every NEW/RECUR row in the plan
science skills curate --apply --term <term>  # execute only the named term(s); repeatable
science skills curate --project mm30         # restrict the scan to one registered project
```

`--term` (repeatable, `--apply`-only) is the subset selector the command uses to
apply the human-accepted rows: bare `--apply` files the whole plan; `--apply
--term data-product:X --term data-product:Y` files only those. A `--term` naming
a term absent from the current plan is a hard error (never a silent no-op).

**Inputs.** `scan_portfolio(only=project)` →
`CoverageReport`. The CLI reads `report.candidates` (which, by construction, are
derived from `uncovered` terms only) plus the `covered_not_loaded` /
`unmapped` occurrence counts for the context line.

**Correlation → filing plan.** For each candidate, the CLI builds the canonical
target `skill-coverage:<term>` and correlates it against the current feedback
store via `list_entries(feedback_dir, status=None, target="skill-coverage:*")`,
matching on **normalized target + concern** (the same key `find_duplicate`
uses). Each candidate resolves to exactly one plan row:

| Row | Condition | `--apply` action |
|---|---|---|
| **NEW** | no `skill-coverage:<term>` entry exists | `save_entry` a fresh `FeedbackEntry` under a `next_feedback_id` |
| **RECUR** | an **open** entry exists | `record_occurrence` on it (recurrence = `len(occurrences)` bumps), refreshing the evidence snapshot |
| **SKIP (resolved)** | a `wontfix` / `addressed` / `deferred` entry exists | **no write**; the row is still printed so a gap you previously declined that is now recurring stays visible |

`addressed` with a still-`uncovered` term is a latent contradiction (an authored
skill should make the term covered, so it should not reappear as a candidate) —
the CLI flags such rows distinctly in the plan rather than silently skipping.

**Report-only default.** With no `--apply` the CLI prints the plan and writes
nothing — the `report-only` tier exactly as `science wander`'s CLI behaves. The
report is deterministic and ordered (by score desc, then term) so it is
snapshot-testable.

**Output shape.** A plan object: `scope`, `rows[]` (each
`{term, disposition: new|recur|skip|conflict, score, likely_archetype,
n_plans, n_projects, existing_id?, existing_status?}`), and
`context: {covered_not_loaded, unmapped, skipped_projects}`. Text to stdout by
default; `--output PATH` writes JSON atomically (reusing
`write_report_atomically`).

### Feedback record mapping

Every field is verified present on `FeedbackEntry` / `feedback add`:

| Field | Value |
|---|---|
| `target` | `skill-coverage:<term>` — stable namespace; reliable target-dedup and `feedback list --target 'skill-coverage:*'` |
| `category` | `gap` |
| `concern` | `tooling` (the skill corpus is tooling) |
| `summary` | `skill corpus lacks coverage for <term> (<N> plans / <M> projects)` |
| `detail` | evidence triples (`project / plan_ref / dataset_ref`), `score`, `likely_archetype`, and a candidate **subject-folder** hint for the eventual author |
| `status` | rides existing triage: `open → addressed` (skill authored) `\| wontfix` (not worth one) `\| deferred` |

`recurrence` is **derived** (`len(occurrences)`) — never written directly. A
re-run therefore records an *occurrence*, never a duplicate entry.

### Layer 2 — `commands/curate-skills.md`

The agent-facing wrapper that adds judgment and the human gate:

1. Run `science skills curate` (report-only) and read the plan.
2. Present the ranked gaps to the human, each with the proposed
   archetype / subject-folder / summary, and the RECUR / SKIP status against
   existing feedback.
3. Echo the `covered-not-loaded` / `unmapped` context counts — **no filing**;
   name them as project-side follow-ups only.
4. The human accepts a subset. The command runs `science skills curate --apply`
   (scoped to accepted terms) to file / record-occurrence.

The command is the only place the human gate lives; the CLI is mechanical.

### Autonomy fit

The CLI default is a clean `report-only` tier instance; `--apply` writes only to
`~/.config/science/feedback`, which is outside every project graph and is not
belief-bearing. An autonomous curate sweep is therefore envelope-legal, but
**scheduling is out of scope**: what triggers a sweep and how it emits work is
the deferred S2 (recurrence) / S3 (task-eligibility) autonomy slices. v1 is the
manual instance only.

### New-command plumbing

Adding a command means the agent-assets generator
([`2026-07-27-coding-agent-support-design.md`](2026-07-27-coding-agent-support-design.md))
emits `skills/generated/science-curate-skills/SKILL.md` and
`commands/opencode/science-curate-skills.md`. The implementation includes a
`science agents generate` regen and the committed-mirror equality check, plus a
`commands/INDEX.md` (or equivalent registry) row if commands are registered.

## Scope guardrails

- **No skill files authored.** The command's only side effect is feedback.
- **`uncovered` only** is filed; the other two occurrence states are context.
- **No auto-reopen** of a `wontfix` gap in v1; the rising occurrence count is
  the signal, surfaced in the report.
- **No new store, no belief writes.** Records are feedback entries only.

## Testing

1. **Plan determinism** — a fixture portfolio yields a stable, ordered plan.
2. **Target-dedup → RECUR** — a second run over the same gap produces a RECUR
   row, not a second NEW.
3. **Resolved-entry → SKIP-but-report** — a `wontfix` `skill-coverage:<term>`
   entry suppresses filing but still appears in the plan.
4. **`--apply` idempotency** — applying twice records an occurrence
   (recurrence `2`), never a duplicate entry.
5. **Report-only default** — a run without `--apply` writes nothing to the
   feedback dir (assert against an injected `SCIENCE_FEEDBACK_DIR`).
6. **Uncovered-only filing** — `covered-not-loaded` / `unmapped` occurrences
   never produce feedback rows; they appear only in the context counts.
7. **`addressed`-conflict flag** — an `addressed` entry whose term is still
   `uncovered` is flagged as a conflict row, not a silent skip.

## Code layout

- `science/src/science_tool/skills_coverage/curate.py` — plan builder
  (correlation + disposition), pure over injected feedback entries + candidates.
- `science/src/science_tool/skills_coverage/cli.py` — add the `curate` click
  command; register on `skills_group` in `skills_lint/cli.py`.
- Reuse: `science_model.skill_coverage` (candidate/report types),
  `science_tool.skills_coverage.scan.scan_portfolio`,
  `science_tool.feedback` (`FeedbackEntry`, `list_entries`, `find_duplicate`,
  `record_occurrence`, `save_entry`, `next_feedback_id`).
- `commands/curate-skills.md` — the agent command; regenerate agent assets.
- `docs/conventions/skill-coverage.md` — extend with a `curate` section.

## Alternatives considered

- **A dedicated `skills/coverage-ledger.yaml`.** Rejected: reinvents the
  dedup / recurrence / triage that feedback already provides, and a file inside
  `skills/` collides with the generated-mirror / inventory-exclusion contract.
- **`meta/` `science tasks`.** A real backlog, but per-project (not the
  portfolio-global scope of the gaps), no occurrence-based recurrence, and it
  couples corpus health to one project's backlog. Feedback is the envelope's own
  escalation channel; `meta/` remains the home for the *research question* of
  whether curation improves health, which is separate.
- **Command-only, zero new Python.** Rejected: the target-dedup correlation is
  deterministic and fiddly — it belongs in tested Python, not agent prose, and a
  command-only version is not autonomy-ready.
- **Scaffold stubs / full agent drafting.** Rejected as v1 scope: both write
  skill files and carry corpus-drift risk; triage-to-backlog keeps authoring
  judgment human.
