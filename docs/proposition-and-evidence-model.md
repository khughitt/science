# Proposition And Evidence Model

This document is the canonical reference for the Science reasoning model.
It defines the primary units of uncertainty, how evidence updates belief, and which fields should be authored versus derived.

> **Design source:** The entity types and terminology in this document reflect the Project Model spec (`docs/specs/plans/2026-04-05-project-model.md`), which formalized the shift from `claim`/`relation_claim` to `proposition` and from `evidence` node to `observation` + evidence edge.

The model is intentionally small.
Use `proposition` as the primary truth-apt unit.
Propositions with explicit subject-predicate-object structure are the preferred form for uncertain scientific relations in the graph.

## Core Stance

- Propositions are uncertain.
- Evidence updates belief via evidence edges.
- Hypotheses are proposition bundles or proposition-like conjectures.
- Direct scientific edges should not be treated as established truth by default.

## Epistemic Glossary

These terms are related, but they are not interchangeable:

| Term | Meaning |
|---|---|
| `belief_state` | The overall derived interpretation of a proposition given the current record, such as `speculative`, `supported`, or `contested`. |
| `confidence` | A derived measure of how strongly the current evidence supports the proposition. Higher confidence means the support is stronger, more relevant, or more independent. |
| `uncertainty` | The remaining lack of warranted confidence. Uncertainty stays high when evidence is sparse, weak, indirect, or conflicting. |
| `contestation` | The degree to which credible support and credible dispute coexist for the same proposition. |
| `fragility` | How easily the current belief could change because support is narrow, low-quality, or dependent on a small number of sources. |

Use `belief_state` for the top-level summary, and treat `confidence`, `uncertainty`, `contestation`, and `fragility` as different derived aspects of that summary.

## Core Types

| Type | Purpose | Authored Fields | Derived Fields |
|---|---|---|---|
| `question` | Frames what the project wants to learn. | `id`, `title`, `question_text`, scope, assumptions, linked inquiry | linked propositions, linked studies, open gaps, priority |
| `hypothesis` | Groups one or more propositions into a working conjecture. A hypothesis may also be a single proposition-like conjecture before it is decomposed further. | `id`, `title`, conjecture text, linked question, linked propositions, rationale | aggregate support, aggregate dispute, aggregate `belief_state`, unresolved sub-propositions |
| `proposition` | The primary truth-apt assertion. All scientific uncertainty should attach here. May be a simple assertion or carry explicit subject-predicate-object structure for graph-native uncertain scientific relations (e.g., `sleep extension improves reaction time`). | `id`, proposition text, subject, predicate, object (for S-P-O form), qualifiers, scope, provenance | support summary, dispute summary, belief state, confidence, uncertainty, contestation, fragility |
| `observation` | A concrete empirical finding — a measured outcome, dataset result, or recorded datum — that grounds evidence edges. | `id`, description, data source, measurement, direction, effect size, uncertainty interval, sample size, analysis method | evidence extraction targets, result interpretation |
| `study` | A bounded investigation that can produce one or more observations and evidence edges. | `id`, title, design, population or system, intervention or exposure, comparator, protocol or source, dates | study quality summary, links to resulting evidence |
| `inquiry` | A scoped work program that connects questions, hypotheses, propositions, studies, decisions, and next actions. | `id`, title, scope, linked questions, linked hypotheses, linked propositions, linked studies, decision points | inquiry status, uncertainty hotspots, priority recommendations |
| `data-package` | A bundled set of analysis results, narrative context, and execution provenance. Produced by a `workflow-run`. | `id`, `type` (e.g., `result`), workflow reference, git commit, inputs, figures, prose | freshness status, downstream consumers |

Evidence edges (rather than evidence nodes) connect observations and propositions to target propositions with a stance of `supports` or `disputes`.

## Evidence Taxonomy

Every evidence edge should use one of these types:

| Evidence Type | Use |
|---|---|
| `literature_evidence` | A proposition about what prior publications report, summarize, or argue. Use this for cited papers, reviews, or meta-analyses when the evidence is grounded in the literature record. |
| `empirical_data_evidence` | Evidence from observed or experimental data. This is usually the strongest evidence class when methods are sound and sources are independent. |
| `simulation_evidence` | Evidence from computational, mechanistic, or generative simulations. It can strengthen or weaken belief, but should usually be treated as weaker than independent empirical confirmation unless validated against data. |
| `benchmark_evidence` | Evidence from benchmark tasks, evaluation suites, or standardized comparisons. This is useful for model comparison and operational performance propositions. |
| `expert_judgment` | A structured assessment from domain experts. This can guide inquiry and interpretation, but should not silently substitute for empirical support. |

