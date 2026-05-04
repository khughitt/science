---
name: research-proposition-schema
description: Use when authoring or updating proposition entities, hypothesis frontmatter, or knowledge-graph claim metadata. Defines the strict enums and field semantics for the Science project model.
---

# Proposition and Evidence Schema

Project-specific schema for the Science proposition/evidence model. For the
generic methodology layer (source hierarchy, evaluating sources, citation
discipline), see [`SKILL.md`](./SKILL.md). For the prose explanation of the
model, see `docs/proposition-and-evidence-model.md`.

When the project uses layered-claim metadata:

- use `claim_layer` only when the authored proposition really needs that distinction
- treat `identification_strength` as an evidence-design label, not as confidence
- keep `measurement_model` separate from the concrete `observation`
- do not promote mechanistic prose into `mechanistic_narrative` unless the supporting lower-layer structure is explicit
- if rival models are genuinely in play, prefer a bounded `rival_model_packet` over free-form prose comparison
- treat `current_working_model` as optional; do not invent one just to satisfy a schema

## Allowed Enum Values

These fields are strict enums. **Do not invent values** - if no listed value
fits, drop the field and explain in `measurement_model.rationale` or
`known_failure_modes` instead.

- **`claim_layer`** - what kind of claim is this?
  - `empirical_regularity` - observed pattern in data (a correlation, a frequency, a trend)
  - `causal_effect` - claim about a causal effect of one variable on another
  - `mechanistic_narrative` - proposed mechanism story; requires linked lower-layer support
  - `structural_claim` - claim about graph topology, model structure, or definitional scaffolding
- **`identification_strength`** - how much causal leverage does this evidence carry *in the target system*?
  - `none` - no causal handle (descriptive only)
  - `structural` - derived from network/model structure or theory, not data
  - `observational` - observational study, association adjusted for confounders
  - `longitudinal` - within-subject change over time
  - `interventional` - perturbation in the target system
  - `analogical` - interventional in a *model* system, extrapolated to target by analogy
- **`proxy_directness`** - `direct` | `indirect` | `derived`
- **`supports_scope`** - `local_proposition` | `hypothesis_bundle` | `cross_hypothesis` | `project_wide`

Methodological scaffolding (analysis methods, definitional/framework material,
historical context) usually does **not** belong as a `proposition`. Use
`method:`, `topic:`, or `discussion:` entity types instead - those don't
require enum classification.

## Companion Skills

- [`SKILL.md`](./SKILL.md) - generic research methodology that this schema overlays.
- [`annotation-curation-qa.md`](./annotation-curation-qa.md) - curated claims that will populate proposition entities.
