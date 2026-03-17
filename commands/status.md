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
3. If present, read `docs/claim-and-evidence-model.md`.

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
science-tool graph uncertainty --format json
science-tool graph gaps --format json
```

2. Surface:
- contested claims
- single-source claims
- low-confidence claims
- high-uncertainty neighborhoods
- structurally fragile areas

3. Prefer this section over simplistic “supported vs refuted” summaries.

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

## Output Format

Use rich terminal output:
- section headers
- tables where useful
- compact graph summaries when relevant

## Optional `--save`

If `$ARGUMENTS` contains `--save`:
- save to `doc/meta/status-snapshot-YYYY-MM-DD.md`
- commit the snapshot
