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

All generated synthesis files use `type: synthesis` and distinguish their role
with `report_kind`. The canonical section shape lives in
`templates/synthesis.md`.

## Question Resolution And Aspect Filtering

Big-picture synthesis starts by resolving questions to hypotheses. It excludes
pure software-development questions from research synthesis when the project has
research aspects available. The same filtered question set drives both
hypothesis bundles and topic-coverage gap computation, so a software-only
question does not create research demand.

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

External literature IDs canonicalize to `paper:<bibkey>`. During the transition
window, `article:<bibkey>` still counts as the same external paper for coverage
deduplication. The canonical bibkey and legacy-alias policy are documented in
[Refs Check](../conventions/refs-check.md).

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
