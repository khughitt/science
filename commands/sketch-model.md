---
description: Sketch a research model interactively as an inquiry subgraph — variables, relationships, data sources, and unknowns. Use when exploring what variables matter, how they connect, or how to approach a causal question (DAG, confounders, treatment effect).
---

# Sketch a Research Model

> **Prerequisites:**
> - Read `docs/user-guide/science-model.md`, `docs/user-guide/entities.md`,
>   `docs/user-guide/epistemic-model.md`,
>   `docs/user-guide/graph-and-derived-state.md`, and
>   `docs/plans/historical/2026-03-01-knowledge-graph-design.md` for model,
>   entity, inquiry, and graph semantics before starting.
> - If causal mode is active: also read
>   `references/dag-two-axis-evidence-model.md`.

## Overview

This command helps the user sketch the shape of an investigation: what variables matter, how they might connect, what data exists, and what remains unknown.

At sketch time:
- uncertainty is expected
- missing provenance is acceptable
- edges are tentative
- candidate propositions are more important than polished formalism

The output is an inquiry subgraph plus a rough set of candidate propositions that can later be formalized with `/science:specify-model`.

## Causal Mode Detection

Switch to causal mode when any of the following are true:

1. The `causal-modeling` aspect is active in `science.yaml`
2. User language signals causal intent: "causal", "DAG", "confounders", "treatment effect", "what causes", "intervention"
3. Existing causal inquiries already exist in the project

When causal mode is active:
- create the inquiry with `--profile causal`
- use `scic:causes` and `scic:confounds` as tentative causal structure
- set the estimand in the source file with `--treatment` and `--outcome`
- treat each causal edge as a candidate proposition, not an established fact
- ask what evidence would support or dispute each proposed causal edge

When causal mode is not active:
- use `sci:feedsInto` for flow or processing structure
- use loose associations only when the relationship is not yet clear
- keep the sketch lightweight and incomplete where needed

## Tool Invocation

All `science` commands below use this pattern:

```bash
uv run science <command>
```

## Rules

- **MUST** initialize the graph if it does not exist (`science graph init`)
- **MUST** create the inquiry source file before adding boundary roles or flow edges (`science inquiry init`)
- **MUST** add reusable variables, questions, hypotheses, datasets, and propositions as source entities before referencing them from the inquiry block
- **SHOULD** name candidate propositions explicitly in notes or prose when the user proposes a real scientific relationship
- **MUST NOT** treat sketch edges as validated
- **MUST NOT** require provenance or confidence at this stage
- **SHOULD** use `sci:Unknown` nodes to make uncertainty visible rather than hiding it in prose

## Workflow

### Step 1: Gather Context

Read these project files if they exist:
- `specs/research-question.md`
- `entities/hypotheses/`
- `entities/questions/`
- `knowledge/graph.trig`
- `entities/patches/`
- `entities/inquiries/`

If no graph exists:

```bash
science graph init
```

### Existing Inquiry Upgrade

If `$ARGUMENTS` names an existing graph-backed inquiry source at
`entities/patches/<slug>.md`, edit that source file instead of creating a
duplicate inquiry identity. If a legacy prose inquiry exists at
`entities/inquiries/<slug>.md`, treat it as context and migrate the graph-backed
parts into `entities/patches/<slug>.md` when a queryable inquiry graph is needed.

- Read the existing file and preserve its existing slug and frontmatter,
  including focal target and status.
- Register the existing inquiry before adding graph nodes or edges.
- If migrating from a legacy prose inquiry, do not delete the prose note unless
  the user explicitly asks; create the graph-backed source as the durable
  compiled-inquiry surface.
- In the final summary, state whether this was an edit of an existing inquiry
  source or a migration from legacy prose.

### Step 2: Interactive Conversation

Have a natural, adaptive conversation.

1. **Target**
   - What question, hypothesis, or inquiry is this sketch meant to address?

2. **Variables**
   - What can be observed directly?
   - What is latent, inferred, or computed?
   - What datasets or assays touch these variables?
   - Which variables are only available through proxies and will later need `measurement_model`?

3. **Candidate Relations**
   - What seems related to what?
   - Which of these are merely associative, and which are candidate causal claims?
   - Where is the user confident, and where are they mostly guessing?

4. **Evidence Outlook**
   - What would count as literature support?
   - What empirical-data evidence would matter most?
   - Are any proposed edges especially fragile because they rest on one idea or one source?

5. **Unknowns**
   - What variables, confounders, or mechanisms are missing?
   - Where should `sci:Unknown` nodes be used?

