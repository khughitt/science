---
description: Show a curated project orientation — active hypotheses, open questions, uncertainty hotspots, recent activity, and next steps. Use at the start of a session or when the user says "where are we", "what's the status", or "catch me up".
---

# Project Status

Print a curated orientation for the current research project.

The default stance is skeptical:
- hypotheses are organizing conjectures
- claims carry uncertainty
- evidence updates belief
- sparse or contested regions deserve attention

Output goes to the terminal unless `$ARGUMENTS` contains `--save`.

## Setup

1. Read `specs/research-question.md`.
2. Read `science.yaml`.
3. If present, read `${CLAUDE_PLUGIN_ROOT}/docs/proposition-and-evidence-model.md`.

## Sections

Keep output under ~100 lines.

### 1. Project Identity

From `science.yaml` and `specs/research-question.md`:
- project name and status
- research question
- tags

### 2. Active Hypotheses

From `specs/hypotheses/*.md`:
- list each hypothesis with ID, short title, and current status
- describe it briefly as an organizing conjecture, not a proven result
- highlight which ones are under active investigation

### 3. Open Questions

From `doc/questions/*.md`:
- list the top 5 by priority
- include the question text and type

### 4. Claim And Graph Uncertainty

When `knowledge/graph.trig` exists:

1. Run:

```bash
science-tool graph project-summary --format json
science-tool graph question-summary --format json  # full by default; add --top to narrow
science-tool graph inquiry-summary --format json
science-tool graph dashboard-summary --format json
science-tool graph neighborhood-summary --format json
science-tool graph uncertainty --format json
science-tool graph gaps --format json
```

For `software` projects, skip `project-summary` for now and start from `question-summary` / `inquiry-summary`.

2. Surface:
- research project summary
- high-priority questions from the full question rollup
- high-priority inquiries
- contested claims
- single-source claims
- claims lacking empirical data evidence
- evidence-type mix when relevant
- high-uncertainty neighborhoods
- structurally fragile areas

3. Prefer the higher-level drill path:
- `project-summary` for the top-level rollup on `research` projects only
- `question-summary` for the full question rollup; add `--top` to narrow it
- `inquiry-summary` for research-thread prioritization
- `dashboard-summary` and `neighborhood-summary` for exact weak points
- `uncertainty` and `gaps` as secondary support views rather than the main dashboard

4. If the graph does not expose claim-backed evidence summaries yet, say that the project appears only partially migrated and treat the uncertainty section as provisional.

Also run:

```bash
science-tool health --project-root . --format json
```

Surface, at minimum:

- proposition `claim_layer` coverage,
- causal-leaning proposition `identification_strength` coverage,
- unsupported mechanistic narratives still flagged by the migration helper,
- proxy-mediated propositions still missing `measurement_model`,
- rival-model packets missing discriminating predictions.

If high-impact claims still carry only one visible `independence_group`, call that out explicitly as a fragility note even if the project has not yet promoted it into a first-class dashboard metric.

### 5. Recent Activity

Run:

```bash
git log --oneline -10 --format="%h %s (%cr)"
```

Show recent project movement.

### 6. Staleness Warnings

Flag:
- stale tasks
- old untouched hypotheses
- graph/doc drift if the graph changed but interpretation/docs did not

**Cross-project sync staleness:**

Run `science-tool sync status` to check when the last cross-project sync was performed.
If sync is stale (over the configured threshold), mention it:

> Cross-project sync is N days stale. Run `/science:sync` to align with N other registered projects.

If the current project has new entities since last sync, also mention:

> This project has N new entities since last sync.

### 7. Document Inventory

Count key document classes:
- topics
- papers
- questions
- methods
- datasets
- discussions
- interpretations
- hypotheses

### 8. Next Steps

From tasks, graph uncertainty, and recent activity, show:
- the top few high-value next actions
- where uncertainty reduction is most likely to pay off
- blocked tasks or missing evidence
- which findings belong in `doc/reports/` or `doc/interpretations/`
- which follow-up actions should be added under `tasks/`

## Output Format

Use rich terminal output:
- section headers
- tables where useful
- compact graph summaries when relevant

## Optional `--save`

If `$ARGUMENTS` contains `--save`:
- save to `doc/meta/status-snapshot-YYYY-MM-DD.md`
- commit the snapshot
