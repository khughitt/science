# First-Class Minimum Viable Synthesis Artifacts

> **Status:** Active design note (Science/meta). Completes `task:t073` by
> defining how Science should represent a minimum viable synthesis when formal
> quantitative synthesis is blocked.

## Goal

When an author cannot defend a pooled estimate, product Bayes factor,
transported causal estimate, or other formal synthesis, the workflow should not
end at a prose-only abstention. It should produce a structured artifact that
preserves why stronger synthesis is blocked, what comparison remains useful,
and what work would make a later stronger synthesis possible.

Cancer-meta proved the pattern in `report:0018-federation-evidence-synthesis-method-guide`
and `report:0030-t042-prostate-nepc-minimum-viable-synthesis`: a blocked
quantitative synthesis can still emit a structured comparison, heterogeneity or
incompatibility statement, blocker list, follow-up route, and adapted certainty
block. This note lifts that shape into the Science toolkit design without
making cancer-specific certainty labels part of core semantics.

## Design stance

A minimum viable synthesis is a **first-class synthesis artifact**, not a
terminal abstention and not merely a report section.

It fits the existing `t022`/`t023` model:

- It is a synthesis operation that consumes inputs and records an operator
  decision.
- It can target propositions, but usually with `validation_role:
  prioritize-attention` or `record-only`.
- It does not strengthen belief by default. Stronger roles require a later
  formal synthesis branch or project-specific guardrail to supply the missing
  comparability, causal, uncertainty, or source-reliability fields.
- It produces reusable output: a comparison table, a blocker map, a follow-up
  route, and optionally a scoped certainty block.

The central distinction is between **no defensible quantitative synthesis** and
**no useful synthesis artifact**. The former is common; the latter should be
rare.

## Proposed synthesis family

Add a synthesis-family candidate to the `t023` taxonomy:

| Family | Default permission | Max permission with conditions | Typical outputs | Primary owner |
|---|---|---|---|---|
| `minimum-viable-synthesis` | `record-only` | `prioritize-attention` when the comparison has a scoped claim, visible blocker list, and follow-up route | structured comparison, blocker map, adapted certainty block, follow-up route | `[t073]` / synthesis-operation extension |

This family is intentionally weaker than `hypothesis-support-synthesis`,
`effect-size-pooling`, `causal-meta-analysis`, or `bayesian-model-comparison`.
Its role is to keep incompatible evidence useful without laundering
incompatibility into support.

Routing rule:

- Use `minimum-viable-synthesis` when inputs are relevant to one research
  question or candidate proposition but do not share a compatible effect,
  diagnostic target, proposition mapping, causal estimand, calibratable
  parameter, or source-independence argument.
- Do not use it when a formal branch is merely inconvenient. If required fields
  exist for a stronger branch, use that branch and record uncertainty there.
- Do not use it as a substitute for expert judgment. If the output is an
  elicited probability distribution from a qualified panel, route to a
  structured expert-judgment family once that family exists.

## Minimum contract

A minimum viable synthesis artifact should include these sections or equivalent
machine-readable fields.

### Method decision

The method decision records the routing claim:

- claim sentence
- input artifact refs
- evidence object class for each input
- selected method class: `minimum-viable-synthesis`
- stronger alternatives considered
- why each stronger alternative was rejected
- no-synthesis boundary

The no-synthesis boundary is load-bearing. It states what downstream consumers
must not infer from the artifact, for example: not a pooled effect, not a
causal effect, not a formal GRADE rating, not a product Bayes factor, not a
graph-facing support update.

### Structured comparison

The structured comparison preserves each input's own semantics instead of
forcing a common scale.

Required columns should be chosen by the artifact's domain, but the comparison
must preserve at least:

- input ref
- claim or finding sentence
- measurement layer or evidence object
- population, context, or scope
- timing or lifecycle frame when relevant
- uncertainty or validation status when available
- current verdict for this input's contribution to the scoped comparison

### Incompatibility statement

The incompatibility statement explains why stronger synthesis is blocked.
It should name the incompatibility class, not only say "heterogeneous".

Common classes:

- different effect scales or evidence objects
- missing shared proposition map
- incompatible populations, contexts, timing, or measurement layers
- missing causal estimand or identification argument
- missing source-independence argument
- missing uncertainty, validation, or source-reliability fields
- graph, clustering, classifier, or model outputs that are exploratory rather
  than evidence for a specific proposition

### Missing fields

Missing fields must be split into two lists:

- `blocks_stronger_synthesis`: fields whose absence prevents the stronger
  branch from being valid.
- `lowers_confidence`: fields whose absence weakens the comparison but does
  not prevent the minimum viable synthesis from being useful.

This split is the main improvement over prose abstention. It lets future tasks
repair the synthesis rather than rediscover the same blockers.

### Follow-up route

The follow-up route names the owner and the smallest next artifact that would
make progress.

Good routes look like:

- child-local export with standardized claim, population, effect object,
  uncertainty, and source-reliability fields
- proposition-map task that defines informative hypotheses and alternatives
- source-dependence audit for shared cohorts, papers, pipelines, prompts, or
  graph views
- causal-claim checklist completion before causal synthesis is attempted
- validation or replication artifact that can retire a blocking reason code

The route should not quietly assign work to "meta" when the missing artifact is
child-owned.

### Adapted certainty block

An adapted certainty block is optional but recommended when a human needs a
compact confidence summary.

