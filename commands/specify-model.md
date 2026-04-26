---
description: Formalize a research model with explicit claims, evidence provenance, and residual uncertainty. Use when the user wants to make a sketch rigorous, attach support/dispute to candidate relations, resolve unknowns, or formalize assumptions.
---

# Specify a Research Model

> **Prerequisite:** Read `docs/proposition-and-evidence-model.md` and `docs/specs/2026-03-01-knowledge-graph-design.md` for ontology reference before starting.

## Overview

This command takes an inquiry from sketch to specified status.

In the skeptical model:
- variables get formal types
- non-trivial scientific relations become explicit `relation_claim`s
- evidence updates those claims via support/dispute
- uncertainty remains explicit unless the evidence base is genuinely strong

The goal is not to convert every edge into a fact. The goal is to convert vague structure into explicit, reviewable claims with provenance.

## Tool Invocation

All `science-tool` commands below use:

```bash
uv run science-tool <command>
```

## Rules

- **MUST** read the existing inquiry before modifying it
- **MUST** assign formal types to all important variables
- **MUST** identify which inquiry edges are structural only and which represent uncertain scientific claims
- **MUST** represent uncertain scientific relations as `relation_claim`s
- **MUST** attach provenance to authored claims
- **MUST** keep residual uncertainty visible when support is sparse, contested, or low-quality
- **MUST** run `inquiry validate` after specifying
- **SHOULD** identify confounders for directional or causal claims
- **SHOULD** ask what would materially change belief in each key claim

## Workflow

### Step 1: Load And Assess The Inquiry

If `$ARGUMENTS` contains a slug:

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Identify:
- variables lacking proper types
- vague edges that should become explicit claims
- unresolved unknowns
- unsupported causal assumptions
- places where the inquiry is structurally useful but epistemically fragile

If no slug is provided, ask which inquiry to specify.

### Step 2: Specify Variables

For each important variable:

1. **Type**
   - What kind of thing is this?
   - Use the most specific reasonable type.

2. **Observability**
   - Is this observed, latent, or computed?

3. **Provenance**
   - Where does this variable definition come from?

Use commands like:

```bash
science-tool graph add concept "<name>" --type <CURIE> --definition "<definition>"
```

### Step 3: Convert Scientific Edges Into Explicit Claims

For each non-trivial scientific relation in the inquiry:

1. Clarify the content of the claim
   - What exactly is being asserted?
   - Is it `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`?
   - Is the observed evidence direct or proxy-mediated?

2. Create a `relation_claim`

```bash
science-tool graph add relation-claim \
  "concept:<subject>" \
  "<predicate>" \
  "concept:<object>" \
  --source "<ref>" \
  --confidence <0-1> \
  --text "<clear claim text>"
```

3. Attach the claim to the inquiry edge when the edge should remain in the model

```bash
science-tool inquiry add-edge "<slug>" "concept:<subject>" "<predicate>" "concept:<object>" \
  --claim "relation_claim:<id>"
```

Use direct structural edges without claims only when the edge is organizational or procedural rather than epistemic.

When the claim is materially clearer with layered metadata, author it explicitly:
- `claim_layer`
- `identification_strength`
- `proxy_directness`
- `measurement_model`
- `supports_scope` as a review hint only
- `rival_model_packet` using optional `current_working_model`

### Step 4: Attach Support And Dispute

For each important claim, ask:
- What currently supports it?
- What currently disputes it?
- What evidence is missing?
- Does the support come from one independence group only?
- Is any support actually a proxy that still needs a measurement model?

When the project has concrete supporting or disputing project claims, represent them explicitly:

```bash
science-tool graph add claim "<supporting or disputing statement>" --source "<ref>" --confidence <0-1>
science-tool graph add relation-claim \
  "claim:<supporting-claim>" \
  "cito:supports" \
  "relation_claim:<target>" \
  --source "<ref>"
```

Use `cito:disputes` analogously for counter-evidence.

Do not force a flat verdict when the evidence is mixed or weak.

### Step 5: Resolve Unknowns And Assumptions

For each `sci:Unknown` node:
- resolve it to a real entity
- justify why it remains unknown
- or remove it if it no longer matters

For each assumption:
- note why the model currently relies on it
- note what evidence or analysis would reduce that reliance

### Step 6: Validate And Finalize

```bash
science-tool inquiry validate "<slug>" --format json
```

Update the inquiry status to `specified` only when:
- the model structure is coherent
- the important claims are explicit
- the main evidence links are recorded
- major unknowns are either resolved or intentionally documented

Then:

```bash
science-tool graph stamp-revision
```

### Step 7: Suggest Next Steps

1. `/science:interpret-results` when new empirical results should update support/dispute
2. `/science:compare-hypotheses` when competing claim bundles need head-to-head evaluation
3. `/science:discuss` when a claim remains contested or structurally important but weakly evidenced

## Important Notes

- Specifying a model increases clarity, not certainty.
- A relation-claim with one weak line of evidence is still fragile.
- The main output of this command is a model whose uncertainty can be inspected, challenged, and improved.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:specify-model" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead
