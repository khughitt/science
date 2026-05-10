---
title: Wander — serendipitous random-sample review loop
date: 2026-05-09
status: design
---

# Wander · Design

## 1. Intent

A casual, low-stakes serendipity loop. The user runs `/wander` periodically.
The agent samples a small handful of project entities at random (weighted by
existing attention machinery), reviews each one for gaps, looks for
unappreciated pairwise connections, and writes a short report. Default mode is
read-only; `--apply` may create tasks but never edits prose or code.

### Goals

- **Continuous curation** of project entities at low cost per session.
- **Serendipity:** counter local optima and attention bias by giving every
  *epistemic* entity (those with `sci:freshnessState`) a non-zero chance of
  being visited each walk.
- **Re-assessment:** revisit older ideas in the context of current
  understanding.

### Non-goals (v1)

- Nested or profile-based sampling policies.
- Automatic 30-day pruning enforcement (only flagging is in scope).
- Walking source code or files outside `knowledge/graph.trig`.
- Learning sampling weights from past walks.
- Sampling **non-epistemic** entities (datasets, code modules, raw notes,
  anything without `sci:freshnessState`). The existing attention machinery in
  `science_tool.graph.attention` is explicitly epistemic, and v1 inherits that
  scope. Broadening the candidate set is future work — see §9.

## 2. Scope and constraints

Sampling is bounded by epistemic entities materialized into
`knowledge/graph.trig` (entities carrying `sci:freshnessState`). If
`knowledge/graph.trig` is missing, `science wander` errors with a hint to run
`science graph build` first (the existing CLI command — `/science:create-graph`
is the slash-command analog, but the CLI surface is what the error message
points at). Code-level review only happens when an entity explicitly references
implementation (e.g., a hypothesis pointing at a pipeline, a dataset with a
loader); the walk does not go hunting through `src/` for entities that are not
grounded there.

## 3. CLI surface

A new `science wander` subcommand in `science_tool/cli.py`. It is a thin
evidence-gathering layer — it does no LLM work. Mirrors the role of
`science curate inventory`.

```
science wander [OPTIONS]

Options:
  --n INTEGER              Number of entities to sample. Default 3.
  --seed INTEGER           Reproducibility seed (forwarded to sampler).
  --kind TEXT              Restrict to one or more entity kinds (multi).
  --epsilon FLOAT          Positive weight floor (forwarded). Default 0.05.
  --graph-path PATH        Override graph path. Default knowledge/graph.trig.
  --format [json|markdown] Output format. Default markdown.
  --out PATH               Output path. Default doc/meta/walks/walk-<id>.md
                           (markdown) or stdout (json).
```

Behavior:

1. Resolve graph path; error with actionable message if missing
   (`run \`science graph build\` first`).
2. Load the dataset and call `compute_attention_candidates(...)` followed by
   `weighted_sample_without_replacement(...)` — both already public in
   `science_tool.graph.attention`. **Do not** call the higher-level
   `query_attention_sample`, which discards the URI and raw weight components
   we need for the context bundle. No changes to `attention.py` are required.
3. For each sampled entity, assemble a **context bundle** by combining the
   `AttentionCandidate` fields (id, uri, kind, label, raw weight components)
   with additional lookups from the same dataset and from disk:
   - **From the candidate:** id, uri, kind, label, freshness state, weight,
     and the full `components` mapping (incoming_bears_on,
     days_since_last_review, support_count, dispute_count, etc.).
   - **From the graph (re-query the loaded dataset):** direct neighbors —
     incoming + outgoing `sci:bearsOn` (uncapped) and up to 10 each direction
     for any other predicate; created date (`dcterms:created` or
     `sci:created` if present); active references from tasks/hypotheses (any
     subject with kind in `{task, hypothesis}` whose object is this entity).
   - **From disk:** source file path resolved by querying the provenance
     graph (`graph/provenance` named graph) for the entity's
     `prov:wasDerivedFrom` source URI and reading its `schema:identifier`
     literal — the same mechanism `science_tool.graph.materialize` uses to
     emit provenance. From that path, read `mtime` and content length in
     characters. If no provenance edge resolves (entity has no source file),
     omit the filesystem fields rather than failing.
