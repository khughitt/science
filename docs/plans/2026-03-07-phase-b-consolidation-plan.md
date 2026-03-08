# Phase B: Consolidate Docs + Streamline Preambles

> **Status: COMPLETE** — All 17 tasks implemented 2026-03-07.

**Goal:** Merge the notes/summaries dual-layer system into a single doc-per-entity structure under `doc/`, create a shared command preamble, and update all commands to use the new paths and streamlined setup sections.

**Architecture:** Templates get YAML frontmatter merged from note templates. Commands reference a shared preamble file plus command-specific setup. The `create-project` scaffold produces the new directory layout. A `notes-organization.md` reference is replaced by the new structure being self-documenting.

**Tech Stack:** Markdown files only — no code changes in this phase.

---

### Task 1: Create merged templates (papers)

**Files:**
- Modify: `templates/paper-summary.md`
- Delete: `templates/notes/article-note.md`

**Step 1: Read both templates**

Read `templates/paper-summary.md` and `templates/notes/article-note.md` to understand the merge.

**Step 2: Add YAML frontmatter to paper-summary template**

Merge the article-note frontmatter into the paper-summary template. The result should have YAML frontmatter at the top (from article-note) followed by the existing paper-summary body. Keep all existing paper-summary sections intact.

New `templates/paper-summary.md`:

```markdown
---
id: "paper:{{bibtex_key}}"
type: "paper"
title: "{{Title}}"
status: "active"
tags: []
ontology_terms: []
datasets: []
source_refs:
  - "cite:{{bibtex_key}}"
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---

# {{Title}}

- **Authors:** {{authors}}
- **Year:** {{year}}
- **Journal:** {{journal}}
- **DOI/URL:** {{url}}
- **BibTeX key:** {{bibtex_key}}
- **Source:** LLM knowledge | web search | PDF

## Key Contribution

<!-- 2-3 sentences: what is the main claim or result? -->

## Methods

<!-- What approach did they use? What data? What key assumptions? -->

## Key Findings

<!-- The specific results that matter for our project -->

## Relevance

<!-- How does this connect to our research questions/hypotheses? Reference hypothesis IDs. -->

## Limitations

<!-- What did they NOT address? Questionable assumptions? Known weaknesses? -->

## Follow-up

<!-- Papers to read next. Questions this raises for our project. -->
```

**Step 3: Delete the article-note template**

Delete `templates/notes/article-note.md`.

**Step 4: Commit**

```bash
git add templates/paper-summary.md
git rm templates/notes/article-note.md
git commit -m "refactor: merge article-note frontmatter into paper-summary template"
```

---

### Task 2: Create merged templates (topics)

**Files:**
- Modify: `templates/background-topic.md`
- Delete: `templates/notes/topic-note.md`

**Step 1: Add YAML frontmatter to background-topic template**

New `templates/background-topic.md`:

```markdown
---
id: "topic:{{slug}}"
type: "topic"
title: "{{Title}}"
status: "active"
tags: []
ontology_terms: []
datasets: []
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---

# {{Title}}

## Summary

<!-- 2-3 sentence overview of this topic and why it matters for the project -->

## Key Concepts

<!-- Define essential terms and frameworks. Be precise — these definitions may be referenced by other documents. -->

## Current State of Knowledge

<!-- What is well-established? What's the consensus view? Cite key references. -->

## Controversies & Open Questions

<!-- Where do experts disagree? What remains unknown? -->

## Relevance to This Project

<!-- How does this topic connect to our research question and hypotheses? Reference specific hypothesis IDs where applicable. -->

## Key References

<!-- Cite the most important 3-5 papers. Full entries must exist in papers/references.bib -->
```

**Step 2: Delete the topic-note template**

Delete `templates/notes/topic-note.md`.

**Step 3: Commit**

```bash
git add templates/background-topic.md
git rm templates/notes/topic-note.md
git commit -m "refactor: merge topic-note frontmatter into background-topic template"
```

---

### Task 3: Relocate remaining note templates

**Files:**
- Move: `templates/notes/question-note.md` → `templates/question.md`
- Move: `templates/notes/method-note.md` → `templates/method.md`
- Move: `templates/notes/dataset-note.md` → `templates/dataset.md`
- Delete: `templates/notes/index.md`
- Delete: `templates/notes/` directory

**Step 1: Move and rename each template**

```bash
git mv templates/notes/question-note.md templates/question.md
git mv templates/notes/method-note.md templates/method.md
git mv templates/notes/dataset-note.md templates/dataset.md
git rm templates/notes/index.md
```

Verify `templates/notes/` is empty, then remove it.

**Step 2: Commit**

