# Plan-Pipeline RunPod Advisory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the plan-pipeline command and generated Codex skill so GPU-intensive workflows suggest the RunPod skill to the user before planning proceeds.

**Architecture:** Keep the change documentation-only and localized. Add one rule-level note plus one workflow step in both `commands/plan-pipeline.md` and `codex-skills/science-plan-pipeline/SKILL.md`, using the same advisory logic and the same references to `skills/pipelines/runpod.md`.

**Tech Stack:** Markdown

---

### Task 1: Add the RunPod advisory to the Claude command doc

**Files:**
- Modify: `commands/plan-pipeline.md`

**Step 1: Update the rules section**

Add a new `SHOULD` bullet near the existing tool-specific guidance saying that GPU-intensive workflows should prompt the planner to suggest the RunPod skill as an option.

**Step 2: Add a new workflow step after computational requirement identification**

Insert a new step between current Step 2 and Step 2b. The new step should:

- identify common GPU-heavy signals
- tell the planner to suggest `skills/pipelines/runpod.md` to the user
- require an explicit yes/no decision before incorporating that guidance

**Step 3: Reinforce the policy in Important Notes**

Add one short note clarifying that RunPod is advisory, not automatic.

### Task 2: Mirror the advisory in the generated Codex skill

**Files:**
- Modify: `codex-skills/science-plan-pipeline/SKILL.md`

**Step 1: Update the rules section**

Mirror the new command bullet.

**Step 2: Add the matching workflow step**

Mirror the same advisory step added to `commands/plan-pipeline.md`, keeping the wording aligned with Codex skill naming conventions.

**Step 3: Update Important Notes**

Mirror the same advisory-only policy.

### Task 3: Verify alignment and scope

**Files:**
- Read: `commands/plan-pipeline.md`
- Read: `codex-skills/science-plan-pipeline/SKILL.md`

**Step 1: Check both files mention RunPod in the intended sections**

Run:

```bash
rg -n "RunPod|GPU-intensive|skills/pipelines/runpod.md|science has a RunPod skill" \
  commands/plan-pipeline.md codex-skills/science-plan-pipeline/SKILL.md
```

Expected:

- both files mention the advisory
- both files reference the RunPod skill path or name

**Step 2: Review the diff**

Run:

```bash
git diff -- commands/plan-pipeline.md codex-skills/science-plan-pipeline/SKILL.md \
  docs/plans/2026-04-22-plan-pipeline-runpod-advisory-design.md \
  docs/plans/2026-04-22-plan-pipeline-runpod-advisory-implementation.md
```

Expected:

- only the two docs and the two new plan files changed
- the command and Codex skill stay semantically aligned
