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
  entity a non-zero chance of being visited.
- **Re-assessment:** revisit older ideas in the context of current
  understanding.

### Non-goals (v1)

- Nested or profile-based sampling policies.
- Automatic 30-day pruning enforcement (only flagging is in scope).
- Walking source code or files outside `knowledge/graph.trig`.
- Learning sampling weights from past walks.

## 2. Scope and constraints

Sampling is bounded by what is materialized into `knowledge/graph.trig`. If a
project has not built its graph, `science wander` errors with a hint to run
`science create-graph` first. Code-level review only happens when an entity
explicitly references implementation (e.g., a hypothesis pointing at a
pipeline, a dataset with a loader); the walk does not go hunting through `src/`
for entities that are not grounded there.

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

1. Resolve graph path; error with actionable message if missing.
2. Call `query_attention_sample(...)` from `science_tool.graph.attention`
   directly — same package, no subprocess.
3. For each sampled entity, assemble a small **context bundle**:
   - id, kind, label, weight components (freshness, days since last review,
     support/dispute counts);
   - file path on disk if resolvable from the entity provider;
   - last-modified timestamp of that file;
   - direct neighbors in the graph (incoming + outgoing `bears_on` and a small
     fixed cap on other relation types — 10 each direction).
4. In `markdown` mode, write a **report skeleton** at `--out`: the report
   template from §6 with frontmatter and the **Sample** and **Per-entity
   review** scaffolding pre-filled with sampled rows and context bundles. The
   review prose, pairwise, prune, and spawned-tasks sections are present as
   empty headings, ready for the agent to fill in. In `json` mode, emit the
   raw context bundles to stdout for programmatic consumers.

The slash command (next section) runs `science wander` to produce the
skeleton, then fills it in *in place* — there is exactly one walk file per
run.

## 4. Slash command

`commands/wander.md` is the agent loop. It:

1. Generates a walk path `doc/meta/walks/walk-YYYY-MM-DD-HHMM.md` and runs
   `science wander --format markdown --out <walk-path>` to materialize the
   report skeleton.
2. Reads the skeleton, including each entity's context bundle.
3. Performs the review loop (§5).
4. Edits the same file in place, filling in the empty sections (per-entity
   gaps, pairwise connections, prune candidates, spawned tasks).
5. If `--apply` is in `$ARGUMENTS`, may invoke `science tasks add` per §7
   and append the resulting task IDs under "Spawned tasks".

The slash command parses `$ARGUMENTS` for the same flag surface as the CLI,
plus `--apply`.

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

1. Created more than 60 days ago.
2. Zero incoming `bears_on` edges in the graph.
3. Not referenced by any active task or hypothesis.
4. Content under approximately 500 characters, **or** unchanged since
   creation.

Single-criterion flagging will produce too much noise; the conjunction is
deliberate. Flagging is purely advisory in v1 — there is no automatic
archival.

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

Without `--apply`: pure prose report. No file edits, no task creation.

With `--apply`, the agent may make exactly one kind of side effect:

- `science tasks add` — for either:
  - "investigate connection X↔Y" findings the agent judges worth tracking;
  - "review for deprecation: <stub-entity>" tasks, with a 30-day reconsider
    date in the body.

No prose edits. No DAG edits. No archival.

Tasks created get a `source: wander/<walk_id>` marker in their description so
they remain traceable back to the walk that spawned them.

## 8. Tests

Following the existing pattern under `tests/`:

- Unit test `science wander` CLI:
  - Returns expected JSON shape given a fixture graph.
  - Respects `--seed` for reproducibility (same seed → same sample).
  - Respects `--n` and `--kind` filters.
  - Errors with an actionable message when `graph.trig` is missing.
  - Markdown output is well-formed (frontmatter parses, table renders).
- Integration test:
  - End-to-end `science wander --format markdown --seed 42` against a small
    fixture project produces a prep doc whose frontmatter matches the
    sampled entities.
- No agent-loop tests; that path is exercised by interactive use of the
  slash command.

## 9. Future work (explicitly deferred)

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