If causal mode is active, also ask:
- What is the treatment?
- What is the outcome?
- What variables might confound both?
- Which causal arrows are most uncertain?

If the sketch is mostly formal or architectural rather than empirical, say so explicitly and treat the key propositions as likely `structural_claim`s rather than as causal or mechanistic claims.

### Step 3: Author The Inquiry Source

1. **Create the inquiry**

```bash
science inquiry init "<slug>" \
  --label "<descriptive label>" \
  --target "<hypothesis:hNN or question:qNN>" \
  --profile investigation
```

If causal mode:

```bash
science inquiry init "<slug>" \
  --label "<descriptive label>" \
  --target "<hypothesis:hNN or question:qNN>" \
  --profile causal \
  --treatment "<existing-treatment-ref>" \
  --outcome "<existing-outcome-ref>"
```

Treatment and outcome refs may be `concept:*` only when the concept already
resolves through a source owner such as `entities/concepts/*.md`.

2. **Create or update durable source entities**

Create or update source records before referencing them from the inquiry. Use
the most specific registered source kind available before creating a local
concept. Good targets include `question`, `hypothesis`, `dataset`,
`proposition`, `method`, `construct`, `outcome`, or a declared domain kind. Use
CLI helpers where available, then rebuild the graph.

For durable source records, use the generic entity lifecycle only for source
kinds the project actually supports or has registered:

```bash
science entity create <kind> "<title>" --id "<kind>:<slug>"
```

Use `science entity create concept "<title>"` when the model genuinely needs a
reusable project-local concept with a Markdown owner. Keep weak ideas in prose
when they do not need graph refs yet.

Do not invent unsupported `variable` or `unknown` entity files just to satisfy a
sketch. If no supported durable source kind exists yet, describe the term in the
inquiry patch prose and defer boundary roles or flow edges until a source owner
is available. Unknown markers may be used in sketch as temporary uncertainty
markers; resolve or justify them before moving out of sketch.

`boundary_roles` and `flow_edges` should reference existing source refs.
Unknown refs are sketch markers, not durable owners. Use the patch source for
inquiry-local assumptions and transformations; the inquiry compiler mints those
local nodes from the authored patch. Do not use `science graph add concept` as
the durable authoring path. Direct graph mutation writes to
`knowledge/graph.trig`, which is regenerated by `science graph build` from
source files.

3. **Edit the `inquiry:` block**

Open `entities/patches/<slug>.md` and add boundary roles and flow edges.

Refs may be `concept:*` only when the concept already resolves through
`entities/concepts/*.md` or another supported source owner.

```yaml
inquiry:
  profile: investigation
  status: sketch
  boundary_roles:
    - ref: "<existing-input-ref>"
      role: BoundaryIn
    - ref: "<existing-output-ref>"
      role: BoundaryOut
  flow_edges:
    - subject: "<existing-from-ref>"
      predicate: feedsInto
      object: "<existing-to-ref>"
      claim_refs: []
  assumptions: []
  transformations: []
  unknowns:
    - "<unknown-ref>"
```

Use `predicate: causes` for causal edges in a causal inquiry. Do not imply that
the edge is proven; record in the source prose which candidate propositions need
formalization next. The `unknowns` placeholder above is sketch-only; replace it
with a source-backed ref or justify the remaining uncertainty before moving the
inquiry out of `sketch`.

4. **Build the compiled view**

```bash
science graph build
```

### Step 4: Visualize And Summarize

```bash
science inquiry show "<slug>" --format table
science inquiry validate "<slug>" --format json
```

The source file is `entities/patches/<slug>.md`. If the project also keeps a
prose inquiry note in `entities/inquiries/<slug>.md`, keep it consistent with
the patch source but do not treat it as the compiled graph source.

The summary should explicitly note:
- tentative propositions
- unresolved unknowns
- which parts are structurally useful but epistemically weak
- where `supports_scope` should later widen review output, while still remaining only a hint rather than a graph override

### Step 5: Finalize

```bash
science graph stamp-revision
```

Suggest next steps:
1. `/science:specify-model <slug>` to formalize claims and attach evidence
2. `/science:critique-approach <slug>` if causal structure needs skeptical review
3. `/science:add-hypothesis` if the sketch revealed a new organizing conjecture
4. `/science:research-topic` or `/science:search-literature` if the main gap is background evidence

## Important Notes

- A good sketch makes uncertainty explicit.
- A candidate edge is not a validated edge.
- Multiple sketches are fine; they are research tools, not final statements of truth.
- Prefer a small number of meaningful variables and candidate claims over a bloated diagram.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:sketch-model" \
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
