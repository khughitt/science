---
id: "plan:2026-06-26-dataset-catalog-triage-pack-design"
type: "plan"
title: "Dataset catalog triage pack — access semantics, reference-class datasets, coverage reasons, and commons promotion"
status: "proposed"
created: "2026-06-26"
updated: "2026-06-26"
related:
  - "plan:2026-06-21-catalog-datasets-design"
  - "plan:2026-06-21-dataset-catalog-cli-design"
  - "plan:2026-06-24-dataset-verify-access-design"
  - "plan:2026-06-24-dataset-reach-authoring-surfaces-design"
---

# Dataset catalog triage pack

## Purpose

The dataset catalog now has the right core pieces: `science dataset add`,
`science dataset verify-access`, `science dataset prioritize`, `--coverage`, and
the `/science:catalog-datasets` workflow. The remaining feedback is not one
bug. It is a coupled product problem: the current model treats every catalog row
as if it were an obtainable data deposit, while real projects also need to track
reference portals, knowledgebases, metadata catalogs, registration-only
resources, and pointer records that may never materialize as local runtime
files.

This design resolves the open catalog feedback as one triage pack. It keeps the
existing `dataset:*` entity kind, but makes dataset class, access verification,
coverage state, prioritization, and commons promotion explicit enough that
agents can tell "no candidate exists" apart from "a candidate exists but cannot
run yet".

## Feedback covered

- `fb-2026-06-24-003`: gap scan conflates no candidate with inaccessible or
  unverified candidates.
- `fb-2026-06-24-004`: question-side dataset back-edges live in `datasets:`,
  not only `related:`.
- `fb-2026-06-24-005`: `verification_method` values need clearer guidance.
- `fb-2026-06-24-012`: access block alone leaves legacy readiness unknown
  unless `origin` and `license` are also set.
- `fb-2026-06-24-013`: registration-level datasets disappear from default
  prioritize output without enough explanation.
- `fb-2026-06-24-014`: registration-only resources need a clean verified state
  when an agent can confirm the portal but cannot log in.
- `fb-2026-06-24-015`: commons promotion is gated on materialized datapackages,
  which blocks reference and pointer catalogs.
- `fb-2026-06-24-017`: reference-class datasets are not first-class.
- `fb-2026-06-23-008`: old-schema dataset connect steps trigger confusing
  license/provenance warnings.
- `fb-2026-06-23-009`: `access.verified: true` conflicts with
  `dataset_verified_but_unstageable` when tier/stageability is not aligned.
- `fb-2026-06-23-010`: catalog setup still reads pre-layout-v3 `specs/` paths.

## Core decision

Keep `dataset:*` as the single entity kind, but introduce explicit dataset
classes and runtime expectations.

The catalog should distinguish:

| Class | Meaning | Runtime expectation |
|---|---|---|
| `deposit` | Obtainable dataset files, cohorts, or packages intended to become analysis inputs. | May need datapackage/local files when promoted to runnable work. |
| `reference` | Portals, knowledgebases, indexes, or catalogs used for lookup, interpretation, or discovery. | No datapackage required unless a concrete export is later registered as a deposit. |
| `pointer` | Metadata-only record for an external resource useful to track but not yet represented as runnable or reference material. | No runtime files expected; must be visibly non-runnable. |

The existing `source_class` field is currently used for epistemic class values
such as `observational` and `reference`. Overloading it further would keep
semantics muddy. Add a new field:

```yaml
dataset_class: "deposit"  # deposit | reference | pointer
```

Migration/default rule:

- Missing `dataset_class` defaults to `deposit`.
- `source_class` remains a separate epistemic axis (`observational`, `derived`,
  `reference`, etc.) and does not imply `dataset_class`. A reference genome,
  reference annotation, or reference atlas can be a downloadable `deposit`.
- Missing `dataset_class` should produce an info-level
  `dataset.legacy-missing-class` fix-on-touch advisory, not a hard error.
