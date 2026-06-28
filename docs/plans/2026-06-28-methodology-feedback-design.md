# Methodology Feedback — Design Spec

**Date:** 2026-06-28
**Status:** Approved

## Context

The `science` feedback system (see [2026-03-25-feedback-system-design.md](2026-03-25-feedback-system-design.md)) has been an effective channel for projects to report issues upstream and continuously improve the tooling. Until now it has focused on the *tooling surface*: CLI commands, Claude Code commands, templates, entity metadata, skill ergonomics.

There is a parallel, equally valuable opportunity: feedback on the *scientific methodology and process* the tooling encodes. When an analysis fails because a QA issue was missed, when a design doesn't fit the constraints of the data, or when a statistical method is applied in violation of its assumptions, the right response is a post-hoc investigation — understand exactly what went wrong, then reflect on what we could have done differently to surface the issue sooner — and feed that lesson back into the science guidance (skills, commands, checks).

The overlap with the existing system is strong: a methodology lesson, to be actionable, almost always resolves to improving a *guidance surface* (a skill, command, template, or CLI check). The `target` field is already free-form and convention-based, and `skill:*` is already a sanctioned target prefix. So a lesson like *"we violated an exchangeability assumption — the statistics skill needs an assumption-check item"* already has a home at `target: skill:statistics`, and the existing dedup/clustering/triage/report plumbing is target-agnostic.

This spec extends the existing system rather than forking a new one.

## Goal

Let the feedback system capture **generalized scientific-methodology lessons** alongside tooling feedback, in one store, with a single discriminator so a user can "interface with one or the other depending on their goals." Add a guided reflection workflow that produces these lessons from post-hoc investigation of failures and surprises.

## Key boundary decisions

1. **One store, not two.** Extend `FeedbackEntry` and the `feedback` CLI; no parallel system.
2. **A global entry is always a generalized guidance improvement.** The failed analysis is *evidence*, not the entry. Project-specific post-mortems stay in the project (as an interpretation/note/task); only the cross-project lesson is filed globally. This keeps the store full of improvements, not incidents.
3. **Discriminator is a namespaced taxonomy field** (`concern`), glob-filterable like `target`.
4. **Lessons are produced by a guided reflection skill** and persisted through a lightly-extended `feedback add` — no new persistence surface (no `reflect` subcommand, no structured root-cause schema fields). The rigor lives in the skill; its output is plain feedback entries.
5. **The reflection skill is standalone**, with a soft, behavior-neutral handoff pointer from `interpret-results`.

## Design

### 1. Schema change (`feedback.py`)

Add one field to `FeedbackEntry`, as the **last field**, with a default that keeps every existing entry valid:

```python
concern: str = "tooling"
```

Values are namespaced, mirroring the existing `target` convention (`prefix:detail`):

| Value | Meaning |
|---|---|
| `tooling` | Current behavior; ergonomics of the science software/surfaces. **Default.** |
| `methodology:statistics` | Assumptions, inference validity, finite-sample/model choices |
| `methodology:qa` | Data/quality checks that should have caught the issue |
| `methodology:design` | Analysis/study design vs. the question or data constraints |
| `methodology:data-fitness` | Dataset suitability, preprocessing, provenance |
| `methodology:reasoning` | Interpretation / causal / epistemic errors (over-claiming, confounding) |

The `methodology:*` vocab is a **controlled set**, expandable later as real failure modes demand. `tooling` is kept bare (no sub-area) so existing entries need no reclassification.

