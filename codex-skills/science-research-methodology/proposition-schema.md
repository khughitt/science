---
name: research-proposition-schema
description: Use when authoring or updating proposition entities, hypothesis frontmatter, or knowledge-graph claim metadata. Defines the strict enums and field semantics for the Science project model.
---

# Proposition and Evidence Schema

Project-specific schema for the Science proposition/evidence model. For the
generic methodology layer (source hierarchy, evaluating sources, citation
discipline), see [`SKILL.md`](./SKILL.md). For the prose explanation of the
model, see `docs/user-guide/epistemic-model.md` and
`docs/user-guide/evidence-lines.md`.

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

## Bundle Membership and Roles

`discusses:` declares which hypothesis/mechanism bundle(s) a proposition
belongs to (materialized as `cito:discusses`). Each entry has a **membership
role** that controls whether the proposition enters the bundle's weakest-link
belief conjunction:

- `core` (default) - a load-bearing claim of the bundle; **enters** the conjunction.
- `rival` - a competing alternative to the bundle's claims; **excluded** from the conjunction.
- `background` - contextual/governance/scoping material, not load-bearing; **excluded** from the conjunction.

A bare string is sugar for `core`. Use the object form to assign a non-core role:

```yaml
discusses:
- hypothesis:0001-foo            # core (bare string)
- frame: hypothesis:0002-bar     # excluded from 0002's belief conjunction
  role: background
```

A proposition has **exactly one role per bundle frame**. Excluded members are
still listed as bundle members (they show up in coverage and neighborhood
views); they just don't drag the weakest-link belief down.

**Role assignment by authoring surface:**

- `discusses:` frontmatter (above) — full role control via the `role:` field.
- `knowledge/sources/local/relations.yaml` — a `cito:discusses` relation whose
  object is a bundle (hypothesis/mechanism) now accepts an optional `role:` field
  (absent = `core`). The store-CLI bridge also accepts `--bridge-role` when
  ingesting a discusses edge from an external store. A `cito:discusses` relation
  whose object is a non-bundle (e.g. a question or topic) is a plain structural
  link with no membership role.
- `sci:hasProposition` (mechanism steps) is always authoritatively `core` and
  cannot be demoted.

## Companion Skills

- [`SKILL.md`](./SKILL.md) - generic research methodology that this schema overlays.
- [`annotation-curation-qa.md`](./annotation-curation-qa.md) - curated claims that will populate proposition entities.
