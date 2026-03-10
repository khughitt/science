# Meta-Feedback for Science Commands

## Problem

The effectiveness of the science tool depends on the quality of its guidance: command prompts, document templates, section structures, and metadata conventions.
Bad templates can harm research quality as much as good ones help it.
Currently there is no feedback loop — agents execute commands but never report on whether the guidance actually served the research task.

## Goal

Add a structured reflection step to selected commands so that agents report friction, gaps, and successes after each invocation.
This feedback accumulates per-project and is periodically reviewed by the plugin developers to evolve the science tool.

## Scope

### Commands receiving feedback prompts (6 total)

**Tier 1 — template/structure directly shapes research capture:**

| Command | Reflects on |
|---|---|
| `research-topic` | background-topic template sections, source hierarchy guidance |
| `research-paper` | paper-summary template sections, cross-checking guidance |
| `add-hypothesis` | hypothesis template sections, falsifiability/predictions prompts |
| `discuss` | discussion template sections, standard vs double-blind mode guidance |
| `interpret-results` | interpretation template sections, signal classification, aspect-contributed sections |

**Tier 2 — analytical judgment about what matters:**

| Command | Reflects on |
|---|---|
| `research-gaps` | gap analysis framework (coverage dimensions, prioritization criteria) |
| `critique-approach` | critique rubric (structural checks, confounder identification, edge review) |

### Commands excluded

Mechanical/infrastructure commands (`create-graph`, `update-graph`, `create-project`, `review-tasks`, `plan-pipeline`, `review-pipeline`, `sketch-model`, `specify-model`) and compatibility aliases (`summarize-topic`, `summarize-paper`) are excluded.
These don't involve template/structure decisions that meaningfully affect research quality.

## Design

### Feedback file

- **Path:** `doc/meta/skill-feedback.md` inside each research project
- **Format:** Append-only, one entry per command invocation
- **Created automatically** on first feedback entry (mkdir -p + append)

### Entry format

```markdown
## YYYY-MM-DD — <command-name>

**Template/structure friction:**
- Any section left empty, filled with boilerplate, or that felt forced

**Missing capture:**
- Information the agent wanted to record but had no natural place for

**Guidance issues:**
- Command instructions that were confusing, contradictory, or didn't help

**Suggested improvement:**
- Concrete proposal for fixing any friction above (optional but encouraged)

**What worked well:**
- A section or instruction that genuinely improved the output
```

### Four fixed categories

Each category targets a specific failure mode:

1. **Template/structure friction** — detects sections that don't fit real research tasks
2. **Missing capture** — detects information gaps in templates
3. **Guidance issues** — detects confusing or counterproductive instructions
4. **What worked well** — prevents removing things that work (kept last and brief)

### Prompt design

Each of the 6 commands gets a "Process Reflection" section appended at the end, consisting of:

1. A **one-line custom preamble** specific to what that command should reflect on
2. A **shared epilogue block** with the entry format and guidelines

### Guidelines for the agent

- Be concrete and specific, not generic
- 2-5 bullets total; skip empty categories
- "No friction encountered" is a valid entry — don't manufacture feedback

## What this is NOT

- Not a per-session journal — entries are short and structured
- Not a suggestion box — categories force friction-focused observations
- Not automated — developers manually review feedback across projects and decide what to act on

## Evolution: Aspect-Based Framework (2026-03-10)

The feedback system surfaced a systematic pattern: certain template sections are forced for projects
that don't need them. This led to the aspect-based framework design
(see `docs/plans/2026-03-10-aspect-based-framework.md`), which makes sections composable
based on project characteristics declared in `science.yaml`.

The feedback entry format was also updated:
- Added 5th category: **"Suggested improvement"** for concrete fix proposals
- Added recurrence guidance to surface patterns that need systematic fixes
- Added aspect fit check to the process reflection step

## Implementation

Six command files need a "Process Reflection" section appended:

1. `commands/research-topic.md`
2. `commands/research-paper.md`
3. `commands/add-hypothesis.md`
4. `commands/discuss.md`
5. `commands/research-gaps.md`
6. `commands/critique-approach.md`

Each edit is small — approximately 20-25 lines added to the end of each file.
