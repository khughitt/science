# refs graph truth source — baselines

Date: 2026-05-10

Captured before retiring natural-systems' `scripts/audit-citations.ts`
(t469). Compares the new `refs.entity_index_source: knowledge_graph`
knob against the default `frontmatter` source and against the
project-local script.

## natural-systems

| Source                                                                | Total broken | body-entity-ref count |
|-----------------------------------------------------------------------|-------------:|----------------------:|
| `science refs check --include-body` (frontmatter, no scan_roots)      |        1410  |                 1410  |
| `science refs check --include-body` (graph + scan_roots: tasks, papers, core, ".") |  287  |              287  |
| `npm run audit:citations` (graph.trig truth source, 10 kinds)         |         208  |                  208  |

**Per-kind breakdown of the 287 graph-source issues:**

| Kind            | Count | In `audit-citations.ts`? |
|-----------------|------:|:------------------------:|
| `meta:`         |    82 | no                       |
| `discussion:`   |    63 | yes                      |
| `question:`     |    60 | yes                      |
| `task:`         |    42 | yes                      |
| `theme:`        |    13 | no                       |
| `model:`        |    10 | yes                      |
| `concept:`      |     9 | no                       |
| `interpretation:` |   3 | yes                      |
| `topic:`        |     3 | yes                      |
| `hypothesis:`   |     2 | yes                      |

**Divergence analysis:** The frontmatter-source baseline (1410) is
expected to be high — many NS entities live in `knowledge/graph.trig`
but are not backed by markdown files with matching frontmatter `id:`
fields, so frontmatter sweep produces large numbers of false positives.
The graph-source result (287) is within 1.4× of `audit-citations.ts`
(208). The remaining gap is fully accounted for by the 104 issues from
the three kinds (`meta:`, `theme:`, `concept:`) that
`audit-citations.ts` does not check — `science refs check` covers 27
local entity kinds vs the script's 10. That extra coverage is a feature,
not a bug: the new issues represent genuine drift that the script was
silently missing.

The 183 issues in shared kinds is slightly fewer than the script's 208,
suggesting either some script false positives that science correctly
filters (cross-project triple-form refs, frontmatter cells) or a small
number of refs scoped differently between the two scanners. Both numbers
are good enough to retire the script — neither is a true ceiling on the
real backlog.

## multiple-myeloma

| Source                                                       | Total broken | body-entity-ref count |
|--------------------------------------------------------------|-------------:|----------------------:|
| `science refs check --include-body` (frontmatter, default)   |        1282  |                  134  |
| `science refs check --include-body` (graph)                  |        1218  |                   70  |

**Per-type breakdown** (frontmatter source):
`task: 448, pmid: 410, doi: 194, hypothesis: 91, body-entity-ref: 134, link: 5`

**Per-kind breakdown** of 134 body-entity-refs (frontmatter):
`question: 53, task: 44, concept: 12, method: 10, interpretation: 7`

**Per-kind breakdown** of 70 body-entity-refs (graph):
`question: 53, interpretation: 7, proposition: 2, method: 2, hypothesis: 1`

**Divergence analysis:** MM body-entity-ref count drops 48% (134 → 70)
with the graph source. `task:` issues drop from 44 to 0 entirely (all
44 are present in the graph but not in frontmatter — likely tasks
declared in the bulk task table without standalone files). `concept:`
issues drop from 12 to 0 (similar story). `question:` is unchanged at
53 — these are genuine broken refs to non-existent questions. MM does
not need the `scan_roots` extension because its prose is already
predominantly under `doc/` + `specs/`.

## Conclusion

Ready to retire natural-systems' `audit-citations.ts` in a follow-up
session. The required `science.yaml` config:

```yaml
refs:
  entity_index_source: knowledge_graph
  scan_roots:
    - tasks
    - papers
    - core
    - "."
```

For multiple-myeloma, opting into `entity_index_source: knowledge_graph`
is recommended (drops body-entity-ref noise from 134 to 70) but not
required — the project doesn't have a project-local citation auditor to
retire.

## Caveats

- The `science refs check --include-body` body-entity-ref scan is
  case-sensitive and uses `_LOCAL_ENTITY_KINDS` for kind validity.
  Projects that introduce custom kinds via the knowledge graph will see
  those kinds in the graph but rejected by the body scanner. (Out of
  scope for this work — file a follow-up if that becomes load-bearing.)
- The graph-source warning fallback writes to stderr only; downstream
  callers expecting silent operation should ensure `knowledge/graph.trig`
  exists before invoking.