`negative_result` is not a separate evidence type.
It is a result or interpretation pattern: an observation can report no observed effect, and the resulting evidence edge will usually have `stance: disputes` or weaken support for the target proposition.

## Authored Versus Derived Fields

The model distinguishes between fields a user records directly and fields the system computes from structure.

### Authored Fields

Authored fields capture what a person or source actually says happened.
They include:

- question text, proposition text, and S-P-O triples
- evidence stance, provenance, method, caveats, and quality inputs
- study design, observation metrics, and links between records
- inquiry scope, decision points, and workflow notes

Authored fields should be explicit and reviewable.
They should not hide epistemic conclusions inside a single manual status field.

### Derived Fields

Derived fields summarize what follows from the authored record.
They include:

- proposition `belief_state`
- proposition `confidence`, `uncertainty`, `contestation`, and `fragility`
- aggregate support and dispute counts
- hypothesis roll-ups across linked propositions
- neighborhood fragility and inquiry-level uncertainty summaries

Derived fields should be recomputed from evidence structure.
They are interpretations of the record, not primary authored facts.

## Optional Layered-Claim Metadata

Some projects need a little more authored structure than proposition text plus evidence stance.
Use these fields when they materially clarify what kind of claim is being made or how directly the evidence speaks to it.
Do not fill them performatively.

### `claim_layer`

`claim_layer` is an authored classification for the proposition itself:

- `empirical_regularity`
- `causal_effect`
- `mechanistic_narrative`
- `structural_claim`

Use `structural_claim` for definitional, benchmark, or model-structure assertions.
Do not auto-upgrade a proposition to `mechanistic_narrative` just because the prose sounds mechanistic.

### `identification_strength`

`identification_strength` records how much leverage the evidence line or proposition has:

- `observational`
- `longitudinal`
- `interventional`
- `structural`

This is not a confidence score.
It answers "what kind of identification situation is this?" rather than "how much do we believe it?"

### `measurement_model`

Many useful propositions depend on a proxy for a latent construct.
In those cases:

- keep `observation` as the concrete empirical finding node,
- treat `measurement_model` as sibling metadata,
- use it to say which observed entity is serving as a proxy for which latent construct,
- record known failure modes when they matter.

Do not replace the `observation` node with a second observation-like construct.

### `supports_scope`

`supports_scope` is a review-radius hint.
It can widen review output, but it must not override explicit graph dependencies.

### `rival_model_packet`

Use `rival_model_packet` when a proposition participates in an explicit bounded comparison among competing models.
`current_working_model` is optional; teams do not need to pretend a preferred model exists before one emerges.

## Migration And Health Surfaces

The layered-claim migration helper is intentionally conservative.
Treat it as an audit/validator surface first, not as a primary authoring workflow.
Run:

```bash
uv run science graph migrate --project-root <root> --format json
uv run science health --project-root <root> --format json
```

`graph migrate` is dry-run by default. It previews alias rewrites and layered-claim migration
state without mutating the project. Pass `--apply` only when you explicitly want it to write
source rewrites, local-source scaffolding, and `knowledge/reports/kg-migration-audit.json`.

Use the migration output for:

- safe first-pass `claim_layer` and `identification_strength` suggestions,
- explicit TODOs for ambiguous propositions,
- warnings for unsupported mechanistic narratives,
- warnings for proxy-mediated propositions that still lack `measurement_model`.

Prefer authored proposition files plus explicit metadata for the real migration work. Use the
helper afterward to check coverage, warnings, and remaining manual judgment calls.

Use the health output for:

- authored `claim_layer` coverage across propositions,
- authored `identification_strength` coverage across causal-leaning propositions,
- rival-model packets missing discriminating predictions,
- migration issues that still need manual judgment.

## Skeptical Default Stance

Every new proposition starts from skepticism.
The default question is not "how do we mark this true?" but "what evidence would move belief, and how much?".

In practice this means:

- a proposition without evidence remains uncertain
- a single source may increase belief but usually leaves the proposition fragile
- conflicting evidence increases contestation rather than forcing a binary verdict
- higher confidence should require multiple, independent, relevant lines of support
- hypotheses do not become accepted merely because they were written down

The system should therefore treat support and dispute as updates to belief, not as switches between truth states.

## Evidence Integrity (Non-Negotiable)

Belief state, validation, and health checks are instruments for reading the evidence — never targets to
be hit. **Gaming any check by misrepresenting evidence is never acceptable.** Specifically, never:

- relabel a weak or indirect line as `strong` / `direct_test` to clear a fragility or leave-one-out warning;
- assign distinct `independence_group`s to lines that are not actually independent (same cohort, same
  instrument, same source) to inflate the independent-support count;
- overstate `stance`, `strength`, `relevance`, or `claim_layer` to push a proposition's `belief_state` up;
- add, drop, or re-scope evidence edges for the purpose of changing a check's color rather than because
  the evidence genuinely warrants it.

**A check may legitimately remain yellow.** If the honest evidence is one strong line plus weaker support,
the correct outcome is a fragile/`supported` belief with the warning standing — not a green check bought by
mislabeling. Driving a check green by overstating evidence is a worse outcome than an honest yellow,
because it silently corrupts every downstream belief that reads it.

When a check fires, the only acceptable moves are: (1) add *genuine* independent evidence that honestly
clears it, (2) correct an *actual* mislabeling in the existing evidence, or (3) accept the residual flag
and record why the evidence warrants it. **"Force the check green by overstating" is not an option and
agents must not present it as one.** Treat this as a load-bearing, project-wide constraint.

*Worked case (health-cycles H03).* `proposition:reproductive-stage-distinct-from-age` had one strong
independent direct test (Levine2016 multi-cohort epigenetic). Fully clearing the leave-one-out warning
would have required mislabeling Qu2025 (MR cycle-length→BMD) or Day2015 (puberty timing) as a `strong
direct_test` of stage-distinct-from-age — a misrepresentation. The honest outcome was to add the genuine
independent lines (upgrading `supported`→`well_supported`, removing the single-SWAN-cohort dependence)
and **accept one residual leave-one-out flip** rather than suppress it.

## Worked Example

### 1. Question

`question`: Does extending nightly sleep improve next-day reaction time in healthy adults?

### 2. Proposition

`proposition` (S-P-O form):

- subject: `sleep_extension`
- predicate: `improves`
- object: `reaction_time_in_healthy_adults`

Readable form: extending nightly sleep improves next-day reaction time in healthy adults.

This proposition begins in a skeptical state.
It is a plausible conjecture, but it is not treated as established.

### 3. Evidence Edges

First evidence edge (grounded by an observation):

- type: `empirical_data_evidence`
- stance: supports
- observation: randomized crossover study in healthy adults — faster median reaction time after one week of extended sleep
- caveats: modest sample size and short follow-up

Second evidence edge (grounded by a separate observation):

- type: `empirical_data_evidence`
- stance: disputes
- observation: separate study in shift workers — no measurable improvement under high schedule variability
- caveats: different population and sleep protocol

### 4. Updated Belief

After the first evidence edge, belief increases from purely speculative to supported but fragile.
After the second evidence edge, belief does not collapse to false.
Instead, the proposition becomes contested:

- there is credible support
- there is credible dispute
- population differences may explain part of the mismatch
- the inquiry now needs discriminating follow-up evidence

At the hypothesis level, a broader hypothesis such as "sleep extension improves cognitive performance" would inherit a partial update through this linked proposition, not a final yes or no verdict.

## Modeling Rules

- Attach evidence edges to `proposition` nodes, not directly to a scientific edge as if the edge were settled fact.
- Treat `study` and `observation` as structured provenance and outcome records that can ground evidence edges.
- Use `hypothesis` for working conjectures and bundles of related propositions, not as the only place where uncertainty lives.
- Use `inquiry` to organize work and decisions around uncertain propositions.

## Canonical Language

Use this language consistently across docs, commands, templates, and code:

- propositions are uncertain
- evidence edges update belief
- support and dispute are both first-class
- hypotheses are proposition bundles or proposition-like conjectures
- propositions with S-P-O structure are the graph-native form of uncertain scientific assertions

