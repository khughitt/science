# `science explore-ideas apply` CLI — Design

> **Status:** design accepted (brainstorming). Implementation plan to follow via
> `writing-plans`.
> **Date:** 2026-07-04
> **Depends on:** the shipped `/science:explore-ideas` command + report format
> (`docs/plans/2026-07-04-explore-ideas-design.md`) and the entity
> origin-provenance model (`origins`/`added_by`). This design graduates the
> deferred `science explore-ideas apply` CLI named in that design's §12.

## 1. Motivation

Today `/science:explore-ideas --apply` is executed entirely as **prose** by the
command/agent: parse the report's fenced `yaml` blocks, map each `decision:
keep` candidate to a `science questions|hypotheses create` shell-out, route
literature anchors to `--origin`/`--source-ref`, and write `decision: applied`
back into the report. Only `parse_origin_spec` is unit-tested; the entire apply
mechanism is re-interpreted from prose on every run and verified by a **manual**
smoke-check doc (`2026-07-04-explore-ideas-manual-check.md`). A prose slip
(mis-routed origin, missed write-back, a double-applied candidate) **fails
silently**.

This design moves all apply *mechanics* into a tested, fail-loud Python surface —
`science explore-ideas apply` — leaving only agent *judgment* (Phase 3 classify:
novelty bucketing, reading sources, resolving raw anchors to `paper:`/`cite:`)
in the command. It matches the `classify|apply` split the original design already
anticipated.

## 2. Scope

**In:** a new `explore-ideas` CLI group with a single `apply` subcommand; a new
apply module with pure helpers and one impure orchestration boundary; the rewrite
of the command's Apply mode to a thin delegation; converting the manual
smoke-check fixture into a real integration test.

**Out (unchanged from the parent design's deferred list):** a `classify` CLI
subcommand (classify stays agent judgment in the command); `--origin`/`--added-by`
on `topics`/`themes` create (so apply still routes `question`/`hypothesis` only);
embedding-based dedup.

## 3. Module & CLI layout

- **`science/src/science_tool/explore_ideas.py`** (new). Owns apply. The pure
  functions (`resolve_report_path`, `parse_report`, `build_create_plan`, the
  routing helpers, `write_back`) do no side effects. `apply_report` is the single
  **impure orchestration boundary** — it reads the report, calls `create_entity`
  (which writes entity files), and flushes report write-backs to disk. The module
  is "pure-ish": everything except `apply_report` is a pure transform.
- **`science/src/science_tool/cli.py`** — a new `@main.group("explore-ideas")`
  with one `apply` subcommand, registered with `main.add_command(...)` beside the
  other groups. It parses flags, calls `apply_report`, renders the result, and
  sets the exit code. No apply logic lives here.
- **`commands/explore-ideas.md`** — Apply mode collapses to: run
  `uv run science explore-ideas apply --from <report> --model-id <id>`, relay its
  output, and `git commit` if `--commit` was passed. The prose create-command
  templates and anchor-routing rules are **deleted** from the command (they now
  live in the module, tested).

The `parse_origin_spec` `+literature:` grammar extension remains a valid manual
`create` feature but is **no longer on apply's critical path** — apply builds
origins directly from the report's finalized `origin_plan.origins` dicts (§5),
never re-serializing them to spec strings.

## 4. CLI surface

```
uv run science explore-ideas apply --from <report-path-or-id> --model-id <id> [--format text|json]
```

- `--from` **required**. A path to an existing file is used directly; otherwise
  the value is treated as a report id (basename stem, e.g. `explore-2026-07-04`)
  and resolved to `entities/meta/explorations/<id>.md` — the `explore-` prefix is
  **not** re-prepended (the id already carries it). Absent `--from` is a hard
  error (the CLI never guesses "the latest report").
- `--model-id` **required**. Stamped into every `--added-by`
  (`explore-ideas:<model-id>:<candidate_id>`). Absent is a hard error.
- `--format text` (default) prints created / skipped / manual / failure lines;
  `--format json` emits the `ApplyResult` (§7) for machine use.
- **No `--commit`** — matching every other `create` command (none commit). The
  slash command runs `git commit` itself when `--commit` was passed.
- Exit code: non-zero on a pre-flight abort (§6), a fatal post-create write-back
  error (§5), or any per-item execution failure; zero otherwise.

## 5. Apply pipeline (`apply_report`)

`apply_report(project_root: Path, from_value: str, model_id: str, today: date) ->
ApplyResult`. `today` is injected (defaults to `date.today()` in the CLI layer)
so tests are deterministic.

1. **Resolve** `from_value` → report path (`resolve_report_path`, pure). Missing
   file is a hard error.
2. **Parse** (`parse_report`, pure): return every fenced ` ```yaml ` block that
   contains a `candidate_id` key as a `CandidateBlock{data: dict, candidate_id:
   str}`. Surrounding markdown is ignored. Blocks without `candidate_id` are not
   candidates and are skipped silently (they are human prose).
3. **Pre-flight validate + plan** (fail-early, zero writes on bad input — §6).
   Build a `CreatePlan` for every applicable block; if *any* block is invalid,
   raise `ApplyValidationError` naming the offending `candidate_id`(s) before a
   single entity is written.
