---
description: Formalize a research model with explicit claims, evidence provenance, and residual uncertainty. Use when the user wants to make a sketch rigorous, attach support/dispute to candidate relations, resolve unknowns, or formalize assumptions.
---

# Specify a Research Model

> **Prerequisite:** Read `docs/user-guide/science-model.md`, `docs/user-guide/entities.md`, `docs/user-guide/graph-and-derived-state.md`, and `docs/plans/historical/2026-03-01-knowledge-graph-design.md` for model, entity, and graph semantics before starting.

## Overview

This command takes an inquiry from sketch to specified status.

In the skeptical model:
- variables get formal types
- non-trivial scientific relations become explicit `proposition` records, preferably with subject-predicate-object structure
- evidence lines update those propositions via support/dispute
- uncertainty remains explicit unless the evidence base is genuinely strong

The goal is not to convert every edge into a fact. The goal is to convert vague structure into explicit, reviewable propositions with provenance.

## Tool Invocation

All `science` commands below use:

```bash
uv run science <command>
```

## Rules

- **MUST** read the existing inquiry, hypothesis, or target epistemic entity before modifying it
- **MUST** assign formal types to all important variables
- **MUST** identify which modeled relations are structural only and which represent uncertain scientific claims
- **MUST** represent uncertain scientific relations as `proposition` entities
- **MUST** attach provenance to authored propositions and evidence lines
- **MUST** keep residual uncertainty visible when support is sparse, contested, or low-quality
- **MUST** run the relevant validation path after specifying (`inquiry validate`, project DAG check, or graph build)
- **SHOULD** identify confounders for directional or causal claims
- **SHOULD** ask what would materially change belief in each key claim

## Workflow

### Step 0: Detect The Target Kind And DAG Representation

`$ARGUMENTS` is not always an inquiry. Before Step 1, resolve what you were handed and how this
project represents its model graph — otherwise `science inquiry show` errors (e.g. on a
`hypothesis:` ref, which is not an inquiry).

1. **Resolve the target kind.** If the ref is `inquiry:<slug>` (or a bare inquiry slug), proceed with
   the inquiry/RDF-graph path (Step 1 onward). If it is a `hypothesis:` (or other epistemic kind), do
   **not** run `science inquiry show` — read the entity file directly and treat *it* as the model to
   specify.

2. **Detect the DAG representation.** Some projects author the inquiry graph through the
   source-first inquiry patch path (`entities/patches/<slug>.md` with `patch_type: inquiry`). Others author
   per-hypothesis DAGs as a **file pair** — e.g. `doc/figures/dags/<id>.dot` + `<id>.edges.yaml` —
   consumed by `science big-picture` provenance-coverage rather than by `science graph add`. Check the
   project for such a convention (look under `doc/figures/dags/`, `*.edges.yaml`, or the project's
   `RESEARCH_PLAN`/conventions) before assuming the inquiry patch path.

3. **Route accordingly:**
   - **Inquiry patch project** → Steps 1–6 as written, editing the source file and rebuilding before validation.
   - **Hypothesis + file-based DAG project** → skip the `inquiry show/validate/add-edge` and
     `graph add concept` steps (they don't map onto the file pair). Instead author/validate the
     `.dot` + `.edges.yaml` pair the project's tooling consumes, and still do Step 3 (durable
     `proposition` entities) and Step 4 (evidence-line entities) — those are tool-supported and
     durable regardless of DAG representation. Validate with the project's DAG check (e.g.
     `science big-picture`) rather than `inquiry validate`.
   - **Hypothesis / epistemic entity with no DAG yet** → decompose the hypothesis into durable `proposition:` entities.
     For each proposition, link each proposition back to the hypothesis with `related: ["hypothesis:<id>"]`.
     Then add the proposition refs to the hypothesis's Proposition Bundle so the bundle is explicit and queryable.
     Do not leave the decomposition only as prose inside the hypothesis file. If a DAG is later useful, build it
     from those proposition records rather than replacing them.

