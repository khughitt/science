---
description: Interpret analysis results and feed findings back into the research framework. Use when the user has pipeline output, notebook results, statistical summaries, or preliminary findings to evaluate against claims and hypotheses and update project priorities.
---

# Interpret Results

Interpret the results specified by `$ARGUMENTS` and update the project in a claim-centric way.

In this project, results do not automatically prove or refute a hypothesis. They shift support, dispute, and uncertainty for specific claims.

If no argument is provided, ask the user to describe their findings or point to a results file.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `docs/claim-and-evidence-model.md`.
2. Read `templates/interpretation.md`.
3. Read active hypotheses in `specs/hypotheses/`.
4. Read open questions in `doc/questions/`.
5. Read relevant prior interpretations in `doc/interpretations/`.
6. If an inquiry slug is involved, load it:

```bash
uv run science-tool inquiry show "<slug>" --format json
```

## Input

`$ARGUMENTS` may be:
- a path to a results file, notebook, or output directory
- a prose description of findings
- an inquiry slug

If given a directory, scan for result files and summarize what is available.

## Modes

- **Write mode:** no existing interpretation document yet
- **Update mode:** an interpretation already exists; update framework implications without rewriting the whole narrative
- **Dev mode:** the result is about tooling or workflow rather than substantive empirical evidence

Always note the mode at the top of the output when not in standard write mode.

## Workflow

### 1. Summarize The Findings

Extract the main findings and classify each as:
- `strong`
- `suggestive`
- `null`
- `ambiguous`
- `methodological`

Also identify the evidence type where possible:
- `literature_evidence`
- `empirical_data_evidence`
- `simulation_evidence`
- `benchmark_evidence`
- `expert_judgment`
- `negative_result`

Include effect sizes, uncertainty intervals, and sample counts where available.

### 2. Map Findings To Claims

For each relevant hypothesis or inquiry, ask:
- Which specific claims are touched by these results?
- Does this result support, dispute, or leave each claim unresolved?
- How much does it actually move belief?

Prefer outputs like:
- “supports claim C1 modestly”
- “disputes relation-claim RC3”
- “leaves the hypothesis organizing idea intact but increases uncertainty in claim C2”

Avoid outputs like:
- “the hypothesis is now proved”
- “this edge is validated”

### 3. Evaluate Against Open Questions

For each relevant open question:
- is it addressed, partially addressed, or unchanged?
- what constraints or new uncertainty does the result introduce?
- what sub-question becomes more important now?

### 4. Check Evidence Quality

Before updating beliefs, check:
- data quality
- sample counts
- control integrity
- whether the result is confirmatory or exploratory
- whether the result is independent of prior supporting evidence or largely redundant
- whether it adds empirical support to a claim that previously had only literature or simulation support

If the finding is fragile, say so explicitly.

### 5. Update Claim Support / Dispute

When graph updates are warranted, frame them as claim updates:
- add a project claim describing the result
- attach it as `cito:supports` or `cito:disputes` to the affected `relation_claim`
- note residual uncertainty, especially when evidence is single-source, weak, or contested
- classify the new evidence explicitly using the canonical evidence types above

Do not use hypothesis status changes as the primary output.
Hypothesis-level summaries can be updated later as a secondary reflection of underlying claim changes.

### 6. Surface New Questions

Identify new questions raised by the results.

For each:
- priority
- type: empirical / methodological / theoretical
- what evidence would most efficiently reduce uncertainty

### 7. Update Priorities

Propose changes to the task queue:
- new tasks to add
- claims needing more empirical evidence
- contested areas needing direct comparison or replication
- weakly supported regions of the graph worth prioritizing
- high-uncertainty neighborhoods that look likely to pay off with targeted follow-up

When `knowledge/graph.trig` exists, prefer using:

```bash
science-tool graph project-summary --format json
science-tool graph question-summary --format json
science-tool graph inquiry-summary --format json
science-tool graph dashboard-summary --format json
science-tool graph neighborhood-summary --format json
```

to anchor the prioritization section, especially for:
- the overall research-project rollup
- high-priority questions
- high-priority inquiries
- claims lacking empirical support
- single-source claims
- contested local clusters

For `software` projects, skip `project-summary` for now and start at `question-summary` / `inquiry-summary`.

Use them in this order:
1. `project-summary` to see the current research-level rollup, when the project is `research`
2. `question-summary` and `inquiry-summary` to find which threads deserve attention
3. `dashboard-summary` and `neighborhood-summary` to identify the exact claims and clusters driving that priority

## Writing

Follow `templates/interpretation.md`.
Save to `doc/interpretations/YYYY-MM-DD-<slug>.md`.

Populate frontmatter:
- `id`
- `related`
- `source_refs`
- `input`
- `created`
- `updated`

## After Writing

1. Update relevant hypothesis documents with new support/dispute and uncertainty notes.
Do not mechanically flip them to `supported` or `refuted`.
2. Add new questions to `doc/questions/` when needed.
3. Update tasks via `science-tool tasks`.
Write durable result interpretations under `doc/interpretations/`, and when the findings change the project-level narrative or current state substantially, summarize that in `doc/reports/` as well.
4. If graph updates were proposed, point the user to the exact claim or relation-claim updates to make.
5. If the project still lacks claim-backed evidence summaries, say that it appears partially migrated and that interpretation quality is constrained by that gap.
6. Suggest next steps:
   - `/science:compare-hypotheses`
   - `/science:discuss`
   - `/science:add-hypothesis`
   - `/science:pre-register`

## Process Reflection

Reflect on the **claim update** workflow and whether the template made it easy to separate:
- findings
- evidence quality
- support/dispute updates
- residual uncertainty

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md`.
