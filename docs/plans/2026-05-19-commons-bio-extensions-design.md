# Phase H — Bio extensions for shared datasets

**Status:** design
**Date:** 2026-05-19
**Parent design:** [`2026-05-13-multiproject-schema-and-shared-store-design.md`](2026-05-13-multiproject-schema-and-shared-store-design.md) §3.6 (Domain extensions) and §9 Phase H
**Predecessor:** Phase G — `science commons promote dataset` ([`2026-05-18-commons-promote-datasets-design.md`](2026-05-18-commons-promote-datasets-design.md))

---

## 1. Goal

Add bio-domain schema mixins to the multi-project commons so that shared datasets carry typed bio metadata (species, assay, matrix shape, value dtype, …) on their canonical surface. Mixins compose with `science-entity-base/1.0+dataset/1.0` via the existing `+`-stacked `schema_profile`. A new `--mixin` option on `science commons promote dataset` is the single entry point for tagging a dataset at promote time.

**v1 scope:** five mixin schemas — two structural (`bio.matrix`, `bio.table`) and three domain (`bio.rnaseq`, `bio.scrna`, `bio.cna`). The existing partial draft `extension-bio-rnaseq-1.0.json` is patched in place (`species` is widened to an array to support mixed-species datasets) since it has no current consumers.

**v1 non-goals:**

- Post-hoc annotation of already-promoted bare datasets. A `commons annotate dataset` command is deliberately deferred; the v1 path is "promote with `--mixin`, or stay bare".
- Inference of mixin / mixin fields from the data file or markdown body. v1 trusts the explicit declaration.
- Mixins for proteomics, epigenome, methylation, mutation calls, etc. Each is a future follow-on.
- A registry-rebuild back-fill that retro-fits `schema_profile` onto entities promoted before Phase H landed. v1 leaves those bare; they can be re-promoted explicitly.

---

## 2. Context

After Phase G landed, the commons can hold hash-verified datasets at
`~/d/science-shared/datasets/<slug>/{entity.md, datapackage.yaml}` with
`schema_profile: science-entity-base/1.0+dataset/1.0`. The dataset mixin
covers commons-wide concerns (datapackage pointer, origin, tier, access,
derivation). Nothing in the v1 dataset mixin captures bio-domain identity,
which means cross-dataset filtering on "all scRNA-seq datasets" or
"all CNA matrices" cannot be done from frontmatter — only from
free-text body content.

Phase H extends the dataset's typed surface with bio mixins. The work is
small because three existing pieces already compose:

- `entity_schema/profile.py` parses arbitrarily many `+`-stacked
  extensions. Its docstring already shows
  `science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.scrna/1.0`.
- `entity_schema/loader.py` maps dotted names (`bio.matrix`) to flat
  filenames (`extension-bio-matrix-1.0.json`) by replacing dots with
  hyphens, and raises `SchemaNotFoundError` when an extension is missing
  — fail-loud by default.
- `entity_schema/validator.py._compose` already `allOf`-stacks
  `profile.extensions` into the composed schema.

Phase H ships:

1. Five new/patched JSON Schemas under
   `science/model/src/science_model/schemas/`.
2. A `--mixin` flag on `science commons promote dataset` that routes
   mixin fields to canonical and rewrites `schema_profile`.
3. A stacking-rule guard in `commons/promote.py` (≤1 structural mixin).
4. Tests at three levels (schema unit, promote integration, end-to-end
   pilot smoke test).

No validator, profile parser, or loader changes are required.

---

## 3. Architecture

### 3.1 Layered mixins

Bio mixins split along **structure** and **domain**:

| Mixin | Layer | What it asserts |
|---|---|---|
| `bio.matrix/1.0` | structural | Dataset is a rectangular matrix of uniform-dtype values (RNA-seq counts, CNA segment-mean, protein quant, methylation β). |
| `bio.table/1.0` | structural | Dataset is a rectangular table with heterogeneous-typed columns (DEG result tables, clinical metadata). |
| `bio.rnaseq/1.0` | domain | Dataset is bulk RNA-seq. |
| `bio.scrna/1.0` | domain | Dataset is single-cell RNA-seq. |
| `bio.cna/1.0` | domain | Dataset is copy-number alteration. |

