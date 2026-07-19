---
name: skill-taxonomy
description: Use when classifying a skill, choosing its archetype, or applying the skill frontmatter contract. Defines the axes, the six leaf archetypes, and the metadata contract.
archetype: normative-reference
provenance: internal
---

# Skill Taxonomy

## Scope

The classification contract every skill is described by.

## Vocabulary / schema / enums

### The five axes

| Axis | Values | Captured how |
|---|---|---|
| **1. Structural role** | `index`, `router`, `leaf` | **Derived**: `INDEX.md` → index; `SKILL.md` → router; else → leaf. No field. |
| **2. Leaf archetype** | `measurement-qa`, `method-guide`, `analysis-discipline`, `normative-reference`, `tool-guide`, `practice-guide` | **New `archetype:` field** (leaves only, exactly one). |
| **3. Depth** | `standard`, `deep-reference` | Existing `type:` field, **renamed `depth:`**. Absent ⇒ `standard`. |
| **4. Subject** | genomics, transcriptomics, statistics, writing, pipelines, … | **Derived** from path (until migration reshapes the tree). No field. |
| **5. Source-basis** | internal, external-spec, external-tool, external-methodology, mixed | **Derived** from `provenance:`/`sources:` + registry `kind`. Records the *source basis*, **not** governing authority. `spec` ⇒ external-spec; `software`/`package-docs` ⇒ external-tool; `skill-repo` ⇒ external-methodology (ideas/practices basis, e.g. `baygent-skills`); `book`/`paper`/`course` ⇒ supporting citation; multiple substantive source kinds ⇒ mixed. A single cited source never *by itself* sets a skill's source basis to external. No field. |

### Leaf archetypes

#### `measurement-qa`

**Answers:** is this observed or derived measurement trustworthy for inference?
**Classification test:** is the skill primarily evaluating whether a data product *faithfully measures or represents what downstream analysis assumes*? → `measurement-qa`.
**Slots:** sources & ingestion/construction · pre-flight checklist · QA metrics table · common failure modes · halt-on conditions · minimum output-package (fixed directory tree).
**Success test:** does the produced QA package contain the named files, and does the summary state which halt-on conditions were evaluated?

#### `method-guide`

**Answers:** given this question and data-generating situation, which model/procedure applies, and how do I fit and diagnose it?
**Classification test (verb):** central verb is *select / construct / fit / estimate / compare*.
**Slots:** applicability & non-applicability · estimand & assumptions · model/procedure choices · fitting/execution guidance · diagnostics · failure modes · outputs & reporting.
**Success test:** are applicability and assumptions stated, is the model/procedure selection justified, and are model-specific diagnostics present with a verdict downgrade when they fail?

#### `analysis-discipline`

**Answers:** regardless of the selected method, what required reasoning, check, or precommitment must be satisfied before the result may be interpreted?
**Classification test (verb):** central verb is *justify / certify / arbitrate / lock / acknowledge / audit* — a discipline applied *to* a result, not a procedure that produces one.
**Slots:** triggering condition · the required reasoning/check/precommitment · decision rule or reasoning criteria · outcomes (pass/fail/indeterminate, or the branch/threshold selected) · halt/escalation conditions · required evidence/artifacts · permitted reporting language.
**Success test:** was the required reasoning/precommitment carried out *before* interpretation, and does the conclusion follow from it — mechanically where a locked table applies, by the stated criteria otherwise?

#### `normative-reference`

**Answers:** what must this artifact *mean* or *contain*?
**Classification test:** the skill *is* the contract/schema for an artifact type (vs. teaching how to operate a tool).
**Slots:** scope · vocabulary/schema/enums · invariants · conformance rules · examples · versioning/migration · invalid cases.
**Success test:** is there an explicit conformance check against the vocabulary/invariants — mechanical (lint/validate) where available, an itemized checklist otherwise? (Not necessarily schema-lintable.)

#### `tool-guide`