```bash
git commit -m "refactor: flatten note templates into templates/"
```

---

### Task 4: Update `create-project` scaffold directory structure

**Files:**
- Modify: `commands/create-project.md`

**Step 1: Read `commands/create-project.md`**

**Step 2: Replace the directory tree**

Replace the old tree with the new layout. Key changes:

Old:
```
├── doc/
│   ├── background/
│   ├── discussions/
│   ├── 01-overview.md ... 08-open-questions.md ... 10-research-gaps.md
├── papers/
│   ├── references.bib
│   ├── pdfs/
│   └── summaries/
├── notes/
│   ├── index.md
│   ├── topics/ articles/ questions/ methods/ datasets/
```

New:
```
├── doc/
│   ├── topics/
│   ├── papers/
│   ├── questions/
│   ├── methods/
│   ├── datasets/
│   ├── searches/
│   ├── discussions/
│   ├── interpretations/
│   ├── index.md
│   ├── 01-overview.md
│   ├── 02-background.md
│   ├── 03-model.md
│   ├── 04-approach.md
│   ├── 05-data.md
│   ├── 06-evaluation.md
│   ├── 09-causal-model.md
│   └── 99-next-steps.md
├── papers/
│   ├── references.bib
│   └── pdfs/
```

Removed from scaffold:
- `papers/summaries/` (replaced by `doc/papers/`)
- `notes/` (entire directory — replaced by `doc/` subdirs)
- `doc/background/` (replaced by `doc/topics/`)
- `doc/07-hypotheses.md` (generated from `specs/hypotheses/`)
- `doc/08-open-questions.md` (replaced by `doc/questions/`)
- `doc/10-research-gaps.md` (generated by `research-gaps` command)

Added to scaffold:
- `doc/topics/`, `doc/papers/`, `doc/questions/`, `doc/methods/`, `doc/datasets/`
- `doc/searches/`, `doc/interpretations/`
- `doc/index.md`

**Step 3: Update scaffold file contents**

Update the `notes/index.md` scaffold section to become the `doc/index.md` scaffold:

```markdown
# Document Index

## Topics
<!-- doc/topics/*.md -->

## Papers
<!-- doc/papers/*.md -->

## Hypotheses
<!-- specs/hypotheses/*.md -->

## Questions
<!-- doc/questions/*.md -->

## Methods
<!-- doc/methods/*.md -->

## Datasets
<!-- doc/datasets/*.md -->
```

Remove the `notes/index.md` scaffold section and the `notes-organization.md` reference.

**Step 4: Update scaffold for CLAUDE.md template references**

Any reference in the CLAUDE.md scaffold content to old paths needs updating.

**Step 5: Commit**

```bash
git add commands/create-project.md
git commit -m "refactor: update create-project scaffold for consolidated doc structure"
```

---

### Task 5: Create shared command preamble

**Files:**
- Create: `references/command-preamble.md`

**Step 1: Write the shared preamble**

```markdown
# Command Preamble

Before executing any research command:

1. Load role prompt: `prompts/roles/<role>.md` if present,
   else `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/<role>.md`.
2. Load the `research-methodology` and `scientific-writing` skills.
3. Read `specs/research-question.md` for project context.
```

**Step 2: Commit**

```bash
git add references/command-preamble.md
git commit -m "refactor: add shared command preamble"
```

---

### Task 6: Update `research-topic` command

**Files:**
- Modify: `commands/research-topic.md`

**Step 1: Read the current file**

**Step 2: Rewrite with new paths and streamlined preamble**

```markdown
---
description: Research and summarize a scientific topic with project-context linking.
---

# Research a Topic

Write a structured background synthesis on the topic specified by `$ARGUMENTS`.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `templates/background-topic.md`.
2. Check `doc/topics/` for existing coverage; ask before overwriting.
3. Check `doc/papers/` for relevant summaries.

## Research Process

1. Start from LLM knowledge and draft core concepts, active debates, and project relevance.
2. Use web search to verify key references and capture recent changes.
3. Do not read PDFs unless user provides a file path.

## Writing

Follow `templates/background-topic.md` and fill all sections.
Save to `doc/topics/<topic-slug>.md`.

The output should include:

- Key subtopics and how they connect.
- What is well-established vs uncertain.
- Links to existing hypotheses and open questions.
- Suggested follow-up research tasks.

## After Writing

1. Add new references to `papers/references.bib` (create with header if missing).
2. Add newly surfaced questions to `doc/questions/` using `templates/question.md`.
3. Update `RESEARCH_PLAN.md` with follow-up tasks derived from the synthesis.
4. Commit: `git add -A && git commit -m "doc: research topic <topic>"`

## Process Reflection

[keep existing Process Reflection section unchanged]
```

