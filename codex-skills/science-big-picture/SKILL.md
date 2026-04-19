---
name: science-big-picture
description: "Generate a multi-scale, hypothesis-organized synthesis report for the current project. Produces per-hypothesis files, an emergent-threads file, and a project-level rollup (synthesis.md). Use when the user says \"big picture\", \"full synthesis\", \"deep dive\", or wants a shareable project-state artifact. Also use when the user explicitly asks for `science-big-picture` or references `/science:big-picture`."
---

# Project Big Picture

Converted from Claude command `/science:big-picture`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `specs/research-question.md` for project context when it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `specs/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science-tool invocation:** When a command says to run `science-tool`,
   prefer the project-local install path: `uv run science-tool <command>`.
   This assumes the root `pyproject.toml` includes `science-tool` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.
   If that fails (no root `pyproject.toml` or science-tool not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science-tool science-tool <command>`

Generate `doc/reports/synthesis/<hyp>.md` files (one per hypothesis), `doc/reports/synthesis/_emergent-threads.md`, and `doc/reports/synthesis.md` (project rollup).

See the design spec at `docs/specs/2026-04-18-project-big-picture-design.md` for full semantics.

## Flags

Parse the user input for:

- `--hypothesis <id>` — regenerate only one per-hypothesis file. Skip steps 3 and the non-targeted writes.
- `--dry-run` — print what would be generated without writing.
- `--commit` — auto-commit written files with `doc(big-picture): regenerate synthesis YYYY-MM-DD`.
- `--snapshot` — after writing, copy `doc/reports/synthesis.md` to `doc/reports/synthesis-history/<YYYY-MM-DDTHHMMSSZ>.md`.
- `--since <date>` — produce a scoped Arc. **Requires `--output <path>`. Never overwrites canonical files.** If `--since` is set without `--output`, refuse with a clear error.

## Phase 1: Precompute

Run these from the project root. All `science-tool` invocations use `uv run science-tool …` so they resolve against the project's editable install (`pyproject.toml` has `science-tool` as a dev dependency in every Science project) and work regardless of whether `science-tool` is on `$PATH`:

```bash
uv run science-tool graph project-summary --format json
uv run science-tool graph question-summary --format json
uv run science-tool graph inquiry-summary --format json
uv run science-tool graph dashboard-summary --format json
uv run science-tool graph uncertainty --format json
uv run science-tool graph neighborhood-summary --format json
uv run science-tool big-picture resolve-questions --project-root .
```

All graph summary commands default to `--path knowledge/graph.trig` (the Science convention), so no flag is needed when run from the project root.

For `software` profile projects, skip `graph project-summary` (follows `science-status` precedent).

**Note on `graph gaps`**: unlike the other summaries, `graph gaps` requires a `CENTER` argument (the node to analyze around). It is **not** called globally in this phase. Per-hypothesis `gaps_slice` is computed during bundle assembly below, centered on each hypothesis ID.

Enumerate hypotheses from `specs/hypotheses/*.md`.

For each hypothesis, assemble a bundle. The bundle is a dictionary you construct in-memory — it is NOT persisted to disk:

**Aspect filtering**. Before assembling bundles, load project aspects via `load_project_aspects` (or parse `science.yaml` directly). Compute `research_filter = project.aspects \ {software-development}`. Throughout bundle assembly, any entity whose resolved aspects (entity `aspects:` if set, else project `aspects:`) does NOT intersect `research_filter` is excluded from the bundle. This means software-oriented questions (e.g., ones explicitly tagged `aspects: [software-development]`) are dropped before hypothesis matching runs. If `research_filter` is empty, refuse to proceed and point the user at `science-tool big-picture` — research synthesis is undefined on a software-only project.

- `hypothesis_path`: path to the `specs/hypotheses/<id>.md` file.
- `hypothesis_frontmatter`: parsed YAML.
- `resolved_questions`: from the resolver output, all questions whose `hypotheses[]` contains this hypothesis. Annotate each with its confidence.
- `tasks`: glob `tasks/*.md` and `tasks/done/*.md`; parse frontmatter; include entries whose `related:` mentions this hypothesis or any of its resolved questions **AND** whose resolved aspects intersect `research_filter`. If `tasks/active.md` is a single aggregated file (common pattern, e.g., mm30), scan its body for per-task headings and `related:` metadata instead of expecting one file per task.
- `interpretations`: glob `doc/interpretations/*.md`; parse frontmatter; include entries that either (a) directly reference this hypothesis in `related:`, or (b) reference a question whose **primary** hypothesis (per resolver output) is this hypothesis. Do NOT include interpretations that only reach this hypothesis via transitive-only questions (questions whose primary_hypothesis is a different hypothesis). This tightens transitive pull-in and prevents early work that is really "central to H<other>" from flooding this hypothesis's bundle. Apply the same `research_filter` aspect check.
- `edges_yaml`: glob `doc/figures/dags/*.edges.yaml`; include any whose filename stem starts with this hypothesis ID.
- `uncertainty_slice`: filter the global uncertainty output to entries referring to this hypothesis or its resolved questions.
- `gaps_slice`: run `uv run science-tool graph gaps "hypothesis:<id>" --format json` for this hypothesis. Skip (empty slice) if the call errors because the hypothesis has no graph neighborhood yet.
- `topic_gaps`: see below.

**Topic gaps** — in a single call before slicing per hypothesis:

```python
from science_tool.big_picture.knowledge_gaps import compute_topic_gaps

all_gaps = compute_topic_gaps(project_root, resolved_questions, included_question_ids)
```