**Answers:** how do I operate this specific product, library, service, or CLI?
**Classification test:** the skill teaches operation of a named product (vs. defining what an artifact must mean). Internal vs. external is *not* the axis — operation is.
**Slots:** setup & version assumptions · command/API surface · failure handling · rate limits (where relevant) · verification/smoke-test.
**Success test:** does the skill complete and verify a *representative operation* end-to-end, including recovery from a common failure? (Not "only the documented commands could have produced X" — that is unprovable.)

#### `practice-guide`

**Answers:** how do I carry out this cross-cutting scientific activity well?
**Classification test:** a cross-cutting activity that is not a method, modality, gate, tool, or spec (e.g. scientific writing, literature evaluation).
**Slots:** when to apply · workflow steps · judgment rules · quality criteria · common pitfalls · outputs.
**Success test:** did the agent carry out the cross-cutting practice according to its workflow, judgment rules, and quality criteria?

## Invariants

- Each leaf has exactly one primary archetype. Subject, depth, provenance, and secondary concerns never create hybrid types. A file that straddles archetypes must resolve to a dominant contract or be split.
- Structural role, leaf archetype, depth, subject, and source-basis remain separate axes. Only archetype and depth are declared fields; structural role and subject are derived.
- A router carries no substantive methodology that would force every user of its subtree to load it.

### The router profile

A router is high-leverage — it governs progressive disclosure. Its minimal contract:

- a precise routing trigger;
- a one-sentence scope boundary;
- a leaf table with **load-when** and preferably **do-not-load-when**;
- decision/compose order where leaves combine;
- links to parent/index and neighboring routers;
- **no substantive methodology** that forces every user of the subtree to load it.

## Conformance rules

- **Add `archetype:`** — MAY be absent; if present, MUST be exactly one recognized scalar from the six-value catalog. **Completeness is not enforced this phase** (leaves are not yet required to declare it). Routers and `INDEX.md` MUST NOT carry `archetype:` (structural role stays derived).
- **Rename `type:` → `depth:`** — values `standard | deep-reference`; absent ⇒ `standard`. The old `type:` key becomes **invalid immediately**. **No compatibility alias** (matches the project's no-legacy-layer rule).
- Every skill Markdown file (router and leaf) must carry `provenance: internal` or valid `sources:` — `missing-provenance` is ERROR.
- **Structural role** — **Derived**: `INDEX.md` → index; `SKILL.md` → router; else → leaf. No field.
- **Subject** — **Derived** from path (until migration reshapes the tree). No field.
- Check conformance mechanically with `science skills lint` where the linter covers the rule; otherwise use the archetype's itemized slot and success-test checklist.

## Examples

| Skill or candidate | Primary archetype | Contract reason |
|---|---|---|
| `bulk-rnaseq-qa` | `measurement-qa` | audits whether RNA-seq measurements are trustworthy for inference |
| `survival-and-hierarchical-models` | `method-guide` | selects, fits, and diagnoses model families |
| `causal-identification` | `analysis-discipline` | identification licenses estimation before a model is chosen |
| `skill-taxonomy` | `normative-reference` | defines what skill metadata and structure mean |
| Frictionless CLI operation guidance | `tool-guide` | teaches a named CLI end-to-end |
| `skill-authoring` | `practice-guide` | governs a cross-cutting authoring activity |

## Versioning / migration

- A skill `name` is a stable identifier; renaming is a breaking, migration-scoped change.
- `depth:` replaces `type:` immediately, with no compatibility alias.
- Declaring `archetype:` remains optional in this phase. Reorganizing the corpus, backfilling all leaves, and extracting methodology from hubs are deferred to the migration driven by the corpus matrix.

## Invalid cases

1. A present `type:`.
2. `archetype:` on a router or `INDEX.md`.
3. An unknown, `null`, list, or mapping `archetype:` or `depth:`.
4. `sources:` and `provenance:` together.
5. Malformed `sources:`.
6. Treating secondary concerns as a hybrid archetype instead of choosing one primary contract or splitting the leaf.

## Success test

Conformance is checked explicitly against the vocabulary and invariants: mechanically with `science skills lint` where available, and with an itemized archetype checklist otherwise.

## Companion Skills

- [`skill-authoring.md`](skill-authoring.md) — the procedure for applying this contract.
- [`../INDEX.md`](../INDEX.md) — the skill index.
