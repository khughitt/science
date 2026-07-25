# Data-Product Vocabulary and Skill Coverage (Adaptive Skills v1) — Design

> **Status:** design / spec for review. The implementation plan is a separate
> `docs/plans/2026-07-23-…-implementation.md` produced after this design is approved.
> **Rev 5** — clarifies that the skill overlay is a role-typed Python index joined
> to the project graph by canonical id, not a second in-memory RDF graph.
> **Rev 4** — adds the generation-dispatch matrix, the raw-field/generation-aware
> parser boundary, the command's read-path data-flow, the concrete enrollment
> shape, the structurally discriminated report union, and the full RDF identity
> contract.
> **Rev 3** — resolved the schema-generation mechanism, corpus-vs-observed
> coverage split, `covers:` hierarchy semantics, closed-declaration enrollment,
> the overlay container/lifecycle, and the report/reification contracts.

## Motivation

Phase 4 left a clean, router-invariant skills corpus (46 leaves, zero hubs). The
next ambition is an **adaptive** skill system — one that surfaces where a skill is
*missing*, not merely where an existing one lives. The "skills as KG entities"
framing bundled three separable problems: **routing** (already solved by the
index/router tree), **gap detection** (unsolved; the only part needing the
graph), and **representation** (a means, not an end). Making skills first-class
domain/project nodes pollutes the graph, because a skill is a
**normative/procedural** resource, distinct from the domain *concept* it teaches
and the project *instance* that exercised it. The resolution is a thin
**methodology overlay**: skills stay in their own namespace, derived from
frontmatter, connected to the graph by a few typed edges. Its payoff is
**coverage analysis**, not routing.

## Goal (approved v1 framing — the north star)

> Establish a canonical molecular data-product vocabulary and repair capability
> schema drift; normalize participating bio/assay projects onto it; derive a
> normative skill overlay with validated data-product coverage; join project
> capabilities and canonicalized `skills_loaded` records; report out-of-domain,
> unmapped, and uncovered states separately; generate evidence-backed candidates
> but no skill prose.

## Grounding findings that shape the design

- **No canonical method/data-product namespace exists.** `method` is a core kind
  but project-local, heterogeneous prose (46/51 authored method entities are
  glossary/design notes).
- **The data-product axis exists bottom-up.** `provided_capabilities` on datasets,
  mirrored by `required_capabilities` on questions/hypotheses; shipped validator
  (`dataset_capabilities.py`) and matcher (`datasets/capabilities.py`). Adoption
  where the domain applies: mm30 ~72%, health 95%, cbioportal 76%;
  cancer-evolution 0%, natural-systems 0%.