- New `dataset add` defaults to `deposit`; `--class reference|pointer` sets the
  field explicitly.

## Access and verification semantics

The current `verification_method` vocabulary is too deposit-centered. Expand it
while keeping existing values valid:

| Method | Applies to | Meaning |
|---|---|---|
| `retrieved` | `deposit` | Files/artifacts were actually retrieved or listed as directly downloadable. |
| `credential-confirmed` | `deposit`, `reference` | Access was confirmed using held credentials or a login. |
| `landing-confirmed` | `reference`, `pointer` | Landing page, portal, accession, or catalog entry resolves and is usable for lookup. |
| `metadata-confirmed` | `reference`, `pointer` | Metadata record was confirmed, but no runtime data retrieval is expected. |

Use `reference` for a portal, knowledgebase, or lookup surface that is useful
now but does not itself produce runtime files. Use `pointer` for a resource
worth tracking but not yet useful as lookup material or runnable data.

For `deposit`, `access.verified: true` means access to the data itself was
confirmed. For `reference`, it means the reference surface is usable. For
`pointer`, it means the pointer is real and current, not that runnable data
exists.

`science dataset verify-access` remains the only supported command for coupled
legacy backfill. It should:

- set `origin: external` when verifying or exception-gating a non-derived
  dataset;
- require or preserve `license`;
- update `access`;
- set or preserve `dataset_class`;
- print both access readiness and runtime stageability.

Example outputs:

```text
dataset:geo -> access=available (weight 1), runtime=reference-only
dataset:foo -> access=available (weight 1), runtime=unstaged-deposit
dataset:bar -> access=registration-confirmed, runtime=blocked-access
```

## Readiness versus runtime stageability

Access readiness and runtime stageability are different axes.

Access readiness answers: "Can we confirm this resource exists and is accessible
under its class semantics?"

Runtime stageability answers: "Can this resource be used as an input to a
workflow right now?"

Add a small derived runtime state for dataset display, prioritization, and
validation. Runtime state is derived in this precedence order:

1. If `dataset_class=reference`, return `reference-only` even if a stray runtime
   artifact is present. Validation reports `dataset.reference-runtime-artifact`
   separately and suggests converting the row to `deposit`.
2. If `dataset_class=pointer`, return `pointer-only` even if a stray runtime
   artifact is present. Validation reports `dataset.pointer-runtime-artifact`
   separately and suggests converting the row to `deposit`.
3. For `dataset_class=deposit`, if `datapackage`, `local_path`, or another
   runtime artifact exists, return `runnable`.
4. For `dataset_class=deposit`, if access has a Branch-B exception or
   `access.level` is `registration`, `controlled`, or `commercial` while
   `access.verified` is false, return `blocked-access`.
5. For `dataset_class=deposit`, if `access.verified: true`, return
   `unstaged-deposit`.
6. Otherwise return `blocked-access`.

This resolves the `dataset_verified_but_unstageable` confusion: a verified
deposit with no local artifact is not contradictory. It is
`access=available`, `runtime=unstaged-deposit`. The warning should tell the user
to either route to `plan-pipeline`/download work or set the tier to `track` if
it is not intended for immediate execution.

## Coverage and gap reasons

`science dataset prioritize --coverage` should report more than `covered|gap`.

Add:

```json
{
  "target": "question:q001",
  "coverage_state": "blocked-access",
  "gap_reason": "only-gated",
  "datasets": ["dataset:foo"],
  "counts": {
    "runnable": 0,
    "unstaged_deposit": 1,
    "reference": 0,
    "pointer": 0,
    "unverified": 0,
    "gated": 1
  }
}
```

Coverage states:

| State | Meaning |
|---|---|
| `covered-runnable` | At least one runnable deposit reaches the Q/H. |
| `covered-unstaged` | Verified deposit reaches the Q/H, but runtime files are not staged. |
| `covered-reference` | Only reference-class resources reach it. |
| `blocked-access` | Only gated or exception-gated deposits reach it. |
| `unverified` | Candidate datasets reach it, but none are verified or exception-classified. |
| `no-candidate` | No dataset, reference, or pointer reaches it. |

