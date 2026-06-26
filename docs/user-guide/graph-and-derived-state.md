# Graph And Derived State

Science builds graph state from authored project sources.

```bash
science graph build
science graph dashboard-summary
science belief snapshot
```

## Graph Build

`science graph build` materializes project sources into graph files under
`knowledge/`. The graph is a derived view over source-authored entities,
bibliography records, structured sources, and project configuration.

Do not edit `knowledge/graph.trig` as the durable fix. Correct the source and
rebuild.

For local cleanup in a project that declares peers, use:

```bash
science graph build --local-only
```

This refreshes `knowledge/graph.trig` and leaves `knowledge/composite.trig` untouched.
Use the default `science graph build` when you intentionally want to refresh the
peer-composed graph.

## Dashboard Summaries

Dashboard summaries are compact readings of the current graph: unresolved
references, evidence status, graph hygiene, and project orientation. They help
agents and humans decide where to work next.

## Belief Snapshots

`science belief snapshot` appends reproducible belief-state rollups to
`knowledge/belief-snapshots.jsonl`. Use snapshots at review milestones when you
want to preserve the state of support, dispute, fragility, and contestation.

## Prose-Derived Reports

When a project uses prose epistemics, decomposition, grounding, and prose health
artifacts are also derived state. They summarize how much authored prose has
been decomposed, promoted, and grounded. They do not replace the source
Markdown, propositions, or evidence lines.
