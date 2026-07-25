---
id: theme:0001-toolkit-evaluation
kind: theme
title: Toolkit Evaluation
status: active
theme_kind: methodological
theme_scope: project
related:
- question:0041-ecological-validity-of-the-simulator-as-researcher-proxy
- question:0042-factorial-design-to-isolate-per-skill-contribution
- question:0043-do-agent-scaffolds-cause-epistemic-deskilling
- question:0055-reflexive-validity-of-self-directed-claims
- question:0057-marginal-epistemic-return-per-authoring-cost
- question:0017-benchmark-grounding-metrics
- hypothesis:0008-structured-workflow-reduces-analyst-belief-divergence
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- topic:evaluating-research-tools
source_refs: []
origins: []
evidence_refs: []
created: '2026-07-25'
updated: '2026-07-25'
---
# Theme: Toolkit Evaluation

## Definition

The frame that treats the Science toolkit as an **intervention on a researcher** whose
effect must be measured, rather than as a design whose merit is argued. It covers the
instruments, control conditions, outcome operationalizations, and validity threats
involved in asking whether using Science makes research better — and what "better" would
have to mean for the question to be answerable.

## Why It Matters

The project has 50-plus questions and hypotheses about how to *represent* evidence, and
until 2026-07-25 had almost none about whether the representation helps anyone. That
asymmetry was invisible while every entity was judged against its neighbours rather than
against the project's overall coverage. Making the theme explicit means a proposed schema
addition can be asked what measured effect it is supposed to produce, not only whether it
is epistemically defensible.

It also conditions how strongly the project may state its own conclusions: without an
external instrument, favourable evidence about the toolkit gathered through the toolkit is
internal consistency rather than validity.

## Boundaries

**Inside:** study design and instruments for measuring the toolkit's effect; outcome
operationalizations of research quality; validity threats (ecological, construct,
common-method); external grounding and benchmark portfolios; longitudinal effects on the
researcher, including negative ones; the reflexivity constraint on self-directed claims.

**Outside:** the *content* of any particular design bet (those stay as their own
hypotheses); graph-internal correctness properties such as determinism or merge algebra,
which are verification rather than evaluation; adoption and market questions, which belong
to `question:0052`.

## Current Project Links

- Instrument validity: `question:0041` (simulator as researcher proxy)
- Study design: `question:0042` (factorial dismantling against an unstructured-LLM control)
- Core value proposition: `hypothesis:0008` (analyst-divergence reduction)
- Negative arm: `question:0043` (epistemic deskilling over sustained use)
- Reflexivity constraint: `question:0055` (which self-claims need an external instrument)
- Cost/benefit stopping rule: `question:0057` (marginal return per authoring cost)
- External grounding: `question:0017`; calibration bet: `hypothesis:0002`
- Literature base: `topic:evaluating-research-tools`

## Guardrails

- **A favourable result produced by the toolkit is not evidence about the toolkit.** Apply
  the `question:0055` criterion — could this evidence have been produced without it?
- **Do not let "research quality" go unoperationalized.** The choice among candidate
  outcome measures partly determines the result and must be pre-committed.
- **Any evaluation design must be able to resolve negative.** A design that can only detect
  improvement is not a test.
- **Do not treat simulation results as evidence about human researchers** until
  `question:0041` is answered; simulation evidence is indirect evidence in the
  `topic:evidence-grading-and-belief-ceilings` sense.

## Downstream Work

- Task group `toolkit-evaluation` in the backlog.
- Deepen `topic:evaluating-research-tools` via a `research-topic` pass; promote its
  unverified intake list to real paper entities.
- Determine whether a many-analysts design is feasible at this project's scale or needs
  outside collaborators.

## Open Questions

- Is any evaluation requiring human participants tractable for a single-researcher project,
  or does this theme mostly generate questions the project cannot itself answer?
- If nearly all current evidence about Science is Science-produced, does this theme's
  guardrail invalidate a large share of existing recorded belief?

## Update Triggers

- A new skill or schema addition is proposed without a stated measurable effect.
- `question:0041` resolves, changing how simulation evidence may be used.
- Any external instrument (benchmark, human study, collaborator) becomes available.
