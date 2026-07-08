# Big-Picture Synthesis

`/science:big-picture` creates a research synthesis from authored project
sources. It is a derived report surface: edit questions, hypotheses,
interpretations, tasks, topics, papers, evidence, and graph sources first, then
regenerate the synthesis.

The command produces three synthesis roles:

| Role | Purpose |
|---|---|
| `hypothesis-synthesis` | One file per hypothesis, focused on state, arc, research fronts, candidate frames, and local gaps. |
| `emergent-threads` | Cross-cutting patterns and orphan research questions that are not yet attached to a hypothesis. |
| `synthesis-rollup` | Project-level rollup across the per-hypothesis files and emergent threads. |
| `paper-batch-synthesis` | Literature-batch synthesis over a set of paper summaries, used as authored source material for later hypothesis and project rollups. |

All generated synthesis files use `kind: synthesis` and distinguish their role
with `report_kind`. The canonical section shape lives in
`templates/synthesis.md`.

## Artifact Layout

Big-picture synthesis artifacts are source-authored synthesis entities in the
layout v3 owner tree:

```text
entities/synthesis/
├── <nnnn>-<hypothesis-slug>.md      # report_kind: hypothesis-synthesis
├── <nnnn>-emergent-threads.md       # report_kind: emergent-threads
└── <nnnn>-project-synthesis.md      # report_kind: synthesis-rollup
```

The exact filenames follow the `synthesis` entity path policy, but the roles are
identified by frontmatter, not by filename. Canonical artifacts belong under
`entities/synthesis/`.

All canonical synthesis artifacts are regenerated from current project sources.
Do not treat generated synthesis prose as the authority for questions,
hypotheses, evidence, tasks, topics, or graph claims. Fix those source records
first, regenerate the synthesis, and then commit the resulting entity files.

## Frontmatter Contract

All synthesis roles share these fields:

```yaml
id: synthesis:<local-part>
kind: synthesis
title: "<human-readable title>"
status: active
report_kind: hypothesis-synthesis | synthesis-rollup | emergent-threads | paper-batch-synthesis
generated_at: "<ISO-8601 timestamp>"
source_commit: "<project commit SHA>"
```

Each role adds role-specific fields:

| `report_kind` | Required fields |
|---|---|
| `hypothesis-synthesis` | `hypothesis`, `provenance_coverage` |
| `synthesis-rollup` | `synthesized_from`, `emergent_threads_sha`, `orphan_question_count` |
| `emergent-threads` | `orphan_question_count`, `orphan_interpretation_count`, `orphan_ids` |

`synthesized_from` uses block-list YAML so the rollup can detect stale
per-hypothesis inputs:

```yaml
synthesized_from:
  - hypothesis: hypothesis:h1-example
    file: entities/synthesis/0001-h1-example.md
    sha: "<git-hash-object value>"
```

When only one hypothesis synthesis is regenerated, the rollup may still point at
an older file hash. The next full big-picture run should warn about the stale
rollup and then refresh it.

## Generation Contract

`/science:big-picture` is an orchestrated generation workflow rather than a
single Python renderer. The Python CLI provides inspectable support surfaces:

```bash
science big-picture resolve-questions --project-root .
science big-picture knowledge-gaps --project-root .
science big-picture cluster-digests --project-root .
science big-picture validate --project-root .
```

`cluster-digests` reports live synthesis entities with `report_kind:
cluster-digest`. These digests are the big-picture substitute for archived
member families: the digest stays live and may bridge questions, hypotheses,
interpretations, tasks, and other synthesis records through normal `related:`
frontmatter. With `--deep`, the command resolves each member through the active
archive index and returns index-only member summaries. It does not rehydrate
archived Markdown. A scaffolded-but-unapplied digest has members with
`archived: false`, and only applied archive rows populate the `member_to_digest`
map used for member-id, alias, and `same_as` redirection.

The generation workflow precomputes project summaries, question resolution,
attention samples, uncertainty, graph neighborhoods, and topic gaps, then writes
the synthesis entity files. A full run writes all hypothesis syntheses, emergent
threads, and the rollup. A `--hypothesis <id>` run updates only that hypothesis
synthesis and intentionally leaves the rollup stale until the next full run.