- **The matcher already defines semantics** (`capabilities.py:46-65`):
  subset-per-set, OR-across-sets, flattening top-level string→string keys (a
  nested `qualifiers:` map would be silently dropped). Required qualifiers
  (health's `analysis_role`/`trait`) carry real gate semantics.
- **The assay/modality boundary is unstable across authors** (mm30 vs health swap
  the roles). mm30 has a closed project-scope vocab
  (`~/d/r/mm30/doc/plans/capabilities-vocab.yaml`, `schema_version: 0`).
- **The capability schema is self-contradictory** (`mixin-dataset-2.0.json` types
  items as `string`; validator + matcher require mappings;
  `mixin-hypothesis-1.0.json` `capability_map` = flat string→string, "38 files, 3
  projects, reached via raw-frontmatter re-parse").
- **Schema versioning is per-kind copy-then-bump, and project entities derive
  their profile** (`profile.py`): `PROJECT_MIXIN_NAMES = {"hypothesis"}` (**no
  question mixin, no plan mixin**), `_DEFAULT_MIXIN_VERSION` is per-kind, project
  entities do **not** carry `schema_profile`. `entity_schema_version` is a
  **closed `Literal[1, 2]`, absent ⇒ 1** (`project_config.py:249`); adding a kind
  to `PROJECT_MIXIN_NAMES` closes **all** its entities under
  `unevaluatedProperties:false`. Flipping a default migrates every entity of that
  kind at once; commons records carry their own profile and migrate individually.
- **`skills_loaded` is not graph-visible.** 21 sources; **16 on retired `kind:
  analysis-plan`, 5 on `kind: plan`**; field absent from model/schemas; retired
  skill ids present.
- **The reach graph does not connect an analysis to its products** — it links
  datasets↔q/h, not `analysis-plan → dataset → data-product`. A dataset merely
  present is *inventory*, not *activity*.
- **Graph layers are per-project** (`constants.py:28`, inside each
  `knowledge/graph.trig`); there is a reification precedent
  (`sci:hasDatasetUsage` → reified record, `dataset_usage.py:34`).
- **Skill frontmatter:** `name`/`description` universal; `archetype` universal for
  **leaves**, absent from **routers** by invariant; no `covers:` field; `##
  Companion Skills` universal and parseable, targets include routers/INDEX.
- **Commons is in the blast radius:** 47 dataset/2.0 records incl. a canonical
  with legacy capability mappings.
- **The toolkit repo is not a Science project** — no `results/` convention, no
  project graph to host a global layer.
- **Packaging precedent:** `science_model/ontologies/` (registry + per-file
  catalog + Pydantic models); ownership/packaging precedent only, not the
  `OntologyCatalog` shape.

## Architecture

### Three-tier data model

Authors **select the data product they have**; they never classify assay-vs-modality.

1. **Data-product term — the sole join key** (`data-product:<slug>`). The catalog
   owns granularity (coverage-relevant platform splits become distinct terms).
2. **Term attributes — decided once in the catalog** (`assay`, `technology`,
   `broader`). Roll-ups derive from these, never from string parsing.
3. **Per-use qualifiers — never identity** (`trigger`, `cohort_design`,
   `analysis_role`, `trait`), on both provided and required entries; they gate
   matching, never change identity.

### The canonical data-product catalog (in `science-model`)

Placement is `science-model` by dependency direction: schema,
project-capability, and skill-coverage validation must work from the pinned
toolkit alone. Uses the `ontologies/` packaging precedent but a dedicated
contract (not `OntologyCatalog`), likely `science_model/data_products/`:

```yaml
schema_version: "1"   # validated string pin (science-model idiom; never a bare int)
terms:
  - id: data-product:gene-expression-bulk-rna
    label: Bulk RNA gene-expression matrix
    assay: gene-expression
    technology: bulk-rna
    broader: [data-product:gene-expression]
```

The catalog contract mirrors `ontologies/` (plain-Pydantic `schema.py` + an
`importlib.resources` loader), and — like the ontology catalogs and the inventory
contracts — pins its version as a **validated string** (`schema_version:
Literal["1"]`), never a bare integer. No `pyproject.toml` change ships it:
hatchling already bundles every non-`.py` file under `src/science_model/`.

Exactly one canonical owner; commons references, never mirrors. Semantic change =
versioned model change; aliases migrate identifiers only. Initial breadth =
**used-terms-only** — the seed is the **union of terms actually observed across
enrolled projects**, structured by the mm30 assay-family vocabulary
(`~/d/r/mm30/doc/plans/capabilities-vocab.yaml`, 17 families); it is a superset of
that file, since live data uses assay/modality pairs the seed omits. `broader`
must form a DAG: **self-referential and cyclic `broader` are rejected at load**,
alongside unresolved parents.

### Capability shape and matching semantics

**One object shape on both sides**, no string-or-object union:

```yaml
- data_product: data-product:gene-expression
  qualifiers: {analysis_role: mr_exposure}
```

**Matching** (rewritten `capabilities.py`): provided term **equals-or-descends**
required term (via catalog `broader`); **every required qualifier equals the
provided** qualifier (subset, scoped to `qualifiers`); **OR across alternatives**.
Tests: exact-term, broader-term (descent), qualifier-mismatch, multiple-alternative.

### Schema-drift repair as a new project schema generation

String→object is breaking; the versioning doctrine is copy-then-bump with a
**closed `entity_schema_version`**. Therefore this repair is a **new project
schema generation (generation 3)**, opted into per project by declaring
`entity_schema_version: 3` (extend the closed `Literal[1, 2] → [1, 2, 3]`).

**Generation-dispatch matrix (not a single constant).** Today
`sources.py:363` arms schema validation only when the pin equals the lone
`ENTITY_SCHEMA_VERSION` constant; simply moving it to 3 would strip generation-2
projects of their strict hypothesis validation. Replace the constant with a
**generation matrix**:

| Generation | Behavior |
|---|---|
| 1 (absent) | legacy: no schema-first validation |
| 2 | hypothesis/1.0 strict |
| 3 | hypothesis/2.0 strict **+** dataset/3.0 + question capability object-shape validation **+** typed plan `skills_loaded` |

**Every shape-selecting authority dispatches on the declared generation (project
entities) or the carried `schema_profile` (commons records), never on the input
shape.** Profile resolution, the load/write gates, the matcher
(`capabilities.py`), and `_capability_shape_issue` each take the generation/profile
and select the string-map (≤gen 2) or object (gen 3) shape accordingly — so the
new object-only parser never rejects a legitimate generation-2 mapping, honoring
the rollback promise.

Authorities and their scope:

- **`mixin-dataset-3.0.json`** (commons mixin, open): `provided_capabilities`
  items become the `{data_product, qualifiers}` object (`data_product` required,
  `data-product:`-patterned). dataset/2.0 retained as rollback. **Project**
  datasets migrate via the generation; **commons** datasets migrate individually
  through their carried `schema_profile` (all 47, incl. the canonical legacy
  mapping).
- **`mixin-hypothesis-2.0.json`** (project mixin, strict): `capability_map` `$def`
  → the same object. hypothesis/1.0 retained. **Every hypothesis entity in an
  enrolled project validates against 2.0** — a no-op for those without
  `required_capabilities`, a shape migration for the 38 that have it.
- **Project datasets get gen-3 capability validation without becoming a strict
  closed mixin.** `_validate_against_schema` (`sources.py:1278`) gates strict
  JSON-Schema checking on `PROJECT_MIXIN_NAMES` (hypothesis only), so project
  datasets never enter it. dataset/3.0 capability object-shape validation is added
  as a **separate generation-gated capability hook** applied to dataset (and
  question) entities under generation 3 — dataset stays a commons (open) mixin and
  is **not** added to `PROJECT_MIXIN_NAMES`.
- **Question and plan are NOT strict JSON-Schema project mixins in v1** (no such
  mixin exists; adding one would force every question/plan entity into a strict
  generation for one field). Crucially, `required_capabilities` is **absent from
  `Entity` today** (`test_hypothesis_entity.py:63`); adding it as an object-only
  typed field globally would hard-fail legacy generation-2 question values at
  Pydantic load, before any WARN validator runs. So the capability fields stay
  **preserved raw frontmatter** (`Entity` `extra="allow"`), read through the
  **generation-aware canonical capability parser** (`capabilities.py`) and checked
  at **WARN** — never a typed object field on `Entity`. **Success is scoped
  accordingly: question capability enforcement is generation-aware validator-level,
  not JSON-Schema-mixin-level.**
- **The matcher/parser** (`datasets/capabilities.py`) and **the validator**
  (`_capability_shape_issue`) become generation-aware: under gen 3, a
  `{data_product, qualifiers}` record validates under both JSON Schema (dataset via
  the gen-3 hook; hypothesis via the strict mixin) and the WARN validator, and a
  legacy string map is rejected **for a gen-3 project**; under ≤gen 2 the string
  map is accepted unchanged. `capability_scope` exemption preserved.

### `skills_loaded` absorption (single truth path, reified)

Migration route, not a raw scanner (which would be a second truth path):

- migrate the 16 legacy `kind: analysis-plan` sources → `kind: plan` +
  `plan_kind: analysis-plan`;
- add a typed `skills_loaded: [{id, reason}]` field to the plan model + validator,
  gated to generation 3. **A malformed `skills_loaded` is a structural error**
  (hard failure at the plan validation gate); the coverage/reference findings it
  later feeds (unmapped/uncovered/`unmapped-skill-reference`) are **WARN
  diagnostics** — the two severities are deliberately distinct.
- canonicalize skill ids through an explicit **alias table**; unresolved ids
  become **`unmapped-skill-reference`** diagnostics (raw id + plan ref), never
  silently "no covering skill."
- **Reject duplicate canonical loads.** Since the load-record identity is
  `(plan, canonical skill, source)` and deliberately **excludes `reason`**, two
  entries that resolve to the same canonical skill under one plan/source — whether
  literally repeated or two raw aliases converging on one canonical id — would
  otherwise silently collapse into a single RDF node bearing multiple
  `sci:loadReason` literals. Canonical skill ids are therefore required **unique
  per `(plan, source)` after alias resolution**; a collision is a **structural
  error** at the plan validation gate (covered by a test), not a silent merge.

**RDF identity contract** (materialized into the project graph for general
queryability; the coverage command does not depend on it — see data-flow below):

- **Skill URI namespace:** a stable, global scheme `sci:skill/<name>` (identical
  across projects, since the skills corpus is toolkit-global). Registered once.
- **Reified skill-load record:** mirrors `sci:hasDatasetUsage`
  (`dataset_usage.py:34`). Destination layer **`graph/provenance`**. Record
  **identity is deterministic** — a stable function of `(plan canonical id,
  canonical skill id, source)` (same hashing discipline as the dataset-usage
  record), so re-materialization is idempotent.
- **Predicates** (registered in `PREDICATE_REGISTRY`, layer `graph/provenance`):
  `sci:hasSkillLoad` (plan → record), `sci:skill` (record → skill URI),
  `sci:loadReason` (record → literal), `sci:usageSource` (record → projection
  source). These names are adopted as the stable public graph API.

### Skills-corpus locator (packaged inventory)

The coverage command must reach the canonical skills corpus, but an **installed**
`science` runs from a research project and the wheel packages only
`src/science_tool` (`science/pyproject.toml:44`) — the repository-root `skills/`
tree is **not shipped**. (`science skills lint` sidesteps this only by defaulting
`--root` to a cwd-relative `"skills"`, `skills_lint/cli.py:29`, which resolves
solely when run from the toolkit checkout.) A cwd-relative or `--skills-root`
locator would forfeit the "pinned toolkit alone is authoritative" property.

The authority is therefore a **version-matched, machine-readable skill inventory
packaged as a toolkit resource inside `science_tool`** (package data under
`src/science_tool/`, so it ships in the wheel automatically). It records, per
skill: canonical name, role (leaf/router), `archetype` (leaves), authored
`covers:` term ids, and companion edges. It is **generated from and drift-checked
against root `skills/`** by a script + a guard test — the same generated-artifact
discipline as `codex-skills/` (`scripts/generate_codex_skills.py`). An installed
`science` at a pinned revision thus carries the inventory that matches its own
code. The inventory is an **input resource**; the command builds a role-typed
Python overlay/index in memory from it (below) — the inventory is not a persistent
overlay, and the corpus is not materialized into a second RDF graph.

### Skill overlay (derived, role-typed, in-memory)

Derived from the packaged skill inventory (above), never a `kind: skill`. Because
the toolkit repo is not a project and graph layers are per-project, the overlay is
**constructed in-memory by the coverage command** from the inventory + catalog —
a role-typed Python lookup keyed by canonical skill id, with no second RDF
materialization, no staleness/fingerprint problem, and nothing to hide from an
assertional graph. The project graph already carries the reified
`sci:skill/<id>` load targets; the command joins those ids against this lookup.
(A persistent XDG global artifact with fingerprint rules is a deferred option,
not v1.)

Overlay resources are **role-typed**:
- **leaf** — requires `archetype`; may carry authored `covers:` (canonical
  data-product ids only, catalog-validated);
- **router** — `archetype` absent by invariant; **no `covers:`**.

Companion edges parse from `## Companion Skills` (targets may be leaf/router/INDEX).

### Coverage: two sets, and the states

For an enrolled analysis touching a term, compute **two distinct sets**:

- **global covering set** — skills in the corpus whose `covers:` includes the
  term (from the overlay);
- **loaded covering set** — skills the analysis actually loaded (via canonicalized
  `skills_loaded`) that cover the term.

**Coverage is exact-term, not ancestor-aware.** A skill covering a broader term
does **not** auto-cover descendant terms. Rationale: the catalog already owns
coverage-relevant granularity (it splits a term precisely when coverage differs),
so ancestor-inheritance would reintroduce the ambiguity the split removed. This is
the deliberate dual of the matcher's descent rule — data *fitness* flows up the
hierarchy (a specific dataset satisfies a general demand); skill *coverage* does
not. Tested on parent/child pairs.

Only an **empty global covering set** yields `uncovered` and a skill candidate.
"Global set non-empty but the analysis did not load it" is a **routing/usage
gap** (`covered-not-loaded`), emitted as its own diagnostic and **excluded from
candidate generation**.

### The evidence occurrence (the real join)

The authoritative plan→dataset edge is an analysis plan's **`dataset_usage`**:

```text
analysis-plan ──dataset_usage──▶ dataset ──provided_capabilities.data_product──▶ term
analysis-plan ──skills_loaded (reified, canonicalized)──▶ skill ──covers──▶ term
```

Only this establishes "an analysis touching product X loaded skill Y", tagged
`observation_level: analysis-usage`. A build that must fall back to shared q/h
reach is tagged `observation_level: project-demand` and makes **no**
co-observation claim.

### Enrollment as a closed declaration

Enrollment is a **closed declaration** in `science.yaml`. The `out-of-domain`
sentinel is kept out of any field that otherwise holds domain identifiers, by
making the **value** the status:

```yaml
skill_coverage:
  domains:
    molecular-measurement: enrolled   # value ∈ {enrolled, out-of-domain}
```

- Domain keys are drawn from a **closed vocabulary** with a single registered
  authority (the coverage module in `science-model`, alongside the term catalog);
  an unknown domain key is a hard config error.
- **Absence of the block, or of a given domain key, means `undeclared`** for that
  domain — never inferred as out-of-domain.
- **Cross-field rule:** `molecular-measurement: enrolled` **requires
  `entity_schema_version: 3`** (enrolling without generation 3 is a config
  validation error), because coverage reads the gen-3 capability shape.

The portfolio scan yields, per registered project:

- **enrolled** (domain declared) → `unmapped` / `uncovered` / `covered-not-loaded`
  occurrences;
- **out-of-domain** (explicitly declared) → exactly one `out-of-domain` result;
- **undeclared** (field absent) → exactly one `undeclared-domain` diagnostic.

`unmapped` = enrolled, relevant analysis activity present but untagged against a
term (mapping debt). natural-systems, once it declares `out-of-domain`, yields one
out-of-domain result; a registered project that has not declared yields
`undeclared-domain`.

### Public interface

- **Portfolio surface:** the existing **global project registry** enumerates
  candidate projects; enrollment is read from each `science.yaml`.
- **Overlay:** global, in-memory, built per command run (above).
- **Command:** `science skills coverage` — portfolio scan emitting the report.
- **Data-flow (read path):** the command builds a **read-only in-memory evidence
  projection from the canonical project loader** (the same `sources`/entities path
  that already materializes plans at `materialize.py:371`) — it computes
  dataset→term (from raw `provided_capabilities`), plan→dataset (from
  `dataset_usage`), and plan→skill (from `skills_loaded`) directly. It does **not**
  require fresh project graphs and does **not** read possibly-stale materialized
  capability edges — capability records are not graph-materialized, and there is
  **no silent source-level fallback**. (The reified skill-load records of the RDF
  contract are materialized for *general* graph consumers; the coverage command is
  independent of them.)
- **Portfolio failure semantics (fail-early):** a registered project that is
  missing, unreadable, has invalid configuration, or fails canonical loading
  **aborts the scan with a nonzero exit**, emits **no partial report**, and leaves
  any `--output` target **untouched**. Such a project is **never** classified as
  `undeclared-domain` — undeclared is a coverage state for a validly-loaded,
  enrolled-vocabulary project, not a stand-in for a load failure.
  > **Superseded by sub-plan 4** ([`2026-07-25-skill-coverage-command-design.md`](2026-07-25-skill-coverage-command-design.md) §6): "fails canonical loading" is narrowed to a two-tier gate — a valid `science.yaml` is required of **every** project, but **source/entity** loading (and its failure gate) applies **only to enrolled** projects; a non-enrolled project's entity integrity is `validate`'s job. The `--output` untouched guarantee is made real by an atomic same-directory temp-file + `os.replace`.
- **Report destination & ownership:** the toolkit has no `results/` convention, so
  there is **no implicit path** — the `coverage-report` JSON is written to
  **stdout by default**, with optional `--output PATH` for a file.
- **Report schema (`coverage-report`) — a structural discriminated union.** Each
  `coverage_occurrences[]` entry is discriminated by `state`, with **state-specific
  required fields** so invalid combinations are unrepresentable:
  - `out-of-domain` / `undeclared-domain` — `{project}` only; **no** `term`, **no**
    `observation_level`;
  - `unmapped` — `{project, observation_level, evidence_refs[]}` (plan/dataset or
    demand evidence); no `term`;
  - `uncovered` — `{project, term, observation_level, evidence_refs[]}` (`term`
    required);
  - `covered-not-loaded` — `{project, term, observation_level,
    available_skill_ids[], evidence_refs[]}` (`available_skill_ids` required, making
    the routing gap actionable).

  Plus a separate `skill_reference_diagnostics[]` of `unmapped-skill-reference`
  `{raw_skill_id, plan_ref}` (may coexist with any coverage state), and
  `candidates[]` from `uncovered` only: `{proposed_scope, likely_archetype |
  indeterminate, score, evidence_refs[]}`. Evidence-backed candidates only — **no
  skill prose is generated.**
  > **Superseded by sub-plan 4** (§5): the diagnostic is `{project, plan_ref, skill_id}` — the reified `SkillLoadRecord` keeps only the **canonical** id, so it reports the canonical (post-alias) id under `skill_id` (not `raw_skill_id`) and adds `project` for cross-project disambiguation. Occurrence and candidate evidence are **structured** (`{plan_ref, dataset_ref}` pairs; candidate `evidence` uses `{project, plan_ref, dataset_ref}` triples), not flattened `evidence_refs[]`, so the cross-project score is reproducible from the report.

## Prioritization

v1 ranks on **measurable, structured signals only**: enrolled-project count on the
term, analysis-plan count touching it (analysis-usage occurrences), feedback
recurrence (`concern`+`target`), and coverage absence/over-generality. Non-
structured factors (consequence severity, detection lateness) are deferred unless
a transparent derivation exists; `likely_archetype` is emitted only when inferable,
else `indeterminate`.

## Scope

**In scope (v1):** the `science-model` term catalog (used-terms-only, DAG-checked);
the generation-3 capability repair (dataset/3.0 + hypothesis/2.0 + validator-level
question/plan + matcher/validator + commons migration) to the `{data_product,
qualifiers}` shape with the matching rewrite; closed-declaration `science.yaml`
enrollment; `skills_loaded` absorption (migrate 16 legacy plans, typed field,
reified materialization, alias table, `unmapped-skill-reference`); catalog-validated
`covers:` on the bio leaf subtree; role-typed in-memory overlay; the
`dataset_usage`-based occurrence join; `science skills coverage` + the
`coverage-report`; exact-only coverage with the two-set (global/loaded) split.

**Deferred:** the method/operation axis (join *and* `covers:` authoring);
`guardsAgainst` failure-mode edges; embeddings (discovery aid only); non-bio
domains; a persistent overlay artifact; strict JSON-Schema question/plan mixins;
typed companion-edge relation semantics.

## Invariants / boundaries

- One object capability shape on both sides; no string-or-object union.
- **Shape is selected by declared generation / carried `schema_profile`, never by
  input shape** — the gen-3 object parser never rejects a gen-2 mapping.
- **Capability fields stay preserved-raw** (never a typed object field on `Entity`,
  which would hard-fail legacy loads); a generation-aware parser reads them.
- Matching = term-equals-or-descends + qualifier-subset + OR.
- **Coverage is exact-term** (never ancestor-aware); only an empty global covering
  set yields `uncovered`/candidate; covered-not-loaded is a routing diagnostic.
- Only **leaf** overlay resources carry `covers:`/`archetype`; routers carry neither.
- Roll-ups derive from catalog relations; `broader` is a DAG (self/cyclic rejected).
- Per-use qualifiers never change term identity; one canonical owner (`science-model`).
- Capability schema changes are copy-then-bump behind a new closed
  `entity_schema_version` generation; prior versions retained as rollback.
- Question capability enforcement is generation-aware validator-level (no strict
  mixin); project datasets get gen-3 capability validation via a generation-gated
  hook, not by joining `PROJECT_MIXIN_NAMES`.
- Malformed typed `skills_loaded` is a **structural error**; coverage/reference
  findings are **WARN**.
- One truth path for `skills_loaded` (migrate + reified materialization); no raw
  scanner. The reified load record has deterministic identity in
  `graph/provenance`; skill URIs use the stable global `sci:skill/<name>` scheme.
- Load-record identity is `(plan, canonical skill, source)` and excludes `reason`;
  canonical skill ids are **unique per `(plan, source)` after alias resolution** — a
  collision is a structural error, never a silent multi-reason merge.
- The skills corpus is reached through a **packaged, drift-checked skill inventory**
  shipped in `science_tool`, never a cwd-relative or `--skills-root` path — the
  pinned toolkit alone is authoritative.
- Enrollment is a closed `science.yaml` declaration where the **value** carries
  status (`enrolled`/`out-of-domain`); absence = `undeclared`; `enrolled` requires
  `entity_schema_version: 3`.
- The overlay is in-memory and never a project graph layer; the coverage command
  reads the canonical loader with no silent stale-graph fallback.
- A missing/unreadable/invalid/unloadable registered project aborts the scan
  nonzero with no partial report and an untouched `--output`; it is never demoted
  to `undeclared-domain`.
- Coverage checks WARN-first, honoring `capability_scope`; ERROR is a later ratchet.
- No autonomous generation of skill prose.

## Migration work

1. Reconcile mm30/health/cbioportal capability values into canonical terms; build
   the value→term crosswalk. The crosswalk is **not purely mechanical** — it
   encodes the catalog's granularity decisions (which raw values collapse, which
   force a term split), so it gets a **review checkpoint before any project
   migration runs against it**.
2. Add the **packaged skill inventory** generator + drift-check guard test
   (generated from root `skills/`, shipped in `science_tool`); author the bio leaf
   subtree's `covers:` term ids and validate them against the catalog.
3. Replace the single-constant schema gate with the **generation matrix** and add
   the gen-3 capability hook (dataset + question); make the matcher/validator
   generation-aware. Introduce generation 3; migrate enrolled projects'
   `provided_capabilities` (project datasets via generation) and
   `required_capabilities` (hypothesis/2.0 + validator-level question) to
   `{data_product, qualifiers}`, preserving health's required qualifiers. Validate
   all enrolled hypothesis entities against 2.0.
4. Migrate the 47 commons dataset/2.0 records to dataset/3.0 via their carried
   `schema_profile`. Only **one** (`hmcl-drug-screen`) carries
   `provided_capabilities` — and it already uses the array-of-maps shape that
   dataset/2.0's `[string]` type forbids, so the drift is live in commons too; that
   record's capability block is reshaped to `{data_product, qualifiers}`. The other
   46 have no capabilities and satisfy dataset/3.0 on the profile bump alone. (There
   is **no** "canonical legacy mapping" record in commons — it does not exist.)
5. Migrate 16 legacy `kind: analysis-plan` → `kind: plan` + `plan_kind`; add the
   typed `skills_loaded` field; build the alias table. Plans already flow through
   `_add_entity` (`materialize.py:371`), so **only skill-load record emission is
   new** — add it to the plan materialization path.

## Testing approach

- Catalog: `schema_version` round-trip; unknown/duplicate ids rejected; `broader`
  resolves; **self-referential and cyclic `broader` rejected** (not only unresolved).
- Matching: exact-term, broader-term descent, qualifier-mismatch, multiple-alternative;
  health's `analysis_role` gate still rejects a descriptive dataset.
- Schema repair / generation dispatch: under gen 3, an object record validates
  (dataset via the gen-3 hook + hypothesis via the strict mixin) and a legacy string
  map is rejected; under gen 2 the same string map **loads unchanged** and hypotheses
  keep strict/1.0 validation (moving the constant did not disarm them);
  `capability_scope` exemption still suppresses; dataset/2.0 + hypothesis/1.0 still load.
- Raw-field boundary: a generation-2 project with legacy string-map
  `required_capabilities` on a question **loads without a Pydantic hard-fail** (the
  field is preserved-raw, not typed on `Entity`).
- Malformed typed `skills_loaded` on a gen-3 plan is a **hard error**; a coverage/
  reference finding on a well-formed plan is a **WARN**.
- Coverage split: empty global set → `uncovered` + candidate; non-empty global but not
  loaded → `covered-not-loaded`, **no** candidate; **exact-only**: a skill covering the
  parent term leaves a child-term analysis `uncovered`.
- `skills_loaded`: migrated plan materializes a reified load record; retired id resolves
  via alias; unknown id → `unmapped-skill-reference` with raw id + plan ref, never
  "no covering skill."
  > **Superseded by sub-plan 4** (§5): the diagnostic carries `{project, plan_ref, skill_id}` (canonical id, since the authored id is not retained by the reified record).
- Occurrence: `dataset_usage` chain yields an `analysis-usage` occurrence; project
  inventory does not; q/h-reach fallback is tagged `project-demand`.
  > **Deferred by sub-plan 4** (§3): v1 emits `analysis-usage` occurrences only; the `project-demand` q/h-reachability fallback is out of scope (it needs epistemic-graph reachability, which the lightweight no-graph read path does not build). The `observation_level` field is kept forward-compatible.
- Enrollment: `molecular-measurement: enrolled` → coverage occurrences; `out-of-domain`
  → one out-of-domain result; **absent → one `undeclared` diagnostic**; an unknown
  domain key is a hard config error; **`enrolled` without `entity_schema_version: 3`
  is a config validation error**.
- Report union: each state carries exactly its required fields — `uncovered` without a
  `term`, or `out-of-domain` with a `term`, is unrepresentable; `covered-not-loaded`
  requires `available_skill_ids`.
- RDF contract: a reified skill-load record lands in `graph/provenance` with
  `sci:hasSkillLoad`/`sci:skill`/`sci:loadReason`/`sci:usageSource`; re-materializing
  identical inputs is idempotent (deterministic record identity).
- Overlay: leaf requires archetype and may carry `covers:`; router rejects both;
  companion edges parse leaf/router/INDEX targets; a `covers:` id absent from the catalog
  fails authoring validation; two runs over identical inputs produce identical overlays.
- Inventory locator: the packaged inventory drift-check fails when it diverges from root
  `skills/` (regenerate-to-fix); the overlay builds from the packaged inventory with **no
  dependence on a cwd-relative `skills/` path** (simulating an installed run).
- Duplicate loads: two `skills_loaded` entries resolving to one canonical id under a
  single `(plan, source)` — literal repeat and two-aliases-converging — are a **hard
  error**, not a single record with two reasons.
- Portfolio failure: a missing/unreadable/invalid/unloadable registered project makes
  the scan exit nonzero, write no report, and leave `--output` untouched — and is **not**
  emitted as `undeclared-domain`.

## Open questions (residual, for the plan)

The rev-3 residuals are now resolved (enrollment shape + vocabulary authority
settled above; plans already materialize via `materialize.py:371` so only load-record
emission is new; the `sci:hasSkillLoad`/`sci:skill`/`sci:loadReason`/`sci:usageSource`
predicates are adopted). Remaining items for the plan:

- The exact CLI grouping/placement of `science skills coverage` (mechanical).
- The concrete contents of the value→term crosswalk — a **data-authoring task, not a
  mechanical one**: it encodes catalog granularity decisions, so it carries a review
  checkpoint (Migration step 1) before project migrations consume it.

## Success criteria

- Schema drift closed at dataset/3.0 + hypothesis/2.0: **dataset and hypothesis
  receive dual (JSON Schema + validator) enforcement of the one object shape, and
  questions receive generation-aware validator enforcement**; prior versions
  retained; a project on generation 2 is untouched.
- Matcher honors term-descent + qualifier-subset + OR (health's gate intact); coverage
  is exact-only with the global/loaded split.
- Enrolled bio projects (incl. commons) carry `data_product`-keyed capabilities; the 16
  legacy analysis-plans are `kind: plan` with reified, alias-canonicalized `skills_loaded`.
- The bio leaf subtree carries catalog-validated `covers:`; the role-typed overlay builds
  deterministically in memory.
- `science skills coverage` emits a `coverage-report` with a discriminated
  `coverage_occurrences[]` (out-of-domain / undeclared-domain / unmapped / uncovered /
  covered-not-loaded), a separate `skill_reference_diagnostics[]`, and `uncovered`-only
  candidates — writing no skill prose, to stdout or `--output`.
- A registered project with no enrollment declaration yields exactly one
  `undeclared-domain` diagnostic; one that declares `out-of-domain` yields exactly one
  out-of-domain result.