4. In `markdown` mode, write a **report skeleton** at `--out`: the report
   template from §6 with frontmatter and the **Sample** and **Per-entity
   review** scaffolding pre-filled with sampled rows and context bundles. The
   per-entity review section embeds the context bundle (label, weight
   breakdown, neighbors, created date, file path, mtime, length) as a small
   block under each entity heading, so the agent can read it without
   re-querying. The review prose, pairwise, prune, and spawned-tasks sections
   are present as empty headings, ready for the agent to fill in. In `json`
   mode, emit the raw context bundles to stdout for programmatic consumers.

The slash command (next section) runs `science wander` to produce the
skeleton, then fills it in *in place* — there is exactly one walk file per
run.

## 4. Slash command

`commands/wander.md` is the agent loop. It:

1. Parses `$ARGUMENTS` for `--apply` (consumed by the slash command itself)
   and **forwards every other flag verbatim** to `science wander` —
   specifically `--n`, `--seed`, `--kind`, `--epsilon`, `--graph-path`. This
   keeps `/wander` and `science wander` reproducible and filterable in the
   same ways; nothing diverges silently.
2. Generates a walk path `doc/meta/walks/walk-YYYY-MM-DD-HHMM.md` and runs
   `science wander --format markdown --out <walk-path> <forwarded-flags>`
   to materialize the report skeleton.
3. Reads the skeleton, including each entity's context bundle.
4. Performs the review loop (§5).
5. Edits the same file in place, filling in the empty sections (per-entity
   gaps, pairwise connections, prune candidates, spawned tasks).
6. If `--apply` was passed, may invoke `science tasks add` per §7 and append
   the resulting task IDs under "Spawned tasks".

## 5. Agent loop

### Per-entity review

For each sampled entity, the agent makes one short pass and notes:

- **Text gaps:** prose quality, missing citations or provenance, broken
  cross-refs, weak or disconnected annotation.
- **Code/data gaps:** *only when the entity references implementation.* Look
  for silent failures, magic numbers, drift from claimed behavior. Skip if not
  grounded in code.
- **Epistemic gaps:** unstated assumptions, claims without support edges,
  propositions with stale verdicts. Treated as a sub-category of text gaps,
  not a separate layer.
- **Stub-smell:** apply heuristics in §5.3.

Brief is correct. If the entity looks healthy, say "no gaps surfaced" and move
on — do not manufacture findings.

### Pairwise pass

For each unordered pair (n=3 → 3 pairs), ask:

> Is there an unappreciated connection between these two? If so, what would
> tracking it look like?

Most pairs will be "no, nothing obvious." That is the expected default. Say so
in one line and move on. When a real connection surfaces, name it concretely:
shared variable, shared mechanism, contradicting assumption, candidate edge
for the DAG, etc. **Do not invent connections to fill the section.**

### Stub-smell heuristics

Flag an entity as a prune candidate **only if all four hold**:

1. **Created more than 60 days ago.** Source: `dcterms:created` /
   `sci:created` in the graph if present; otherwise fall back to the
   first-commit date for the entity's source file via
   `git log --diff-filter=A --format=%aI -- <path>`; otherwise file `mtime` as
   a last resort.
2. **Zero incoming `sci:bearsOn` edges in the graph.** Source: context
   bundle's neighbors block.
3. **Not referenced by any active task or hypothesis.** Source: context
   bundle's "active references" block (subjects of kind `task` or
   `hypothesis` whose object is this entity). "Active" excludes archived /
   completed tasks.
4. **Content under approximately 500 characters, or unchanged since
   creation.** Source: file length from the context bundle; "unchanged since
   creation" means git shows only the initial commit for the file.

All four signals are pre-computed by `science wander` and embedded in the
context bundle, so the agent never has to re-derive them. Single-criterion
flagging will produce too much noise; the conjunction is deliberate. Flagging
is purely advisory in v1 — there is no automatic archival.

## 6. Walk report template

Path: `doc/meta/walks/walk-YYYY-MM-DD-HHMM.md`.