Structural mixins say "what shape the values have." Domain mixins say
"what the values mean biologically." A typical RNA-seq counts dataset
stacks both: `+bio.matrix/1.0+bio.rnaseq/1.0`. A DEG result table stacks
`+bio.table/1.0` alone (or `+bio.table/1.0+bio.rnaseq/1.0` if the
provenance is RNA-seq).

### 3.2 Stacking rules

- **At most one structural mixin** (`bio.matrix` xor `bio.table`). A
  dataset is one or the other; stacking both is a category error.
- **Any number of domain mixins** (zero or more). Pure-structural is
  allowed; pure-domain is allowed; combined is allowed.
- Stacking order in `schema_profile` follows the source-of-truth
  convention: base → type mixin → structural → domain. The parser does
  not enforce order (composition is `allOf`, which is commutative), but
  the canonical artifact is rendered in this order for readability.

Stacking-rule enforcement lives in `commons/promote.py` rather than in
the validator. JSON Schema speaks per-instance field constraints, not
profile-level structural rules. Keeping the rule in promote keeps the
validator generic.

### 3.3 Field bucketing

All bio mixin fields are **canonical**. They describe the data, not
project-specific interpretation, so they live in the commons entity.md
frontmatter and never in a project overlay. The mechanism is the same
one Phase G uses to split frontmatter into canonical / overlay buckets
(`_classify_entity` in `commons/promote.py`): the per-mixin field set
is added to the canonical allowlist whenever that mixin is active for
a given promote. The plan finalizes whether this is a new
`canonical_fields_from_extensions(...)` helper or an inline extension
of the existing canonical-field set. Overlay attempts to set bio
fields are rejected at overlay-validate time by the overlay schema's
`additionalProperties: false`.

### 3.4 Composition > inheritance

Mixins do not inherit. Each JSON Schema declares only its own fields
with `additionalProperties: false`. Composition is `allOf` at validate
time. A dataset's typed surface is the structural union of all stacked
schemas. Adding a future mixin (e.g. `bio.proteomics`) requires no
changes to the existing five.

---

## 4. Schemas

All five files live in `science/model/src/science_model/schemas/`.

### 4.1 `extension-bio-matrix-1.0.json` (new)

Structural mixin for uniform-dtype rectangular matrices.

```yaml
# Required
n_rows: integer ≥ 1
n_cols: integer ≥ 1
value_dtype: enum ["float32", "float64", "int32", "int64", "uint8", "uint16", "uint32", "bool"]
feature_axis: enum ["rows", "cols"]      # bio convention: usually "rows"

# Optional
row_kind: string                          # e.g. "gene", "probe", "protein", "segment"
col_kind: string                          # e.g. "sample", "cell", "donor"
```

`additionalProperties: false`. Field meanings: `feature_axis = "rows"`
means features (genes, proteins, …) index the rows and observations
(samples, cells) index the columns — the bio convention, opposite of
the pandas / sklearn convention.

### 4.2 `extension-bio-table-1.0.json` (new)

Structural mixin for rectangular tables with heterogeneous columns.

```yaml
# Required
n_records: integer ≥ 1
columns:
  type: array
  minItems: 1
  items:
    type: object
    required: [name, dtype, kind]
    properties:
      name: string (minLength 1)
      dtype: enum ["string", "integer", "float", "boolean", "date", "datetime", "categorical"]
      kind: string                        # e.g. "feature-id", "log2fc", "pvalue", "padj", "stage"
    additionalProperties: false
```

`additionalProperties: false` on the outer object and inner column
descriptor.

### 4.3 `extension-bio-rnaseq-1.0.json` (patch in place)

Domain mixin for bulk RNA-seq. The existing draft is rewritten:

```yaml
# Required
species:
  type: array
  minItems: 1
  items: {type: string, minLength: 1}
assay:
  enum: ["bulk-rnaseq", "ribo-zero-rnaseq", "polya-rnaseq", "3prime-tag-rnaseq"]

# Optional
library_prep: string                     # e.g. "Illumina TruSeq Stranded mRNA"
reference_genome: string                 # e.g. "GRCh38", "GRCh38.p14"
preprocessing_version: string
```