The proposition + evidence-line authoring (Steps 3–4) is representation-agnostic; only the
structural-graph steps (1, 2, the inquiry source edit in 3, and 6's `inquiry validate`) are inquiry-specific.

### Step 1: Load And Assess The Target

*(Inquiry + RDF-graph path — see Step 0. For a hypothesis in a file-based DAG project, read the
hypothesis file and its `.dot`/`.edges.yaml` pair instead. For a hypothesis with no DAG yet, read the
hypothesis file and prepare the proposition bundle before adding any structural graph.)*

If `$ARGUMENTS` contains an inquiry slug:

```bash
science inquiry show "<slug>" --format table
science inquiry validate "<slug>" --format json
```

Identify:
- variables lacking proper types
- vague edges that should become explicit claims
- unresolved unknowns
- unsupported causal assumptions
- places where the inquiry is structurally useful but epistemically fragile

If no slug is provided, ask which inquiry, hypothesis, or epistemic target to specify.

### Step 2: Specify Variables

For each important variable:

1. **Type**
   - What kind of thing is this?
   - Use the most specific reasonable type.

2. **Observability**
   - Is this observed, latent, or computed?

3. **Provenance**
   - Where does this variable definition come from?

For inquiry-patch projects, record durable variable refs in
`entities/patches/<slug>.md`. Add or update source entity files under
`entities/` for variables that are durable project concepts, then rebuild the
graph from source.

Direct `science graph add concept` writes are exploratory and non-durable. They
write to `knowledge/graph.trig`, which is regenerated from source files. Use
them only for temporary graph inspection, and repeat the durable definition in a
source file before treating the model as specified:

```bash
science graph add concept "<name>" --type <CURIE> --definition "<definition>"
```

### Step 3: Convert Scientific Edges Into Explicit Propositions

For each non-trivial scientific relation in the inquiry:

1. Clarify the content of the proposition
   - What exactly is being asserted?
   - Is it `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`?
   - Is the observed evidence direct or proxy-mediated?

2. Create a durable proposition

```bash
science propositions create "<clear proposition title>" \
  --id "proposition:<id>" \
  --source-ref "<ref>"
```

Then fill the proposition file with explicit subject-predicate-object structure in prose and, when useful, frontmatter fields such as:

```yaml
subject: "concept:<subject>"
predicate: "<predicate>"
object: "concept:<object>"
claim_layer: "empirical_regularity|causal_effect|mechanistic_narrative|structural_claim"
```

3. Attach the proposition to the inquiry edge when the edge should remain in the model.

Edit `entities/patches/<slug>.md` and add the proposition to the edge's
`claim_refs:` list:

```yaml
flow_edges:
  - subject: "concept:<subject>"
    predicate: feedsInto
    object: "concept:<object>"
    claim_refs:
      - "proposition:<id>"
```

Use direct structural edges without propositions only when the edge is organizational or procedural rather than epistemic.

When the proposition is materially clearer with layered metadata, author it explicitly:
- `claim_layer`
- `identification_strength`
- `proxy_directness`
- `measurement_model`
- `supports_scope` as a review hint only
- `rival_model_packet` using optional `current_working_model`

`proxy_directness:` must be one of `direct`, `indirect`, or `derived`. Do not write `proxy`; graph build rejects it.
Use `direct` when the evidence observes the target construct itself, `indirect` for a measured proxy of the target construct,
and `derived` for a computed or model-derived proxy. If `proxy_directness` is `indirect` or `derived`, include a
`measurement_model` that explains what the proxy measures, the latent construct it stands in for, and known failure modes.

### Step 4: Attach Support And Dispute

For each important proposition, ask:
- What currently supports it?
- What currently disputes it?
- What evidence is missing?
- Does the support come from one independence group only?
- Is any support actually a proxy that still needs a measurement model?

When the project has concrete supporting or disputing evidence, represent it as evidence-line entities:

```bash
science entity create evidence-line "<supporting or disputing evidence line>" \
  --id "evidence-line:<id>" \
  --source-ref "<ref>" \
  --related "proposition:<target>"
```

Then set `target: "proposition:<target>"`, `stance: "supports"` or `stance: "disputes"`, and fill in strength, method, independence, and caveats.

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
science graph build
science inquiry validate "<slug>" --format json
```

Update the inquiry status to `specified` only when:
- the model structure is coherent
- the important claims are explicit
- the main evidence links are recorded
- major unknowns are either resolved or intentionally documented

Then:

```bash
science graph stamp-revision
```

### Step 7: Suggest Next Steps

1. `/science:interpret-results` when new empirical results should update support/dispute
2. `/science:compare-hypotheses` when competing claim bundles need head-to-head evaluation
3. `/science:discuss` when a claim remains contested or structurally important but weakly evidenced

## Important Notes

- Specifying a model increases clarity, not certainty.
- A proposition with one weak line of evidence is still fragile.
- The main output of this command is a model whose uncertainty can be inspected, challenged, and improved.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
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
