# Multi-Lens Views as a First-Class Content Dimension

> **Status:** Active design note (Science/meta). Proposes a change to the
> `science_model` entity schema, the `explore-ideas` command contract, graph
> materialization, and validation. Motivated by upstream feedback
> `fb-2026-07-04-005` (`command:explore-ideas`), filed from the
> `post-acute-infection` project's first `explore-ideas` run on 2026-07-04.

## Goal

Make the **analytical lens** through which a research idea is framed a
first-class, multi-valued property of the entity it produced — so that when two
lenses independently surface the same idea, both framings are *preserved* rather
than one being kept and the other discarded.

The concrete trigger: the 2026-07-04 `explore-ideas` pass generated two
convergent candidate pairs (trained-immunity/HSPC via the *mechanism* and
*analogy* lenses; critical-slowing-down via the *analogy* and *temporal*
lenses). The command's report contract emitted one YAML block per lens and
instructed the human to "keep only one of each convergent pair." Keeping one
throws away the complementary view, which is signal, not redundancy. The
workaround that day was to consolidate each pair manually and record the second
lens as an independent `assistant` origin. This note designs the durable
replacement.

## Framing: a lens is a view over a shared object

`~/d/natural-systems` has already worked the meaning of "lens" hard, in a
narrower (mathematical) setting, and its abstraction sharpens ours. There
(`question:0008-multi-lens-as-enriched-category`,
`synthesis:0005-enriched-categorical-lenses`):

- **A lens is a notion of "sameness"/structure imposed over a shared set of
  objects.** The objects are primary and shared; a lens is a *view* layered on
  them, not a property that fragments them.
- **The multi-lens system is the product of those views**, and the *alignment
  between structurally-distinct lenses is itself a measured, meaningful
  quantity* — convergence is signal.
- **The lens taxonomy is a first-class, versioned artifact** — `natural-systems`
  maintains a named lens vocabulary and has renamed it via an explicit
  taxonomy-redesign spec, not by editing hardcoded strings.

Our needs differ enough that we borrow the abstraction, not the machinery. Their
lenses are quantitative similarity metrics over a fixed catalog of mathematical
models (literal Lawvere / monoidal enrichment). Ours are **generative analytical
perspectives** — mechanism, methodology, population, contrarian, analogy,
temporal — applied to research ideas, hypotheses, and questions, where
"sameness" is semantic convergence rather than a metric. We take three
transferable principles and leave the category theory as an open door:

1. **Lens = view over the shared entity.** Keep the entity primary; attach
   lens-views to it. Do not split one idea into per-lens entities.
2. **Cross-lens convergence is first-class signal**, to be preserved and made
   queryable.
3. **The lens set is a registered, versioned vocabulary**, not prompt strings.

## Central model: `lens_views`

The unifying move is to stop treating convergence as a special case. `lens_views`
is the **general** representation of "which analytical perspective(s) frame this
idea, and how." A single-lens idea carries one lens-view; a convergent idea
carries two or more. The keep-one problem dissolves as a consequence of the
model rather than as a bolt-on merge feature.

Add an optional, multi-valued `lens_views` field to epistemic entities
(`question`, `hypothesis`; extensible later to `topic`/`theme`):

```yaml
lens_views:
  - lens: mechanism                     # slug from the packaged lens vocabulary
    rationale: >                        # THIS lens's distinct framing — the view we must not discard
      IL-6/STAT3 imprinting of hematopoietic progenitors as an antigen-independent
      driver of sustained monocyte hyperreactivity in PAIS.
    origin_ref: explore-ideas-mechanism # optional link to the generating origin (see below)
  - lens: analogy
    rationale: >
      PAIS as a maladaptive trained-immunity set-point propagated through
      progenitor epigenetic memory — the same phenomenon read as a learned,
      self-sustaining state rather than a signalling lesion.
    origin_ref: explore-ideas-analogy
```

Each `lens_view` record is:

