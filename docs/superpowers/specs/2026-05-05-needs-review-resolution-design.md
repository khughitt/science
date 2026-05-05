# Needs-Review Resolution And Conclusion-Amendment Design

## Status

Approved design for `meta/tasks/active.md` task `t017`.

## Problem

The epistemic dependency graph can now mark epistemic entities as
`needs-review` when upstream evidence changes. That freshness signal answers
"what deserves a fresh look?" but it deliberately does not answer "did the
standing actually change?"

The missing workflow is what happens after a reviewer inspects the flagged
entity. If the new upstream evidence changes the standing of a prior
interpretation, finding, discussion, or report, Science needs an append-only way
to record the new conclusion, connect it to the prior conclusion, and then mark
the reviewed epistemic target as reconsidered.

## Goals

- Keep freshness as a review prompt, not a conclusion mutator.
- Represent conclusion change with explicit graph semantics.
- Preserve old conclusions for provenance while making replacement visible.
- Give commands and templates a clear decision tree for `needs-review`
  resolution.
- Keep the first implementation small enough to land before adding higher-level
  review automation.

## Non-Goals

- No qualitative standing ladder in this task. That remains tracked separately
  by `t016`.
- No cross-project amendment semantics in this task. Cross-project freshness is
  tracked by `t015`.
- No new transaction-style review command yet.
- No automatic mutation of prior conclusions from freshness propagation.
- No compatibility layer for every historical amendment field shape in
  downstream projects.

## Decisions

### 1. Conclusion Change Is A Graph Fact

Add two semantic relations for conclusion-like epistemic entities:

- `sci:amends`: a newer conclusion revises, narrows, qualifies, or extends an
  older conclusion without replacing it.
- `sci:supersedes`: a newer conclusion replaces an older conclusion as the
  current canonical reading.

The durable semantic fact is:

```text
new conclusion X amends/supersedes old conclusion Y
```

This is distinct from lifecycle metadata on either file. The graph relation is
the source of truth for reconstructing conclusion chains.

### 2. `status: superseded` Is A Lifecycle Hint

When a new conclusion fully replaces an older one, the author should mark the
older conclusion:

```yaml
status: superseded
```

This status helps summaries, recommendations, and readers avoid treating the old
file as current. It is not the semantic source of truth. A conclusion is known
to supersede another conclusion because the graph contains a `sci:supersedes`
edge.

For `sci:amends`, the older entity usually stays `active` because it still has
current value when read with the amendment.

### 3. Review State Remains Outcome-Neutral

`science-tool entity review <ref>` continues to do one thing:

```text
review_state.last_reviewed = today
```

and optionally records `review_state.last_review_note`.

Review state means "this epistemic target was reconsidered as of this date." It
does not mean "standing unchanged", "standing amended", or "standing
superseded." Those outcomes live in the authored conclusion and its graph
relations.

### 4. Valid Endpoints Are Conclusion-Like

`amends` and conclusion-level `supersedes` should be valid between
conclusion-like epistemic entities:

- `interpretation`
- `finding`
- `discussion`
- `report`
- `validation-report`
- `story`

The conclusion relation design is symmetric across these kinds: any
conclusion-like kind may amend or supersede any other conclusion-like kind. For
example, `report:new sci:amends interpretation:old` and
`interpretation:new sci:amends report:old` are both valid.

Do not allow arbitrary operational entities as endpoints for these conclusion
relations. `workflow-run`, `dataset`, `data-package`, and `task` already have
separate operational lifecycle semantics.

The existing `workflow-run -> workflow-run` `supersedes` relation remains valid
for operational run replacement. The first implementation should preserve that
behavior while expanding `supersedes` to also support conclusion replacement.

### 5. Relation Kinds Need Explicit Endpoint Pairs

`RelationKind` currently has flat `source_kinds` and `target_kinds` lists. That
shape implies a Cartesian product, which cannot express:

```text
workflow-run -> workflow-run
OR
conclusion-kind -> conclusion-kind
```

without also allowing invalid pairs such as:

```text
interpretation -> workflow-run
workflow-run -> interpretation
```

For this task, extend the relation schema with an optional explicit endpoint
pair list, for example:

```python
class RelationEndpointPair(BaseModel):
    source_kind: str
    target_kind: str


class RelationKind(BaseModel):
    name: str
    predicate: str
    source_kinds: list[str]
    target_kinds: list[str]
    allowed_kind_pairs: list[RelationEndpointPair] = Field(default_factory=list)
    layer: str
    description: str = ""
```

Validation semantics:

- When `allowed_kind_pairs` is non-empty, it is the authoritative endpoint
  allow-list.
- When `allowed_kind_pairs` is empty, keep the current Cartesian
  `source_kinds` / `target_kinds` behavior.
- Empty `source_kinds` or `target_kinds` keep their current "unrestricted"
  meaning for relations that intentionally allow broad endpoints.

Use `allowed_kind_pairs` for:

- `amends`: full conclusion-kind Cartesian product.
- `supersedes`: full conclusion-kind Cartesian product plus exactly
  `workflow-run -> workflow-run`.

Do not model this as two `RelationKind` entries sharing `sci:supersedes`.
`build_relation_registry` keys by relation name, and split names would make
predicate-level consumers harder to reason about.

### 6. Authored Relation Blocks Are The Initial Write Surface

The first implementation should use the existing authored relation machinery.
For a new conclusion that amends an older one:

```yaml
relations:
  - predicate: sci:amends
    target: interpretation:old
```

For a new conclusion that replaces an older one:

```yaml
relations:
  - predicate: sci:supersedes
    target: interpretation:old
```

Structured `knowledge/sources/<local-profile>/relations.yaml` can express the
same facts when a project keeps graph relations outside entity frontmatter.

No new command is required for the first implementation. A future task can add a
transaction command once the semantics have proven stable.

## Review Workflow

The normal `needs-review` resolution flow is:

1. Run `science-tool entity needs-review`, or encounter a sampled
   `needs-review` entity in `science:status` or `science:next-steps`.
2. Inspect the flagged entity, its `sci:triggeredBy` upstream sources, and
   nearby conclusion entities.
3. If the new evidence does not change standing, run:

   ```bash
   science-tool entity review <target-ref> --note "Reviewed against <source>; no standing change."
   ```

4. If the new evidence changes standing, author a new `interpretation` or
   `finding`.
5. Add `sci:amends` or `sci:supersedes` from the new conclusion to the prior
   conclusion.
6. If using `sci:supersedes`, mark the old conclusion `status: superseded` as
   an explicit authoring action.
7. Run this on the flagged entity, not on the newly authored conclusion:

   ```bash
   science-tool entity review <target-ref> --note "Reconsidered; see interpretation:new."
   ```

8. Rebuild the graph so freshness clears if no upstream source remains newer
   than the review date.

This keeps the human judgment step explicit. Freshness says "look here"; the
new conclusion says what changed; review state says the target was reconsidered.

## Data Flow

Materialization should emit `sci:amends` and `sci:supersedes` triples from
authored relation blocks and structured relation files.

Freshness derivation continues to read:

- upstream `sci:bearsOn` sources
- upstream `created` / `updated` dates
- target `review_state.last_reviewed`
- optional target review horizon

Freshness does not inspect amendment or supersession edges to infer belief
state. Amendment edges are for provenance, chain reconstruction, summary
selection, and future standing derivation.

## Command And Template Updates

Update `commands/interpret-results.md` so update mode distinguishes:

- unchanged review: record `entity review` with a note
- amendment: create a new conclusion with `sci:amends`
- replacement: create a new conclusion with `sci:supersedes`, then mark the old
  conclusion `status: superseded`

Update `templates/interpretation.md` and `templates/interpretation-dev.md` to
include relation guidance near `prior_interpretations`.

`prior_interpretations` is not a semantic source of truth after this task. It
may remain as a narrative/display breadcrumb, but first-class amendment and
supersession semantics must come from `relations`. Update
`commands/big-picture.md` so provenance coverage and arc reconstruction consult
materialized `sci:amends` / `sci:supersedes` chains instead of treating
`prior_interpretations` as the machine-readable chain. Do not materialize
`prior_interpretations` into `sci:amends`; the field cannot distinguish
amendment from replacement.

Update `commands/next-steps.md` and `commands/status.md` so `needs-review`
entities are framed as candidates for this resolution workflow, not as evidence
that prior conclusions are wrong.

