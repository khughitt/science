# Topic Deprecation and Mechanism Design

**Date:** 2026-04-22
**Status:** Draft
**Builds on:**
- `docs/specs/2026-04-05-project-model-design.md`
- `docs/specs/2026-04-20-multi-backend-entity-resolver-design.md`
- `docs/specs/2026-04-21-open-ended-kinds-and-catalog-registration-design.md`
- `docs/specs/2026-04-21-unified-entity-references-design.md`

## Motivation

Recent work on the unified `Entity` model exposed a deeper problem with
`topic:` than missing files or storage inconvenience.

`topic:` has been serving as a semantic sink:

- ontology-backed domain entities (`topic:PHF19`, `topic:multiple-myeloma`)
- methods (`topic:bayesian`, `topic:causal-inference`)
- project-local concepts (`topic:progression`, `topic:subtypes`)
- operational markers (`topic:t414`, `topic:H2`)
- named multi-entity explanatory structures
  (`topic:phf19-prc2-ifn-immunotherapy`)

The existing "narrow `topic` to synthesis notes" direction improves this, but
it still leaves a weak fallback category that tends to absorb anything not yet
otherwise modeled. That is contrary to the purpose of Science's model layer.

The goal is not to provide a small baseline vocabulary and let everything more
interesting collapse into project-specific `topic:` strings. The goal is to:

- use strong domain-agnostic core entities;
- load domain-specific kinds from opt-in ontology catalogs;
- make project extensions explicit and typed when genuinely needed; and
- keep graph semantics in typed entities and explicit relations, not in
  semantically-void labels.

## Core Position

Science should deprecate `topic` as a first-class semantic kind for new work.

That does **not** mean prose topic files must disappear. It means:

- prose documents do not imply `topic:*` entity identities by default;
- semantic meaning should be represented through typed entities, propositions,
  and relations;
- current `topic:*` notes should be reclassified by intent;
- where a project needs a named explanatory multi-entity structure, it should
  use a stricter kind than `topic`.

This spec proposes that stricter kind as **`mechanism`**.

## Scope and Non-Goals

This design is for the **core semantic and tooling direction**, not for
project-by-project migration execution.

For this branch of work:

- do **not** expand the biology catalog opportunistically;
- do **not** rebrand `topic` as a softer synonym for `mechanism`;
- do **not** add wildcard compatibility aliases for new authoring;
- do **not** attempt MM30 entity migration in the same branch as the core
  `mechanism` landing.

MM30 remains the motivating audit case, but migrating MM30 refs is a follow-on
effort after the model and tooling changes land.

## Design Principles

- **Semantic-first, prose-second.** A prose note may describe a thing, but the
  note title is not itself the ontology.
- **No kitchen-sink fallback.** If a label has real semantics, it should map to
  an existing kind or motivate a typed extension.
- **Prefer explicit graph structure.** Multi-entity ideas should be represented
  by typed participants, propositions, and relations before they receive a
  named wrapper entity.
- **Wrapper entities must earn their existence.** A named bundle like
  `phf19-prc2-ifn-immunotherapy` should only be first-class if the graph needs
  to cite, compare, support, dispute, refine, or supersede that bundle as a
  unit.
- **Narrative and semantics are distinct.** `story` is a communication-layer
  synthesis. `mechanism` is a semantic/explanatory structure in the graph.
- **Project extensions are explicit.** If ontology catalogs and core kinds are
  insufficient, use typed project/profile extensions, not `topic`.

## Reclassification Rules

When a user currently reaches for `topic:*`, the system should instead ask:

1. **Is this a single thing with a catalog home?**
   Use a domain kind:
   `gene`, `protein`, `protein_family`, `disease`, `biological_process`,
   `pathway`, `cell`, `drug`, `treatment`, etc.

2. **Is this a method or analytical procedure?**
   Use `method`.

3. **Is this a project-local abstract concept?**
   Use `concept`, preferably in lightweight aggregate storage such as
   `terms.yaml`.

4. **Is this a conjecture under investigation?**
   Use `hypothesis`.

5. **Is this an analysis-session narrative?**
   Use `interpretation`.

6. **Is this a communication-layer synthesis organized around a question or
   hypothesis?**
   Use `story`.

