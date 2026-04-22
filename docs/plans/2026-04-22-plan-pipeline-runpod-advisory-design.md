# Plan-Pipeline RunPod Advisory Design

## Goal

Make `plan-pipeline` explicitly surface the new RunPod pipeline skill when a planned workflow appears GPU-intensive, while still leaving the final execution choice to the user.

## Context

Science now has a dedicated RunPod pipeline skill and starter templates:

- `skills/pipelines/runpod.md`
- `templates/runpod/push_to_runpod.sh`
- `templates/runpod/setup.sh`
- `templates/runpod/run.sh`

That guidance is useful for rented GPU execution, but it is not automatically surfaced anywhere in the current planning flow. `plan-pipeline` already has the right conceptual hook because it:

- identifies computational requirements
- references tool-specific skills where applicable
- stays tool-agnostic by default unless the user opts into something specific

The desired behavior is not to silently switch planning into a RunPod path. The user should first be told the RunPod skill exists, then decide whether to consider it.

## Approaches Considered

### 1. Advisory trigger inside `plan-pipeline`

When the workflow appears GPU-intensive, `plan-pipeline` briefly flags the RunPod skill as a relevant option and asks the user whether to consider it. If the user agrees, the agent reads `skills/pipelines/runpod.md` and can reference the starter templates in the plan.

Pros:

- keeps the behavior inside the existing pipeline planning workflow
- preserves user choice
- fits the current “reference tool-specific skills where applicable” rule
- requires only small synchronized doc changes

Cons:

- relies on heuristic detection rather than strict classification

### 2. Passive mention in general notes only

Add a generic note somewhere in `plan-pipeline` saying GPU-heavy workflows may want RunPod.

Pros:

- minimal change

Cons:

- too easy to miss
- does not trigger at the moment the user is making planning decisions

### 3. Separate command for remote GPU planning

Create a new command or skill path specifically for remote GPU infrastructure.

Pros:

- explicit specialization

Cons:

- duplicates `plan-pipeline`
- too much surface area for a narrow decision point

## Decision

Use **an advisory trigger inside `plan-pipeline`**.

The command and its generated Codex skill should stay tool-agnostic by default, but add a clear conditional branch: if the workload appears GPU-intensive, suggest the RunPod skill to the user and let them decide whether to incorporate it.

## Detection Model

Detection should stay simple and descriptive, not algorithmic. Good signals include:

- explicit user mention of GPU execution, rented GPU pods, RunPod, or remote pods
- model inference or training steps that obviously imply GPU execution
- large embedding generation or similar batch workloads that are likely GPU-bound
- dependencies or runtime requirements that clearly point to CUDA / GPU use

The command should not pretend to infer exact cost thresholds or hardware sizing.

## User Interaction

The new behavior should say, in effect:

- this plan looks GPU-intensive
- Science has a RunPod skill for rented GPU pod workflows
- do you want to consider that path before finalizing the plan?

If the user says no, continue planning normally.

If the user says yes:

- read `skills/pipelines/runpod.md`
- incorporate its operational guidance where relevant
- reference `templates/runpod/*` as an optional starter kit

## Scope

In scope:

- `commands/plan-pipeline.md`
- `codex-skills/science-plan-pipeline/SKILL.md`

Out of scope:

- automatic selection of RunPod
- any new CLI command
- modifying downstream project scaffolding
- changing the RunPod skill itself

## Expected Outcome

After this change:

- GPU-heavy pipeline planning naturally surfaces RunPod as an option
- the user stays in control of whether remote rented GPU execution is adopted
- Claude-command and Codex-skill behavior remain aligned