Gap reasons:

- `no-candidate`
- `only-unverified`
- `only-gated`
- `only-reference`
- `only-pointer`
- `unstaged-deposit`

The derivation has one source of truth. Per-dataset runtime states are computed
first. Coverage rows count runtime states for each Q/H target. `coverage_state`
is derived from those counts, and `gap_reason` is then derived 1:1 from
`coverage_state`:

| Coverage state | Gap reason |
|---|---|
| `covered-runnable` | `none` |
| `covered-unstaged` | `unstaged-deposit` |
| `covered-reference` | `only-reference` |
| `blocked-access` | `only-gated` |
| `unverified` | `only-unverified` |
| `no-candidate` | `no-candidate` |

`catalog-datasets` should use these rows as the source of truth. It should not
manually infer coverage by eyeballing only `related:`.

## Prioritization defaults

The default `science dataset prioritize` should remain actionable, but it must
explain exclusions.

Default ranking:

- include public and mixed deposits;
- include verified unstaged deposits;
- exclude registration/controlled/commercial deposits unless `--include-gated`
  or `--level` is set;
- exclude reference and pointer rows from the main runnable ranking unless
  `--include-reference` or `--include-pointer` is set.

Always print or emit a summary:

```text
Excluded by default: 3 gated deposits, 4 reference datasets, 2 pointer records.
Use --include-gated, --include-reference, or --include-pointer to inspect them.
```

JSON output should include `excluded_summary` at top level when using the CLI,
or the library should expose enough data for the CLI to compute it.

## Commons promotion

Promotion eligibility must follow dataset class:

| Class | Promotion rule |
|---|---|
| `deposit` | Promote as runnable only when datapackage/materialized artifact exists, or as candidate deposit if explicitly promoted with non-runnable status. |
| `reference` | Promote as a reference record when `access.verified: true`, `source_url` exists, and verification method is `landing-confirmed`, `metadata-confirmed`, or `credential-confirmed`. |
| `pointer` | Promote only as a metadata stub with explicit `runtime_state: pointer-only`; never counted as a runnable dataset. |

This avoids polluting commons with speculative deposits while allowing shared
catalog resources such as portals and knowledgebases to become first-class
commons records.

## Command changes

### `science dataset add`

Add:

```bash
science dataset add <slug> --class deposit|reference|pointer
```

Defaults:

- `--class deposit`
- `--level controlled` remains existing behavior unless changed separately;
  `catalog-datasets` should keep passing `--level public` for public resources.

For `--class reference`, require `--source-url`.

### `science dataset verify-access`

Add:

```bash
--class deposit|reference|pointer
--method landing-confirmed|metadata-confirmed
```

Validation:

- `retrieved` is invalid for `reference` and `pointer` unless a concrete export
  is being registered as a `deposit`.
- `landing-confirmed` and `metadata-confirmed` are invalid for runnable deposit
  verification.
- Branch-B exceptions remain deposit-centered; references and pointers should
  normally use `verified=false` plus a clear note, or `metadata-confirmed` when
  the pointer is valid.

### `science dataset prioritize`

Add:

```bash
--include-reference
--include-pointer
--runtime-state runnable|unstaged-deposit|blocked-access|reference-only|pointer-only
```

Coverage mode should include coverage state and gap reason rows.

### `/science:catalog-datasets`

Update setup to layout v3:

- read `science.yaml`, `entities/questions/`, `entities/hypotheses/`,
  `entities/datasets/`, and relevant `docs/`/`doc/` context when present;
- do not require `specs/research-question.md` or `specs/scope-boundaries.md`;
- if old paths exist, treat them as optional context.

Update Step 2 discovery:

- classify candidates as deposit/reference/pointer before authoring;
- do not create duplicate deposits for resources already represented as
  reference catalogs;
- use `reference` for portals and knowledgebases.