| Field | Required | Meaning |
| --- | --- | --- |
| `lens` | yes | Slug from the packaged vocabulary (`science_model.lenses`). |
| `rationale` | yes | This lens's distinct framing of the idea (the preserved complementary view). |
| `origin_ref` | no | The `OriginRecord.ref` value of one of the entity's own origins — the origin that produced this view. |

Independence and date are **not** duplicated on the lens-view; they live on the
linked origin and are derived. Convergence is therefore a derived predicate:
**an entity has convergent lens-views when it has ≥2 lens-views whose linked
origins are `independent: true`.**

## Lens vocabulary (packaged, stable slugs)

The six lenses become a controlled vocabulary **shipped in tool core** as
`science_model.lenses` — a packaged artifact, not project-authored entities.
Placing it in the model keeps schema validation, report parsing, `apply`
behavior, and graph materialization all reading from one authoritative source;
project-local vocabulary entities would make validation circular (the thing
being validated would also define what is valid).

Each entry carries `slug`, `name`, `description`, and `kind:
generative-analytical`. Consumers reference lenses by **slug**.

Versioning policy, deliberately lightweight:

- **Slugs are stable identifiers.** `names` and `descriptions` may evolve freely.
- **No per-entity vocabulary version.** We do not stamp entities with the
  vocabulary revision that was current when they were written; that complexity
  only pays off if we ever need historical mixed vocabularies in one project,
  which we do not.
- **A slug change is an explicit migration**, not silent aliasing — a rename
  rewrites the affected entities in one pass (as `natural-systems` did with its
  taxonomy redesign).

## Origins linkage and the provenance invariant

`OriginRecord` (in `science_model.entities`) is **unchanged**. Its contract —
"provenance metadata only; MUST NOT affect evidential weight", `extra="forbid"` —
is preserved. `lens_views` is a *parallel content field*; a lens's rationale is
analytical content, not provenance, so it must not live on the origin.

The link between the two is tightly constrained:

- `origin_ref` on a lens-view **must be non-null and resolve to one of the
  entity's own `origins[].ref` values** — never to an arbitrary project ref.
- **Non-null** origin `ref`s within a single entity **must be unique**; if two
  origins share a non-null `ref`, `origin_ref` is ambiguous and validation fails.
  Origins with no `ref` are permitted and unconstrained here — a lens-view simply
  cannot link to them. (v1 requires unique *non-null* origin refs rather than
  inventing a disambiguation scheme; `OriginRecord.ref` remains optional.)

This keeps two clean concepts — provenance (`origins`) and framing
(`lens_views`) — joined by one unambiguous, entity-local link.

## Body rendering

Entity bodies gain a generated `## Lens Views` section for human reading.
**Frontmatter is the single source of truth**; the body section is a rendered
affordance, regenerated from frontmatter and never parsed back. There is no
bidirectional sync — a rule that avoids the class of drift bugs where two
representations of the same fact disagree.

## Graph representation

Materialization **reifies each lens-view as a node** so the lens↔origin
association survives into the graph:

- `<entity> sci:hasLensView <view>` for each lens-view.
- `<view> sci:viewedThroughLens lens:<slug>`.
- `<view> sci:fromOrigin <origin>` when the lens-view carries an `origin_ref`,
  resolved to the origin node the entity already materializes (today
  `sci:hasOrigin` → `origin/<canonical_id>/<i>`, typed `sci:Origin`, carrying
  `sci:independentOrigination` for independent origins).
- `lens:<slug>` nodes are materialized **from the packaged vocabulary**, not from
  authored project entities.

A flat `<entity> sci:viewedThroughLens lens:<slug>` edge is deliberately *not*
used: it would drop which origin backs which view, making the convergence query
below impossible. The reified view node preserves the association.

Convergence remains **derived**, not stored: entities with ≥2 lens-views whose
`sci:fromOrigin` origin carries `sci:independentOrigination`. This unlocks the
analyses the flat-string model could not express — which lenses co-fire, and
which lens is under-represented in a given project's idea set (directly useful to
the next `explore-ideas` pass, which can then bias toward the thin lenses).

## `explore-ideas` pipeline contract

The report contract changes so that `apply` never has to infer cluster semantics
from several kept blocks. The clustering is an internal Phase-3 aid; the Phase-4
report speaks in **apply units**.