7. **Is this a named explanatory multi-entity structure that the graph needs to
   treat as a semantic object?**
   Use `mechanism`.

If none of the above fits, only then consider a new typed project extension.

## Why `mechanism`

The motivating examples are not well-represented as plain bags of node refs:

- `phf19-prc2-ifn-immunotherapy`
- `proliferation-translation-cell-state-axis`
- `e2f1-repressor-chromatin-crosstalk`

Representing these only as prose topic notes loses structure.
Representing these only as a naked cluster of nodes and edges makes them hard
to cite, compare, support, weaken, or supersede as a unit.

A `mechanism` entity solves that by acting like a disciplined hyperedge or
claim bundle:

- it names a reusable explanatory structure;
- it points to explicit typed participants;
- it points to explicit propositions/findings/interpretations that define it;
- it can carry status and provenance;
- it remains rare and structured rather than becoming a label sink.

## `mechanism` Semantics

### Definition

A `mechanism` is a first-class project entity representing a named explanatory
structure involving multiple typed entities and one or more explicit claims.

It is not:

- a generic theme label;
- a prose convenience title;
- a substitute for missing ontology terms;
- a substitute for `story`, `hypothesis`, or `interpretation`.

### Required properties

A valid `mechanism` should:

- involve at least two typed participant entities;
- be grounded in one or more explicit propositions and/or findings;
- have an authored summary describing the explanatory structure;
- support provenance and status updates over time.

In v1, participant entities should be restricted to the **semantic substrate**:

- ontology/catalog-backed domain entities; and
- project `concept` entities.

They should **not** be compositional communication or reasoning entities such
as `story`, `interpretation`, `hypothesis`, `question`, `task`, or `paper`.
Those entities may discuss, test, organize, or compare a mechanism, but they
should not be mechanism participants.

### Long-term shape

The ideal long-term shape is:

- typed participant links to domain/core entities;
- explicit proposition links describing the mechanism's claims;
- optional grounding links to findings / interpretations / workflow outputs;
- optional prose note for human-readable explanation.

### Minimal v1 shape

To avoid overdesign, v1 should likely require only:

- `participants: list[str]`
- `propositions: list[str]`
- `summary: str`
- normal entity metadata (`id`, `kind`, `status`, `related`, `source_refs`)

This keeps the first landing simple while still making `mechanism` stricter
than `topic`.

For status, v1 should reuse the existing entity-level `status` field rather
than inventing a mechanism-specific vocabulary in the first landing.

This design assumes `proposition` remains the explicit claim substrate.
That is already a first-class Science kind and is not a new prerequisite
introduced by `mechanism`.

## `mechanism` vs existing kinds

### `mechanism` vs `story`

- `story` is for synthesis and communication around a question/hypothesis.
- `mechanism` is the semantic object being claimed.
- A story may discuss or compare one or more mechanisms.

### `mechanism` vs `hypothesis`

- `hypothesis` is a conjecture under investigation.
- `mechanism` is the structured explanatory object.
- A hypothesis may assert that a mechanism holds.
- A mechanism may persist while hypotheses about its scope or truth change.

### `mechanism` vs `interpretation`

- `interpretation` is session-scoped.
- `mechanism` is cross-session and reusable.
- An interpretation may propose, refine, weaken, or dispute a mechanism.

### `mechanism` vs `concept`

- `concept` is a lightweight semantic node for an idea or category.
- `mechanism` is a structured explanatory bundle with explicit participants and
  claims.

### `mechanism` vs future `pattern`

This spec proposes **only `mechanism`** for now.

A future `pattern` kind may become useful for recurring descriptive structures
that are not yet explanatory or causal. But adding both now would create
boundary ambiguity before the first one is operationalized.

The design rule should be:

- if the project is asserting an explanatory structure, use `mechanism`;
- if later we repeatedly encounter important non-explanatory recurring
  structures that do not fit `concept` or `mechanism`, consider `pattern`.

## Topic Deprecation

### New policy

For new modeling work:

- do not create new `topic:*` semantic entities;
- do not recommend topic stubs as the default remediation path;
- treat existing `topic:*` usage as migration debt unless it is already
  reclassified into a more precise existing kind or into `mechanism`.