**Validation is fail-loud** (per the project's "fail early / avoid silent fallbacks" rule): an unknown `concern` value is rejected. The accepted set is `tooling` plus the enumerated `methodology:*` members. Loading legacy YAML with no `concern` key defaults to `tooling`, so the field is backward-compatible with **no migration**.

`concern methodology:*` (fnmatch) selects the whole methodology lens in one filter.

**Deliberately *not* changed:** the `category` vocab (`friction | gap | guidance | suggestion | positive`). The nature-axis transfers cleanly to methodology — a missed check is a `gap`, misleading guidance is `guidance`, a concrete improvement is a `suggestion`, a worked-well pattern is `positive`. `friction` will rarely apply to methodology, which is fine: `concern` and `category` are orthogonal. (YAGNI: no methodology-specific categories until a real case doesn't fit the existing five.)

### 2. Evidence linking (no new fields)

The generalized lesson lives in the global store; the incident stays in the project. Reuse existing fields:

- `project` — records the surfacing project (already auto-detected).
- `detail` — holds the incident narrative plus a pointer (path or id) to the project's own entity (interpretation/task) where the failure is recorded.
- `related` — unchanged; remains feedback-to-feedback.

No cross-store coupling, no new schema for evidence.

### 3. Core logic — `concern` becomes part of entry identity (`feedback.py`)

A namespaced `concern` is not just display metadata; it partitions the entry space. Three existing functions key on `target` (and `category`) and must be widened to include `concern`, or a methodology lesson and an unrelated tooling entry that happen to share a `target` will be wrongly conflated:

- **`find_duplicate`** (currently keys on `target` + summary) must also key on `concern`. Two entries with the same `target` and similar summary but different `concern` are **distinct** and must not increment each other's `recurrence`. (Test: same target/summary, different concern → two entries, no merge.)
- **`group_for_triage`** (currently groups by `target`) must group by `(concern, target)` so methodology lessons form their own groups. **A raw `(concern, target)` tuple must not leak into CLI headings or the telemetry join.** Either the grouped result carries explicit `concern` and `target` fields (preferred), or the CLI unpacks the tuple before display and before calling `summarize_recent_for_feedback_target` (which keys on `target`).
- **`cluster_for_triage`** (currently matches clusters on `target` + `category`) must include `concern` in the cluster key, and the cluster row must carry `concern`.

### 4. CLI surface (`cli.py`)

- **`feedback add`** — new `--concern` option, default `tooling`.
- **`feedback list`** — new `--concern` filter supporting fnmatch glob (reuse the existing `--target` glob path), so `--concern 'methodology:*'` works.
- **`feedback update`** — new `--concern` option (threaded through `update_entry`), so a misclassified entry can be corrected. Since `concern` is a controlled taxonomy applied by judgment in the post-mortem flow, a CLI correction path is required, not optional.
- **`feedback triage`** — accept a `--concern` filter; grouping/clustering already partition by `concern` per Section 3, so methodology lessons cluster separately from tooling ergonomics, and `concern` is shown in the rows.
- **`feedback report`** — accept a `--concern` filter, and with no filter, **group `concern → target`** (top-level by `concern`, then `target` within). This makes the methodology lens a visible block rather than entries scattered through a target-first list, matching the goal of interfacing with one lens at a time.

### 5. New skill — `/science:post-mortem`

*(Name is the working choice; `reflect` / `retrospective` are alternatives.)*

A read-mostly reasoning skill, invoked when an analysis failed or behaved unexpectedly. Flow:

1. **Scope** — what was attempted, what was expected, what actually happened.
2. **Root cause** — the actual technical/methodological reason it failed or surprised.
3. **Earlier signal** — *what would have surfaced this sooner?* The core reflective step.
4. **Generalize gate** — is there a cross-project lesson? If the issue is purely project-local, **stop**: record it in the project and file nothing globally. This gate enforces boundary decision #2 and keeps the global store free of incident dumps.
5. **Target the surface** — which guidance artifact should change (`skill:` / `command:` / `template:` / a CLI check) → sets `target` + `concern`.
6. **Emit** — one or more `science feedback add` calls: the generalized lesson as `summary`, the incident as `detail` evidence, `project` stamped, `concern: methodology:*`, an appropriate `category`.

### 6. Soft handoff

Add a pointer near the end of the `interpret-results` command: *"If a result contradicted a pre-registered expectation, a run failed, or an assumption turned out violated, consider `/science:post-mortem` to capture a methodology lesson."* This is discoverability only — `interpret-results` behavior is unchanged, and the reflection skill is never forced into a results-interpretation run.

## Non-goals

- No `feedback reflect` subcommand and no first-class `root_cause` / `earlier_signal` schema fields. Structured rigor lives in the skill; output is plain feedback entries.
- No methodology-specific `category` values (until a real case doesn't fit).
- No knowledge-graph integration of feedback entries.
- No auto-promotion of project incidents into global lessons; promotion is a human/agent judgment in the skill's generalize gate.

## Testing

- Schema: `concern` defaults to `tooling`; legacy YAML without the key loads as `tooling`; unknown values are rejected fail-loud; `methodology:*` members accepted.
- Duplicate identity: same `target` + similar summary but different `concern` → two distinct entries, no `recurrence` merge.
- Triage partitioning: `group_for_triage` and `cluster_for_triage` separate entries that share a `target` but differ in `concern`; cluster rows carry `concern`.
- CLI: `feedback add --concern` round-trips; `feedback list --concern 'methodology:*'` glob filter selects the lens; `feedback update --concern` corrects an entry; `triage --concern` filters; `report` groups `concern → target` and honors `--concern`.
- Backward-compat: existing entries and existing tests remain green with no migration.

## Files touched

- `science/src/science_tool/feedback.py` — `FeedbackEntry.concern` field + validation + accepted-vocab constant; widen `find_duplicate`, `group_for_triage`, and `cluster_for_triage` (+ `_FeedbackCluster` / cluster row) to key on `concern`; add `concern` to `update_entry` and `list_entries`.
- `science/src/science_tool/cli.py` — `--concern` on `add` / `list` / `update` / `triage` / `report`; glob filter; `concern → target` report grouping; surface in triage rows.
- `science/tests/test_feedback.py`, `science/tests/test_feedback_cli.py` — coverage above.
- `commands/post-mortem.md` — **durable source** for the new `/science:post-mortem` skill. The `codex-skills/` tree is generated from `commands/*.md` (`codex_skills.py:36`), so after authoring run `python scripts/generate_codex_skills.py` to produce `codex-skills/science-post-mortem/SKILL.md` and refresh `codex-skills/INDEX.md`. Do not hand-edit the generated files.
- `commands/interpret-results.md` — soft handoff pointer (also regenerates its codex-skills counterpart).
