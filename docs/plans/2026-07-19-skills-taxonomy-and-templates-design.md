# Skills Taxonomy & Templates — Design

**Status:** design — approved; implementation plan authored (`2026-07-19-skills-taxonomy-and-templates-implementation.md`)
**Companion:** [`2026-07-19-skills-taxonomy-corpus-matrix.md`](./2026-07-19-skills-taxonomy-corpus-matrix.md) — the ratifying classification of all 42 corpus files.

## Goal

Establish a durable, executable doctrine for how Science skills are **classified, named, organized, and authored**, and deliver **one authoring template per recognized leaf archetype** plus a minimal **router profile**. This gives users and agents a familiar, recognizable format when moving between skills, and a decision procedure for creating/splitting/extending skills.

## Scope

**In scope (this phase):**
1. A `meta/` skill (a router + doctrine leaves) defining the taxonomy, naming/placement rules, the frontmatter contract, the create/split/extend decision procedure, and the router invariant.
2. Six archetype templates + one router-profile template.
3. Minimal linter wiring that makes the frontmatter contract executable.
4. The corpus classification matrix (companion), as the ratifying + migration-input artifact.

**Explicitly out of scope (separate downstream project):** the corpus migration — reorganizing/renaming directories, backfilling `archetype:` onto the 34 leaves, extracting doctrine from the 6 hubs, and rewriting `INDEX.md`/the codex mirror to match. This phase produces the taxonomy the migration is *driven by*, so files are never moved twice.

## Motivation

The corpus mixes three orthogonal things into one flat directory layout:
- `data/` conflates generic **data management** (frictionless, sources) with 11 domain-specific **measurement-QA** leaves.
- `statistics/` flat-mixes **method families**, **epistemic-discipline gates**, and **numerical-rigor** skills.
- Names already encode *latent* types (`*-qa`, `*-models`, `prereg-*`, `*-schema`) but nothing declares or enforces them, and there is no authoring standard, so each new skill reinvents its shape.

The corpus matrix confirms the incoherence is specifically **type-mixing**, and that the latent types are stable and populous enough to formalize.

## The model — three layers + orthogonal attributes

A skill is described on **five axes**. Only one becomes a new frontmatter field; the rest are derived or already present.

| Axis | Values | Captured how |
|---|---|---|
| **1. Structural role** | `index`, `router`, `leaf` | **Derived**: `INDEX.md` → index; `SKILL.md` → router; else → leaf. No field. |
| **2. Leaf archetype** | `measurement-qa`, `method-guide`, `analysis-discipline`, `normative-reference`, `tool-guide`, `practice-guide` | **New `archetype:` field** (leaves only, exactly one). |
| **3. Depth** | `standard`, `deep-reference` | Existing `type:` field, **renamed `depth:`**. Absent ⇒ `standard`. |
| **4. Subject** | genomics, transcriptomics, statistics, writing, pipelines, … | **Derived** from path (until migration reshapes the tree). No field. |
| **5. Source-basis** | internal, external-spec, external-tool, external-methodology, mixed | **Derived** from `provenance:`/`sources:` + registry `kind`. Records the *source basis*, **not** governing authority. `spec` ⇒ external-spec; `software`/`package-docs` ⇒ external-tool; `skill-repo` ⇒ external-methodology (ideas/practices basis, e.g. `baygent-skills`); `book`/`paper`/`course` ⇒ supporting citation; multiple substantive source kinds ⇒ mixed. A single cited source never *by itself* sets a skill's source basis to external. No field. |

Each leaf has **exactly one primary archetype**. Subject, depth, provenance, and secondary concerns never create hybrid types. There is **no permanent `hybrid` or `hub` type** — a file that straddles archetypes is a *migration candidate* that must resolve to a dominant contract or be split.

## The six leaf archetypes

Each archetype is defined by its **agent-facing contract**: the question it answers, the required content slots (the template skeleton), and the **success test** — how you check that an agent actually used the skill. An archetype earns a template only when it changes *both* the content slots *and* the success test.

### `measurement-qa`
**Answers:** is this observed or derived measurement trustworthy for inference?
**Definition:** guidance for auditing the validity of observed or derived measurements — their sources, ingestion or construction, quality checks, failure modes, and fitness for downstream inference.
**Classification test:** is the skill primarily evaluating whether a data product *faithfully measures or represents what downstream analysis assumes*? → `measurement-qa`.
**Slots:** sources & ingestion/construction · pre-flight checklist · QA metrics table · common failure modes · halt-on conditions · minimum output-package (fixed directory tree).
**Success test:** does the produced QA package contain the named files, and does the summary state which halt-on conditions were evaluated?
**Spans:** assay/sequencing outputs, protein sequence/structure records, embeddings/manifolds, mutation calls, curated labels and extracted claims.

