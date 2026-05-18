---
id: hypothesis:h06-adaptive-project-topology-improves-research-fit
type: hypothesis
title: Adaptive project topology improves research fit
status: proposed
phase: active
source_refs: []
related:
- question:14-adaptive-project-topology
- task:t053
- task:t054
- task:t055
- task:t056
- task:t057
- task:t058
created: '2026-05-17'
updated: '2026-05-17'
---
# Hypothesis: Adaptive project topology improves research fit

## Organizing Conjecture

Science projects will stay better aligned with active research work if project topology is periodically reviewed against artifact-derived signals and explicit human judgment prompts.
The conjecture is not that dense graph clusters automatically deserve projects.
It is that a manual-first topology review can reduce known organizational harms: duplicated conceptual models, work landing in the wrong repo, stale branches remaining active by default, reusable resources staying trapped in domain projects, and cross-project synthesis repeatedly re-deriving the same frame.

The strongest version of this hypothesis predicts that a small set of computable signals can identify candidate topology mismatches, while human review remains necessary for boundary-setting, novelty, actionability, and provenance costs.

## Proposition Bundle

### Core Propositions

**P1 (mismatch detection).**
Artifact-derived signals can identify candidate topology mismatches better than ad hoc review alone.
Relevant signals include entity density, graph connectivity, backlog pressure, commit and document recency, stale graph inputs, unresolved references, repeated paper-routing decisions, and reuse across projects.

**P2 (manual review).**
Topology decisions require judgment prompts in addition to computable signals.
Uncertainty gradient, novelty, actionability, coherence, false-positive risk, and provenance cost cannot be trusted as v1 automatic scores.

**P3 (harm reduction).**
A dry-run topology recommendation workflow will reduce or expose known harms relative to the current baseline: duplicate world-model homes, wrong-repo routing, cross-project re-derivation, stranded commons candidates, and ambiguous parenthood.

**P4 (provenance preservation).**
Promotion, demotion, merge, and archive actions are only acceptable if stable entity references, graph nodes, decisions, task history, paper-summary provenance, and parent/peer-link changes remain traceable.

### Supporting Or Auxiliary Propositions

**P5 (bio/meta case study).**
`~/d/bio/meta` is a useful first case because it tests whether a cross-project biological substrate model can be separated from `~/d/health/meta` as an applied health lens.

**P6 (rubric learning).**
The first pilot should shape the v1 signal rubric.
Building the full rubric before auditing actual topology harms risks optimizing abstract signal families rather than decision usefulness.

**P7 (commons routing).**
Adaptive topology and commons promotion are related but distinct.
The topology process should identify commons candidates, but it should not treat every reusable idea as a project.

## Current Uncertainty

- Current support is internal and process-level.
  It comes from recent Science/meta planning, cross-project paper triage, commons-promotion work, and the `bio/meta` boundary problem.
- No pilot has yet compared topology recommendations against a written baseline of harms.
- The candidate computable signals may overfit to visible artifact density and miss high-value quiet work.
- The human-review prompts may be too broad unless the first pilot narrows them.
- The provenance contract is currently a design constraint, not a tested migration workflow.
- It remains unresolved whether `~/d/bio/meta` is the right first promoted project or whether the biological substrate model should remain inside `~/d/health/meta` until the boundary is sharper.

## Predictions

- A baseline-of-harm audit will find concrete examples of topology cost, especially duplicated world-model framing, wrong-repo routing, repeated cross-project synthesis, stranded commons candidates, or ambiguous parent/peer relationships.
- A dry-run topology audit will nominate `~/d/bio/meta` as either a legitimate manually promoted project candidate or a boundary failure that should block scaffolding.
- Computable signals will be useful for surfacing candidates but insufficient for final decisions.
  At least one high-signal cluster should be rejected or deferred by reviewer prompts.
- The pilot will reveal a smaller v1 score than the initial signal list.
  Some signals currently described as judgment prompts may later become computable, but not before the pilot.
- A recommendation that lacks explicit destinations for entity IDs, graph nodes, decisions, task history, and paper summaries will be judged incomplete.

## Falsifiability

- **P1 weakened:** a topology audit surfaces mostly obvious candidates already visible from ordinary task review, or misses known topology harms.
- **P2 weakened:** reviewer prompts do not change any candidate recommendation beyond the computable score.
- **P3 weakened:** recommendations do not map to baseline harms, or they increase churn without reducing misrouting, duplication, or stale work.
- **P4 weakened:** demotion or merge recommendations cannot name stable destinations for graph nodes, decisions, task history, paper summaries, and replacement links.
- **P5 weakened:** the `bio/meta` case cannot be separated cleanly from `health/meta`, suggesting the problem is conceptual boundary-setting rather than project topology.

## Supporting Evidence

- `expert_judgment` - Recent planning identified a specific load-bearing boundary risk between `~/d/health/meta` and proposed `~/d/bio/meta`.
- `expert_judgment` - Recent paper-batch synthesis across health, cancer, cycles, and pre-cancer repeatedly surfaced shared themes: nested biological systems, reachability, perturbation response, observability, and timebase-aware causal inference.
- `expert_judgment` - Recent commons-promotion work shows that reusable topics and workflows need a destination outside domain projects once they are implemented and broadly useful.
- `expert_judgment` - The current design note already splits v1 computable signals from judgment-required prompts, which is consistent with a manual-first decision-support hypothesis.

## Disputing Evidence

- No direct pilot result currently supports that adaptive topology improves project outcomes.
- The strongest objection is false-positive churn: creating, merging, or demoting projects may consume attention without improving research quality.
- A second objection is measurement bias.
  Artifact density may reward projects with more documentation rather than projects with greater uncertainty reduction or downstream utility.
- A third objection is provenance cost.
  Even a correct merge or demotion can damage the research record if links, decisions, task history, or paper provenance become harder to follow.

## Evidence Needed To Shift Belief

- Write a baseline-of-harm note naming concrete topology failures in current Science, health, and cancer projects.
- Run a dry-run topology audit against Science/meta, health/meta, cycles, cancer-evolution, pre-cancer, and pan-disease.
- Compare recommendations against the baseline: would they have reduced a known harm, or are they merely plausible reorganizations?
- Record false positives, false negatives, reviewer overrides, and provenance blockers.
- Use the pilot to define the smallest computable v1 score and the minimum recommendation format.
- Re-evaluate H06 after the `~/d/bio/meta` brief: if the boundary cannot be stated cleanly, the hypothesis should be narrowed or the case study changed.

## Related Work

- `question:14-adaptive-project-topology` asks how Science should adapt project topology to evidence, uncertainty, and decay.
- `[t053]` tracks the adaptive project topology task group.
- `[t054]` will define the v1 signal metrics after the pilot constrains the signal set.
- `[t056]` will design the recommendation workflow, including reviewer cadence and provenance contract.
- `[t057]` will run the baseline-of-harm and pilot audit.
- `[t058]` will prepare the `~/d/bio/meta` scaffold brief as the first case study.
- `doc/plans/2026-05-17-adaptive-project-topology-and-bio-meta-next-steps.md` is the current design note.
