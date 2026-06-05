---
description: Scrutinize one or more epistemic entities (hypothesis, proposition, interpretation, report) for claim-vs-operationalization drift, leaky or overstated language, eroded falsifiability, and unincorporated open questions, then record an artifact-guarded review. Use when an entity looks settled but is heavily caveated or carries open-question debt, or on a periodic sweep of the attention ranking.
---

# Entity Review

Review load-bearing (epistemic) entities for drift between what they claim and what their
evidence and operationalization actually support. Targets failure mode A
(scope/operationalization drift) and the residue of B/C that static checks cannot
adjudicate. See `docs/plans/2026-06-04-epistemic-drift-detection-design.md` and
`science-meta:question:15-claim-operationalization-drift`.

Use `$ARGUMENTS` to scope the review to specific epistemic entities. If no scope is given,
pull the top of the attention ranking. If `$ARGUMENTS` names an operational entity such as
`dataset:*`, `paper:*`, `workflow:*`, `workflow-run:*`, `task:*`, `plan:*`, or
`pre-registration:*`, do not stamp it with `entity review`; follow it only as evidence or
manifest context for the epistemic claim under review.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).
Load the `research-methodology` and `scientific-writing` skills.

## Selecting targets

If `$ARGUMENTS` names epistemic entities, review exactly those. Otherwise pull the
deterministic attention ranking (rows carry `open_question_debt` and reason codes):

```
science graph attention-rank --limit 15 --format json
```

Prefer the conjunction that names the blind spot — settled-looking but overdue and
indebted. Rank by, in order: `open_question_debt` desc, then `needs-review`/`stale`
freshness, then `status: supported` / high-confidence with an old `last_reviewed`.
Independent entities may be reviewed in parallel (one sub-agent per entity, mirroring
`big-picture`'s per-hypothesis fan-out). Do not parallelize entities that cite each other.

## Per-kind rubric

For every epistemic kind, check: does the stated scope exceed what is actually
operationalized/measured? Is the language leaky or overstated relative to the evidence?
Are there open questions (debt statuses: `active` / `partially-answered` / `deferred`)
related to this entity, or sharing a theme, that have never been folded into its claims?

- **hypothesis:** scope vs operationalization (enumerate what the pipeline/code actually
  measures and compare to the prose claim); falsifiability still crisp and testable;
  confidence rating justified by *current* evidence, not legacy; high-risk or edge cases
  the framing silently excludes.
- **proposition:** claim layer and identification strategy still accurate; evidence stance
  (supports/disputes balance) current; not over-generalized beyond its tested contexts.
- **interpretation:** conclusions still match the cited evidence and effect sizes; no
  drift between the headline reading and the underlying numbers.
- **report:** headline claims still match the entities they summarize; no inherited
  overstatement from a since-narrowed source entity.

**Decisions are out of scope for now.** `decision` is not a registered entity kind;
decisions live as `##` sections in `core/decisions.md` without their own `review_state`.
Do not run `entity review` on a decision. If a review surfaces a stale or code-contradicted
decision, record it as a finding/task and flag it for the future decision-review path.

**Operational entities are context, not review targets.** `dataset`, `paper`, `workflow`,
`workflow-run`, `research-package`, `task`, `plan`, and `pre-registration` are operational
in the core registry. Inspect them for manifests, evidence, provenance, and contradiction
checks, but record the review on the epistemic entity whose claim depends on them.

## Recording the review (artifact-required)

A review MUST emit a concrete artifact before the timestamp is set — never a bare bump:

1. **Finding / overstatement:** edit the entity to qualify or narrow the claim, or open a
   task (`science tasks add ...`) capturing the data-dependent follow-up.
2. **Prose-vs-code contradiction (mode B):** correct the prose and cite the authoritative
   manifest (e.g. a code constant such as `constants.py::EVENTS`).
3. **Unincorporated question (mode C):** fold it into the claim, or explicitly link/defer
   it with a reason.
4. **No change warranted:** record the *reasoning* for why no change is needed.

Then stamp the review with the artifact as the note:

```
science entity review <kind>:<id> --note "<finding | diff summary | task id | reasoned no-change>"
```

The command refuses an empty `--note` — that guard is what keeps this review honest.