## Epistemic Dependency: `bears_on` and Freshness

Propositions, observations, findings, and interpretations all participate in the project's
forward-in-time epistemic dependency graph via the `bears_on` relation. When an upstream
entity changes — a dataset is re-processed, a paper is added to `source_refs`, an
observation's grounding workflow-run is rerun — the freshness engine flags downstream
propositions and interpretations as `needs-review`. This complements the static `supports`
/ `disputes` evidence edges by making "what should I revisit?" a query the system can answer.

`graph build` derives `bears_on` automatically from typed edges (`tests`, `grounded_by`,
`contains`, `synthesizes`, `has_proposition`, `grounds`, `cito:supports`/`cito:disputes`)
and from `prov:wasDerivedFrom` provenance triples, closing the relation transitively across
operational hops. The resulting freshness flag (`fresh` / `needs-review` / `stale`) is
stored as `sci:freshnessState` in the materialized graph.

**Freshness is a flag, not a gate.** A `needs-review` proposition remains readable, citable,
and usable in synthesis — the flag only affects what `science:status` and
`science:next-steps` surface for human attention.

The flag is set and cleared via `science entity review <id>` (records last-reviewed)
and surfaced via `science entity needs-review` (read-only listing). See
`docs/claim-and-evidence-model.md` for the full mechanism description and
`docs/plans/2026-05-03-epistemic-dependency-graph-design.md` for the design.

## Pre-registration: Operational vs Epistemic Targets

Pre-registrations carry commitments about future analyses. Two distinct
commitment shapes coexist under the single `type: pre-registration`:

- **Operational pre-regs** commit to a procedure: "run pipeline P with
  params X before unblinding." These are **gating** — deviations require
  an `amendments:` record. Belief about the operational target is binary
  (the procedure either ran as committed or it didn't).
- **Epistemic pre-regs** commit to an interpretation rule: "if effect > 0.3,
  treat hypothesis H as supported." These are **non-gating** — the result
  feeds H's evidence base via a weighted `bears_on` edge derived at
  graph-build time. A null result against an epistemic pre-reg is
  evidence weighted by the pre-reg's commitment, not a kill switch on H.

The classification falls out of the registered `EntityClass` of each entity
in the pre-reg's `related:` field — no per-entity schema change is needed.
Epistemic kinds for `bears_on` participation are: `hypothesis`, `question`,
`proposition`, `inquiry`, `interpretation`, `finding`, `report`, `story`,
`assumption`, `discussion`, `validation-report`, `mechanism`, and
`observation`. (Note: `inquiry` is `EPISTEMIC` as part of the recast — it
organizes uncertain assertions, same as questions and propositions.)
Mixed pre-regs (an analysis that commits to both a procedure and an
interpretation rule) split cleanly: the operational portion remains an
amendment-gate check at interpret-results time, and the epistemic portion
materializes as a `bears_on` edge into the epistemic target. Operational
targets are not `bears_on` sinks, so no operational `bears_on` is emitted.

When the pre-reg's frontmatter includes the optional `commits_to:` field,
that field overrides `related:` for commitment-target derivation:
`bears_on` edges are emitted from the pre-reg only to entities listed in
`commits_to:`, treating other `related:` entries as navigation context
only. This handles the common case where `related:` is used both for
genuine commitment targets and for discoverability.

`commits_to:` is an edge-scoping field, not a lock. It records which
epistemic entities receive the pre-reg's evidential signal; it does not
freeze those entities, suppress upstream changes, or exempt them from
freshness propagation. A committed-to hypothesis, question, proposition, or
inquiry remains responsive to every other upstream dependency in the
`bears_on` graph. If a newer dataset, workflow-run, observation, proposition,
interpretation, report, or other upstream epistemic entity changes, the
target should still become `needs-review` through the existing freshness
engine.

This dissolves the "gate slammed shut on a viable pathway" failure mode:
under hard-gating semantics, a null result against a pre-registered
prediction terminates a hypothesis even when the underlying physical claim
is still viable. Under the recast, the null result reduces belief weighted
by the pre-reg's commitment level, and the hypothesis remains queryable
and reviewable in the graph (subject to freshness propagation).

See `commands/pre-register.md` for the authoring workflow and
`commands/interpret-results.md` for the evaluation workflow.
