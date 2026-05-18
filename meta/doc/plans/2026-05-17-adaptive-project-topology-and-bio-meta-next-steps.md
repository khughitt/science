# Adaptive Project Topology And Bio Meta Next Steps

> **Status:** Draft design spec for `[t053]` through `[t058]`.
> This is a Science/meta design note.
> It intentionally separates the research-organization model from the proposed biological model in `~/d/bio/meta`.

## Goal

Define a manual-first path for two linked but distinct ideas:

1. `~/d/science/meta` should track an **adaptive project topology** model: a way to decide when themes should be promoted into projects, split, merged, demoted, archived, or turned into commons resources.
2. `~/d/bio/meta` should be prepared as the first candidate project created from this reasoning: a biological meta-model for nested, multiscale dynamical systems under partial observation.

The two ideas should cross-reference each other, but they should not live in the same project.
`~/d/science/meta` studies how research projects evolve.
`~/d/bio/meta` studies the biological model that downstream health, cancer, cycles, and pre-cancer projects can inherit.

## Load-Bearing Boundary

The `health/meta` versus `bio/meta` boundary is the main architectural risk.
`~/d/health/meta` already describes itself as holding the health family's world model: health framed as homeostasis of nested biological systems.
That overlaps with the proposed `~/d/bio/meta` charter unless the two layers are separated explicitly.

The proposed boundary is:

- `~/d/bio/meta` owns the **substrate model**: multiscale biological systems, state spaces, time and space, reachability, path dependence, control regimes, perturbation response, observability, sampling, and resolution.
- `~/d/health/meta` owns the **applied health lens**: homeostasis, disease, intervention, health-state axes, family coordination, and decisions about which child health projects should exist.

Under this boundary, cancer, cycles, and pre-cancer can link to both layers for different reasons.
They use `bio/meta` for general biological modeling primitives, and `health/meta` when the question is specifically about health, disease, homeostatic failure, or intervention.

`[t058]` must settle this boundary before `~/d/bio/meta` is scaffolded.
If this boundary cannot be made crisp, `bio/meta` should not be created yet; otherwise the system will have two world-model homes with ambiguous parenthood.

## Design Stance

The adaptive-topology system should start as a research question and task group, not as automation.
The near-term output is a rubric and workflow that recommends topology changes for human review.
Automatic project creation, pruning, or migration should wait until the recommendation workflow has been tested on existing projects.

The working conjecture is that a research system can use graph and backlog signals to notice when its current project topology no longer matches the actual density of evidence, uncertainty, novelty, and downstream utility.
The risk is premature taxonomy churn: creating projects because a topic is interesting, not because it has enough evidence, questions, tasks, or reusable structure to justify its own home.

## Objects

| Object | Meaning | Candidate action |
|---|---|---|
| Theme | A recurring topic or cluster inside one or more projects. | Keep as topic, promote, merge, or make commons resource. |
| Project idea | A theme with enough coherence to plausibly become a Science project. | Write project brief; run topology audit. |
| Project | A Science-managed repo with its own question, tasks, graph, and docs. | Keep active, split, merge, demote, or archive. |
| Commons resource | A reusable method, dataset, schema, model, or workflow used by multiple projects. | Promote to `~/d/science-commons` once that system exists. |
| Topology recommendation | A proposed structural change with evidence, tradeoffs, and approval status. | Dry-run report first; apply only after review. |

## Signal Rubric

`[t054]` should not try to operationalize every interesting signal in v1.
The signal list splits into two classes.

V1 scoreable signals are computable from existing artifacts:

- **Entity density:** number of linked papers, summaries, questions, hypotheses, tasks, datasets, reports, and evidence artifacts.
- **Graph connectivity:** incoming and outgoing links, cross-project refs, `bears_on` edges, stale-input counts, and unresolved-reference counts.
- **Backlog pressure:** task count, task priority distribution, blocked/proposed/active status, and repeated task-group references.
- **Recency and decay:** commit recency, document `updated` recency, stale graph inputs, and age since last meaningful task or report.
- **Reuse signals:** repeated references from multiple projects, commons-candidate flags, and repeated routing decisions in paper manifests.

V1 judgment-required prompts should appear in the human review report but not contribute to an automatic score:

- **Uncertainty gradient:** whether unresolved questions are high-information rather than merely numerous.
- **Novelty:** whether recent papers or datasets introduce a genuinely new direction.
- **Actionability:** whether available datasets or methods make a theme testable now.
- **Coherence:** whether a cluster has a clear research question and scope boundary.
- **False-positive risk:** whether promotion would duplicate an existing project, overfit to one literature batch, or create maintenance burden.

This split keeps `[t054]` from becoming a tar pit.
The first pilot should teach which judgment-required signals can later become computable.

## Baseline Of Harm

Before `[t057]` pilots any rubric, the project needs a short written baseline describing where current topology has actually hurt.
Candidate harms to inspect:

- Work landing in the wrong repo because two projects both look like the world-model home.
- Topics duplicated across projects without a clear owner.
- Cross-project sync or paper-triage passes re-deriving the same conceptual model.
- Commons candidates accumulating in domain projects because `~/d/science-commons` is not yet initialized.
- Child-project parenthood becoming ambiguous when a theme is both biological substrate and applied health lens.