`additionalProperties: false`. Structural fields (`n_samples`,
`n_genes`) are deliberately not declared here — they belong on
`bio.matrix`.

Patch is in-place, not a 1.1, because no entity in the commons currently
references `bio.rnaseq/1.0`.

### 4.4 `extension-bio-scrna-1.0.json` (new)

Domain mixin for single-cell RNA-seq.

```yaml
# Required
species:
  type: array
  minItems: 1
  items: {type: string, minLength: 1}
assay:
  enum: ["10x-chromium-3prime", "10x-chromium-5prime", "drop-seq",
         "mars-seq", "smart-seq2", "smart-seq3", "perturb-seq",
         "split-seq", "indrops"]

# Optional
tissue: string                            # free text; ontology-linkable later
library_prep: string
reference_genome: string
preprocessing_version: string
```

`additionalProperties: false`. Note `bio.scrna` does not carry
`n_cells` — that lives on `bio.matrix` as `n_cols` when
`feature_axis = "rows"`.

### 4.5 `extension-bio-cna-1.0.json` (new)

Domain mixin for copy-number alteration.

```yaml
# Required
species:
  type: array
  minItems: 1
  items: {type: string, minLength: 1}
assay:
  enum: ["snp-array", "array-cgh", "wes-cna", "wgs-cna", "shallow-wgs"]

# Optional
segmentation_method: string               # e.g. "CBS", "GISTIC", "PSCBS"
reference_genome: string
preprocessing_version: string
```

`additionalProperties: false`.

---

## 5. Validator changes

**None required.** The existing infrastructure handles Phase H end-to-end:

- `parse_profile` already accepts arbitrarily many `+`-stacked
  extensions (`profile.py:46-63`).
- `SchemaLoader._filename_for` already maps `bio.<name>` to
  `extension-<flat>-<version>.json` with dots→hyphens
  (`loader.py:39-48`).
- `SchemaLoader.load` raises `SchemaNotFoundError` when a referenced
  extension file is missing — this is the fail-loud behavior chosen for
  unknown bio.* extensions (`loader.py:56-60`).
- `EntityValidator._compose` already `allOf`-stacks `profile.extensions`
  into the composed schema (`validator.py:82-87`).
- The per-`(name, version)` schema cache in `SchemaLoader._cache` covers
  bio extensions for free (`loader.py:27`).

Phase H confirms these paths through tests but adds no new validator
code.

---

## 6. CLI changes

One new option on `science commons promote dataset` — no new
subcommand.

### 6.1 Option shape

```
science commons promote dataset \
    --from <project>           # required (existing)
    --slug <slug>              # required (existing)
    --mixin <spec>             # NEW; repeatable
    [--dry-run] [--force] …    # unchanged
```

`<spec>` accepts two forms:

- **Explicit version**: `bio.matrix/1.0`. Recorded verbatim in the
  canonical `schema_profile`.
- **Sugar**: `bio.matrix`. Resolves at CLI parse time to the highest
  installed version (`1.0` in v1). The resolved version is what gets
  written to `schema_profile`; the entity always records the explicit
  version.

### 6.2 Parsing & validation order

In the CLI handler:

1. Collect `--mixin` values into a tuple. Empty tuple = bare dataset
   (current Phase G behavior, unchanged).
2. Resolve each value's version (sugar → explicit). Reject malformed
   syntax with a clear error pointing at the bad argument.
3. Enforce the stacking rule (`_validate_mixin_stacking`):
   ≤1 structural mixin.
4. Pass the resolved tuple through the per-call promote context (the
   same object that already carries `--from`, `--slug`, `--force`),
   under a `mixin_extensions: tuple[ProfileComponent, ...]` attribute.
   The canonical-render path composes `schema_profile`, classifies
   fields, and runs `EntityValidator().validate(...)` — which now
   exercises the composed schema.

### 6.3 PromoteKindConfig change

Phase G's `PromoteKindConfig` dataclass gains one field, defaulted so
paper/topic/theme are unaffected:

```python
@dataclass(frozen=True, slots=True)
class PromoteKindConfig:
    # ... existing fields ...
    accepts_mixin_extensions: bool = False   # NEW; True only for dataset in v1
```