Key changes:
- `doc/background/NN-topic.md` → `doc/topics/<topic-slug>.md`
- `papers/summaries/` → `doc/papers/`
- `doc/08-open-questions.md` → `doc/questions/` + template
- Removed `notes/topics/` creation step
- Removed `notes-organization.md` reference
- Removed `templates/notes/topic-note.md` reference
- Removed "Compatibility Note" section
- Preamble uses shared reference
- Dropped sequential numbering

**Step 3: Commit**

```bash
git add commands/research-topic.md
git commit -m "refactor: update research-topic for consolidated doc structure"
```

---

### Task 7: Update `research-paper` command

**Files:**
- Modify: `commands/research-paper.md`

**Step 1: Read the current file**

**Step 2: Rewrite with new paths and streamlined preamble**

Key changes:
- `papers/summaries/AuthorYear-short-title.md` → `doc/papers/<citekey>.md`
- `notes/articles/<citekey>.md` → removed (merged into paper doc)
- `doc/08-open-questions.md` → `doc/questions/` + template
- Preamble uses shared reference
- Removed "Compatibility Note" section
- Removed `notes-organization.md` and `notes/articles/` references

Save path becomes `doc/papers/<citekey>.md` (e.g., `doc/papers/Smith2024-causal-inference-review.md`).

**Step 3: Commit**

```bash
git add commands/research-paper.md
git commit -m "refactor: update research-paper for consolidated doc structure"
```

---

### Task 8: Update `search-literature` command

**Files:**
- Modify: `commands/search-literature.md`

**Step 1: Read the current file**

**Step 2: Update paths**

Key changes:
- `papers/summaries/` → `doc/papers/`
- `notes/articles/<citekey>.md` → `doc/papers/<citekey>.md`
- `notes/topics/`, `notes/questions/` → `doc/topics/`, `doc/questions/`
- `doc/07-hypotheses.md` → `specs/hypotheses/`
- `doc/08-open-questions.md` → `doc/questions/`
- `papers/searches/` → `doc/searches/`
- Remove first-use compatibility scaffolding
- Remove `notes-organization.md` reference
- Preamble uses shared reference

**Step 3: Commit**

```bash
git add commands/search-literature.md
git commit -m "refactor: update search-literature for consolidated doc structure"
```

---

### Task 9: Update `add-hypothesis` command

**Files:**
- Modify: `commands/add-hypothesis.md`

**Step 1: Read the current file**

**Step 2: Update paths and streamline**

Key changes:
- `doc/08-open-questions.md` → `doc/questions/`
- `doc/07-hypotheses.md` → drop (hypotheses are in `specs/hypotheses/`; index is generated)
- Preamble uses shared reference

**Step 3: Commit**

```bash
git add commands/add-hypothesis.md
git commit -m "refactor: update add-hypothesis for consolidated doc structure"
```

---

### Task 10: Update `discuss` command

**Files:**
- Modify: `commands/discuss.md`

**Step 1: Read the current file**

**Step 2: Update paths and streamline**

Key changes:
- `doc/08-open-questions.md` → `doc/questions/`
- `doc/background/` → `doc/topics/`
- Preamble uses shared reference

**Step 3: Commit**

```bash
git add commands/discuss.md
git commit -m "refactor: update discuss for consolidated doc structure"
```

---

### Task 11: Update `research-gaps` command

**Files:**
- Modify: `commands/research-gaps.md`

**Step 1: Update paths and streamline**

