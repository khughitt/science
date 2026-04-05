# Claim And Evidence Model

> **Superseded.** This document used the old `claim`/`relation_claim` terminology.
> The canonical reference is now [`docs/proposition-and-evidence-model.md`](proposition-and-evidence-model.md).
> All new work should use `proposition` (with optional S-P-O structure) instead of `claim`/`relation_claim`,
> and evidence edges + observations instead of `evidence` nodes.

This document is the canonical reference for the Science reasoning model.
It defines the primary units of uncertainty, how evidence updates belief, and which fields should be authored versus derived.

The model is intentionally small.
Use `claim` and `relation_claim` as the primary truth-apt units.
Do not introduce parallel abstractions such as `statement` or `proposition`.

## Core Stance

- Claims are uncertain.
- Evidence updates belief.
- Hypotheses are claim bundles or claim-like conjectures.
- Direct scientific edges should not be treated as established truth by default.

## Epistemic Glossary

These terms are related, but they are not interchangeable:

| Term | Meaning |
|---|---|
| `belief_state` | The overall derived interpretation of a claim given the current record, such as `speculative`, `supported`, or `contested`. |
| `confidence` | A derived measure of how strongly the current evidence supports the claim. Higher confidence means the support is stronger, more relevant, or more independent. |
| `uncertainty` | The remaining lack of warranted confidence. Uncertainty stays high when evidence is sparse, weak, indirect, or conflicting. |
| `contestation` | The degree to which credible support and credible dispute coexist for the same claim. |
| `fragility` | How easily the current belief could change because support is narrow, low-quality, or dependent on a small number of sources. |

Use `belief_state` for the top-level summary, and treat `confidence`, `uncertainty`, `contestation`, and `fragility` as different derived aspects of that summary.

## Core Types

| Type | Purpose | Authored Fields | Derived Fields |
|---|---|---|---|
| `question` | Frames what the project wants to learn. | `id`, `title`, `question_text`, scope, assumptions, linked inquiry | linked claims, linked studies, open gaps, priority |
| `hypothesis` | Groups one or more claims into a working conjecture. A hypothesis may also be a single claim-like conjecture before it is decomposed further. | `id`, `title`, conjecture text, linked question, linked claims, rationale | aggregate support, aggregate dispute, aggregate `belief_state`, unresolved subclaims |
| `claim` | The primary truth-apt assertion. All scientific uncertainty should attach here. | `id`, claim text, claim kind, scope, provenance, links to question or hypothesis | support summary, dispute summary, belief state, confidence, uncertainty, contestation, fragility |
| `relation_claim` | A `claim` whose content is explicitly `subject-predicate-object`, such as `sleep extension improves reaction time`. This is the preferred form for uncertain scientific relations in the graph. | `id`, subject, predicate, object, qualifiers, scope, provenance | `belief_state`, confidence, uncertainty, contestation, fragility, roll-up into higher-level views |
| `evidence_item` | A concrete line of support or dispute for a target claim. | `id`, target claim, stance, evidence type, provenance source, method, limitations, quality inputs, independence group | contribution to belief, contribution to contestation, evidence summaries |
| `study` | A bounded investigation that can produce one or more results and evidence items. | `id`, title, design, population or system, intervention or exposure, comparator, protocol or source, dates | study quality summary, links to resulting evidence |
| `result` | A structured outcome produced by a study or analysis. A result is not a belief update by itself; it is an observed outcome that can ground evidence. | `id`, linked study, measured outcome, direction, effect size, uncertainty interval or standard error, sample size, p-value when relevant, analysis method, result status | result interpretation, evidence extraction targets |
| `inquiry` | A scoped work program that connects questions, hypotheses, claims, studies, decisions, and next actions. | `id`, title, scope, linked questions, linked hypotheses, linked claims, linked studies, decision points | inquiry status, uncertainty hotspots, priority recommendations |

## Evidence Taxonomy

Every `evidence_item` should use one of these types:

| Evidence Type | Use |
|---|---|
| `literature_evidence` | A claim about what prior publications report, summarize, or argue. Use this for cited papers, reviews, or meta-analyses when the evidence item is grounded in the literature record. |
| `empirical_data_evidence` | Evidence from observed or experimental data. This is usually the strongest evidence class when methods are sound and sources are independent. |
| `simulation_evidence` | Evidence from computational, mechanistic, or generative simulations. It can strengthen or weaken belief, but should usually be treated as weaker than independent empirical confirmation unless validated against data. |
| `benchmark_evidence` | Evidence from benchmark tasks, evaluation suites, or standardized comparisons. This is useful for model comparison and operational performance claims. |
| `expert_judgment` | A structured assessment from domain experts. This can guide inquiry and interpretation, but should not silently substitute for empirical support. |

`negative_result` is not a separate evidence type.
It is a result or interpretation pattern: a `result` can report no observed effect, and the resulting `evidence_item` will usually have `stance: disputes` or weaken support for the target claim.

## Authored Versus Derived Fields

The model distinguishes between fields a user records directly and fields the system computes from structure.

### Authored Fields

Authored fields capture what a person or source actually says happened.
They include:

- question text, claim text, and relation claim triples
- evidence stance, provenance, method, caveats, and quality inputs
- study design, result metrics, and links between records
- inquiry scope, decision points, and workflow notes

Authored fields should be explicit and reviewable.
They should not hide epistemic conclusions inside a single manual status field.

### Derived Fields

Derived fields summarize what follows from the authored record.
They include:

- claim `belief_state`
- claim `confidence`, `uncertainty`, `contestation`, and `fragility`
- aggregate support and dispute counts
- hypothesis roll-ups across linked claims
- neighborhood fragility and inquiry-level uncertainty summaries

Derived fields should be recomputed from evidence structure.
They are interpretations of the record, not primary authored facts.

## Skeptical Default Stance

Every new claim starts from skepticism.
The default question is not "how do we mark this true?" but "what evidence would move belief, and how much?".

In practice this means:

- a claim without evidence remains uncertain
- a single source may increase belief but usually leaves the claim fragile
- conflicting evidence increases contestation rather than forcing a binary verdict
- higher confidence should require multiple, independent, relevant lines of support
- hypotheses do not become accepted merely because they were written down

The system should therefore treat support and dispute as updates to belief, not as switches between truth states.

## Worked Example

### 1. Question

`question`: Does extending nightly sleep improve next-day reaction time in healthy adults?

### 2. Relation Claim

`relation_claim`:

- subject: `sleep_extension`
- predicate: `improves`
- object: `reaction_time_in_healthy_adults`

Readable form: extending nightly sleep improves next-day reaction time in healthy adults.

This claim begins in a skeptical state.
It is a plausible conjecture, but it is not treated as established.

### 3. Evidence

First evidence item:

- type: `empirical_data_evidence`
- stance: supports
- source: randomized crossover study in healthy adults
- result: faster median reaction time after one week of extended sleep
- caveats: modest sample size and short follow-up

Second evidence item:

- type: `empirical_data_evidence`
- stance: disputes
- source: separate study in shift workers
- result: no measurable improvement under high schedule variability
- result status: negative result for this claim in that study context
- caveats: different population and sleep protocol

### 4. Updated Belief

After the first evidence item, belief increases from purely speculative to supported but fragile.
After the second evidence item, belief does not collapse to false.
Instead, the claim becomes contested:

- there is credible support
- there is credible dispute
- population differences may explain part of the mismatch
- the inquiry now needs discriminating follow-up evidence

At the hypothesis level, a broader hypothesis such as "sleep extension improves cognitive performance" would inherit a partial update through this linked claim, not a final yes or no verdict.

## Modeling Rules

- Attach evidence to `claim` or `relation_claim`, not directly to a scientific edge as if the edge were settled fact.
- Treat `study` and `result` as structured provenance and outcome records that can ground evidence.
- Use `hypothesis` for working conjectures and bundles of related claims, not as the only place where uncertainty lives.
- Use `inquiry` to organize work and decisions around uncertain claims.

## Canonical Language

Use this language consistently across docs, commands, templates, and code:

- claims are uncertain
- evidence updates belief
- support and dispute are both first-class
- hypotheses are claim bundles or claim-like conjectures
- relation claims are the graph-native form of uncertain scientific assertions