The dataset kind config sets `accepts_mixin_extensions=True`. Other
kinds reject `--mixin` at CLI-parse time with a clear error.

The resolved tuple of extensions rides through the promote pipeline via
the existing per-call context object (the one that already carries
`--from`, `--slug`, `--force`), not as a new global. One pass-through
parameter, no new state.

### 6.4 Help text

```
  --mixin TEXT     Bio-domain mixin to stack onto schema_profile,
                   e.g. "bio.matrix/1.0" or "bio.rnaseq". Repeatable.
                   At most one structural mixin (bio.matrix or
                   bio.table); domain mixins (bio.rnaseq, bio.scrna,
                   bio.cna) may be combined.

  Example (bulk RNA-seq counts matrix):
    --mixin bio.matrix --mixin bio.rnaseq
```

### 6.5 New error class

`PromoteMixinStackingError`, subclass of the existing
`PromoteValidationError`. Raised by `_validate_mixin_stacking`. Other
bad-mixin paths reuse existing errors:

- Unknown bio.* extension → `SchemaNotFoundError` (from loader, surfaced
  through the validator).
- Missing required field in stacked schema → `EntityValidationError`
  (from the composed `allOf`).
- Wrong kind for `--mixin` (e.g. `promote paper --mixin bio.rnaseq`)
  → `PromoteValidationError` with kind-incompatibility message.

---

## 7. Data flow

```
project-side data-*.md  (bio fields in frontmatter)
        │
        ▼
science commons promote dataset --from <proj> --slug <s> \
                                --mixin bio.matrix --mixin bio.rnaseq
        │
        ▼
CLI handler:
  • Resolve mixin sugar to explicit versions
  • _validate_mixin_stacking(extensions)             ← Phase H
  • PromoteKindConfig(dataset).accepts_mixin_extensions = True
  • Pass extensions through promote context
        │
        ▼
_render_canonical:
  • Compose schema_profile: base + dataset + extensions  ← Phase H
  • Route mixin fields into canonical bucket             ← Phase H
        │
        ▼
EntityValidator().validate(canonical_frontmatter):
  • parse_profile → ProfileString(base, dataset, [bio.matrix, bio.rnaseq])
  • _compose → allOf [base, dataset, bio.matrix, bio.rnaseq]
  • Draft202012Validator runs; raises on first failure
        │
        ▼ (only on validation pass)
write entity.md      ← canonical, includes bio fields and full schema_profile
write overlay        ← project-only fields only; no bio fields
write audit log      ← records active extensions for traceability
```

Atomic semantics from Phase G are unchanged: a validation failure on
the composed schema aborts the promote before any artifact is written
(steps 2–6 of Phase G's apply ordering are unaffected; only validation
content changes).

---

## 8. Testing

Five layers, mirroring Phase A and Phase G patterns.

### 8.1 Schema unit tests

`science/model/tests/test_bio_extensions.py` (new):

- Per mixin (matrix, table, rnaseq, scrna, cna):
  - Minimal valid frontmatter passes.
  - Missing each required field fails with a JSON pointer naming the
    field.
  - Unknown field rejected (`additionalProperties: false`).
- `species` array (rnaseq/scrna/cna):
  - `["Homo sapiens"]` passes.
  - `["Homo sapiens", "Mycobacterium tuberculosis"]` passes
    (mixed-species).
  - `"Homo sapiens"` (bare string) fails.
  - `[]` (empty array) fails.
- Assay enum, per mixin: one in-list value passes; one out-of-list
  value fails.
- `bio.matrix.value_dtype` enum: one in-list passes; one out-of-list
  fails.
- `bio.matrix.feature_axis`: `"rows"` and `"cols"` pass; `"diagonal"`
  fails.
- `bio.table.columns`: at least one column required; per-column dtype
  enum enforced; `additionalProperties: false` on column descriptor.

### 8.2 Validator composition

Extend `science/model/tests/test_entity_schema_validator.py` (or
equivalent test module):

- Composed profile parses end-to-end:
  `science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0`
  → four `ProfileComponent`s in order.
- `allOf` composition is strict: frontmatter that satisfies matrix-only
  fails when rnaseq's required fields are absent, and vice versa.