`--since <date>` is scoped output, not the canonical synthesis. It must be
written to an explicit output path and include `since:` in frontmatter so a
partial-window narrative cannot be mistaken for the authoritative project
rollup.

## Grounding And Degraded Modes

Big-picture synthesis must preserve provenance rather than fill gaps with
plausible narrative.

For claim and evidence structure, use the highest-priority source with content:

1. Graph claim/proposition surfaces when present.
2. Relational propositions compiled from patch workbenches; DAG DOT files are
   view topology only.
3. Authored frontmatter relations among hypotheses, questions,
   interpretations, tasks, and digests.
4. Summary surfaces such as uncertainty, gaps, attention samples, and dashboard
   summaries as complementary context.

The synthesis should not merge conflicting structured claim sources
field-by-field. If graph claim surfaces exist for a hypothesis, treat them as
the claim-structure authority for that hypothesis. Summary surfaces remain
context, not claim identity.

`provenance_coverage` communicates how much arc reconstruction is available:

| Value | Meaning |
|---|---|
| `high` | Structured claim evidence exists, or enough interpretation conclusion chains are materialized to support a narrative arc. |
| `partial` | Some conclusion-chain provenance exists, but structured claim evidence is absent. |
| `thin` | The hypothesis has sparse structured provenance. The Arc section must stay short and explicitly name the limitation. |

Generated factual claims should cite concrete project artifacts such as
`hypothesis:*`, `question:*`, `interpretation:*`, `task:*`, `topic:*`, DAG edge
IDs, or graph claim IDs. When `provenance_coverage: thin`, omit unsupported
connective tissue instead of inventing it.

Run validation after generation:

```bash
science big-picture validate --project-root .
```

The validator flags references in generated synthesis text that do not resolve
to project entities or aggregated task IDs. It also checks thin-coverage Arc
length and rollup orphan-question counts.

## Question Resolution And Aspect Filtering

Big-picture synthesis starts by resolving questions to hypotheses. It excludes
pure software-development questions from research synthesis when the project has
research aspects available. The same filtered question set drives both
hypothesis bundles and topic-coverage gap computation, so a software-only
question does not create research demand.

Question resolution is many-to-many. Associations are collected in this order:

1. Direct `hypothesis:` fields on the question.
2. Hypothesis `related:` fields that list the question.
3. Question `related:` fields that list the hypothesis.
4. Interpretations or cluster digests whose `related:` fields bridge a question
   and a hypothesis.

The resolver reports all matching hypotheses, a `primary_hypothesis`, and the
question's resolved aspects. Questions with no research hypothesis match become
emergent-thread orphans; pure software-only questions are excluded from research
orphan counts.

Use the CLI surfaces to inspect the inputs without regenerating a full report:

```bash
science big-picture resolve-questions --project-root .
science big-picture validate --project-root .
```

## Knowledge Gaps

Knowledge gaps are a legacy topic-coverage signal. They answer a narrow
question: which authored `topic:` entities are referenced by more research
questions than the project has paper coverage for?

They do not create or recommend new topic entities, and they are not a general
semantic-gap model. Use them only for existing topic docs under
`entities/topics/`.

For each topic:

- **Demand** is the number of aspect-filtered questions whose `related:` field
  directly lists the topic ID.
- **Coverage** is the deduplicated union of external papers listed in the
  topic's `related:` field, papers whose `related:` field lists the topic, and
  `cite:<key>` entries in the topic's `source_refs:`.
- **Gap score** is `max(0, demand - coverage)`.

Topics with zero demand are omitted. Topics where coverage is greater than or
equal to demand are omitted. Output is ordered by gap score descending, then
topic ID ascending.

External literature IDs use `paper:<bibkey>`. Coverage deduplication compares
the canonical paper bibkey exactly; `article:<bibkey>` is not a literature ref
prefix.

Inspect the computed list directly with:

```bash
science big-picture knowledge-gaps --project-root .
science big-picture knowledge-gaps --project-root . --limit 10
```

`/science:big-picture` renders knowledge gaps in two places:

- Per-hypothesis files receive a Knowledge Gaps item inside Research Fronts
  when that hypothesis's question set drives topic demand.
- The project rollup receives a `## Knowledge Gaps` section with the top topic
  gaps, or a one-line empty state when none are detected.