- **Phase 3 (Classify)** — with full visibility, the agent may tag raw candidate
  blocks with an internal `convergence_group: <id>`. This is a classification
  aid only; it never reaches `apply` as a contract.
- **Phase 4 (Report)** emits **exactly one candidate block per apply unit.** A
  convergent cluster is emitted as a *single* block that already carries
  `lens_views: [...]` (equivalently a `members: [...]` list resolved into
  lens-views). Singletons carry one lens-view.
- **`apply`** stays one-block-to-one-entity and idempotent. It never merges
  separate kept blocks, so there are no rules to invent for mixed keep/drop
  decisions inside a group, no duplicate write-back, and no ambiguity over which
  `candidate_id` owns the created entity.

**Block-internal origin contract.** A block that carries `lens_views` **must also
carry the matching `origin_plan.origins`**, and every `lens_views[].origin_ref`
must equal one of those planned origin refs. `apply` validates this
correspondence *before* writing, then creates the entity's `origins` and
`lens_views` together atomically — a lens-view can never reference an origin the
block did not also plan, and the two-lens convergent case is expressed entirely
within a single block (two planned origins, two lens-views, each linked). This
gives `apply` a stated contract for producing `origins` and `lens_views` as one
unit.

The old "keep only one of each convergent pair" instruction is removed.

## Validation

New checks:

1. Every `lens_view.lens` is a slug in the packaged vocabulary.
2. Every `origin_ref` is non-null and resolves to one of the entity's own
   `origins[].ref`; non-null origin refs within an entity are unique (origins
   without a `ref` are allowed and simply cannot be linked from a lens-view).
3. **At most one lens-view per lens per entity** in v1. Repeated views from the
   same lens are disallowed unless a future revision adds an explicit reason
   field to justify them.
4. Soft-warn (migration nudge) when an entity's origins encode a lens in their
   `ref` (e.g. `explore-ideas-mechanism`) but the entity has no `lens_views`.

## Migration

Backfill `lens_views` for the 28 `explore-2026-07-04` entities in
`~/d/health/processes/post-acute-infection` from the report's per-block `lens`
and `rationale`, with `origin_ref` pointing at each entity's existing origin.

This closes the loop opened on 2026-07-04: **the two dropped twin blocks are
still present in that report as `decision: drop`**, so their rationales are
recoverable. `question:0026` (HSPC) regains its *analogy* lens-view from
`cand-analogy-maladaptive-trained-immunity-hsc-setpoint`, and `question:0036`
(critical-slowing-down) regains its *analogy* lens-view from
`cand-analogy-critical-slowing-down-pais-chronification`. The views we discarded
come back as content.

Backfill is a one-time script over that project; general projects without
`lens_views` remain valid (the field is optional).

## Scope and non-goals

In scope: `question` and `hypothesis` entities; an optional field; extensible to
`topic`/`theme` when `explore-ideas` learns to propose them (ties to
`fb-2026-07-04-007`).

Explicit non-goals for v1 (YAGNI):

- No categorical machinery (no enrichment objects, monoidal products, or
  distance metrics). The `natural-systems` formalism is cited as prior art and
  left as an open door, not imported.
- No per-lens confidence weights.
- No automated *semantic* convergence detection inside validation — detection is
  the pipeline/agent's job; validation only checks structural well-formedness.
- No lens hierarchies; the vocabulary is a flat set.

## Follow-ups this design implies

- A `core/decisions.md` entry recording the schema constraint (packaged lens
  vocabulary; `lens_views` as parallel content; provenance invariant preserved).
- Tool implementation tasks against `~/d/science/science`: `science_model`
  schema + `science_model.lenses`; `explore-ideas` Phase-3/Phase-4 contract;
  graph materialization; validation checks; the PAIS backfill script.
- Open question: is a `theme` (per `fb-2026-07-04-007`) just a coarse-grained
  lens, and if so should `theme` and `lens` share representation? Deferred.
- Open question: cross-project sharing of the lens vocabulary and of derived
  "lens coverage" statistics. Deferred.