It must be scoped and labeled as **adapted**, not formal GRADE/SWiM, unless the
artifact is actually a systematic-review-shaped intervention evidence batch
using the formal frameworks.

Minimum fields:

```markdown
### Adapted certainty block

- certainty scope:
- certainty label:
- source-bias / source-reliability concerns:
- inconsistency / cross-input discordance:
- indirectness / transportability concerns:
- imprecision / sparsity concerns:
- reporting / availability-bias concerns:
- what would raise certainty:
- what would lower certainty:
```

The label is project-calibrated and scoped to the comparison. Core Science
should support the shape, not canonize label thresholds globally. A project may
use `high`, `moderate`, `low`, and `very-low`, but those labels are local
calibration outputs unless a future shared extension standardizes them.

## Payload mapping

The shape maps onto the `t022` core and `t023` synthesis operation contract:

```yaml
core:
  artifact_type: minimum-viable-synthesis
  extensions: [synthesis-operation, minimum-viable-synthesis]
  input_artifact_refs: [...]
  proposition_refs: [...]        # optional; empty when the artifact is only a methods comparison
  comparison_target: n-a         # or hypothesis-set when a scoped proposition map exists
  support_direction: qualifies
  validation_role: record-only   # or prioritize-attention when the scoped comparison is auditable
  validation_status: pending
  uncertainty_summary: "structured comparison; quantitative synthesis blocked"
  reason_codes: [...]

extension/synthesis-operation:
  output_artifact_refs: [...]
  operator_assumption_refs: [...]

extension/minimum-viable-synthesis:
  selected_method_class: minimum-viable-synthesis
  alternatives_considered: [...]
  rejection_rationales: [...]
  no_synthesis_boundary: str
  structured_comparison_ref: ref
  incompatibility_classes: [...]
  blocks_stronger_synthesis: [...]
  lowers_confidence: [...]
  follow_up_route: [...]
  adapted_certainty_block: {...} # optional
```

The exact extension field names can wait for implementation. The design
commitment is the boundary: blockers, confidence-lowering gaps, follow-up route,
and no-synthesis boundary are part of the artifact, not free prose.

## Reason-code hooks

Minimum viable synthesis should contribute reason codes to `t025` rather than
inventing a parallel uncertainty vocabulary.

Candidate generic codes:

- `synthesis-incompatible-inputs`
- `shared-proposition-map-missing`
- `source-independence-missing`
- `effect-object-mismatch`
- `measurement-layer-mismatch`
- `target-population-mismatch`
- `uncertainty-fields-missing`
- `source-reliability-fields-missing`
- `formal-synthesis-blocked`

Default blocking policy:

- Codes that explain why a stronger branch is invalid should block
  `strengthen-belief`.
- The artifact itself can still be `record-only` or `prioritize-attention`.
- A downstream validation or child export can retire a blocking code by
  supplying the missing field or assumption.

This keeps H03 attention useful: a minimum viable synthesis can draw attention
to repairable uncertainty without pretending to be evidence of the domain claim.

## Source-reliability alignment

The cancer-meta examples make source reliability part of the minimum artifact.
Science should preserve that, but not force every project into one reliability
scale.

Minimum viable synthesis should record:

- which source-reliability fields are absent
- whether absence blocks stronger synthesis or merely lowers confidence
- whether source dependence is known, suspected, checked, or unchecked
- which follow-up artifact would make the reliability claim auditable

This aligns with `t031` source-dependence detection and `t037` agent/tool
operation provenance. Agent-generated syntheses should cite operation records
instead of duplicating model, prompt, context, or tool-chain details.

## Formal GRADE/SWiM boundary

Formal SWiM/GRADE remains appropriate for systematic-review-shaped intervention
evidence when the review is actually using those methods and reporting
requirements.

For heterogeneous cross-child, cross-project, graph, mechanism, or methods
comparisons, Science should use **adapted certainty**, not formal GRADE/SWiM.

The adapted block may borrow the idea of explicit downgrade dimensions, but it
must not imply that:

- the inputs are studies of the same intervention and outcome,
- certainty has been graded under Cochrane/GRADE rules,
- a qualitative certainty label is evidence for a causal or pooled-effect
  proposition,
- compatibility blockers have been resolved.

## Tooling recommendation

Do not build a large command first. The next implementation should be small:

1. Add a template for `minimum-viable-synthesis` sections or a report scaffold.
2. Add validation that checks for the required sections when the family is
   declared.
3. Add docs that route "no quantitative synthesis" decisions to this artifact
   shape.

Command support can follow only after two or three project examples prove the
field names are stable.

## Acceptance criteria for future implementation

A future toolkit implementation should pass these checks:

- An author can create a minimum viable synthesis without claiming support for
  the target proposition.
- Validation requires a no-synthesis boundary, structured comparison,
  incompatibility statement, blocker list, and follow-up route.
- Adapted certainty blocks are clearly marked as adapted and scoped.
- Project-specific label thresholds are not baked into core Science.
- Reason codes can block `strengthen-belief` while still allowing
  `prioritize-attention`.
- Existing synthesis families remain available for formal quantitative,
  causal, diagnostic, graph-valued, or Bayesian synthesis when their required
  fields are present.

## Follow-up tasks

- Add `minimum-viable-synthesis` to the synthesis-family taxonomy and validator.
- Add a template or command scaffold after one more non-cancer example is
  authored.
- Mirror the generic reason codes into the `t025` registry.
- Audit `science-research-papers` batch synthesis output for places where a
  prose abstention should become a minimum viable synthesis artifact.