Then for each hypothesis bundle, filter `all_gaps` to topics whose `hypotheses` list includes this hypothesis's ID. Pass the filtered list to the hypothesis-synthesizer agent as `topic_gaps`.

`included_question_ids` is the exact set already computed earlier in Phase 1 for aspect filtering — DO NOT recompute it here.

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

## Phase 3: Synthesize (project rollup)

Skip this phase if `--hypothesis <id>` is set.

After the dispatch phase completes, read back each just-written per-hypothesis file and the emergent-threads file. You (the orchestrator, on Opus 4.7) are the only agent with visibility across all hypotheses, so cross-hypothesis synthesis happens here — do not dispatch another sub-agent for this.

Write `doc/reports/synthesis.md` with this structure:

Frontmatter:

```yaml
---
type: "synthesis-rollup"
generated_at: "<ISO-8601>"
source_commit: "<SHA>"
synthesized_from:
  - { hypothesis: "<hyp-id>", file: "doc/reports/synthesis/<hyp-id>.md", sha: "<SHA>" }
  # one entry per hypothesis
emergent_threads_sha: "<SHA>"
orphan_question_count: <int>
---
```

Body sections (~1000–1500 words total):

- **TL;DR** — 5–7 bullets, most salient project-wide facts. Distilled from each per-hypothesis State, not a per-hypothesis recap.
- **State** — cross-hypothesis consolidation. What the project collectively believes, where the strongest evidence sits, what's contested.
- **Arc** — one paragraph per hypothesis, plus a framing paragraph on how the hypotheses relate.
- **Research fronts** — ranked list across all hypotheses. Signals: uncertainty density, recent activity, explicit task priority. Cite source: "from <hyp-id>" for each front.
- **Knowledge Gaps (rollup)** — The orchestrator reuses the `all_gaps` list computed in Phase 1 (no second call to `compute_topic_gaps`). Render the top 10 entries (by `gap_score` desc, ties broken by topic ID asc) as a markdown table with columns: Topic, Coverage, Demand, Gap, Hypotheses. If `all_gaps` is empty, emit the one-liner: "No knowledge gaps detected this run." and skip the table. Per-hypothesis files render their own Knowledge Gaps sub-bullet inside Research Fronts per the spec (with a rendering cap of 5 `demanding_questions` IDs + "… and N more" tail).
- **Emergent threads** — 2–3 sentence pointer to `_emergent-threads.md`. Include the orphan-question count.

Computing SHAs:

```bash
git hash-object doc/reports/synthesis/<hyp-id>.md
git hash-object doc/reports/synthesis/_emergent-threads.md
```

**Orphan-question counting**:

- Compute via `count_research_orphans(resolved, project_root)` from `science_tool.big_picture.validator`. The count excludes questions whose resolved aspects are only `[software-development]`; these are out of scope for research synthesis. The orchestrator does not re-derive this count manually — delegate to the helper so the rollup and validator agree on the definition.

**Citation inheritance**: the rollup inherits the citation and grounding requirements from the per-hypothesis files. Every factual claim traces back to a specific per-hypothesis file's content. No new unsupported claims are introduced at the rollup level.

## Phase 4: Write

All canonical artifacts are overwritten on regen.

- Per-hypothesis files: already written by sub-agents in Phase 2.
- Emergent-threads file: already written by sub-agent in Phase 2.
- Project rollup: write `doc/reports/synthesis.md` (from Phase 3).

If `--snapshot` is set:

```bash
mkdir -p doc/reports/synthesis-history
ts="$(date -u +%Y-%m-%dT%H%M%SZ)"
cp doc/reports/synthesis.md "doc/reports/synthesis-history/${ts}.md"
```

If `--dry-run` is set: do not write any files. Print, for each intended file, the target path and a summary (section word counts). Do not invoke sub-agents.

If `--commit` is set: stage all written files and commit with message `doc(big-picture): regenerate synthesis YYYY-MM-DD`.

## Staleness check for partial regen

After any `--hypothesis <id>` invocation, the rollup's `synthesized_from` frontmatter still references the old per-hypothesis SHAs. On the next invocation (any invocation), before Phase 1, compare each entry in the rollup's `synthesized_from` to the current file's SHA:

```bash
for each entry in synthesized_from:
  current_sha = git hash-object <entry.file>
  if current_sha != entry.sha:
    print warning: "Rollup is stale relative to <entry.file>. Run science-big-picture without --hypothesis to refresh."
```

The staleness warning is informational — do not block execution.

## `--since` handling

If `--since <date>` is set:

- Require `--output <path>` as well. If absent, refuse with: "`--since` requires `--output <path>` to avoid overwriting canonical artifacts. Pass `--output doc/reports/some-scoped-name.md`."
- Do NOT write canonical files (`doc/reports/synthesis.md`, `doc/reports/synthesis/`, `_emergent-threads.md`). Write only to `--output`.
- In the output, include `since: <date>` in frontmatter, and a banner at the top: `> **Scoped synthesis:** includes only activity after <date>. Not the authoritative project synthesis.`

## Output to user

After all phases:

- Run the validator automatically: `uv run science-tool big-picture validate --project-root .`. Show the output verbatim. If `nonexistent_reference` issues surface, treat them as real signals — the sub-agents wrote IDs that do not resolve to any entity in the project. Before reporting success, either (a) re-dispatch the relevant per-hypothesis sub-agent with the failed IDs listed as "do not cite; use verified IDs from the bundle", or (b) list the issues for the user to resolve manually. Do NOT silently declare success while citation errors exist.
- Show the list of files written.
- Show any staleness warnings.
- Show any sub-agent "unused in synthesis" reports — these are candidates for future bundle improvements.
