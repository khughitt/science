# Inquiry Edge Posterior Annotations

**Status:** proposed
**Created:** 2026-04-17
**Source:** feedback fb-2026-04-13-006 (mm30)

## Problem

Inquiry-DAG edges in `mm30` carry their most load-bearing evidence — Bayesian
posteriors (β, HDI, P(sign)) — only in prose. As a result:

- DAG renderers cannot color or weight edges by posterior magnitude/sign.
- A change in a refit's β is not a structured diff.
- `science graph` has no way to surface "edges with no posterior fit yet"
  as a first-class gap.

The user is already maintaining this data project-locally in
`doc/figures/dags/*.edges.yaml` (~85 edges, ~15 with fitted posteriors). If
science adopted it as a first-class field, it would compose with
`export-pgmpy` / `export-chirho` and unlock several diagnostics for free.

## Proposed schema

Add an optional `posterior` block to inquiry-edge annotations:

```yaml
posterior:
  beta: -0.273              # point estimate of the effect
  hdi_low: -0.468           # 95% HDI lower bound (or other-credibility lower)
  hdi_high: -0.092          # 95% HDI upper bound
  prob_sign: 0.994          # P(sign(beta) matches the modeled sign)
  fit_task: t140            # task ID of the fit; must resolve via refs check
  datasets: 5               # number of datasets included in the fit
  adjusted_for: [proliferation]   # covariates / adjustment set
  hdi_credibility: 0.95     # optional, default 0.95 if omitted
```

All fields are optional inside the block; the only invariant is "if the block
is present, `beta` and a (`hdi_low`, `hdi_high`) pair must be present."

## Storage

The annotation lives where inquiry-edge metadata already lives — adjacent to
the inquiry's named graph in `knowledge/graph.trig`. Express each posterior
field as a triple keyed off a `sci:Posterior` reified node so multiple refits
over time can coexist:

```
<inquiry/X/edge/E> sci:posterior <inquiry/X/edge/E/posterior/2026-04-13-t140> .
<.../posterior/2026-04-13-t140> a sci:Posterior ;
    sci:beta -0.273 ;
    sci:hdiLow -0.468 ;
    sci:hdiHigh -0.092 ;
    sci:probSign 0.994 ;
    sci:fitTask <task/t140> ;
    sci:datasetsCount 5 ;
    sci:adjustedFor "proliferation" .
```

Reified nodes give us provenance (which task fitted it, when) and let later
refits append rather than overwrite. The most-recent posterior is the canonical
one for visualization; the history is queryable.

## Surface

Three new query paths, each behind a flag-gated extension to existing output
schemas (no breaking changes):

1. **`science inquiry show <slug> --posteriors`**
   - Adds a `posteriors:` block to each edge in the JSON output.
   - Marks edges with no posterior as `posterior: null`.

2. **`science inquiry uncertainty --type=posterior`**
   - New subtype of an existing uncertainty command.
   - Lists edges with wide HDIs (e.g. `width(hdi) > threshold`) and edges
     whose HDI crosses zero (`prob_sign < 0.95`).
   - Default thresholds: HDI width > 0.4, prob_sign < 0.95.
   - `--threshold-hdi-width`, `--threshold-prob-sign` flags for tuning.

3. **`science graph neighborhood-summary`** (existing command)
   - When an edge has a posterior block, include `beta`, `hdi_low`, `hdi_high`,
     `prob_sign`, `fit_task` columns. Empty for edges without posteriors.

## Visualization integration

Inquiry-DAG renderers can consume the new fields directly:

- **edge color** ← `sign(beta)` (positive vs. negative)
- **edge thickness** ← `|beta|` clipped to a sensible range
- **edge style** ← `dashed` when `prob_sign < 0.95` (low-confidence sign)
- **edge label** ← `β = -0.27 [95% HDI: -0.47, -0.09]`

This is opt-in per renderer; the data being structured is the prerequisite.

## Cross-cutting concerns

- `refs validate` should treat `fit_task` as a task-ID reference and confirm
  it resolves (covered by the existing task-ID check after fb-2026-04-13-007).
- `science graph` must not silently drop posterior nodes during the
  layered-claim migration — extend the migration audit to count
  `sci:Posterior` nodes pre/post.
- `export-pgmpy` and `export-chirho` should emit the posterior as the prior /
  initial parameter when present, not re-fit from scratch.

## Implementation plan

Ship in two PRs:

1. **PR 1: schema + storage + read.**
   - Define `sci:Posterior` and the seven fields in `SCHEMA_PREDICATES`.
   - Add `add_posterior_to_edge(...)` in `science/src/science_tool/graph/store.py`.
   - Add CLI: `science inquiry add-posterior <inquiry/edge> --beta ... ...`.
   - Tests: write/read round-trip, multiple posteriors per edge.

2. **PR 2: surface + queries.**
   - Extend `inquiry show --posteriors`, `inquiry uncertainty --type=posterior`,
     `neighborhood-summary` columns.
   - Document renderer integration points (no renderer code in this PR).

Skip until at least one consumer needs it. mm30 is the obvious candidate; if
mm30 migrates its `doc/figures/dags/*.edges.yaml` file into the graph, that
demand surfaces naturally.

## Out of scope

- Frequentist analogs (CI vs. HDI) — the schema is Bayesian-shaped on purpose;
  if a project needs frequentist edges, model them as a separate predicate
  rather than overloading `sci:Posterior`.
- Per-fit dataset *details* (which sample IDs, which preprocessing) — those
  belong to the `fit_task`'s data package, linked through `fit_task`.
- Renderer code — graph viz lives outside science's CLI surface.

## Non-goals

- Replacing prose explanations of posteriors. The structured fields add
  machine-readability; the "what does this β mean for our hypothesis" reading
  still belongs in interpretation documents.
- Forcing every edge to have a posterior. The point of structuring "edges
  without posteriors" is to surface them as gaps, not to demand they be filled.