## Implementation Boundary

The first implementation should:

- Add `amends` to the core relation profile.
- Add `allowed_kind_pairs` to `RelationKind` and use it to broaden
  `supersedes` without allowing invalid cross-domain pairs.
- Introduce authored-relation endpoint validation during graph materialization.
  This is new validator infrastructure, not a small tweak to an existing
  endpoint checker.
- Update interpretation templates and relevant command prose, including the
  `big-picture` chain/coverage reader.
- Leave `entity review` behavior unchanged.
- Leave freshness behavior unchanged except for any tests proving it ignores
  amendment relations.

Do not add a new review transaction command in this task.

## Validation And Error Handling

Invalid amendment or supersession endpoints should fail early during
materialization with a message naming the subject, predicate, object, and source
path.

The endpoint validator should run for declared authored relations after subject
and object refs resolve to canonical entities. For declared predicates:

1. Look up the matching `RelationKind` by predicate.
2. Resolve subject and object kinds.
3. If `allowed_kind_pairs` is non-empty, require that exact pair.
4. Otherwise apply the existing `source_kinds` / `target_kinds` constraints.
5. Include the source relation's `source_path` in failures.

This generalizes the current `bears_on` materialization guard instead of adding
another predicate-specific branch.

Valid examples:

```text
interpretation:new sci:amends interpretation:old
finding:new sci:supersedes finding:old
report:new sci:amends interpretation:old
workflow-run:new sci:supersedes workflow-run:old
```

Invalid examples:

```text
interpretation:new sci:amends task:t017
dataset:new sci:supersedes interpretation:old
workflow-run:new sci:amends workflow-run:old
```

The `workflow-run -> workflow-run` example remains valid only for
`sci:supersedes`, not for `sci:amends`.

Self-reference is invalid: an entity must not amend or supersede itself. Cycles
in the amendment/supersession subgraph are invalid and should fail
materialization with the cycle path. Multiple newer conclusions may supersede
the same older conclusion; consumers should choose the current canonical item by
newest `updated` date, falling back to `created`, and report an ambiguity when
dates tie.

`sci:supersedes` is distinct from the existing `sci:supersedesClaim` predicate
used by falsification records. This task does not change
`sci:supersedesClaim`.

## Superseded Status Consumers

The first implementation should update only the surfaces touched by this
workflow:

- `commands/interpret-results.md`: tells authors when to set
  `status: superseded`.
- `commands/status.md` and `commands/next-steps.md`: describe superseded
  conclusions as non-current when they appear near a `needs-review` workflow.
- `commands/big-picture.md`: reconstructs current arcs from
  `sci:amends` / `sci:supersedes` and should prefer non-superseded current
  conclusions when a replacement chain exists.

Weighted attention sampling does not change in this task. If other summaries
need to filter or demote superseded conclusions, that should be a follow-up
consumer task rather than hidden behavior in the relation implementation.

## Test Plan

- `RelationKind.allowed_kind_pairs` validates and preserves existing
  Cartesian behavior when unset.
- Materialization emits `sci:amends` for a valid conclusion relation.
- Materialization emits `sci:supersedes` for a valid conclusion replacement.
- Materialization still accepts `workflow-run -> workflow-run`
  `sci:supersedes`.
- Materialization rejects invalid `amends` endpoints with a clear error.
- Materialization rejects invalid conclusion `supersedes` endpoints with a
  clear error while preserving the operational workflow-run case.
- `entity review` tests continue to prove only `review_state` changes.
- Freshness tests prove `amends` / `supersedes` edges do not directly clear or
  create `needs-review`.
- Cycle/self-reference tests prove invalid conclusion chains fail during
  materialization.
- Big-picture tests prove chain/coverage logic reads
  `sci:amends` / `sci:supersedes` rather than `prior_interpretations`.
- Command/template tests or snapshot checks confirm the new decision-tree prose
  is present.

## Future Work

- A transaction command could later combine "author relation", "mark old status",
  and "record review" once the workflow is proven.
- Qualitative standing derivation can eventually use amendment and supersession
  chains, but that belongs to `t016`.
- Cross-project conclusion amendment can be designed after cross-project entity
  resolution and freshness are settled.