4. **Execute** (impure): for each valid `CreatePlan`, call `create_entity(...)`
   in-process, capture `entity_id`/`path`/`warnings`, then **immediately** apply
   `write_back` to the in-memory report text and flush it to disk. A create that
   raises is recorded in `failures` and the loop continues (the run's final status
   is failure).
5. **Return** the accumulated `ApplyResult` (§7).

**Write-back failure is fatal, not continuable.** A create/`write_back`/disk-write
split is the one place a duplicate can be minted: the entity file exists but the
report was never updated, so a re-run would re-create it. Therefore, if
`write_back` cannot locate the just-created candidate's block, or the disk flush
raises, `apply_report` **stops immediately** and raises a fatal
`ApplyWriteBackError` that names the created `entity_id` and its `path` and states
the report may need manual repair (mark that block `applied` / `applied_as:
<entity-id>`) before a safe retry. It does **not** continue to the next candidate
— unlike a `create_entity` failure (which wrote nothing and is safely resumable),
a post-create write-back failure has already mutated the project and must surface
loudly rather than risk a second create on retry.

**Write-back durability & correctness.** `write_back(text, candidate_id,
entity_id, applied_at) -> new_text` re-locates the target block **by
`candidate_id`** within the *current* text on each call (never a pre-captured
offset, which a prior edit would have invalidated), replaces the value on that
block's existing `decision:` line with `applied`, and inserts `applied_as:` /
`applied_at:` lines immediately after it at matching indentation. Everything else
in the block and file is byte-for-byte preserved. `apply_report` threads the
returned text forward and writes it to disk after **every** successful create, so
a mid-run crash leaves every already-created entity recorded as `applied` — an
idempotent re-run resumes cleanly with no duplicates.

## 6. Pre-flight validation (fail-early)

A block participates in apply when its `decision` is `keep`. Before any writes,
`build_create_plan` / the planning pass rejects the whole run (naming
`candidate_id`s) if any of these hold across the parsed blocks:

- **Duplicate `candidate_id`** across blocks (the write-back key must be unique).
- **Unknown `decision`** value — not one of `keep | drop | defer | applied`.
- A `keep` block whose **`proposed_kind`** is unknown — not one of
  `question | hypothesis | topic | theme`.
- A `keep` block with a routable `proposed_kind` (`question`/`hypothesis`) that is
  **missing `title`** or **missing/empty `origin_plan.origins`**.
- A `keep` block whose **`origin_plan.origins`** contains an entry that fails
  `OriginRecord.model_validate`.
- A `keep` block with a malformed routed **`literature_anchors`** entry: reject
  when `ref` is non-null and not a string, or when `note` is present and not a
  string. A **missing `note`** is valid and routes as non-`predates:` (a plain
  supporting anchor); only a present-but-non-string `note` is rejected. Entries
  with `ref: null` are not routed and are not validated.

Non-`keep` blocks are classified, not rejected: `applied` → `skipped_applied`;
`drop`/`defer` → `skipped_other`. A `keep` block with `proposed_kind ∈
{topic, theme}` is valid but **not applied** — it goes to `manual` (§7), never
silently dropped.

## 7. `ApplyResult` shape (explicit contract)

The dataclass and its `--format json` serialization are the same shape, so text
and JSON output cannot drift:

```json
{
  "report": "entities/meta/explorations/explore-2026-07-04.md",
  "created":         [{"candidate_id": "cand-...", "entity_id": "question-0007", "kind": "question", "path": "entities/questions/question-0007.md", "warnings": ["..."]}],
  "skipped_applied": ["cand-..."],
  "skipped_other":   ["cand-..."],
  "manual":          [{"candidate_id": "cand-...", "proposed_kind": "topic"}],
  "failures":        [{"candidate_id": "cand-...", "error": "..."}]
}
```

- `created` — entities minted this run, in report order. Each entry carries the
  `entity_id`, `kind`, the created file `path`, and the `warnings` list
  `create_entity` returned. Apply must **surface** these warnings (in the text
  render and the JSON), the same way `_create_typed_entity` calls
  `_emit_entity_warnings` — suppressing them would silently drop existing
  create-command behavior such as derived-id truncation warnings.
- `skipped_applied` — blocks already `decision: applied` (idempotent skip).
- `skipped_other` — `drop`/`defer` blocks.
- `manual` — `keep` `topic`/`theme` blocks reported as "apply manually (CLI seam
  pending)".
- `failures` — `keep` blocks whose `create_entity` raised during execution.

Text output is a deterministic rendering of this object (e.g. `2 created, 0
skipped, 1 to apply manually, 0 failed` plus per-line detail). Non-zero exit iff
`failures` is non-empty (execution), an `ApplyValidationError` was raised
(pre-flight), or an `ApplyWriteBackError` was raised (fatal post-create write-back,
§5).

## 8. Routing rules the module owns

For each routable `keep` block, `build_create_plan` derives create args directly
from the block's finalized fields — no spec-string round-trip:

- **`origins`** ← `origin_plan.origins` verbatim, each dict validated via
  `OriginRecord.model_validate`. This already carries the `assistant` origin and,
  for a convergent candidate, the `{type: literature, ref, independent: true,
  date}` origin the classify phase finalized.
- **`source_refs`** ← the `ref` of each `literature_anchors[]` entry that has a
  non-null `ref` **and** whose `note` does **not** start with `predates:`.
  Supporting papers become provenance (`source_refs`), not origins; the
  `predates:` anchors are already represented as literature origins, so excluding
  them here prevents double-counting. The resulting list is **deduplicated
  preserving first-seen order**.
- **`added_by`** ← `f"explore-ideas:{model_id}:{candidate_id}"`.
- Unresolved anchors (`ref: null`) contribute nothing.

Then `create_entity(project_root, kind=proposed_kind, title=title,
source_refs=source_refs, extra_frontmatter={"origins": [...], "added_by": ...})`
— the same seam `hypotheses/questions create` already use.

## 9. Command rewrite (`commands/explore-ideas.md`)

Generate mode (Phases 1–4) is unchanged. Apply mode is rewritten to:

1. Require `--from` (unchanged hard error).
2. Run `uv run science explore-ideas apply --from <value> --model-id <this-model>
   [--format json]`.
3. Relay the created / skipped / manual / failure summary to the user.
4. If `--commit`, `git commit` the created entities plus the updated report with
   `feat(explore-ideas): apply kept candidates YYYY-MM-DD`.

The prose "Create command templates" and "Literature anchor routing" sections are
deleted — they are now the module's tested responsibility. The `codex-skills/`
mirror is regenerated (`scripts/generate_codex_skills.py`); the sync test stays
green.

## 10. Testing

The point of the work: apply becomes deterministically testable. All in
`science/tests/`, using the `seed_project` fixture pattern from
`test_origin_cli.py`.

**Unit (pure functions):**
- `resolve_report_path`: path passthrough; id → `entities/meta/explorations/<id>.md`
  with no `explore-` re-prepend; same-day-suffixed id resolves from its full stem.
- `parse_report`: extracts only blocks with `candidate_id`; ignores surrounding
  markdown and the collapsed `already-covered` list.
- `build_create_plan` routing: reasoned-only → `assistant` origin only, no
  `source_ref`; convergent `predates:` anchor → independent literature origin with
  `date`, and that anchor is **not** also a `source_ref`; supporting (non-predates)
  resolved anchor → `source_ref`, origin stays `assistant`; unresolved anchor →
  dropped; duplicate resolved refs deduped in order.
- `write_back`: flips `decision` and inserts `applied_as`/`applied_at`; folded
  `>` scalars, key order, and surrounding prose are byte-for-byte preserved;
  re-location is by `candidate_id`, so a second write-back to a *different*
  candidate in already-edited text still lands correctly.
- Pre-flight rejections (each raises before any write): duplicate `candidate_id`;
  unknown `decision`; unknown `proposed_kind`; `keep` question/hypothesis missing
  `title`; missing/empty `origin_plan.origins`; an origin failing `OriginRecord`;
  a routed anchor with a non-string `ref` or a present non-string `note` (a
  missing `note` is accepted and routes as non-`predates:`).
- Fatal post-create write-back: when `write_back` cannot find the just-created
  candidate's block in the report text, `apply_report` raises `ApplyWriteBackError`
  (naming the created `entity_id`/`path`) and does **not** proceed to the next
  candidate.
- Warnings surfaced: a created entity's `create_entity` warnings appear in the
  `ApplyResult.created` entry (and thus in both output formats).

**Integration round-trip (`apply_report` against a temp seeded project):** the
3-candidate fixture currently in the manual-check doc →

- exactly **2** entities created (one `question`, one `hypothesis`); nothing for
  the `drop` block;
- the question carries `cite:chen2022` under `source_refs` and only the
  `assistant` origin (supporting anchor never became an origin);
- the hypothesis carries two `origins` — `assistant` and `{literature,
  cite:okafor2015, independent: true, date: 2015-03-12}`;
- both `keep` blocks flip to `applied` with `applied_as`/`applied_at: <today>`,
  the `drop` block untouched;
- a **second** `apply_report` creates **0** (both now `applied`), no duplicate
  files.

**Doc consolidation:** the manual-check doc's premise ("no orchestration function
to call from pytest") is now false. Its fixture is folded into the integration
test and **`docs/plans/2026-07-04-explore-ideas-manual-check.md` is deleted** —
the parent design's §13 and §12 are updated to point at the CLI + its tests.

## 11. New-code footprint

**Builds:** `explore_ideas.py` (apply module + `ApplyResult`); the
`explore-ideas` CLI group + `apply` subcommand; the command Apply-mode rewrite
(+ regenerated codex mirror); the test module; deletion of the manual-check doc.

**Reuses (no new code):** `create_entity` (`entities.py`), `OriginRecord`
(model), the report format contract, `seed_project` test fixture.

**Not touched:** Generate mode, the `idea-lens-researcher` agent, the
`parse_origin_spec` `+` grammar (kept for manual `create`).