- `SchemaNotFoundError` raised for a profile referencing
  `+bio.methylation/1.0` (no such schema installed) — confirms the
  fail-loud path.
- Schema cache: validating twice with the same profile loads each
  extension file exactly once (assert via a `unittest.mock` patch on
  `_load_resource` or by inspecting `SchemaLoader._cache`).

### 8.3 Stacking-rule unit tests

In `science/tests/test_commons_promote_dataset.py`:

- `_validate_mixin_stacking(("bio.matrix/1.0",))` → ok.
- `_validate_mixin_stacking(("bio.table/1.0",))` → ok.
- `_validate_mixin_stacking(("bio.matrix/1.0", "bio.table/1.0"))`
  → `PromoteMixinStackingError`.
- `_validate_mixin_stacking(("bio.rnaseq/1.0", "bio.cna/1.0"))` → ok
  (multiple domain mixins permitted).
- `_validate_mixin_stacking(("bio.matrix/1.0", "bio.rnaseq/1.0",
  "bio.cna/1.0"))` → ok.
- `_validate_mixin_stacking(())` → ok (bare dataset).

### 8.4 Promote integration

In `science/tests/test_commons_promote_dataset.py`:

- Fixture: project-side `data-mockrna.md` with full bio.matrix +
  bio.rnaseq frontmatter (n_rows, n_cols, value_dtype, feature_axis,
  species, assay) plus required dataset-mixin fields.
- Invocation: `CliRunner().invoke(commons_group,
  ["promote", "dataset", "--from", "proj-rnaseq", "--slug", "mockrna",
   "--mixin", "bio.matrix", "--mixin", "bio.rnaseq"])`.
- Assertions:
  - Canonical `entity.md` written with
    `schema_profile: science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0`.
  - All bio fields present in canonical frontmatter.
  - Overlay written without any bio field.
  - Audit log records the active extensions in a new top-level
    `mixin_extensions: ["bio.matrix/1.0", "bio.rnaseq/1.0"]` field on
    the success-shape audit YAML (exact field name finalized in the
    Phase H plan).
