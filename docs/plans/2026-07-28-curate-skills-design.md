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

**Correlation → filing plan.** For each candidate the CLI builds the canonical
target `skill-coverage:<term>` and finds every store entry whose target is
equivalent. **Matching normalizes first, then filters** — it loads *all* entries
(`load_all_entries`, every status) and compares `normalize_target(e.target)`
against `normalize_target("skill-coverage:<term>")`, rather than a raw
`fnmatch("skill-coverage:*")` namespace glob. Raw `fnmatch` is case-sensitive on
POSIX while `normalize_target` lowercases the prefix, so a variant spelled
`Skill-Coverage:…` would be excluded before normalization and a duplicate would
be filed.

The match key is **`(normalize_target(e.target), e.concern == "tooling")`** — a
matching target is only a match when the concern is also `tooling`. Concern is
part of feedback identity (`docs/user-guide/feedback-and-telemetry.md`:
"recurrence is not merged across concerns"; triage groups by `(concern,
target)`), so an entry sharing this target under a different concern (e.g. a
human-filed `methodology:qa` note about the same term) is a distinct record that
curate must **ignore** — never recur, and never count toward the multiple-open
conflict below.

The matched set is partitioned by status, and disposition follows a fixed
precedence:

| Row | Condition | `--apply` action |
|---|---|---|
| **CONFLICT (fail-early)** | more than one **open** matching entry exists | **abort** the run with an error naming the duplicate ids; the store must be merged first (explicit over defensive) |
| **RECUR** | exactly one **open** entry exists | `record_occurrence(entry, date=…, project="science", category="gap", detail=<current snapshot>)` then `save_entry` (recurrence = `len(occurrences)` bumps). The occurrence kwargs are **explicit** — `record_occurrence` defaults to blank `project`/`suggestion`, which would silently drop the cross-project reach the occurrence model exists to preserve |
| **SKIP (resolved)** | no open entry, but ≥1 `wontfix`/`addressed`/`deferred` entry exists | **no write**; the row is still printed with the *current* scan evidence so a declined gap that is now widespread stays visible |
| **NEW** | no matching entry in any status | `save_entry` a fresh `FeedbackEntry` under a `next_feedback_id` |

Precedence is open → resolved → none: an open entry always wins (RECUR), so an
open+resolved pair is unambiguous. Two or more *open* `tooling` entries for one
normalized target is a store anomaly the command refuses to guess about — it
fails early rather than picking one. A SKIP row can have **several** resolved
matches (e.g. an old `wontfix` and a later `deferred`), so the row exposes them
all as `existing[]` (`{id, status}` each), not a single id — a singular field
could not represent a mixed set. If **any** resolved match is `addressed` (the
term should have become covered once a skill was authored, yet it is still
`uncovered`), the row is tagged `skip-addressed-conflict` so the anomaly is
surfaced, not hidden.

The partition recognizes only the known status vocabulary: `open` and the resolved
set `{addressed, deferred, wontfix}` (`feedback.VALID_STATUSES`). `FeedbackEntry.status`
is an unvalidated `str`, so a matched entry carrying any other value is a **hard
error** (fail early), never silently folded into "resolved" and skipped — a
malformed store must be fixed, not guessed past.

**Report-only default.** With no `--apply` the CLI prints the plan and writes
nothing — the `report-only` tier exactly as `science wander`'s CLI behaves. The
report is deterministic and ordered (by score desc, then term) so it is
snapshot-testable.

**Output shape.** One payload object serves both runs, distinguished by a
**top-level `mode: "report" | "apply"`**: `mode`, `scope`, `rows[]`, and
`context: {covered_not_loaded, unmapped, skipped_projects}`. Each row is

```
{term, disposition: new|recur|skip|skip-addressed-conflict,
 score, likely_archetype, n_plans, n_projects,
 existing: [{id, status}, …],   # ALL same-identity matches (target, concern=tooling); [] for NEW
 applied?: bool,                # present only when mode == "apply"
 result?: {action: created|recurred, id, recurrence_after}}   # present iff applied == true
```

`existing[]` lists **every** same-identity match in any status — an open+resolved
pair is a legitimate RECUR that carries both (the open one plus a historical
`wontfix`/`addressed`). The fail-early guard bounds *open* matches to ≤1, so the
entry that recurs is unambiguous, and `result.id` names it.

