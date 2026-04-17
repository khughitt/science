# Layered Claims, Measurement Proxies, and Cross-Impact Propagation

**Date**: 2026-04-15
**Status**: Draft
**Origin**: Generalized from MM30 causal-methodology pressure points, with `natural-systems` selected as the non-biology pilot

## Problem

Science already has a strong skeptical proposition/evidence model, but it does
not yet cleanly represent several distinctions that downstream projects now need
in a first-class way:

1. **Claim layer** — projects often blur together:
   - empirical regularities,
   - causal effect claims,
   - mechanistic narratives,
   - structural or definitional claims.
2. **Identification strength** — downstream DAGs and interpretations often use
   observational, longitudinal, interventional, and structural evidence in the
   same prose without a normalized machine-readable distinction.
3. **Measurement versus latent construct** — many scientifically useful nodes
   are observed only through scores, signatures, annotations, or projections.
   Without explicit proxy metadata, projects can over-claim from proxies as if
   they were direct observations.
4. **Competing model structures** — projects increasingly compare not just
   propositions but rival DAGs or rival causal/mechanistic packets with shared
   observables and discriminating predictions.
5. **Cross-impact propagation** — when a task, edge, or interpretation changes,
   there is no framework-level way to enumerate which downstream claims should
   be reconsidered.
6. **Migration burden** — existing projects can only adopt these distinctions by
   bespoke local prose unless the framework provides migration helpers.

MM30 exposed the cost of these gaps most clearly in t174/t202, but the need is
not MM30-specific. `natural-systems` already has rich proposition/evidence
machinery, provenance concerns, and downstream structural claims that make it a
good generality check.

## Goals

- Keep the current proposition/evidence model as the epistemic core.
- Add a first-class distinction between empirical regularity, causal effect,
  mechanistic narrative, and structural/definitional claims.
- Add normalized evidence metadata for identification strength, independence,
  proxy directness, and update scope.
- Add explicit measurement/proxy structures so projects can say “observed proxy
  for latent construct” instead of encoding that only in prose.
- Add framework-level support for rival-model packets and discriminating
  predictions.
- Add cross-impact tooling so a changed task, interpretation, or proposition can
  surface affected downstream claims.
- Provide migration helpers good enough for existing projects to adopt the new
  schema incrementally.

## Non-Goals

- Do not build full unconstrained structure discovery into Science.
- Do not require every project to author full causal DAGs.
- Do not attempt calibrated causal identification from observational data in the
  framework itself.
- Do not force all projects to use biology-specific ontology terms or
  identification semantics.
- Do not rewrite downstream scientific prose automatically into final form.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Epistemic unit | Keep `proposition` as the primary truth-apt unit | Extends the existing reasoning model rather than replacing it |
| Layering model | Add authored `claim_layer` metadata to propositions and hypothesis-linked summaries | Projects need to distinguish what kind of claim is being updated |
| Identification model | Add normalized `identification_strength` metadata to evidence/proposition bundles | Makes structural vs observational vs longitudinal vs interventional evidence explicit |
| Proxy model | Represent observed-proxy → latent-construct links explicitly | Prevents silent proxy-overclaiming |
| Rival-model support | Add “model packet” structures rather than generic full-DAG discovery | Matches actual project workflows: bounded alternatives, discriminating predictions |
| Cross-impact | Build explicit dependency traversal over propositions, hypotheses, interpretations, and tasks | Manual update propagation is now a bottleneck |
| Migration strategy | Upstream schema first, then `natural-systems` pilot, then MM30 migration | Forces generality before biology-specific downstream use |

## Semantic Boundary

### 1. Claim layer is not belief state

`claim_layer` describes **what kind of proposition** is being made:

- `empirical_regularity`
- `causal_effect`
- `mechanistic_narrative`
- `structural_claim`

It does **not** replace `belief_state`, `confidence`, `uncertainty`, or
`contestation`. A proposition can be strongly supported and still be an
empirical-regularity proposition rather than a mechanistic one.

### 2. Identification strength is not evidence type

`evidence_type` already says whether a line is literature, empirical,
simulation, benchmark, or expert judgment.

`identification_strength` says what kind of causal leverage the line has:

- `none`
- `structural`
- `observational`
- `longitudinal`
- `interventional`

These axes are complementary, not interchangeable.

### 3. Proxy directness is not uncertainty

Projects need to distinguish:

- direct measurements,
- derived measurements,
- proxy-for-latent constructs,
- purely latent or unobserved constructs.

This is a measurement-model concern, not just a confidence score.

### 4. Relationship to the existing `observation` entity

The framework already treats `observation` as a first-class entity that carries
empirical facts. The new measurement/proxy structures must not replace that.

The intended relationship is:

- keep `observation` as the concrete empirical finding node,
- treat `MeasurementModel` as a reusable sibling metadata object,
- allow propositions, evidence lines, and observations to reference a
  `MeasurementModel` when they rely on a proxy-mediated latent construct,
- avoid introducing a second observation-like entity that competes with the
  existing graph semantics.

This keeps the current proposition/evidence/observation model intact while
making proxy assumptions explicit.

### 5. Rival-model packets are not hypotheses in disguise

A `hypothesis` remains a proposition bundle.
A rival-model packet groups:

- a nullable current working model,
- bounded alternatives,
- shared observables,
- discriminating predictions,
- adjudication criteria.

This supports “compare 3 plausible DAGs” without requiring the framework to
search over all DAGs.

## Data Model Extensions

### A. Proposition-level authored metadata

Add optional authored metadata that can live in frontmatter-backed entities and
graph exports:

- `claim_layer`
- `supports_scope`
- `measurement_model`
- `rival_model_packet_ref`

`supports_scope` should capture the authored **review radius hint** for how
widely a proposition’s update should propagate:

- `local_proposition`
- `hypothesis_bundle`
- `cross_hypothesis`
- `project_wide`

Its semantics are deliberately narrow:

- explicit graph links always win,
- `supports_scope` can widen or prioritize review output,
- `supports_scope` must not suppress direct graph dependencies,
- `supports_scope` is therefore a hint, not a graph override.

### B. Evidence-line authored metadata

Add normalized evidence metadata:

- `identification_strength`
- `independence_group`
- `proxy_directness`
- `evidence_role`

`evidence_role` is intentionally small:

- `direct_test`
- `proxy_support`
- `background_constraint`
- `negative_control`
- `model_criticism`

### C. Measurement model object

Introduce a reusable structured object:

- `observed_entity`
- `latent_construct`
- `measurement_relation`
- `rationale`
- `known_failure_modes`
- `substitutable_with`

This can be attached to propositions, hypotheses, source records, or referenced
from observations. The point is not to build a full latent-variable engine; it
is to let projects declare which constructs are directly observed and which are
proxy-mediated.

### D. Rival-model packet object

Introduce a structured packet with:

- `packet_id`
- `target_hypothesis` or `target_inquiry`
- `current_working_model`
- `alternative_models`
- `shared_observables`
- `discriminating_predictions`
- `adjudication_rule`

This packet should be queryable and human-readable.

## Tooling Changes

### Commands

The following commands need to understand the new structures:

- `commands/add-hypothesis.md`
- `commands/interpret-results.md`
- `commands/compare-hypotheses.md`
- `commands/sketch-model.md`
- `commands/specify-model.md`
- `commands/critique-approach.md`
- `commands/status.md`

These do not all need new CLI flags immediately, but the framework must stop
teaching a workflow that silently mixes empirical regularities, causal claims,
and mechanisms.

### Graph / query tooling

The framework needs:

- a structured cross-impact query,
- a proxy/measurement audit,
- a validator for unsupported mechanistic claims,
- migration helpers that can infer missing fields conservatively.

## Validation Rules

The framework should warn or fail when:

1. a `mechanistic_narrative` proposition lacks either:
   - linked lower-layer supporting propositions, or
   - an explicit note that lower-layer support still lives in prose and remains
     to be decomposed,
2. a proposition or evidence line lacks `identification_strength` where the
   project is using causal-modeling aspects,
3. a proxy-mediated proposition is authored without `measurement_model` or
   `proxy_directness`,
4. multiple evidence lines appear independent in summaries but share an
   `independence_group`,
5. a rival-model packet lacks discriminating predictions.

## Migration Strategy

### Backward compatibility contract

This change set should be non-breaking for existing projects that do not opt in
yet.

- all new fields are optional,
- existing validators should continue to pass when the fields are absent,
- materialized graph exports should preserve prior semantics when the new fields
  are unused,
- the first implementation pass should bump schema/documentation versioning only
  if serialized output changes for existing consumers in practice.

If the implementation discovers real external-consumer breakage, the work must
document the version signal explicitly rather than relying on silent drift.

### Upstream first

Implement the schema, query, validation, and migration primitives in `science`
before pushing methodology changes into downstream projects.

### `natural-systems` pilot second

Use one real claim/evidence slice to prove:

- the new abstractions are not biology-specific,
- migration helpers are usable,
- cross-impact output is informative.

### MM30 third

Only after the pilot, migrate MM30 onto the refined upstream interface.
MM30 should consume the framework-level distinctions rather than inventing a
parallel local methodology.

## Shared Pilot Report Template

Both the `natural-systems` pilot and later downstream migrations should use the
same minimum report structure:

1. migrated slice and files touched,
2. safe automatic inferences,
3. manual judgments required,
4. proxy/measurement issues surfaced,
5. cross-impact output summary,
6. upstream refinements required,
7. acceptance decision: stable for downstream use or not yet stable.

## Success Criteria

- Projects can distinguish empirical regularities, causal effect claims,
  mechanistic narratives, and structural claims without inventing local schema.
- Proxy-mediated constructs can be represented without colliding with existing
  `observation` semantics.
- Rival-model packets can be authored without pretending a preferred winner
  already exists.
- Cross-impact propagation uses graph structure first and authored
  `supports_scope` only as a review-radius hint.
- Existing projects can ignore the new fields without breakage until they opt
  in.

## Traceability

| Design requirement | Upstream implementation consequence | Downstream MM30 consequence |
|---|---|---|
| Distinguish claim kinds explicitly | schema enums, validators, migration helper, command guidance | H1/H2/t174/t202 split by layer |
| Make proxy assumptions explicit | `MeasurementModel`, proxy audit, migration warnings | explicit biological proxy handling |
| Compare rival bounded models | rival-model packet support and queryability | t174/t202 rival explanation packet |
| Propagate updates conservatively | cross-impact query with graph-first semantics | cross-hypothesis update review in H1/H2 |
| Avoid forcing adoption through breakage | optional fields, compatibility contract, migration helpers | migration can preserve verdicts and wording ceilings |

## Pilot Selection

The initial `natural-systems` pilot should center on the
`double-categorical-model-relationships` hypothesis and its linked
interpretations/questions because it already combines:

- literature evidence,
- benchmark evidence,
- structural claims,
- empirical downstream implications,
- provenance/independence concerns.

This makes it a better generality test than a purely descriptive or purely
mechanistic slice.