Update Step 3 verification:

- use `landing-confirmed` or `metadata-confirmed` for reference/pointer rows;
- keep `retrieved` for real deposits.

Update Step 5 prioritization:

- present separate groups: runnable deposits, unstaged deposits, blocked/gated
  deposits, references, pointers.

## Validation changes

Add or adjust checks:

- `dataset.reference-missing-source-url`: reference or pointer row lacks
  `access.source_url`. `access.source_url` is the canonical location.
- `dataset.method-class-mismatch`: verification method is incompatible with
  `dataset_class`.
- `dataset.deposit-verified-unstaged`: verified deposit lacks runtime artifact;
  warning text should say it is access-verified but not staged, not imply access
  verification is wrong.
- `dataset_verified_but_unstageable`: health should exempt `reference` and
  `pointer` classes entirely. Only `unstaged-deposit` should receive actionable
  stageability guidance.
- `dataset.reference-runtime-artifact`: reference row has datapackage/local_path;
  suggest converting to `deposit` if it is now runnable.
- `dataset.pointer-runtime-artifact`: pointer row has datapackage/local_path;
  suggest converting to `deposit` if it is now runnable.
- `dataset.legacy-missing-class`: old rows missing `dataset_class`; info-level
  fix-on-touch guidance, not a hard error.

## Migration and transition

No bulk migration is required for v1.

Transition rules:

- Missing `dataset_class` means `deposit`.
- Existing `source_class: reference` does not change `dataset_class`; it remains
  a separate epistemic label. This is intentionally tested with a downloadable
  reference dataset so reference genomes and atlases do not become
  `reference-only` by accident.
- Existing `verification_method: retrieved|credential-confirmed` remains valid.
- `catalog-datasets` and `verify-access` should write `dataset_class` on touch.

This keeps existing entities readable while making future writes explicit.

## Testing strategy

- Unit tests for class inference from frontmatter.
- Unit tests for runtime-state derivation.
- `verify-access` tests for `landing-confirmed` and `metadata-confirmed`.
- Prioritize tests proving reference/pointer rows are excluded by default but
  included with flags.
- Coverage tests for `no-candidate`, `only-reference`, `only-gated`,
  `only-unverified`, and `unstaged-deposit`.
- Validation tests for method/class mismatch and reference missing source URL.
- Command-doc test that `catalog-datasets` no longer requires
  `specs/research-question.md`.

## Implementation phases

### Phase 1: model helpers and validation

- Expand the authoritative `AccessBlock.verification_method` enum to include
  `landing-confirmed` and `metadata-confirmed`; update Pydantic models, JSON
  schemas, templates, CLI choices, and schema-sync tests in the same change.
- Add `dataset_class` reading/default helpers.
- Add deterministic runtime-state derivation.
- Add validation checks and tests.
- Reword/exempt the health stageability warning for non-deposit classes.

`fb-2026-06-24-004` is already partly implemented: `frontmatter_reach()` reads
the first-class `datasets:` surface on questions and hypotheses. Residual work
belongs to Phase 3: update `/science:catalog-datasets` and its generated skill
so agents author those back-edges consistently instead of relying on `related:`.

### Phase 2: command surfaces

- Extend `dataset add`, `verify-access`, and `prioritize`.
- Update CLI output and JSON shapes.

### Phase 3: catalog workflow and commons

- Update `/science:catalog-datasets` and generated skills.
- Adjust commons promotion rules for reference and pointer rows.
- Mark covered feedback entries addressed once verification passes.

## Success criteria

- `catalog-datasets` can distinguish no candidate from only gated, only
  unverified, only reference, and unstaged deposit coverage.
- Reference portals and knowledgebases can be verified without pretending files
  were retrieved.
- Verified deposits without runtime files produce actionable stageability
  guidance instead of contradictory access warnings.
- Commons can promote verified reference records without requiring a
  materialized datapackage.
- New catalog workflows work in layout v3 projects without relying on old
  `specs/` paths.
