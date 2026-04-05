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