The pilot should not tune the rubric to whatever clusters it happens to find.
It should compare recommendations against this baseline and ask whether the recommendation would have prevented or reduced a known cost.

## Recommendation Workflow

`[t056]` should design the workflow as a manual-first command or report.
The first version should produce a dry-run report with one recommendation per candidate cluster.
It should have both a cadence and an owner.

Recommended cadence:

- monthly as part of a Science/meta topology review;
- additionally triggered by large paper-triage batches, commons-promotion candidates, or `science-curate` / `science-next-steps` runs that surface cross-project ambiguity.

Recommended owner:

- `~/d/science/meta` owns the topology report and recommendation format;
- affected domain projects own approval of moves that change their own scope, tasks, or parent/peer links.

Allowed recommendation types:

- promote theme to project
- split project into child projects
- merge project into parent or sibling
- demote project to topic/theme
- archive stale branch
- create commons resource
- create cross-project synthesis task
- leave unchanged

Each recommendation should include:

- target cluster or project
- triggering signals
- counter-signals
- proposed destination
- required human decision
- provenance-preserving links to maintain
- tasks that would be created if accepted

The workflow should not delete or move anything automatically in v1.
Even an apparently stale project may hold latent value as a provenance anchor.

## Provenance Contract For Demotion And Merge

Demotion and merge actions need an explicit provenance contract before `[t056]` designs command behavior.
Minimum v1 contract:

- Stable entity IDs remain resolvable, either in the original archived project or through an explicit alias/archive map.
- Graph nodes from demoted projects are not deleted; they are marked archived, superseded, or moved behind a stable cross-reference.
- Decisions move or copy to the destination only when they remain load-bearing; otherwise they are archived with a replacement pointer.
- Task history remains in the original task archive; destination projects get new follow-up tasks that cite the original task IDs.
- Paper summaries and source refs keep their original provenance; promoted syntheses may cite them, but do not rewrite source history.
- Parent/peer links change only through a reviewed migration note.

This contract constrains recommendation output.
A demotion recommendation is incomplete unless it names where graph nodes, decisions, task history, paper summaries, and replacement links will live.

## Bio Meta Case Study

`~/d/bio/meta` is a useful first case because it emerged from cross-project evidence rather than from a single paper batch.
Health-meta, cycles, cancer-evolution, and pre-cancer all independently point toward a shared biological model:

- nested systems across scales
- time and space as first-class dimensions
- state trajectories and control regimes
- reachability, path dependence, canalization, and ratcheting
- perturbation response and recovery
- observability, denominator, sampling interval, and assay resolution

`[t058]` should prepare a project brief before scaffolding.
The brief should answer:

1. What research question belongs in `~/d/bio/meta`?
2. Which work remains in `~/d/health/meta`?
3. Which themes belong only as initial topics rather than child projects?
4. Which existing projects should link to `~/d/bio/meta` once it exists?
5. What minimum starting tasks and hypotheses would justify scaffolding?

The expected initial `~/d/bio/meta` question is:

> What biological model best represents organisms as nested, multiscale dynamical systems under partial observation?

This is a framing and methodology question, not a narrow empirical question.
That is acceptable, but it means `~/d/bio/meta` should be tagged as a meta-role synthesis project from day one.
It should not pretend to produce primary biological findings.
Its job is to define reusable modeling primitives and organize evidence that constrains those primitives.

Candidate initial topics:

- nested biological systems model
- state-space reachability and path dependence
- sampling, resolution, and observability
- perturbation response as health observable
- timebase-aware causal inference
- control regimes, feedback, cycles, and attractors

## Initial Task Group

The adaptive topology work is tracked in `tasks/active.md`:

- `[t053]` Adaptive project topology task group
- `[t054]` Define adaptive topology signal metrics
- `[t055]` Draft adaptive project topology hypothesis and question
- `[t056]` Design topology-change recommendation workflow
- `[t057]` Pilot topology audit across Science, health, and cancer projects
- `[t058]` Prepare bio/meta scaffold brief as a topology case study

## Next Steps

1. Complete `[t055]`: reserve a Science/meta question and draft a candidate hypothesis.
2. Complete `[t058]`: write the `~/d/bio/meta` project brief, with the `bio/meta` versus `health/meta` boundary settled explicitly.
3. Complete `[t057]`: write the baseline-of-harm note, then pilot topology review against current Science, health, and cancer projects.
4. Use the pilot to constrain `[t054]`: define only the computable v1 score and keep judgment-required signals as review prompts.
5. Let `[t056]` take shape from the pilot, especially the reviewer/cadence and provenance-contract requirements.

## Non-Goals

- Do not scaffold `~/d/bio/meta` from this spec alone.
- Do not automatically create, move, demote, or archive projects in v1.
- Do not collapse biological modeling into Science/meta.
- Do not treat graph density alone as evidence of project-worthiness.
- Do not use LLM-estimated importance as a substitute for inspectable signals.
