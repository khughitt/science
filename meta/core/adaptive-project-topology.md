# Adaptive Project Topology

This note is the durable operating model for `question:0014-adaptive-project-topology`.
It replaces the active role of `doc/plans/historical/2026-05-17-adaptive-project-topology-and-bio-meta-next-steps.md`.

## Status

- Owner: `~/d/science/meta`
- Current mode: manual-first decision support
- Related question: `question:0014-adaptive-project-topology`
- Related hypothesis: `hypothesis:0006-adaptive-project-topology-improves-research-fit`
- Completed setup tasks: `t054`, `t056`
- Remaining pilot task: `t057`

Adaptive topology asks when the Science project graph should change shape.
The first version is not automation: it produces reviewable recommendations
for human approval. Automatic project creation, pruning, demotion, or migration
waits until dry-run recommendations have been compared against known topology
harms.

## Objects

| Object | Meaning | Candidate action |
|---|---|---|
| Theme | A recurring topic or cluster inside one or more projects. | Keep as topic, promote, merge, or make commons resource. |
| Project idea | A theme with enough coherence to plausibly become a Science project. | Write project brief; run topology audit. |
| Project | A Science-managed repo with its own questions, tasks, graph, and docs. | Keep active, split, merge, demote, or archive. |
| Commons resource | A reusable method, dataset, schema, model, or workflow used by multiple projects. | Promote to `~/d/science-commons` once that system exists. |
| Topology recommendation | A proposed structural change with evidence, tradeoffs, and approval status. | Dry-run report first; apply only after review. |

## V1 Signal Rubric

V1 separates computable signals from reviewer prompts. Computable signals can
rank candidates for review; they do not decide topology changes.

Scoreable signals from existing artifacts:

- **Entity density:** linked papers, summaries, questions, hypotheses, tasks,
  datasets, reports, and evidence artifacts.
- **Graph connectivity:** incoming and outgoing links, cross-project refs,
  `bears_on` edges, stale-input counts, and unresolved-reference counts.
- **Backlog pressure:** task count, priority distribution, blocked/proposed/
  active status, and repeated task-group references.
- **Recency and decay:** commit recency, document `updated` recency, stale
  graph inputs, and time since last meaningful task or report.
- **Reuse signals:** repeated references from multiple projects,
  commons-candidate flags, and repeated routing decisions in paper manifests.

Reviewer prompts stay qualitative in v1:

- **Uncertainty gradient:** are unresolved questions high-information rather
  than merely numerous?
- **Novelty:** did recent papers or datasets introduce a genuinely new
  direction?
- **Actionability:** are datasets, methods, or workflows available now?
- **Coherence:** does the cluster have a clear research question and boundary?
- **False-positive risk:** would the change duplicate a project, overfit one
  literature batch, or create maintenance burden?
- **Provenance cost:** can references, graph nodes, decisions, task history,
  and paper provenance remain traceable after the change?

## Recommendation Workflow

The v1 workflow is a dry-run report with one recommendation per candidate
cluster or project.

Recommended cadence:

- monthly as part of a Science/meta topology review;
- additionally after large paper-triage batches, commons-promotion candidates,
  or `science-curate` / `science-next-steps` runs that surface cross-project
  ambiguity.

Ownership:

- `~/d/science/meta` owns the report format, cadence, and recommendation
  record.
- Affected domain projects approve changes that alter their scope, tasks, or
  parent/peer links.

Allowed recommendation types:

- promote theme to project
- split project into child projects
- merge project into parent or sibling
- demote project to topic/theme
- archive stale branch
- create commons resource
- create cross-project synthesis task
- leave unchanged

Each recommendation records:

- target cluster or project;
- triggering signals;
- counter-signals;
- proposed destination;
- required human decision;
- provenance-preserving links to maintain;
- tasks that would be created if accepted.

The workflow does not delete, move, or scaffold anything automatically in v1.
Even stale projects may be needed as provenance anchors.

## Provenance Contract

Demotion and merge recommendations are incomplete unless they name destinations
for graph nodes, decisions, task history, paper summaries, and replacement
links.

Minimum v1 contract:

- Stable entity IDs remain resolvable, either in the original archived project
  or through an explicit alias/archive map.
- Graph nodes from demoted projects are not deleted; they are marked archived,
  superseded, or moved behind a stable cross-reference.
- Decisions move or copy to the destination only when still load-bearing;
  otherwise they are archived with a replacement pointer.
- Task history stays in the original task archive; destination projects get new
  follow-up tasks that cite original task IDs.
- Paper summaries and source refs keep original provenance; promoted syntheses
  may cite them but do not rewrite source history.
- Parent/peer links change only through a reviewed migration note.

## Pilot Protocol

`t057` is the remaining pilot task. It should start with a short
baseline-of-harm note before scoring candidates.

Candidate harms to inspect:

- work landing in the wrong repo because two projects both look like the
  world-model home;
- topics duplicated across projects without a clear owner;
- cross-project sync or paper-triage passes re-deriving the same conceptual
  model;
- commons candidates accumulating in domain projects because
  `~/d/science-commons` is not initialized;
- child-project parenthood becoming ambiguous when a theme is both biological
  substrate and applied health lens.

Pilot scope:

- `~/d/science/meta`
- `~/d/health/meta`
- cycles projects
- cancer-evolution
- pre-cancer
- pan-disease

Pilot output:

- baseline harms found or not found;
- dry-run recommendations;
- false positives and false negatives;
- reviewer overrides;
- provenance blockers;
- smallest useful v1 score and recommendation fields.

The pilot should compare recommendations against the baseline: would the
recommendation have reduced a known cost, or is it merely a plausible
reorganization?
