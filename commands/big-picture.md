---
description: Generate a multi-scale, hypothesis-organized synthesis report for the current project. Produces per-hypothesis files, an emergent-threads file, and a project-level rollup (synthesis.md). Use when the user says "big picture", "full synthesis", "deep dive", or wants a shareable project-state artifact.
---

# Project Big Picture

Generate `doc/reports/synthesis/<hyp>.md` files (one per hypothesis), `doc/reports/synthesis/_emergent-threads.md`, and `doc/reports/synthesis.md` (project rollup).

See the design spec at `${CLAUDE_PLUGIN_ROOT}/docs/specs/2026-04-18-project-big-picture-design.md` for full semantics.

## Flags

Parse `$ARGUMENTS` for:

- `--hypothesis <id>` — regenerate only one per-hypothesis file. Skip steps 3 and the non-targeted writes.
- `--dry-run` — print what would be generated without writing.
- `--commit` — auto-commit written files with `doc(big-picture): regenerate synthesis YYYY-MM-DD`.
- `--snapshot` — after writing, copy `doc/reports/synthesis.md` to `doc/reports/synthesis-history/<YYYY-MM-DDTHHMMSSZ>.md`.
- `--since <date>` — produce a scoped Arc. **Requires `--output <path>`. Never overwrites canonical files.** If `--since` is set without `--output`, refuse with a clear error.

## Phase 1: Precompute

Run these in the project root:

```bash
science-tool graph project-summary --format json
science-tool graph question-summary --format json
science-tool graph inquiry-summary --format json
science-tool graph dashboard-summary --format json
science-tool graph uncertainty --format json
science-tool graph gaps --format json
science-tool graph neighborhood-summary --format json
science-tool big-picture resolve-questions --project-root .
```

For `software` profile projects, skip `graph project-summary` (follows `/science:status` precedent).

Enumerate hypotheses from `specs/hypotheses/*.md`.

For each hypothesis, assemble a bundle. The bundle is a dictionary you construct in-memory — it is NOT persisted to disk:

- `hypothesis_path`: path to the `specs/hypotheses/<id>.md` file.
- `hypothesis_frontmatter`: parsed YAML.
- `resolved_questions`: from the resolver output, all questions whose `hypotheses[]` contains this hypothesis. Annotate each with its confidence.
- `tasks`: glob `tasks/*.md` and `tasks/done/*.md`; parse frontmatter; include entries whose `related:` mentions this hypothesis or any of its resolved questions.
- `interpretations`: glob `doc/interpretations/*.md`; parse frontmatter; include entries whose `related:` mentions this hypothesis or any of its resolved questions.
- `edges_yaml`: glob `doc/figures/dags/*.edges.yaml`; include any whose filename stem starts with this hypothesis ID.
- `uncertainty_slice`: filter the global uncertainty output to entries referring to this hypothesis or its resolved questions.
- `gaps_slice`: same filtering for gaps output.

Compute `provenance_coverage` per hypothesis:
- `high` if ≥1 `.edges.yaml` is present OR ≥1 graph claim surfaces AND ≥60% of related interpretations have `prior_interpretations` chains.
- `partial` if neither of those but ≥30% of related interpretations have `prior_interpretations`.
- `thin` otherwise.

Record the project-level `source_commit`:

```bash
git -C <project-root> rev-parse HEAD
```

Record `generated_at` as the current ISO-8601 UTC timestamp.

## Phase 2: Dispatch

Dispatch sub-agents in parallel using `Agent` tool calls. Send all dispatches in a single message.

For each hypothesis (unless `--hypothesis <id>` is set, in which case only that one):

```
Agent(
  subagent_type="hypothesis-synthesizer",
  description="Synthesize <hyp-id>",
  prompt=<<the prompt below>>
)
```

The prompt passed to each sub-agent includes:

- Project root path.
- Hypothesis ID and `hypothesis_path`.
- The bundle (inlined in the prompt as structured text — the sub-agent does not have access to your in-memory bundle directly).
- Target output path: `doc/reports/synthesis/<hyp-id>.md`.
- `generated_at` and `source_commit` values.
- `provenance_coverage` value.
- If `--since <date>` is set: pass it through AND the `--output <path>` target. Tell the sub-agent to include `since: <date>` in its frontmatter.

Also dispatch one emergent-threads sub-agent:

```
Agent(
  subagent_type="emergent-threads-synthesizer",
  description="Synthesize emergent threads",
  prompt=<<the prompt below>>
)
```

The prompt includes:

- Project root path.
- Full resolver output (JSON from Phase 1).
- Target output path: `doc/reports/synthesis/_emergent-threads.md`.
- `generated_at` and `source_commit` values.

**Important**: if `--hypothesis <id>` is set, skip the emergent-threads dispatch (it's a whole-project artifact).

Collect all sub-agent reports. Expect each to report: the path written, word counts, and any bundle items it could not ground.
