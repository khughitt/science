---
kind: question
title: How should Science adapt project topology to evidence, uncertainty, and decay?
status: active
created: '2026-05-17'
updated: '2026-07-01'
id: question:0014-adaptive-project-topology
ontology_terms: []
datasets: []
source_refs: []
related:
- hypothesis:0006-adaptive-project-topology-improves-research-fit
- task:t053
- task:t055
---
# How should Science adapt project topology to evidence, uncertainty, and decay?

## Summary

This question asks when the Science project graph should change shape.
The immediate problem is not automation.
It is whether Science can define a reviewable, provenance-preserving process for deciding when a theme should stay a topic, become a project, merge into a parent, demote to a topic, archive, or move toward commons.

The current working answer is manual-first.
Topology recommendations should be driven by computable artifact signals where possible, supplemented by explicit human-review prompts for uncertainty, novelty, coherence, actionability, and false-positive risk.
The `~/d/bio/meta` proposal is the first case study because it emerged from repeated cross-project synthesis rather than from one project's backlog alone.
The durable operating model is now `core/adaptive-project-topology.md`; the `bio/meta` candidate brief is `core/bio-meta-scaffold-brief.md`.

## Why It Matters

- Project topology determines where evidence, questions, tasks, paper summaries, and decisions accumulate.
- If topology lags behind actual work, agents repeatedly re-route the same ideas, duplicate conceptual models, and leave commons candidates stranded in domain projects.
- If topology changes too eagerly, Science creates maintenance burden, splits weak themes into premature projects, and obscures provenance.
- This question affects whether `~/d/bio/meta` should be scaffolded now, deferred until the boundary with `~/d/health/meta` is crisper, or kept as a theme under an existing project.
- Risk if unanswered: topology changes will remain ad hoc, and later tooling will optimize whatever artifact density it can measure instead of the project harms we actually care about reducing.

## Current Evidence

- Internal process evidence supports the problem statement: recent paper batches and synthesis passes repeatedly surfaced themes that span health, cancer, cycles, pre-cancer, and Science tooling.
- The adaptive-topology design note identifies a specific current ambiguity: `~/d/health/meta` already owns a health-family world model, while the proposed `~/d/bio/meta` would own a biological substrate model.
- Recent commons-promotion work shows that reusable topics, themes, schemas, and workflows need a destination separate from domain projects once they are implemented and ready.
- Current evidence is still weak for the proposed solution.
  The v1 signal rubric, recommendation workflow, provenance contract, and `bio/meta` brief are documented, but we have not yet run the baseline-of-harm audit or measured whether a topology recommendation would reduce duplication, misrouting, stale work, or cross-project re-derivation.
- There is no evidence yet that a quantitative signal score should make decisions automatically.
  The first version should produce dry-run recommendations for human review.

## Thoughts

- Best current interpretation: adaptive topology is most useful if it is treated as a decision-support layer over the Science graph, not as an autonomous project-creation system.
- The v1 split should be conservative: artifact-derived signals can score candidate clusters, while uncertainty, novelty, coherence, actionability, and false-positive risk remain reviewer prompts.
- The first discriminating test is a pilot against known pain points, not a fully general rubric.
- The major remaining uncertainty is whether the recommendation format in `core/adaptive-project-topology.md` handles promotion, demotion, merge, archive, commons-promotion, and leave-unchanged cases without hiding provenance costs.
- A second uncertainty is whether the boundary in `core/bio-meta-scaffold-brief.md` survives the pilot or whether `~/d/bio/meta` is still a symptom of unresolved `bio/meta` versus `health/meta` ownership.

## Connections to Project

- Related hypotheses: `hypothesis:0006-adaptive-project-topology-improves-research-fit`.
- Related tasks: `[t053]`, `[t057]`; completed setup tasks `[t054]`, `[t055]`, `[t056]`, and `[t058]`.
- Required data or analyses: baseline-of-harm note, dry-run topology audit, and reviewer calibration against known routing failures.
- Priority level: high for Science/meta strategy; medium for tool automation until the pilot shows the recommendation format is useful.

## Related

- Operating model: `core/adaptive-project-topology.md`.
- Bio/meta candidate brief: `core/bio-meta-scaffold-brief.md`.
- Historical planning note: `doc/plans/historical/2026-05-17-adaptive-project-topology-and-bio-meta-next-steps.md`.
- Article notes: none yet.
- Methods/Datasets: project graph audit, task backlog audit, commit recency, stale-input reports, cross-project paper routing manifests, commons-promotion candidates.