### Existing topic notes

Existing topic notes can land in one of four buckets:

1. **Reclassify to existing ontology/core kind**
   Examples: domain entities, methods, concepts.

2. **Reclassify to compositional project model kind**
   Examples: `hypothesis`, `interpretation`, `story`.

3. **Reclassify to `mechanism`**
   For named explanatory bundles that need graph identity.

4. **Discard as entity identity**
   Some notes are useful prose but should not survive as KG entities.

## Model Implications

### Domain-agnostic core changes

Likely additions:

- add `mechanism` as a core project kind in the profile model;
- add relation support so mechanisms can point to participants and claims;
- add minimal authoring/materialization support for those mechanism structure
  links.

Explicitly **out of scope for v1**:

- extending evidence/support/dispute/grounding surfaces to target
  `mechanism` directly;
- adding a second new kind such as `pattern`;
- using `mechanism` as a wrapper around arbitrary project entities.

Likely removals/deprecations:

- remove `topic` from the recommended/active core-kind vocabulary for new work;
- eventually remove `topic` from core registration once migration support is in
  place and dependent tooling is updated.

### Topic-deprecation closure criterion

Keep legacy `topic` registration only until all of the following are true:

- active first-party projects no longer author new semantic `topic:*` refs;
- health/curation no longer recommends topic stubs;
- legacy topic-aware features are explicitly labeled legacy/migration-only.

### Bio/domain-model implications

The audit suggests fewer new biology kinds than expected.

The current biology catalog already provides useful homes for many examples:

- `protein`
- `protein_family`
- `cell`
- `drug`
- `treatment`
- `disease`
- `pathway`
- `biological_process`

The bigger issue is not missing generic biology vocabulary; it is that projects
still fall back to `topic` instead of using those kinds.

### Likely extension candidates

The main recurring candidate still appears to be a project/domain extension
such as:

- `cytogenetic_event`

This looks like a real typed domain concept not well captured by the existing
core or by the currently extracted catalog.

### Remaining modeling gaps

Some cases are still imperfect:

- complexes such as PRC2 do not have a clean dedicated biology kind in the
  current extracted catalog;
- disease-stage and disease-substate modeling may eventually merit a cleaner
  ontology strategy.

Those should be addressed by improving domain catalogs or project extensions,
not by preserving `topic`.

## Tooling Implications

The tooling should change its remediation posture.

### Health / audit / migration guidance

Current guidance that says "create missing topic stubs" should be replaced with
semantic triage:

- ontology-backed entity
- method
- concept
- hypothesis
- interpretation
- story
- mechanism
- metadata / bad prefix

### Reference-resolution

Cross-kind fallback remains useful as a migration aid, but it should not become
an excuse to preserve `topic` as a semantic wrapper forever.

### Storage

Storage should remain independent from semantics:

- prose notes can exist without implying `topic:*`;
- lightweight semantic concepts can live in `terms.yaml`;
- full prose docs for mechanisms/stories/hypotheses remain optional when they
  add value.

## Migration Strategy

1. Stop recommending or generating new `topic:*` semantic entities.
2. Add `mechanism` to the model and tooling.
3. Audit existing topic corpora and reclassify:
   - domain kinds
   - methods
   - concepts
   - hypotheses / interpretations / stories
   - mechanisms
   - prose-only notes with no entity identity
4. Treat legacy topic-aware tooling surfaces explicitly as **migration-only**
   surfaces rather than semantic-authoring guidance.
5. Only after the migration surface is stable, deprecate `topic` in core
   registration and tests.

For this design, "migration surface is stable" should mean at minimum:

- active first-party projects no longer rely on newly-authored `topic:*`
  entities for semantic modeling;
- health/curation tooling no longer recommends topic stubs as the default fix;
- legacy topic-specific features are clearly labeled as legacy/migration
  surfaces rather than model guidance.

## Acceptance Criteria

This design is successful if:

- a user no longer needs `topic` as the default place for semantically rich
  project knowledge;
- named explanatory bundles have a strict, structured home (`mechanism`);
- MM30-like notes can be modeled as explicit typed entities and claims rather
  than label nodes;
- project-specific ontology growth happens through typed extension mechanisms,
  not semantic fallback strings.