- Failure cases (each asserts atomic abort with zero writes):
  - Missing required bio field (e.g. `assay`) → `EntityValidationError`.
  - `--mixin bio.table --mixin bio.matrix` → `PromoteMixinStackingError`.
  - `--mixin bio.bogus` → `SchemaNotFoundError` at sugar-resolution time
    (no installed `extension-bio-bogus-1.0.json`).
  - `--mixin bio.matrix` on `promote paper` → `PromoteValidationError`
    (kind doesn't accept extensions).

### 8.5 Pilot smoke test (runbook, not unit test)

Listed in the Phase H implementation plan as a runbook step rather than
in the test suite. Suggested pilot: `data-gse131651-shah2019-nsd2.md`
in `multiple-myeloma` — a clean bulk-RNA-seq case.

Steps:
1. Hand-edit `data-gse131651-shah2019-nsd2.md` frontmatter to add the
   required bio.matrix + bio.rnaseq fields (n_rows, n_cols, value_dtype,
   feature_axis, species, assay).
2. Run `science commons promote dataset --from multiple-myeloma
   --slug GSE131651 --mixin bio.matrix --mixin bio.rnaseq`.
3. Verify the canonical `entity.md` carries the four-segment
   `schema_profile`.
4. Verify the overlay omits bio fields.
5. Verify `science commons show dataset:GSE131651` round-trips the
   composed schema without validation errors.

The pilot runbook validates the end-to-end happy path on real
content. Coverage of `bio.table` and `bio.scrna` in the pilot is
deferred — synthetic test fixtures suffice in v1 — until a real
first-consumer dataset comes up.

---

## 9. Implementation outline

Phase H decomposes into four sub-phases. Each is a single PR.

- **H.1 — Schema authoring.** Write four new JSON Schema files
  (`extension-bio-matrix-1.0.json`, `extension-bio-table-1.0.json`,
  `extension-bio-scrna-1.0.json`, `extension-bio-cna-1.0.json`).
  Patch `extension-bio-rnaseq-1.0.json` (species → array). Add
  `test_bio_extensions.py` (§8.1). No code changes outside `model/`.
- **H.2 — Validator composition tests.** Extend
  `test_entity_schema_validator.py` (§8.2) to cover stacked composition
  and `SchemaNotFoundError` propagation. Confirms the existing
  infrastructure handles the bio extensions end-to-end. No production
  code changes.
- **H.3 — Promote integration.** Add `accepts_mixin_extensions` to
  `PromoteKindConfig`; plumb `--mixin` through CLI, sugar resolution,
  stacking-rule guard, and canonical-render. Set the dataset kind's
  flag. Add `PromoteMixinStackingError`. Cover §8.3 and §8.4 tests.
- **H.4 — Pilot smoke test.** Hand-edit one MM dataset's project-side
  frontmatter; re-promote with bio mixins; verify. Document outcome in
  the Phase H plan's pilot section.

---

## 10. Open questions

- **Future bio mixins.** `bio.proteomics`, `bio.epigenome`,
  `bio.methylation`, `bio.mutations`, `bio.imaging` are obvious
  follow-ons; each is its own small PR using the pattern Phase H
  establishes. Not in v1.
- **Post-hoc annotation.** A dataset promoted bare in Phase G that
  later qualifies for a bio mixin currently has only two paths: a
  manual edit to the canonical entity.md in `~/d/science-shared/`, or
  a re-promote (if Phase G's idempotency supports it cleanly). Whether
  to add a `commons annotate dataset` command is a v1.1 question.
- **Mixin field merge policy in overlays.** v1 declares all bio fields
  canonical-only via `_classify_entity` allowlist extension. If a
  future use case wants a project to override (e.g.) `tissue`, the
  overlay schema (`overlay-1.1.json`) would need to learn about bio
  fields. Not addressed here.
- **Species ontology.** `species: ["Homo sapiens"]` is free-text in v1.
  Linking to NCBI taxonomy IDs is a richer future direction; not v1.
- **Forbid bio mixins on non-dataset kinds at the schema level.** v1
  enforces this in promote CLI only. A future profile-parser rule
  could enforce it structurally — i.e. `+bio.X` is only valid after
  `+dataset/N.N` in `schema_profile`. Not v1.

---

## 11. Files touched (v1)

New:
- `science/model/src/science_model/schemas/extension-bio-matrix-1.0.json`
- `science/model/src/science_model/schemas/extension-bio-table-1.0.json`
- `science/model/src/science_model/schemas/extension-bio-scrna-1.0.json`
- `science/model/src/science_model/schemas/extension-bio-cna-1.0.json`
- `science/model/tests/test_bio_extensions.py`

Modified:
- `science/model/src/science_model/schemas/extension-bio-rnaseq-1.0.json` (species → array; field set rewritten)
- `science/model/tests/test_entity_schema_validator.py` (composition + cache tests)
- `science/src/science_tool/commons/promote.py` (`PromoteKindConfig.accepts_mixin_extensions`, stacking-rule guard, canonical-render extension, `PromoteMixinStackingError`)
- `science/src/science_tool/commons/cli.py` (`--mixin` option, sugar resolution, kind-acceptance check)
- `science/tests/test_commons_promote_dataset.py` (stacking-rule, integration, failure-case tests)

No changes:
- `science/model/src/science_model/entity_schema/{profile,loader,validator,merge,wrapper}.py` — existing infrastructure already supports `+`-stacked bio extensions end-to-end.

---

## 12. Acceptance criteria

- All five mixin schemas validate against the JSON Schema 2020-12 meta-schema.
- A dataset promoted with `--mixin bio.matrix --mixin bio.rnaseq` round-trips through `science commons show` without validation errors and carries the four-segment `schema_profile` in canonical.
- A dataset promoted with `--mixin bio.matrix --mixin bio.table` aborts with `PromoteMixinStackingError` and writes nothing.
- A dataset promoted with `--mixin bio.bogus` aborts with `SchemaNotFoundError` and writes nothing.
- Phase G's atomic-transaction semantics for paper / topic / theme / bare dataset promotes are unchanged (regression coverage in existing Phase G tests passes unmodified).
- The MM pilot (GSE131651) lands cleanly per the §8.5 runbook.