`mode` and `applied` resolve the scoped-apply ambiguity: under `--apply --term …`
only selected NEW/RECUR rows are written, so a missing `result` must be
distinguishable from a report run. In `mode: "report"` no row has `applied` or
`result`. In `mode: "apply"` **every** NEW/RECUR/SKIP row carries `applied`
(`true` only for a written selected row; `false` for an unselected row or any
SKIP), and `result` is present exactly when `applied == true`. This is the
post-apply action contract the CLI-behavior convention requires ("output should
name what changed"): both `created` and `recurred` return `{action, id,
recurrence_after}`, where `recurrence_after` is the entry's `recurrence`
(= `len(occurrences)`) after the write. **`FeedbackEntry` seeds one occurrence
for every entry** (the `_backfill_occurrences` validator, floor 1), so a freshly
`created` entry is `recurrence_after: 1` and a `recurred` entry is its prior
count + 1. `recurrence_after` is therefore always present and always meaningful —
it is not recur-only (an earlier draft wrongly assumed NEW seeds no occurrence).

A `conflict` (>1 open match) is not a row — it aborts the run with a nonzero exit
before any plan or result is emitted.

Following `docs/conventions/cli-behavior.md`, the CLI takes **`--format
text|json`** (default `text` for terminal review; `json` is machine-readable
JSON only on stdout, which the Layer-2 command consumes). `--output PATH` carries
the **complete selected-format** representation, written atomically (reusing
`write_report_atomically`) — it is not a JSON-only escape hatch. All counts and
ids are structural fields in the JSON payload, never presentation-only strings,
so the wrapper reads them directly. The **default `text`** render is the human
review surface, so it must carry the decision-critical fields: the header names
the scope mode **and** the selected `--project` when scoped, and each row shows
its `likely_archetype` alongside term, disposition, score, and counts.

When `--output` is set, its parent directory is verified **before** any
`--apply` write. Otherwise an unwritable destination would raise only after the
feedback store was already mutated, and a retry would record a second occurrence;
the preflight makes the apply-then-serialize pair fail atomically.

### Feedback record mapping

Every field is verified present on `FeedbackEntry` / `feedback add`:

| Field | Value |
|---|---|
| `target` | `skill-coverage:<term>` — stable namespace; reliable normalized-target dedup and `feedback list --target 'skill-coverage:*'` |
| `project` | **`science`** — set explicitly, never blank. A skill-corpus gap is owned by the toolkit (where the remediation lands), so `feedback list --project science` surfaces the corpus backlog. Portfolio breadth lives in the evidence, not the owner field. |
| `category` | `gap` |
| `concern` | `tooling` (the skill corpus is tooling) |
| `summary` | `skill corpus lacks coverage for <term> (<N> plans / <M> projects)` |
| `detail` | evidence triples (`project / plan_ref / dataset_ref`), `score`, and `likely_archetype` — the two authoring hints that are actually present on `Candidate`. **No subject-folder hint**: it is not derivable from the builder's inputs (`Candidate` carries only scope/archetype/score/evidence), so v1 does not fabricate one. A deterministic catalog→subject resolver is a clean later addition. |
| `status` | rides existing triage: `open → addressed` (skill authored) `\| wontfix` (not worth one) `\| deferred` |

`recurrence` is **derived** (`len(occurrences)`) — never written directly. A
re-run therefore records an *occurrence*, never a duplicate entry.

### Layer 2 — `commands/curate-skills.md`

The agent-facing wrapper that adds judgment and the human gate:

1. Run `science skills curate` (report-only) and read the plan.
2. Present the ranked gaps to the human, each with the proposed
   `likely_archetype` and summary, and the RECUR / SKIP status against existing
   feedback. (Subject-folder placement is an authoring-time human judgment, not a
   field this command produces.)
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
- **No auto-reopen** of a resolved (`wontfix`/`addressed`/`deferred`) gap in v1,
  and no write to it at all. The signal that a declined gap is now widespread is
  the **current scan evidence** (`n_plans` / `n_projects` / `score`) printed on
  its SKIP row — not a feedback-recurrence bump, which a no-write disposition
  cannot produce.
- **No new store, no belief writes.** Records are feedback entries only.

## Testing

1. **Plan determinism** — a fixture portfolio yields a stable, ordered plan.
2. **Target-dedup → RECUR** — a second run over the same gap produces a RECUR
   row, not a second NEW.
3. **Normalized-target dedup** — an existing entry spelled
   `Skill-Coverage:data-product:x` (case/prefix variant) matches the candidate
   `skill-coverage:data-product:x` and yields RECUR, not a NEW duplicate. Guards
   finding 1 (normalize before filtering).
4. **Multiple open matches → fail-early** — two open entries for one normalized
   target abort the run with a nonzero exit naming both ids; no plan is emitted
   and nothing is written. Guards finding 2.
5. **Resolved-entry → SKIP-but-report** — a `wontfix` `skill-coverage:<term>`
   entry suppresses filing but still appears in the plan, carrying the current
   scan `n_plans`/`n_projects` (not a mutated recurrence). Guards findings 2, 5.
6. **`--apply` idempotency** — applying twice records an occurrence
   (recurrence `2`), never a duplicate entry.
7. **Report-only default** — a run without `--apply` writes nothing to the
   feedback dir (assert against an injected `SCIENCE_FEEDBACK_DIR`).
8. **Uncovered-only filing** — `covered-not-loaded` / `unmapped` occurrences
   never produce feedback rows; they appear only in the context counts.
9. **`addressed`-still-uncovered** — an `addressed` entry whose term is still
   `uncovered` yields a `skip-addressed-conflict` row, not a silent skip.
10. **`project` is `science` on entry *and* occurrence** — a NEW entry carries
    `project: "science"`; a RECUR's appended occurrence carries
    `project="science"`, `category="gap"`, and the current `detail` snapshot
    (not the `""`/`suggestion` defaults). Asserted on the persisted entry and
    its last occurrence. Guards findings 4 and R3 (occurrence metadata).
11. **`--format json` is machine-readable** — `--format json` emits parseable
    JSON on stdout with the context counts as structural fields; `--output`
    carries the complete selected-format payload. Guards finding 6.
12. **Cross-concern is not a match** — an entry with the same normalized target
    but concern `methodology:qa` is ignored: the candidate yields NEW (not
    RECUR), and a *second* such entry does not trip the multiple-open conflict.
    Guards R1 (concern identity).
13. **Mixed resolved statuses** — a term with both a `wontfix` and an
    `addressed` match yields one SKIP row whose `existing[]` lists both, tagged
    `skip-addressed-conflict`. Guards R2.
14. **Apply-result contract** — after `--apply`, `mode == "apply"`; a NEW row
    carries `applied: true`, `result.action == "created"` with the generated id
    and `recurrence_after == 1` (the seeded occurrence); a RECUR row carries
    `applied: true`, `result.action == "recurred"` and `recurrence_after ==
    len(occurrences)` (prior + 1); a SKIP row carries `applied: false` and no
    `result`. A report run has `mode == "report"` and neither `applied` nor
    `result` on any row. Guards R4 and the recurrence-seeding contract.
15. **Scoped `--apply --term`** — with one of two NEW terms selected, the
    selected row is `applied: true` (written) and the unselected row is
    `applied: false` (not written, no feedback file created for it); an unknown
    `--term` aborts. Guards R1-scoped (mode/applied disambiguation).
16. **Open+resolved RECUR payload** — a term with one open and one `wontfix`
    match yields RECUR whose `existing[]` lists **both**, and `result.id` is the
    open entry (the one that received the occurrence). Guards R2-precedence.
17. **Unknown status → fail-early** — a matched entry whose `status` is outside
    `{open, addressed, deferred, wontfix}` aborts the run rather than being
    silently treated as resolved/SKIP. Guards the status-vocabulary contract.
18. **Text render carries decision fields** — the default `text` output names
    each row's `likely_archetype` and, when `--project` scopes the scan, the
    project in the header (not just the scope mode).
19. **`--output` preflight is atomic** — with a real gap present, `--apply
    --output <bad-parent>/plan.json` aborts **before** any feedback write (the
    store stays empty and no file is created); a successful `--output` writes the
    full payload to the file and nothing to stdout.

## Code layout

- `science/src/science_tool/skills_coverage/curate.py` — plan builder
  (correlation + disposition), pure over injected feedback entries + candidates.
- `science/src/science_tool/skills_coverage/cli.py` — add the `curate` click
  command; register on `skills_group` in `skills_lint/cli.py`.
- Reuse: `science_model.skill_coverage` (candidate/report types),
  `science_tool.skills_coverage.scan.scan_portfolio`,
  `science_tool.feedback` (`FeedbackEntry`, `load_all_entries`,
  `normalize_target`, `record_occurrence`, `save_entry`, `next_feedback_id`).
  Correlation loads **all** entries and matches on
  `(normalize_target(e.target), e.concern == "tooling")` directly — not
  `list_entries`' raw-`fnmatch` namespace filter (finding 1) — and does not use
  `find_duplicate` (open-only + summary-gated, which would miss resolved matches
  and split same-target entries by summary; finding 2).
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
