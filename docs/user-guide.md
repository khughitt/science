# Science User Guide

Science helps Claude and Codex users keep research work explicit, skeptical,
and durable. It records questions, hypotheses, propositions, evidence,
inquiries, tasks, and graph summaries in version-controlled project files.

This guide follows one possible path through a project:

```text
question -> hypothesis -> proposition -> evidence lines -> graph build ->
dashboard summary -> causal inquiry / analysis planning -> validation / health
```

That path is a teaching spine, not a required order. Real research is nonlinear:
you may start from a paper, a dataset, an existing hypothesis, a failed
analysis, a causal concern, or a health-check warning, then loop through the
same concepts in a different order.

## What Science Helps You Do

Science turns Claude and Codex into research workflow partners that can work
inside a durable project structure. The agent workflows are the primary user
interface; the `science` CLI is the project tooling layer they call when work
needs to create files, validate structure, build graphs, summarize evidence, or
inspect project health.

Science is skeptical by default. It helps you surface disagreement, missing
evidence, fragility, and alternative explanations rather than collect only
confirming notes. Evidence supports or disputes propositions; it does not prove
them outright. Literature provenance, data provenance, causal assumptions, and
belief snapshots are part of the project record.

## Install And Start

Claude users invoke Science as slash commands:

```text
/science:<command>
```

Codex users invoke generated skills:

```text
science-<command>
```

For Codex setup and the generated skill index, see
[`docs/README.codex.md`](README.codex.md).

The CLI form is:

```text
science <group> <command>
```

Common invocation patterns:

| Intent | Claude | Codex | CLI |
|---|---|---|---|
| Sketch a model | `/science:sketch-model` | `science-sketch-model` | `science inquiry ...` |
| Pre-register expectations | `/science:pre-register` | `science-pre-register` | source-authored document workflow |
| Stress-test bias | `/science:bias-audit` | `science-bias-audit` | source-authored document workflow |
| Add durable evidence | workflow-guided | workflow-guided | `science entity create evidence-line ...` |
| Build graph | `/science:create-graph` or `/science:update-graph` | `science-create-graph` or `science-update-graph` | `science graph build` |
| Summarize belief/evidence | `/science:status` | `science-status` | `science graph dashboard-summary` |

## Project Layout And Aspects

Most users work in a small set of project roots:

- `science.yaml`: project manifest, profile, peers, ontologies, and aspects.
- `AGENTS.md` / `CLAUDE.md`: operational instructions for agents.
- `doc/`: background notes, paper summaries, interpretations, discussions,
  reports, datasets, and other research documents.
- `specs/`: hypotheses, propositions, plans, and other structured project
  specifications.
- `tasks/`: active, blocked, deferred, retired, and completed work.
- `knowledge/`: generated graph files, summaries, and belief snapshots.
- `papers/references.bib`: bibliography entries for cited literature.
- `.ai/`: optional project-specific prompts, templates, and overrides.

Science supports `research` and `software` project profiles. For full profile
rules and migration guidance, see
[`docs/project-organization-profiles.md`](project-organization-profiles.md).

Aspects are project-context modifiers declared in `science.yaml`. They tailor
command behavior to the research context without changing the core project
layout. Common aspects include `causal-modeling`, `hypothesis-testing`,
`computational-analysis`, and `software-development`.

## The Reasoning Model

Science keeps the reasoning model explicit:

- `question`: what the project wants to learn.
- `hypothesis`: an organizing conjecture.
- `proposition`: a belief-bearing assertion.
- `observation`: a concrete empirical finding.
- `evidence-line`: durable support or dispute with stance, source, strength,
  role, and independence.
- `inquiry`: a graph-backed work program for questions, variables,
  assumptions, propositions, datasets, transformations, and decisions.

Authored state lives in source files. Derived graph and belief state should be
recomputed from those sources. Support, dispute, contestation, fragility, and
provenance are first-class concerns, not hidden notes.

For field-level details, use
[`docs/proposition-and-evidence-model.md`](proposition-and-evidence-model.md)
as the source of truth; this guide teaches the workflow layer.

## A First Research Loop

This example uses portable `science` CLI commands as the durable artifact
spine. In normal use, Claude or Codex may guide you through the same steps with
workflow commands and generated prompts.

Start with a question:

```bash
science question create "Does sleep extension improve next-day reaction time in chronically sleep-restricted adults?" --id question:q01-sleep-extension-reaction-time
```

Add a hypothesis as the organizing conjecture:

```bash
science hypothesis create "Sleep extension improves next-day reaction time in chronically sleep-restricted adults" --id hypothesis:h01-sleep-extension-reaction-time --related question:q01-sleep-extension-reaction-time
```

Create a proposition as the belief-bearing assertion:

```bash
science proposition create "Sleep extension improves next-day reaction time in chronically sleep-restricted adults" --id proposition:p01-sleep-extension-reaction-time --related hypothesis:h01-sleep-extension-reaction-time
```

Add a durable evidence-line shell:

```bash
science entity create evidence-line "Pilot trial reports faster reaction time after sleep extension" --id evidence-line:sleep-extension-reaction-time-pilot --related proposition:p01-sleep-extension-reaction-time --source-ref cite:example2024sleep
```

The first generated entity of a kind may require `--id` because Science cannot
derive a sibling numbering convention until one exists. After creation, edit
the evidence-line file before building the graph. The important frontmatter
fields are:

```yaml
stance: supports
target: proposition:p01-sleep-extension-reaction-time
source: cite:example2024sleep
evidence_type: empirical_data_evidence
strength: moderate
independence: independent
independence_group: sleep-extension-reaction-time-pilot
evidence_role: direct_test
```