Key changes:
- `doc/background/` → `doc/topics/`
- `doc/07-hypotheses.md` → `specs/hypotheses/`
- `doc/08-open-questions.md` → `doc/questions/`
- `papers/summaries/` → `doc/papers/`
- `doc/10-research-gaps.md` → keep this path (it's a generated report, not entity-per-file)
- Preamble uses shared reference

**Step 2: Commit**

```bash
git add commands/research-gaps.md
git commit -m "refactor: update research-gaps for consolidated doc structure"
```

---

### Task 12: Update `interpret-results` command

**Files:**
- Modify: `commands/interpret-results.md`

**Step 1: Update paths**

Key changes:
- `doc/08-open-questions.md` → `doc/questions/`
- Preamble uses shared reference

**Step 2: Commit**

```bash
git add commands/interpret-results.md
git commit -m "refactor: update interpret-results for consolidated doc structure"
```

---

### Task 13: Update remaining commands with old paths

**Files:**
- Modify: `commands/summarize-topic.md` (add deprecation notice)
- Modify: `commands/summarize-paper.md` (add deprecation notice)
- Modify: `commands/review-tasks.md`
- Modify: `commands/build-dag.md`
- Modify: `commands/sketch-model.md`
- Modify: `commands/create-graph.md`
- Modify: `commands/critique-approach.md`

**Step 1: Add deprecation notices to alias commands**

For `summarize-topic.md` and `summarize-paper.md`, replace the body with:

```markdown
---
description: "[DEPRECATED] Use /science:research-topic instead."
---

# Summarize Topic (Deprecated)

This command has been replaced by `/science:research-topic`.
Please use that command instead.
```

(Same pattern for `summarize-paper.md` pointing to `research-paper`.)

**Step 2: Update paths in remaining commands**

For each command, update:
- `doc/08-open-questions.md` → `doc/questions/`
- `doc/07-hypotheses.md` → `specs/hypotheses/`
- `doc/background/` → `doc/topics/`
- `papers/summaries/` → `doc/papers/`
- `notes/` references → corresponding `doc/` paths

**Step 3: Commit**

```bash
git add commands/summarize-topic.md commands/summarize-paper.md commands/review-tasks.md commands/build-dag.md commands/sketch-model.md commands/create-graph.md commands/critique-approach.md
git commit -m "refactor: update remaining commands for consolidated doc structure"
```

---

### Task 14: Update skills and references

**Files:**
- Modify: `skills/writing/SKILL.md`
- Modify: `skills/research/SKILL.md`
- Modify: `skills/data/SKILL.md`
- Modify: `references/project-structure.md`
- Modify: `references/claude-md-template.md`
- Modify: `references/role-prompts/research-assistant.md`
- Modify: `references/role-prompts/discussant.md`
- Delete: `references/notes-organization.md`

**Step 1: Update each file**

For each file, replace old paths with new paths. Key substitutions:

| Old | New |
|---|---|
| `papers/summaries/` | `doc/papers/` |
| `doc/background/` | `doc/topics/` |
| `doc/08-open-questions.md` | `doc/questions/` |
| `doc/07-hypotheses.md` | `specs/hypotheses/` |
| `notes/articles/` | `doc/papers/` |
| `notes/topics/` | `doc/topics/` |
| `notes/questions/` | `doc/questions/` |
| `notes/methods/` | `doc/methods/` |
| `notes/datasets/` | `doc/datasets/` |

**Step 2: Rewrite `references/project-structure.md`**

Update the directory tree and descriptions to match the new layout.
Remove the `notes/` section entirely.
Update the `doc/` section to describe the new subdirectories.
Remove reference to `notes-organization.md`.

**Step 3: Delete `references/notes-organization.md`**

```bash
git rm references/notes-organization.md
```

**Step 4: Commit**

```bash
git add skills/ references/
git commit -m "refactor: update skills and references for consolidated doc structure"
```

---

### Task 15: Update `README.md`

**Files:**
- Modify: `README.md`

**Step 1: Update any references to old paths**

The README mentions `notes/topics/`, `notes/articles/`, `papers/summaries/`, and `doc/10-research-gaps.md`.
Update to match new structure.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for consolidated doc structure"
```

---

### Task 16: Update `templates/open-question.md`

**Files:**
- Modify: `templates/open-question.md`

**Step 1: Update the usage comment**

The template currently says "Each open question is added as a section in doc/08-open-questions.md".
Change to: "Each open question is saved as a separate file in doc/questions/".

**Step 2: Commit**

```bash
git add templates/open-question.md
git commit -m "refactor: update open-question template for per-file questions"
```

---

### Task 17: Final review and validation

**Step 1: Search for any remaining old paths**

```bash
grep -r "papers/summaries\|notes/articles\|notes/topics\|notes/questions\|notes/methods\|notes/datasets\|notes/index\|doc/background\|doc/07-\|doc/08-open" --include="*.md" . | grep -v ".venv" | grep -v "docs/plans"
```

Expected: no results (except plan documents which describe the migration).

**Step 2: Verify all templates exist**

```bash
ls templates/paper-summary.md templates/background-topic.md templates/question.md templates/method.md templates/dataset.md templates/hypothesis.md templates/discussion.md templates/interpretation.md templates/inquiry.md templates/data-source.md templates/open-question.md
```

Expected: all 11 files exist.

**Step 3: Verify no orphaned note templates**

```bash
ls templates/notes/ 2>&1
```

Expected: "No such file or directory"

**Step 4: Verify shared preamble exists**

```bash
cat references/command-preamble.md
```

**Step 5: Commit any stragglers**

If Step 1 found remaining old paths, fix them and commit.

```bash
git add -A && git commit -m "refactor: fix remaining old path references"
```
