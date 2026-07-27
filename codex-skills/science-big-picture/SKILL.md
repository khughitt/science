---
name: science-big-picture
description: "Generate a multi-scale, hypothesis-organized synthesis for the project — per-hypothesis files, an emergent-threads file, and a project-level rollup (synthesis.md). Use when the user wants a full synthesis or shareable project-state artifact."
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
3. Load the `science-scientific-writing` Codex skill. For research methodology, read `../../skills/INDEX.md` and load the leaves relevant to the task (e.g. `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
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
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
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
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif uv run --frozen science --help >/dev/null 2>&1; then
  # The CLI runs but has no --version option, so it predates the baseline.
  # Decided by behavior, never by matching Click's version-dependent wording.
  SCIENCE_INSTALLED_VERSION=
else
  # The CLI cannot run at all: missing/stale lock, Git fetch failure, import
  # error. Report the real diagnosis; never advise moving the Science pin.
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

After the gate succeeds, run the command through the consumer's project-local
environment as `uv run science <command>`. Missing dependency, missing or stale
lock, and Git fetch failures are surfaced directly and must be fixed in the
consumer project.

A CLI that answers `--help` but rejects `--version` predates the baseline;
malformed successful output and a version below the floor are likewise
compatibility failures, and all three stop with the upgrade command. A CLI that
cannot run at all is an environment failure: its output is printed verbatim and
must be fixed as reported.

The `--help` probe is what separates those two classes. Do not substitute a match
against Click's error text — its wording changed in Click 8.4, and `science`
allows any `click>=8.1`, so a freshly locked consumer can emit either form. The
root `--version` probe is the permanent bootstrap surface; do not replace it with
a preflight subcommand, which an older CLI could not recognize either.

Generate `entities/synthesis/<hyp>.md` files (one per hypothesis), an
`entities/synthesis/<emergent-threads>.md` file, and an
`entities/synthesis/<project-synthesis>.md` rollup. The role is determined by
`report_kind`, not by filename.

See `docs/user-guide/big-picture-synthesis.md` for the durable user-facing
synthesis and topic-coverage gap semantics.

Follow `references/command-preamble.md` before executing this command.

## Flags

Parse the user input for:

- `--hypothesis <id>` — regenerate only one per-hypothesis file. Skip steps 3 and the non-targeted writes.
- `--dry-run` — print what would be generated without writing.
- `--commit` — auto-commit written files with `doc(big-picture): regenerate synthesis YYYY-MM-DD`.
- `--snapshot` — after writing, copy the rollup entity to `entities/synthesis/history-<YYYY-MM-DDTHHMMSSZ>.md`.
- `--since <date>` — produce a scoped Arc. **Requires `--output <path>`. Never overwrites canonical files.** If `--since` is set without `--output`, refuse with a clear error.

## Phase 1: Precompute

Run these from the project root. All `science` invocations use `uv run science …` so they resolve against the project's editable install (`pyproject.toml` has `science` as a dev dependency in every Science project) and work regardless of whether `science` is on `$PATH`:

```bash
uv run science graph project-summary --format json
uv run science graph question-summary --format json
uv run science graph inquiry-summary --format json
uv run science graph attention-sample --limit 8 --format json
uv run science graph dashboard-summary --format json
uv run science graph uncertainty --format json
uv run science graph neighborhood-summary --format json
uv run science big-picture resolve-questions --project-root .
```

All graph summary commands default to `--path knowledge/graph.trig` (the Science convention), so no flag is needed when run from the project root.

If `big-picture resolve-questions` returns `{"status": "empty", ...}`, treat
that as a clean empty state only when the reason is expected for the project
(for example, no question entities yet). A bare `{}` is not an acceptable status
surface; rerun with the current CLI or report feedback because it does not
distinguish clean-empty from unwired.

For `software` profile projects, skip `graph project-summary` (follows `science-status` precedent).
Use `graph attention-sample` to choose which epistemic entities receive close
reading in this synthesis pass. Do not narrow the synthesis solely by
deterministic top-N priority rows.

**Note on `graph gaps`**: unlike the other summaries, `graph gaps` requires a `CENTER` argument (the node to analyze around). It is **not** called globally in this phase. Per-hypothesis `gaps_slice` is computed during bundle assembly below, centered on each hypothesis ID.

Enumerate hypotheses from `entities/hypotheses/*.md`.

For each hypothesis, assemble a bundle. The bundle is a dictionary you construct in-memory — it is NOT persisted to disk:

**Aspect filtering**. Before assembling bundles, load project aspects via `load_project_aspects` (or parse `science.yaml` directly). Compute `research_filter = project.aspects \ {software-development}`. Throughout bundle assembly, any entity whose resolved aspects (entity `aspects:` if set, else project `aspects:`) does NOT intersect `research_filter` is excluded from the bundle. This means software-oriented questions (e.g., ones explicitly tagged `aspects: [software-development]`) are dropped before hypothesis matching runs. If `research_filter` is empty, refuse to proceed and point the user at `science big-picture` — research synthesis is undefined on a software-only project.

- `hypothesis_path`: path to the `entities/hypotheses/<id>.md` file.
- `status`: read `status:` from the hypothesis frontmatter; default to `active` if absent. This is the **lifecycle** (`draft | active | complete | superseded | retired | archived`).
- `verdict`: read `verdict:` from the hypothesis frontmatter; **absent is meaningful** — it means the evidence has not spoken, and it must never be inferred from `status`.
- `hypothesis_frontmatter`: parsed YAML.
- `resolved_questions`: from the resolver output, all questions whose `hypotheses[]` contains this hypothesis. Annotate each with its confidence.
- `tasks`: for this hypothesis and each resolved question, run `uv run science tasks list --all --related=<ref> --format json` to collect open work. For terminal work, derive `<task-window-start>` from `--since` when present or the project's `created` date otherwise, then run the same related filters with `--status done --since <task-window-start>` and `--status retired --since <task-window-start>`. Merge by task ID and include entries whose resolved aspects intersect `research_filter`. The CLI reads one YAML-frontmatter file per open task under `tasks/active/`; do not open task-store files directly.
- `interpretations`: glob `entities/interpretations/*.md`; parse frontmatter; include entries that either (a) directly reference this hypothesis in `related:`, (b) reference a question whose **primary** hypothesis (per resolver output) is this hypothesis, or (c) appear by `interpretation:...` ID in this hypothesis spec's own `related:` frontmatter. Do NOT include interpretations that only reach this hypothesis via transitive-only questions (questions whose primary_hypothesis is a different hypothesis). This tightens transitive pull-in and prevents early work that is really "central to H<other>" from flooding this hypothesis's bundle. Rule (c) is the escape hatch for `weakened`/`proposed`/`candidate` hypotheses that have no resolved questions and that the hypothesis author has explicitly bound to specific interpretations — without it, weakened hypotheses can end up with bundles too sparse to synthesize against. For each included interpretation, parse its frontmatter `id:` field and pass both `path` and canonical `id:` in the bundle entry, so sub-agents can cite by canonical ID without falling back to filename inference. Apply the same `research_filter` aspect check.
- `graph_propositions`: include proposition entities linked to this hypothesis, or whose `legacy_patch` / DAG membership metadata binds them to the hypothesis's DAG. While assembling, build a set of interpretation IDs cited through related evidence-line entities. Pass this set to the sub-agent as `edge_cited_interpretation_ids`: when an interpretation in the bundle is also covered by proposition/evidence-line structure, the sub-agent should cite it through that structure and treat its omission from the prose-level interpretation list as expected — not as a "bundle-unused" gap.
- `uncertainty_slice`: filter the global uncertainty output to entries referring to this hypothesis or its resolved questions.
- `gaps_slice`: run `uv run science graph gaps "hypothesis:<id>" --format json` for this hypothesis. Skip (empty slice) if the call errors because the hypothesis has no graph neighborhood yet.
- `topic_gaps`: see below.

**Topic gaps** — in a single call before slicing per hypothesis:

```python
from science_tool.big_picture.knowledge_gaps import compute_topic_gaps

result = compute_topic_gaps(project_root, resolved_questions, included_question_ids)

if result.status == "unwired":
    # The instrument did NOT run: included questions declare topic: refs, and none
    # of them resolve to a topic entity. STOP and report this. Do NOT proceed as if
    # there were no gaps -- an empty gap list here would tell the reader their topic
    # coverage is complete, when in fact it was never measured.
    raise RuntimeError(f"topic gaps did not run ({result.code}): {result.reason}")

all_gaps = result.rows
if result.reason:
    # A caveat on a SUCCESSFUL run: some declared topic refs dangle and were dropped
    # from demand. Surface it in the report -- do not silently discard it.
    ...
```

`result.status` is `empty` when no included question declares a topic ref at all — that is a **true** zero-gap finding, and you should report it as such. It is `unwired` only when refs were declared and none resolved. Those are different facts and must not be rendered the same way.

Then for each hypothesis bundle, filter `all_gaps` to topics whose `hypotheses` list includes this hypothesis's ID. Pass the filtered list to the hypothesis-synthesizer agent as `topic_gaps`.

`included_question_ids` is the exact set already computed earlier in Phase 1 for aspect filtering — DO NOT recompute it here.
The stable topic-coverage gap contract is documented in
`docs/user-guide/big-picture-synthesis.md`.

Compute `provenance_coverage` per hypothesis:
- `high` if >=1 graph proposition surface exists AND >=60% of
  related interpretations participate in materialized `sci:amends` /
  `sci:supersedes` conclusion chains.
- `partial` if neither of those but >=30% of related interpretations participate
  in materialized `sci:amends` / `sci:supersedes` chains.
- `thin` otherwise.

`prior_interpretations` is a narrative breadcrumb, not the machine-readable chain.
Use materialized `sci:amends` and `sci:supersedes` edges for arc
reconstruction. When a replacement chain exists, prefer non-superseded current
conclusions in the synthesis and keep superseded conclusions as provenance.

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
- Target output path: **resolve it, do not compose it.** Run
  `science big-picture synthesis-path <hyp-id> --project-root <root>` and pass the result
  verbatim. An existing `report_kind: hypothesis-synthesis` entity whose `hypothesis:`
  frontmatter names this hypothesis wins, *whatever its filename* — numbered-entity projects
  store it as e.g. `entities/synthesis/0022-epigenetic-commitment.md`. Composing
  `<hyp-id>.md` in such a project creates a DUPLICATE synthesis entity beside the canonical
  one, with the rollup pointing at one and the graph at the other. The fallback to
  `<hyp-id>.md` applies only when no prior file exists — partial coverage is normal.
- Frontmatter: emit `kind: synthesis` + `title: "Synthesis: <hyp-id>"` + `report_kind: hypothesis-synthesis` + `id: synthesis:<hyp-id>` + `hypothesis: hypothesis:<hyp-id>` + `generated_at` + `source_commit` + `provenance_coverage`. Do *not* emit `synthesized_from:` (the rollup carries that). `title` is required because projects may register `synthesis` as a profile kind. See `agents/hypothesis-synthesizer.md` for the full output spec.
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
- Target output path: `entities/synthesis/<emergent-threads>.md`.
- Frontmatter: emit `kind: synthesis` + `title: "Emergent threads - <project name>"` + `report_kind: emergent-threads` + `id: synthesis:emergent-threads` + `generated_at` + `source_commit` + `orphan_question_count` + `orphan_interpretation_count` + `orphan_ids: [...]`. Do *not* emit `synthesized_from:` — emergent-threads is graph-derived, not file-derived.
- `generated_at` and `source_commit` values.

**Important**: if `--hypothesis <id>` is set, skip the emergent-threads dispatch (it's a whole-project artifact).

Collect all sub-agent reports. Expect each to report: the path written, word counts, and any bundle items it could not ground.

## Phase 3: Synthesize (project rollup)

Skip this phase if `--hypothesis <id>` is set.

After the dispatch phase completes, read back each just-written per-hypothesis file and the emergent-threads file. You (the orchestrator, on Opus 4.7) are the only agent with visibility across all hypotheses, so cross-hypothesis synthesis happens here — do not dispatch another sub-agent for this.

Write the `report_kind: synthesis-rollup` entity under `entities/synthesis/`
with this structure:

The frontmatter follows the canonical synthesis shape documented in `templates/synthesis.md`. All three artifacts produced by this command (per-hypothesis files, emergent threads, and the project rollup) share `kind: synthesis` and differ by `report_kind`. `science validate` warns when any `kind: synthesis` file omits `report_kind`, and applies per-kind field requirements: `synthesis-rollup` must carry `synthesized_from`; `hypothesis-synthesis` must carry `hypothesis` and `provenance_coverage`; `emergent-threads` must carry `orphan_question_count`, `orphan_interpretation_count`, and `orphan_ids`.

Frontmatter:

The block-list form (one field per line) is canonical — see Plan #4 follow-on for the resolved Q2 in `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md`. The inline-dict form `[{...}]` is deprecated.

```yaml
---
id: "synthesis:rollup"
kind: "synthesis"
title: "Project synthesis - <project name>"
report_kind: "synthesis-rollup"
generated_at: "<ISO-8601>"
source_commit: "<SHA>"
synthesized_from:
  - hypothesis: "hypothesis:<hyp-id>"
    file: "entities/synthesis/<hyp-id>.md"
    sha: "<SHA>"
  # one entry per hypothesis
emergent_threads_sha: "<SHA>"
orphan_question_count: <int>
---
```

Body sections (~1000–1500 words total):

- **TL;DR** — 5–7 bullets, most salient project-wide facts. Distilled from each per-hypothesis State, not a per-hypothesis recap.
- **State** — cross-hypothesis consolidation. What the project collectively believes, where the strongest evidence sits, what's contested.
- **Arc** — one paragraph per **active** hypothesis (those whose bundle has `status == "active"` or whose hypothesis file omits `status:`), plus a framing paragraph on how the active hypotheses relate. Draft hypotheses are not included here; they appear in the Draft frames section below. **Exclude every hypothesis whose `status` is `complete`, `superseded`, `retired`, or `archived`** — a closed hypothesis is not part of the live arc.
- **Research fronts** — ranked list across **active** hypotheses only. Signals: uncertainty density, recent activity, explicit task priority. Cite source: "from <hyp-id>" for each front. Candidate hypotheses do not contribute to this section; their fronts (if any) appear inside their per-hypothesis files at `entities/synthesis/<id>.md`.
- **Draft frames** — one paragraph per hypothesis whose bundle has `status == "draft"`. Same citation, grounding, and length rules as the per-hypothesis files. If no drafts exist, emit a single line: `No draft hypotheses.` Do not suppress the section. Active hypotheses are NOT mentioned here — they appear in the Arc and Research-fronts sections only.

  **`status` is the lifecycle axis; `verdict` is the epistemic one, and neither implies the other.** A hypothesis whose `status` is `complete`/`superseded`/`retired`/`archived` is no longer an object of active work — whatever the evidence says about it — so it must not be presented as a *live draft frame*. natural-systems rendered a hypothesis it had stopped working on as a candidate frame, because `status` held the epistemic verdict and there was no lifecycle word to select on. Do not read closure off the verdict either: a `refuted` hypothesis that is still being written up is `status: active`, and it belongs in the Arc.

- **Closed frames** — one line per hypothesis whose `status` is `complete`, `superseded`, `retired`, or `archived`: its ID, its `status`, its `verdict` (`refuted`, `weakened`, `supported`, `partially-supported` — or **none**, if it was closed for pragmatic reasons and the evidence never spoke), and its `closure_basis`. Report an absent verdict AS absent; do not supply one. Closure is not hiding: a closed hypothesis stays queryable and provenance-visible, and the reader must be able to see what was set down and why. If none exist, emit `No closed hypotheses.`

- **Re-homing debt** — run `science graph rehoming-debt`. Open questions attached to a terminal hypothesis do not become uninteresting because their frame died; they become **unhoused**. List them with the terminal hypothesis each still resolves to. Retirement *creates* work, and this section is where that work becomes visible — **the dead hypothesis is not ranked, but its re-homing debt is.** If the instrument reports `unwired` (the project's hypotheses still carry the verdict in `status`, so their closure cannot be read), say so rather than reporting zero debt.
- **Knowledge Gaps (rollup)** — The orchestrator reuses the `all_gaps` list computed in Phase 1 (no second call to `compute_topic_gaps`). Render the top 10 entries (by `gap_score` desc, ties broken by topic ID asc) as a markdown table with columns: Topic, Coverage, Demand, Gap, Hypotheses. If `all_gaps` is empty, emit the one-liner: "No knowledge gaps detected this run." and skip the table. Per-hypothesis files render their own Knowledge Gaps sub-bullet inside Research Fronts per the spec (with a rendering cap of 5 `demanding_questions` IDs + "… and N more" tail).
- **Emergent threads** — 2–3 sentence pointer to `_emergent-threads.md`. Include the orphan-question count.

Computing SHAs:

> **Validate the per-hypothesis files BEFORE stamping their SHAs.** A provenance record
> stamped before its subject is final is not provenance.
>
> The validator legitimately rejects per-hypothesis files — that is its job. The documented
> repair is to re-dispatch the sub-agent, which **rewrites the file and changes its SHA**,
> silently invalidating the `synthesized_from` the rollup already attested to. Nothing
> re-checks it: the staleness warning fires only on the *next* invocation, and is explicitly
> informational (fb-2026-07-11-006).
>
> So the order is: **write → validate → repair (loop until clean) → stamp → write rollup.**
> If any repair loop runs after a stamp, **re-stamp**. Never stamp a file you are still
> willing to change.

Validate the staged/written per-hypothesis files first:

```bash
uv run science big-picture validate --project-root .
```

Only once they are clean, compute the SHAs:

```bash
git hash-object entities/synthesis/<hyp-id>.md
git hash-object entities/synthesis/<emergent-threads>.md
```

**Orphan-question counting**:

- Compute via `list_research_orphans(resolved, project_root)` from `science_tool.big_picture.validator`. `orphan_question_count` is `len(result.rows)` and `orphan_ids` is `result.rows` — **the same call**, so the count and the ID list cannot disagree. (They did: a rollup once reported 40 orphans beside a hand-derived list of 31.) The predicate excludes questions whose resolved aspects are only `[software-development]`; these are out of scope for research synthesis. Do not re-derive either value by hand. There is deliberately no `count_research_orphans`.

**Citation inheritance**: the rollup inherits the citation and grounding requirements from the per-hypothesis files. Every factual claim traces back to a specific per-hypothesis file's content. No new unsupported claims are introduced at the rollup level.

## Phase 4: Write

All canonical artifacts are overwritten on regen.

- Per-hypothesis files: already written by sub-agents in Phase 2.
- Emergent-threads file: already written by sub-agent in Phase 2.
- Project rollup: write the `report_kind: synthesis-rollup` entity under `entities/synthesis/` (from Phase 3).

If `--snapshot` is set:

```bash
mkdir -p entities/synthesis
ts="$(date -u +%Y-%m-%dT%H%M%SZ)"
cp <rollup-path> "entities/synthesis/history-${ts}.md"
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

- Require `--output <path>` as well. If absent, refuse with: "`--since` requires `--output <path>` to avoid overwriting canonical artifacts. Pass `--output entities/synthesis/some-scoped-name.md`."
- Do NOT write canonical synthesis entities under `entities/synthesis/`. Write only to `--output`.
- In the output, include `since: <date>` in frontmatter, and a banner at the top: `> **Scoped synthesis:** includes only activity after <date>. Not the authoritative project synthesis.`

## Output to user

After all phases:

- Run the validator automatically: `uv run science big-picture validate --project-root .`. Show the output verbatim. If `nonexistent_reference` issues surface, treat them as real signals — the sub-agents wrote IDs that do not resolve to any entity in the project. Before reporting success, either (a) re-dispatch the relevant per-hypothesis sub-agent with the failed IDs listed as "do not cite; use verified IDs from the bundle", or (b) list the issues for the user to resolve manually. Do NOT silently declare success while citation errors exist.
- Show the list of files written.
- Show any staleness warnings.
- Show any sub-agent "unused in synthesis" reports — these are candidates for future bundle improvements.