### `method-guide`
**Answers:** given this question and data-generating situation, which model/procedure applies, and how do I fit and diagnose it?
**Classification test (verb):** central verb is *select / construct / fit / estimate / compare*.
**Slots:** applicability & non-applicability · estimand & assumptions · model/procedure choices · fitting/execution guidance · diagnostics · failure modes · outputs & reporting.
**Success test:** are applicability and assumptions stated, is the model/procedure selection justified, and are model-specific diagnostics present with a verdict downgrade when they fail?

### `analysis-discipline`
**Answers:** regardless of the selected method, what required reasoning, check, or precommitment must be satisfied before the result may be interpreted?
**Classification test (verb):** central verb is *justify / certify / arbitrate / lock / acknowledge / audit* — a discipline applied *to* a result, not a procedure that produces one.
**Slots:** triggering condition · the required reasoning/check/precommitment · decision rule or reasoning criteria · outcomes (pass/fail/indeterminate, or the branch/threshold selected) · halt/escalation conditions · required evidence/artifacts · permitted reporting language.
**Success test:** was the required reasoning/precommitment carried out *before* interpretation, and does the conclusion follow from it — mechanically where a locked table applies, by the stated criteria otherwise?
**Range:** spans hard mechanical gates (`estimator-certification`, `prereg-defensive-instrumentation`); threshold/branch precommitments whose lock is conditional on analyst-chosen thresholds (`replicate-count-justification`, `sensitivity-arbitration`); and reasoning disciplines that gate reporting language without a single lookup table (`bias-vs-variance-decomposition`). `causal-identification` is an analysis-discipline (identification licenses estimation before any model is chosen), not a method-guide.

### `normative-reference`
**Answers:** what must this artifact *mean* or *contain*?
**Classification test:** the skill *is* the contract/schema for an artifact type (vs. teaching how to operate a tool).
**Slots:** scope · vocabulary/schema/enums · invariants · conformance rules · examples · versioning/migration · invalid cases.
**Success test:** is there an explicit conformance check against the vocabulary/invariants — mechanical (lint/validate) where available, an itemized checklist otherwise? (Not necessarily schema-lintable.)

### `tool-guide`
**Answers:** how do I operate this specific product, library, service, or CLI?
**Classification test:** the skill teaches operation of a named product (vs. defining what an artifact must mean). Internal vs. external is *not* the axis — operation is.
**Slots:** setup & version assumptions · command/API surface · failure handling · rate limits (where relevant) · verification/smoke-test.
**Success test:** does the skill complete and verify a *representative operation* end-to-end, including recovery from a common failure? (Not "only the documented commands could have produced X" — that is unprovable.)

### `practice-guide`
**Answers:** how do I carry out this cross-cutting scientific activity well?
**Classification test:** a cross-cutting activity that is not a method, modality, gate, tool, or spec (e.g. scientific writing, literature evaluation).
**Slots:** when to apply · workflow steps · judgment rules · quality criteria · common pitfalls · outputs.
**Success test:** did the agent carry out the cross-cutting practice according to its workflow, judgment rules, and quality criteria?
**Population note:** `practice-guide` has **zero clean leaves today** — its members are trapped inside hubs. It earns a template under the eligibility rule (below) on the strength of two concrete extraction targets: scientific writing (`writing/SKILL.md`) and literature evaluation (`research/SKILL.md`). Writing the template now is what makes those extractions clean at migration.

### Template-eligibility rule (recorded doctrine)
> Template eligibility considers both existing leaves and independently identifiable practices embedded in hubs, provided at least two concrete target extractions demonstrate the same content contract and success test.

## The router profile (structural, not a leaf archetype)

A router is high-leverage — it governs progressive disclosure. Its minimal contract:
- a precise routing trigger;
- a one-sentence scope boundary;
- a leaf table with **load-when** and preferably **do-not-load-when**;
- decision/compose order where leaves combine;
- links to parent/index and neighboring routers;
- **no substantive methodology** that forces every user of the subtree to load it.

This is stated as a **target invariant**, not a description of today's corpus: 6 of 7 current `SKILL.md` files are **hubs** (route + teach). `writing/SKILL.md` is the most acute — 108 lines of doctrine routing to zero leaves. Every hub is a migration extraction candidate (see the matrix). A document that routes *and* teaches is a hub; its teaching content is extracted into typed leaves before it is a true router.

## Authoring policy — naming, placement, create/split/extend

`skill-authoring.md` implements this policy; the implementation plan does **not** invent it.