```markdown
---
date: 2026-05-09
walk_id: 2026-05-09-1430
seed: 12345
n: 3
sampled: [entity-id-1, entity-id-2, entity-id-3]
---

# Wander · 2026-05-09 14:30

## Sample
| ID | Kind | Weight | Last reviewed |
| --- | --- | --- | --- |
| ... | ... | ... | ... |

## Per-entity review

### entity-id-1 — <label>
**Gaps:** <prose; or "none surfaced">
**Stub-smell:** <yes/no + brief justification>

### entity-id-2 — <label>
...

### entity-id-3 — <label>
...

## Pairwise connections

### entity-id-1 ↔ entity-id-2
<one paragraph; or "no obvious connection">

### entity-id-1 ↔ entity-id-3
...

### entity-id-2 ↔ entity-id-3
...

## Prune candidates
- <entity-id> — <one-line rationale> [first flagged 2026-05-09]
- (or: "none")

## Spawned tasks
- (empty unless --apply was passed)
```

The frontmatter `seed` makes any walk replayable. `walk_id` lets future walks
reference older ones. The location `doc/meta/walks/` parallels the existing
`doc/meta/curation/` convention.

## 7. `--apply` mode

The walk report itself is **always** written and edited in place — that is the
output of the command, not a side effect. The `--apply` distinction governs
side effects on **everything else** in the project: source prose, code,
graph/DAG, task list, archives.

Without `--apply`:

- Walk file at `doc/meta/walks/walk-<id>.md`: **written and edited in place**
  (skeleton by `science wander`, prose by the agent loop).
- Everything else: **untouched.** No source-prose edits anywhere in `doc/`,
  no code edits, no DAG edits, no task creation, no archival.

With `--apply`, exactly one additional side effect is permitted:

- `science tasks add` — for either:
  - "investigate connection X↔Y" findings the agent judges worth tracking;
  - "review for deprecation: <stub-entity>" tasks, with a 30-day reconsider
    date in the body.

Even with `--apply`: still no source-prose edits, no DAG edits, no archival.
Tasks created get a `source: wander/<walk_id>` marker in their description so
they remain traceable back to the walk that spawned them.

## 8. Tests

Following the existing pattern under `tests/`:

- Unit test `science wander` CLI:
  - Returns expected JSON shape given a fixture graph.
  - Respects `--seed` for reproducibility (same seed → same sample).
  - Respects `--n` and `--kind` filters.
  - Errors with the documented "run `science graph build`" message when
    `graph.trig` is missing.
  - Markdown skeleton is well-formed (frontmatter parses, sample table
    renders, all required empty section headings present).
- Unit tests for context-bundle assembly:
  - Given a fixture dataset, the bundle for a sampled entity contains the
    expected URI, raw weight components, neighbors (incoming + outgoing
    `sci:bearsOn` plus capped other-predicate counts), created date (with
    fallback chain: graph → git first-commit → mtime), and active
    task/hypothesis references.
  - When no source path resolves, filesystem fields (path, mtime, length)
    are omitted and the bundle is still well-formed.
  - All four stub-smell signals are present in the bundle as discrete
    boolean/numeric fields, so neither the agent nor a downstream tool has
    to recompute them.
- Integration test:
  - End-to-end `science wander --format markdown --seed 42 --out <tmp>`
    against the fixture project produces a skeleton whose frontmatter
    `sampled` list matches the sample drawn for that seed.
- No agent-loop tests; that path is exercised by interactive use of the
  slash command.

## 9. Future work (explicitly deferred)

- **Broaden the candidate set beyond epistemic entities.** v1 inherits the
  freshness-state filter from `compute_attention_candidates`. Extending to
  datasets, code modules, raw notes, and other non-epistemic entities
  requires defining default weights for them (they have no freshness state,
  no support/dispute counts, etc.). Worth doing only after v1 reveals which
  entity classes are actually under-attended.
- **Pruning enforcement.** Once enough stub-flag tasks accumulate, design a
  `science prune` command that finds tasks flagged 30+ days ago whose targets
  remain unused, and offers archival.
- **Sampling profiles.** A `--profile` flag selecting between weight policies
  (e.g., "stale-bias", "cold-storage", "high-traffic"). Wait for usage data
  before designing this — picking policies in the abstract is premature.
- **Nested sampling.** Two-stage: sample type mix first, then within types.
  Same rationale: wait for evidence that flat sampling is the bottleneck.
- **Code wander.** A separate command that samples source files / functions
  rather than graph entities.
- **Walk index.** Auto-maintained `doc/meta/walks/INDEX.md` summarizing recent
  walks. Add when you have 10+ walks and feel the lack.
