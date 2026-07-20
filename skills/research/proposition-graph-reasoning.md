---
name: research-proposition-graph-reasoning
description: Use when interpreting or updating the project's own proposition graph — assessing hypothesis support, reading dashboard signals, or deciding where to direct effort.
archetype: analysis-discipline
provenance: internal
---

# Proposition Graph Reasoning

Answers: before interpreting the project's own evidence, what must be checked
about how that evidence is recorded?

## Triggering condition

Fires whenever a conclusion is drawn from the project's own proposition graph
rather than from external literature: writing an interpretation, updating
hypothesis support, summarizing where the project stands, or choosing what to
work on next.

Science uses a skeptical, proposition-centric model:
- hypotheses are organizing conjectures
- propositions are the main units of belief
- observations and propositions support or dispute propositions via evidence edges
- sparse or single-source support should be treated as fragile
- contested neighborhoods and propositions lacking empirical support should be treated as prioritization signals, not just annotations

## Required reasoning / check / precommitment

- Treat the hypothesis as a **bundle of propositions**, not a single binary truth value
- Every important proposition should be **falsifiable** — specify what evidence would lower confidence
- Distinguish **organizing conjecture** from **proposition-level updates**
- Prefer **support / dispute / unresolved** language over premature verdicts
- Note the **evidence type** when possible: literature, empirical-data, simulation, benchmark
- Track **residual uncertainty** explicitly, especially for single-source or indirect support

For the strict enum values, layered-claim metadata semantics, and proposition
entity types, see [`proposition-schema.md`](./proposition-schema.md).

## Decision rule or reasoning criteria

Assess each condition below against the entity files. When
`knowledge/graph.trig` exists, the last four are additionally checked against
the store summaries:

- `science graph dashboard-summary --format json`
- `science graph neighborhood-summary --format json`

These summaries are a prioritization instrument. They report where recorded
evidence is thin or contested; they do not measure whether a proposition is
true.

## Outcomes (flagged conditions)

Outcomes are **non-exclusive flagged conditions**, not a ladder and not a
verdict. Any number may hold at once. Each licenses a prioritization action;
none licenses a claim about how well-supported a proposition is.

| Condition | Fires when | Licenses |
|---|---|---|
| `migration-limited` | hypothesis prose carries the reasoning; scalar `confidence` is doing the epistemic work; propositions are not decomposed; evidence is not attached as support/dispute | prefer creating or refining propositions over editing prose; state that interpretation quality is bounded by migration state |
| `contested` | support and dispute lines both bear on the proposition | read the disagreement before summarizing; do not report a direction of effect as settled |
| `single-source-fragile` | support traces to one source, or to lines sharing an `independence_group` | treat support as fragile; prioritize independent replication |
| `lacks-empirical-support` | support is present but no `empirical_data` line bears on it | name the evidence kind when reporting; prioritize empirical work |
| `high-uncertainty` | the proposition sits in a neighborhood the dashboard reports as high-uncertainty | prioritize reading, replication, or model cleanup here |

**No flagged condition is not certification.** The dashboard reports only over
what has been *recorded*; silence is equally consistent with adequate support
and with nothing having been entered. An instrument that cannot distinguish
those two states cannot certify either, so the absence of a signal licenses
proceeding — and nothing more. It must never be written up as adequate,
sufficient, or well-supported. There is deliberately no `adequate` outcome.

**Unevaluated is a distinct state.** Dashboard summaries are conditional on
`knowledge/graph.trig` existing. When it does not, the last four conditions
cannot be evaluated at all, and that must be recorded as unevaluated — never
collapsed into "no flagged condition." `migration-limited` remains assessable
from the entity files alone.

## Halt / escalation

In those cases:

- prefer creating or refining propositions over editing prose alone
- prefer proposition-backed graph updates over summary-only status changes
- call out that the project still needs migration work when that affects interpretation quality

## Required evidence & artifacts

**Every** condition that fired is recorded, along with every condition that
could not be evaluated and why. Nothing is dropped for being unsurprising.

- **On an interpretation** (`templates/interpretation.md`): the full fired set and the unevaluated set under `## Evidence Quality`; what those flags license under `## Updated Priorities`.
- **On a synthesis** (`templates/synthesis.md`): the full fired set and the unevaluated set under `## Knowledge Gaps` — including `migration-limited`, `contested`, and `single-source-fragile`, not only the gap-shaped ones; the prioritization they license under `## Research fronts`.
- The dashboard command run and its output, when one was run; when `knowledge/graph.trig` was absent, record that instead.

## Permitted reporting language

- Permitted: "supports", "disputes", "leaves unresolved", "is consistent with", "single-source", "contested", "unevaluated".
- **Not licensed by this discipline, ever:** "confirms", "proves", "validates", "establishes", "well-supported", "sufficient". No flagged condition licenses any of them — the conditions report where recorded evidence is thin or contested, and none of them measures whether a proposition is true. A positive support judgment requires a separate warrant this discipline does not supply.
- Forbidden always: reporting the absence of flagged conditions as positive evidence of support.

## Success test

Was the required reasoning/precommitment carried out before interpretation, and does the conclusion follow from it — mechanically where a locked table applies, by the stated criteria otherwise?

## Companion Skills

- [`proposition-schema.md`](proposition-schema.md) - the strict enums and field semantics this reasoning writes against.
- [`literature-evaluation.md`](literature-evaluation.md) - evaluating external sources, as opposed to the project's own graph.
- [`../INDEX.md`](../INDEX.md) — the skill index.