**Naming (stable identifiers):**
- A skill `name` is a **stable identifier**. Renaming is a breaking change (INDEX.md, the codex mirror, and every cross-reference) and is a migration-scoped operation, never casual.
- `name` is kebab-case and encodes the **promised operation on its subject**, not the tool and not the archetype: `bulk-rnaseq-qa`, not `deseq2-guide`; `survival-and-hierarchical-models`, not `method-guide-survival`. The archetype lives in metadata, never in the name.
- Pre-migration, a leaf name carries the **subject prefix of its placement directory** (`data-`, `data-source-`, `data-expression-`, `statistics-`, `pipeline-`, `research-`). This is a *transitional* convention: the migration reshapes subjects, so prefixes are expected to change then, not now.

**Placement (pre-migration):**
- Place a new skill in the **existing directory whose subject matches**, even though several of those directories are known-incoherent — do **not** begin the reorg early or spin up a new top-level directory. `meta/` is the sole new directory this phase.
- If no existing directory fits, that is a signal to record the placement question for the migration, not to invent structure now.

**Create vs. extend vs. split (observable criteria):**
- **EXTEND** an existing leaf when the new guidance shares its archetype **and** its primary artifact/decision **and** would be loaded in the same task.
- **CREATE** a new leaf when the guidance has a **distinct archetype** *or* a **distinct primary artifact/decision loaded independently**.
- **SPLIT** an existing leaf when it carries **two archetypes** (violating exactly-one) *or* **two independent artifacts/decisions loaded in different tasks** (e.g. `frictionless`: the datapackage contract vs. the CLI tooling).

## Frontmatter contract + linter wiring (minimal, this phase)

The contract must be executable, not merely described. Changes to `science/src/science_tool/skills_lint/`:

- **Add `archetype:`** — MAY be absent; if present, MUST be exactly one recognized scalar from the six-value catalog. **Completeness is not enforced this phase** (leaves are not yet required to declare it). Routers and `INDEX.md` MUST NOT carry `archetype:` (structural role stays derived).
- **Rename `type:` → `depth:`** — values `standard | deep-reference`; absent ⇒ `standard`. The old `type:` key becomes **invalid immediately**. **No compatibility alias** (matches the project's no-legacy-layer rule).
- Update the sole existing declaration (`statistics/replicate-count-justification.md`: `type: deep-reference` → `depth: deep-reference`), plus fixtures, tests, and the generated `codex-skills/` mirror.
- **One shared skill-file iterator.** Introduce a single `iter_skill_files(root)` that excludes **only** `meta/templates/**` (authoring scaffolds), and route all three current independent scanners through it — `lint.py:141` (index coverage), `lint.py:206` (check loop), and `cli.py:66` (`science skills sources`). `INDEX.md` is **not** excluded — the linter must inspect it to enforce that it carries no `archetype:` — so each consumer applies its own structural-role filter (index/router) after iterating. The shared iterator's single job is the `meta/templates/**` exclusion, which would otherwise drift across the three independent `rglob` call sites.
- **Deferred to migration:** making `archetype:` required for leaves and backfilling all 34.

Blast radius this phase: `lint.py`, `sources.py`, `cli.py` (shared iterator + `archetype`/`depth` validation); `codex_skills.py` (see *Codex mirror wiring*); one leaf (`replicate-count-justification`); the linter **and** codex tests/fixtures; `INDEX.md` (new `meta/` entries); and a `codex-skills/` regeneration. The `codex-skills/` mirror **must** be regenerated after any `skills/` change (`test_committed_codex_skills_match_fresh_generation` guards this).

## Deliverable layout

```
skills/meta/
  SKILL.md                     # router (nav-only) for the meta skill — dogfoods the router profile
  skill-taxonomy.md            # normative-reference: the 5 axes, 6 archetypes, frontmatter contract
  skill-authoring.md           # practice-guide: selection/creation/naming/placement, create-split-extend
                               #   decision procedure, router invariant, template-eligibility rule
  templates/                   # authoring scaffolds — EXCLUDED from skill discovery (linter + codex)
    router.md
    measurement-qa.md
    method-guide.md
    analysis-discipline.md
    normative-reference.md
    tool-guide.md
    practice-guide.md
```

**Fixed names (stable public identifiers — chosen now, the plan does not invent them):**
- `meta/SKILL.md` → `name: skill-development` (router; generated Codex name `science-skill-development`)
- `meta/skill-taxonomy.md` → `name: skill-taxonomy` (normative-reference leaf)
- `meta/skill-authoring.md` → `name: skill-authoring` (practice-guide leaf)

`meta/` is a structural container, not a subject, so its leaves take the `skill-` **subject** prefix rather than a literal `meta-` container prefix (subject over container). The router name (`skill-development`) is the umbrella for the whole meta domain; the two leaf names are distinct from it and from each other.

- `skills/meta/templates/` holds authoring scaffolds, not loadable skills. They are **excluded from skill discovery** (the shared iterator → linting, index coverage, `science skills sources`) — same class of special-case as `INDEX.md` — but they are **bundled into the generated codex meta skill as resources**, not discarded. The two meta *leaves* and `meta/SKILL.md` are normal skills: linted, indexed in `INDEX.md`, and mirrored to codex.
- Splitting the doctrine into `skill-taxonomy.md` (the contract) and `skill-authoring.md` (the procedure) dogfoods our own router invariant — `meta/SKILL.md` routes and teaches nothing.

**Codex mirror wiring.** `meta/SKILL.md` is added to `COMPANION_SKILLS` in `codex_skills.py`, so the meta skill mirrors like `research-methodology`/`scientific-writing`: its sibling doctrine leaves (`skill-taxonomy.md`, `skill-authoring.md`) are copied as bundled resources by the existing sibling-`*.md` copy. That copy is currently **non-recursive** (`source_path.parent.glob("*.md")`), so it must be extended to also copy `meta/templates/**` into the generated meta skill directory. `codex_skills.py` and its tests are in the blast radius; regenerate the mirror and keep `test_committed_codex_skills_match_fresh_generation` green.
- **The meta skills dogfood the contract they define.** All three carry `provenance: internal` (internal doctrine — required, since `missing-provenance` is now ERROR-severity). The two leaves also declare `archetype:` — `skill-taxonomy.md` → `normative-reference`, `skill-authoring.md` → `practice-guide`. (`skill-authoring.md` is thereby a third concrete `practice-guide` member, alongside the writing and literature-evaluation extraction targets.) The excluded templates carry no provenance/archetype metadata, which is why they must be excluded rather than linted.

## Success criteria (this phase)

1. `science skills lint` passes on the whole corpus with the new contract (archetype optional-but-validated; `depth:` replaces `type:`; `meta/templates/**` excluded).
2. The six archetype templates + router profile exist, each with its slot skeleton and an explicit "success test" section, and each is internally consistent with its archetype definition here.
3. `meta/SKILL.md` is a pure router; `skill-taxonomy.md` and `skill-authoring.md` carry the doctrine; all three are indexed and mirrored.
4. The corpus matrix is committed as the migration input.
5. No existing leaf's behavior changes (this phase adds doctrine + optional metadata only).
6. Validation (below) passes: executable unit tests green, one template-instantiation test per archetype, and the behavioral scenarios demonstrate the doctrine actually changes classification/authoring outcomes.

## Validation

Two tiers — executable tests (pytest/CI) and behavioral scenarios (agent evals). Both are written **failing-first**.

**Executable unit tests:**
- Linter: `archetype:` absent → OK; present-and-valid → OK; present-and-invalid → `invalid-field`; `archetype:` on a router or `INDEX.md` → error; the old `type:` key → invalid (no alias); `depth:` valid / invalid / absent-defaults-`standard`.
- Shared iterator: excludes `meta/templates/**` and, crucially, does **not** exclude `INDEX.md` (so the linter can enforce no-`archetype:`-on-INDEX); each consumer then applies its own structural-role filter.
- Codex mirror: the generated meta skill exists, bundles `skill-taxonomy.md` + `skill-authoring.md`, **and** copies `meta/templates/**`; `test_committed_codex_skills_match_fresh_generation` stays green after regeneration.

**Template-instantiation tests:** one representative instance per archetype (6) authored from its template, asserted to (a) lint clean under the new contract and (b) fill every required slot in the template skeleton.

**Behavioral scenarios (documented + run via subagents):**
- **Baseline** — classification and authoring scenarios run *without* the doctrine, to establish the failure/variance mode.
- **With-doctrine** — the same scenarios *with* `skill-taxonomy` + `skill-authoring` loaded, showing the doctrine changes the outcome.
- **Ambiguous cases** — at least one create-vs-extend-vs-split boundary and one archetype boundary (e.g. a method-vs-discipline case like `bias-vs-variance`), confirming the decision procedure resolves them as designed.

The behavioral scenarios are the acceptance evidence that the doctrine is load-bearing, not merely present.

## Risks / notes

- **Don't overload `type:`.** The new taxonomy goes on `archetype:`; the existing skill/deep-reference distinction moves to `depth:`. Verified load-bearing: `lint.py` currently reads `type` for `{skill, deep-reference}`.
- **`practice-guide` is justified by trapped population, not current leaves.** If review disagrees, the fallback is to defer only that one template to migration; the other five are unconditional.
- **`research-package-rendering`** stays a migration-candidate; it is not the practice-guide exemplar and its contract is resolved at migration.
- **Boundary/split candidates** (`frictionless`, `mutational-signatures-and-selection`, `research-package-rendering`) are recorded in the matrix for the migration phase; none are split now.
