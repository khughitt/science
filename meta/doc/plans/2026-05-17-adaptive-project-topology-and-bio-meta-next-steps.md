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

`[t054]` should define computable signals before any implementation.
Initial signal families:

- **Density:** number of linked papers, summaries, questions, hypotheses, tasks, datasets, reports, and evidence artifacts.
- **Connectivity:** incoming and outgoing graph links, cross-project references, shared concepts, and repeated downstream use.
- **Uncertainty gradient:** open questions, contested propositions, weak support, stale conclusions, and unresolved methodological risks.
- **Novelty:** recent literature influx, new datasets, new methods, new project-relevant concepts, or repeated mentions in reviews.
- **Actionability:** available data, tractable analyses, clear next tasks, and testable hypotheses.
- **Decay:** stale tasks, no recent commits, no downstream references, no active questions, and low revisiting priority.
- **Coherence:** whether the cluster has a clear research question and scope boundary, rather than just a bag of related notes.
- **False-positive risk:** whether promotion would create maintenance burden, duplicate an existing project, or overfit to one recent batch.

The rubric should distinguish **promotion evidence** from **promotion urgency**.
A theme may be dense but not urgent, or highly uncertain and actionable but still too small for a project.

## Recommendation Workflow

`[t056]` should design the workflow as a manual-first command or report.
The first version should produce a dry-run report with one recommendation per candidate cluster.

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
2. Complete `[t054]`: turn the signal rubric into a scoring table with examples from current projects.
3. Complete `[t058]`: write the `~/d/bio/meta` project brief.
4. Use `[t057]` to pilot the rubric on existing projects before implementing any command.
5. Only after the pilot, decide whether `[t056]` should become a Science CLI design or remain a recurring review procedure.

## Non-Goals

- Do not scaffold `~/d/bio/meta` from this spec alone.
- Do not automatically create, move, demote, or archive projects in v1.
- Do not collapse biological modeling into Science/meta.
- Do not treat graph density alone as evidence of project-worthiness.
- Do not use LLM-estimated importance as a substitute for inspectable signals.
