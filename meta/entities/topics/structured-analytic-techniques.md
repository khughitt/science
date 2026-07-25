---
id: topic:structured-analytic-techniques
kind: topic
title: Structured Analytic Techniques and Argument Completeness
status: active
related: []
source_refs: []
created: '2026-07-25'
updated: '2026-07-25'
---
# Structured Analytic Techniques and Argument Completeness

## Summary

Intelligence analysis and safety-critical engineering both face a problem this project
has: an argument must be auditable by someone who was not present when it was made, and
the analyst who built it is motivated to believe it. Both fields answered with explicit
argument structure — a disconfirmation matrix in one case, an assurance case with named
objections in the other — rather than with better evidence.

The shared move is to make *argument completeness* a property you can check, separately
from how strong the evidence is.

> **Intake status.** Every reference below was surfaced by the 2026-07-25
> `explore-ideas` lens pass and is **unverified**: the identifiers are
> model-generated and no source has been read. Nothing here should be cited or
> treated as evidence until the intake task promotes it to a real paper entity.
> This topic is a scoped reading brief, not a synthesis.

## Key Concepts

**Analysis of Competing Hypotheses (ACH).** Build an evidence-by-hypothesis matrix in
which every item of evidence is scored against *every* competing hypothesis, and prefer
the hypothesis least inconsistent with the evidence. The logic is disconfirmatory: the
matrix foregrounds what is ruled out rather than what is supported, and it makes evidence
shared across rival hypotheses visible — a relationship per-hypothesis evidence lists
cannot express.

**Defeater node.** In an assurance case, an explicit representation of a known objection.
Its presence obliges the author either to attach a counter-argument or to mark it as
accepted residual risk. An unanswered defeater is a visible structural hole, not a
silence.

**Argument completeness vs evidence strength.** Two independent audit dimensions. A claim
can be well-evidenced and structurally incomplete — strongly supported, with its strongest
objection never addressed. Only the first is currently representable in the graph.

**Structured technique as debiasing.** Both traditions treat these structures as
countermeasures against motivated reasoning rather than as documentation. Whether they
work as debiasing is contested and is itself part of the literature.

## Current State of Knowledge

The toolkit has workflow-level analogues — `compare-hypotheses` performs head-to-head
evaluation of competing explanations, and `bias-audit` / `review` sweep for unincorporated
open questions — but these are recomputed views and periodic audits, not durable graph
structure. The open residue in both cases is structural, not procedural. No source in this
topic has been read.

## Controversies & Open Questions

- Should the ACH matrix be durable, queryable, diffable graph structure, or is a
  recomputed view sufficient?
- Does requiring a defeater per claim improve reasoning or merely generate ceremony that
  gets filled in perfunctorily — the same failure mode this project fears for its schema?
- Evidence that structured analytic techniques actually debias is mixed; that debate bears
  directly on whether to adopt either.

## Relevance to This Project

Supports `question:0045` (defeater nodes surfacing unclosed argument gaps) and
`question:0046` (ACH-style cross-hypothesis disconfirmation). Both were narrowed at triage
against existing command-level tooling, so this topic's job is to establish whether the
structural half is worth the authoring cost — which links it to `question:0057`.

## Key References

- Dhami et al. (2019) — empirical evaluation of ACH as a debiasing tool *(unverified
  intake)*
- Mandel & Tetlock (2018) — structured analytic techniques as judgment correctives
  *(unverified intake)*
- Kelly & Weaver (2004) — Goal Structuring Notation; goal-strategy-evidence and the
  defeater construct *(unverified intake)*
- Wei et al. (2019) — structured assurance case metamodel; machine-checkable argument
  structure *(unverified intake)*
