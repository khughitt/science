---
description: Show a curated project orientation — hypotheses, open questions, recent activity, staleness warnings, and next steps. Use at the start of a session, when returning to a project, or when the user says "where are we", "what's the status", "catch me up", or "project overview".
---

# Project Status

Print a curated orientation for the current research project. Output goes to the terminal (not saved to file) unless `$ARGUMENTS` contains `--save`.

## Setup

1. Read `specs/research-question.md` for project context.
2. Read `science.yaml` for project metadata.

No skills or role prompts needed — this is a read-only summary command.

## Sections

Produce each section below. Skip any section whose data source doesn't exist. Keep total output under ~100 lines.

### 1. Project Identity

From `science.yaml` and `specs/research-question.md`:

- Project name and status
- Research question (1-2 sentences)
- Tags

### 2. Hypotheses

From `specs/hypotheses/*.md`:

- List each hypothesis with its ID, short title, and status
- Group by status: `under-investigation` first, then `proposed`, then `supported`/`refuted`/`revised`
- If no hypotheses exist, note this and suggest `/science:add-hypothesis`

### 3. Open Questions

From `doc/questions/*.md`:

- List top 5 by priority (high > medium > low)
- Show priority, type, and the question text (truncated to one line)
- If no questions exist, note this

### 4. Recent Activity

Run: `git log --oneline -10 --format="%h %s (%cr)"`

- Show the last 10 commits with relative dates
- Group by scope prefix if possible (doc, papers, hypothesis, plan, etc.)

### 5. Staleness Warnings

Check file modification times:

- Flag `tasks/active.md` if not modified in >14 days
- Flag `specs/hypotheses/` files if none modified in >30 days
- If `knowledge/graph.trig` exists, check whether docs have been modified since the last `graph stamp-revision`
- If nothing is stale, skip this section

### 6. Document Inventory

Count files in each doc subdirectory:

- `doc/topics/` — N topic documents
- `doc/papers/` — N paper summaries
- `doc/questions/` — N open questions
- `doc/methods/` — N method notes
- `doc/datasets/` — N dataset notes
- `doc/searches/` — N literature searches
- `doc/discussions/` — N discussions
- `doc/interpretations/` — N interpretations
- `specs/hypotheses/` — N hypotheses

Skip directories with 0 files. Show totals on one line each.

### 7. Knowledge Graph Core

When `knowledge/graph.trig` exists:

1. Run `science-tool graph stats --format json` for entity/edge counts.
2. Identify the ~5-10 most central entities connected to the research question, treatment/outcome nodes, and hypothesis-linked entities. Prefer semantic centrality over raw degree.
3. Render as a Mermaid diagram:
   ```mermaid
   graph LR
     A[Treatment] -->|causes| B[Outcome]
     C[Confounder] -->|confounds| A
     C -->|confounds| B
   ```
4. For terminal-only contexts, use compact text: `A --causes--> B`
5. Prioritize causal (`scic:causes`) and evidence (`cito:supports`, `cito:disputes`) edges over metadata edges.

When no graph exists, print: "No knowledge graph yet. Run `/science:create-graph` to build one."

### 8. Next Steps

From `tasks/active.md`:

- Show P0 and P1 tasks (top 5 items)
- Note any blocked tasks
- If no tasks file exists, note this and suggest `/science:tasks add`

## Output Format

Use **rich formatting** for terminal output:

- Section headers as `## Section Name`
- Tables for hypotheses and questions
- Bullet lists for activity and inventory
- Mermaid code block for graph visualization

## Optional: `--save`

If `$ARGUMENTS` contains `--save`:
- Save the output to `doc/meta/status-snapshot-YYYY-MM-DD.md`
- Create `doc/meta/` if it doesn't exist
- Commit: `git add doc/meta/ && git commit -m "doc: save status snapshot"`