The citation key should exist in `papers/references.bib`, for example through
`science bib add`. The evidence-line body should state what the line shows, why
it is independent, and the caveats or scope limits. Build only after the line
has stance, source, evidence type, strength, role, and independence recorded;
otherwise validation and summaries can report unscored or unstanced evidence.

Then build the graph and inspect the evidence dashboard:

```bash
science graph build
science graph dashboard-summary
```

For durable evidence, prefer source-authored entities such as
`science proposition create` and `science entity create evidence-line ...`.
Direct graph mutation commands are not the durable path for evidence that
should survive the next graph build.

### Stress-Test Before You Settle

Use rigor workflows when the example reaches predictions, alternatives,
assumptions, or bias risks:

- `pre-register`: make expectations and decision criteria explicit before
  analysis.
- `compare-hypotheses`: force competing explanations into a head-to-head
  comparison.
- `discuss`: run structured critical discussion for assumptions, gaps, and
  alternatives.
- `bias-audit`: check for cognitive and methodological bias.

Claude users invoke these as `/science:pre-register`,
`/science:compare-hypotheses`, `/science:discuss`, and
`/science:bias-audit`. Codex users invoke `science-pre-register`,
`science-compare-hypotheses`, `science-discuss`, and `science-bias-audit`.

## Graphical Questions And Causal Work

An inquiry is a graph-backed work program. It connects questions, hypotheses,
propositions, variables, assumptions, transformations, datasets, and decisions.
Use `/science:sketch-model` or `science-sketch-model` when you want the agent
to sketch the inquiry with you.

When a causal question is involved, causal edges are not settled facts. Treat
them as assumptions or uncertain propositions that need provenance and evidence.
Typical CLI operations include:

```bash
science inquiry init <slug> "<title>"
science inquiry add-node <inquiry> <node-id> --kind variable --label "<label>"
science inquiry add-edge <inquiry> <source-node> <target-node> --predicate causes
science inquiry set-estimand <inquiry> --treatment <node-id> --outcome <node-id>
science inquiry validate <inquiry>
```

For modeling scaffolds, use `science inquiry export-pgmpy` or
`science inquiry export-chirho` when those libraries fit the analysis. Keep the
causal identification limits, measurement limits, and missing confounders in
the authored inquiry or linked propositions.

## Planning Analyses And Interpreting Results

Use `/science:plan-analysis`, `/science:plan-pipeline`, and
`/science:review-pipeline` to turn an inquiry into computation. These workflows
should define inputs, assumptions, validation checks, outputs, and review
criteria before the work is treated as evidential.

A successful notebook, script, or pipeline run is not automatically a belief
update. Use `/science:interpret-results` or `science-interpret-results` to
interpret the output as support, dispute, a null result, or scoped uncertainty.
When a result relates to a pre-registration, compare the observed result to the
pre-registered expectation and record the limits of what the result can decide.

## Maintaining Project Health

Run validation and health checks regularly:

```bash
science validate
science health
science entity needs-review
science belief snapshot
```

Validation protects durable evidence, explicit references, non-silent
uncertainty, and reproducible project structure. Health checks aggregate
diagnostics such as unresolved refs, graph migration issues, invalid aspects,
and related hygiene.

Freshness and `needs-review` are attention surfaces, not hard gates. They help
you decide which entities deserve another look after upstream evidence,
datasets, code, or propositions change.

`science belief snapshot` appends reproducible belief-state rollups to
`knowledge/belief-snapshots.jsonl`. Use snapshots at review milestones when you
want to preserve the state of support, dispute, fragility, and contestation.

## Cross-Project Work

Science projects can recognize peers, compose graphs, and synchronize shared
knowledge. Peers are declared project namespaces in `science.yaml`.

Useful inspection commands:

```bash
science peers list
science peers check
science sync status
```

Use `science sync projects` and `science sync run` when you are ready to inspect
or run cross-project synchronization. For the detailed model, see
[`docs/federation.md`](federation.md).

## Cheat Sheet

Use this as a quick reminder once the concepts are familiar.

| Intent | Claude / Codex workflow | Core CLI |
|---|---|---|
| Start or adopt a project | `/science:create-project`, `/science:import-project`; `science-create-project`, `science-import-project` | project-local setup and `science validate` |
| Orient and plan | `/science:status`, `/science:next-steps`; `science-status`, `science-next-steps` | `science tasks list`, `science tasks summary` |
| Build background knowledge | `/science:research-topic`, `/science:search-literature`, `/science:research-papers`; Codex `science-*` equivalents | `science bib add` |
| Structure hypotheses and uncertainty | `/science:add-hypothesis`, `/science:pre-register`, `/science:compare-hypotheses`, `/science:discuss`, `/science:bias-audit` | `science hypothesis create`, `science question create` |
| Represent propositions and evidence | workflow-guided proposition/evidence authoring | `science proposition create`, `science entity create evidence-line ...` |
| Model inquiries and causality | `/science:sketch-model`, `/science:specify-model`, `/science:critique-approach` | `science inquiry init`, `science inquiry validate`, `science inquiry set-estimand` |
| Plan and interpret computation | `/science:plan-analysis`, `/science:plan-pipeline`, `/science:review-pipeline`, `/science:interpret-results` | source-authored interpretations and validation |
| Maintain graph and project health | `/science:create-graph`, `/science:update-graph`, `/science:health` | `science graph build`, `science graph dashboard-summary`, `science validate`, `science health`, `science belief snapshot` |
| Work across projects | `/science:sync` | `science peers list`, `science peers check`, `science sync status`, `science sync run` |
