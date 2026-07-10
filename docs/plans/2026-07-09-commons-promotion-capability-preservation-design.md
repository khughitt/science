# Commons Promotion — Intrinsic Dataset Capability Preservation

## Status

Proposed. Upstream fix for MM30 task `t871`.
Scope: `science commons promote dataset` + the dataset capability-fit gate.
Does not touch the `capability_scope` marker semantics (already shipped,
`docs/plans/2026-07-07-capability-scope-marker-design.md`) or the overlay schema.

## Context

`science commons promote dataset --slug <slug> --from <project> --apply` promotes a
project dataset entity into `science-commons`, then rewrites the project source
entity into a strict overlay (`overlay_of` + `pin_version` + `source`).

Three fields are **intrinsic to the dataset** — they describe what the dataset
measures, not how one project uses it:

- `provided_capabilities` — the molecular assay/modality the dataset provides,
  consumed by the capability-fit gate.
- `capability_scope` — the intentional "measures nothing molecular" marker
  (Type I clinical/outcome/epi, Type II reference/derived/method/model).
- `identity_context` — organism / reference-genome identity (e.g. `taxon: 9606`).

Promotion currently **drops all three** from both the canonical commons entity
and the project overlay. Verified on the just-promoted HMCL screen
(`science-commons/datasets/hmcl-drug-screen/entity.md`): its source declared
`provided_capabilities: [{assay: drug-sensitivity, modality: cell-line-viability}]`
and `identity_context: {taxon: 9606}`, and the promoted entity carries neither.

Net effect: a commons-promoted dataset **silently loses its capability-fit
provision**. It is non-blocking for HMCL today only because its reached targets
are demand-closed, but it will re-open a `dataset-capabilities.provided-missing`
warning in any consuming project whose open question requires that capability —
a false positive that mislabels an intrinsically-capable dataset as unannotated,
and that can silently distort future capability-fit audits.

## Root cause (verified, file:line)

1. **Promotion drop.** `_classify_entity` (`commons/promote.py:2600-2604`) routes
   each source field by its merge policy:
   `REPLACE / APPEND / FORBIDDEN → canonical bucket`;
   `PROJECT_ONLY` or *no policy entry* `→ project-only bucket`.
   Merge policy is schema-annotation-driven: `read_merge_policy`
   (`model/.../entity_schema/merge.py:21`) reads each field's `science:merge`
   annotation from the composed schema `properties`, defaulting an *undeclared*
   field to `PROJECT_ONLY` at the `merge_policy.get(key, ...)` call. The three
   intrinsic fields are declared in **no** dataset schema component
   (`mixin-dataset-1.0.json` does not list them; the dataset schema is
   `additionalProperties`-open so they validate as free extras), so they fall
   through to project-only, then get filtered out of the overlay too
   (`promote.py:702`, keeping only overlay-1.1 keys). They land in neither
   bucket; `_dataset_dropped_fields` records them for the audit log only.
2. **Commons schema already permits them.** `science-entity-base-1.0.json` and
   `mixin-dataset-1.0.json` both leave `additionalProperties` open; `_compose`
   injects no `additionalProperties: false`. So the canonical commons dataset
   entity **can carry the fields today** — no commons-schema loosening needed.
3. **The gate never resolves overlay → commons, and today drops the overlay
   entirely.** `check_dataset_capabilities` →
   `evaluate_dataset_capabilities(entity_frontmatters(ctx))`
   (`validate/checks/dataset_capabilities.py:242`). `entity_frontmatters`
   (`validate/_helpers.py:146`) returns **raw per-file frontmatter** and
   **skips any record without a `kind`** (`_helpers.py:165`). A dataset overlay
   has no `kind` (overlay-1.1.json is `additionalProperties: false` and does not
   list `kind`), so the promoted dataset's overlay is filtered out before the
   gate ever sees it. Net current behavior: a promoted dataset is **silently
   absent from capability accounting** — it emits no warning *and* provides no
   capability. (Reach still exists via the target side: a hypothesis's `related`
   links the dataset, so `dataset_to_targets` contains it — but the overlay
   record that would carry provision never enters `evaluate_dataset_capabilities`.)
   The gate also never merges an overlay with its commons canonical, so even a
   preserved commons field would be invisible without an explicit resolution
   step.

## Design

Three code parts plus adoption. Boundary decision (confirmed): intrinsic dataset
metadata is preserved on the **canonical commons entity**, and consumers resolve
it through `overlay_of`. The overlay schema stays strict — no duplication of
intrinsic truth into every consuming project.

### P1 — Preserve intrinsic fields on the canonical commons entity

Declare `provided_capabilities`, `capability_scope`, and `identity_context` as
properties of the canonical dataset schema `mixin-dataset-1.0.json`, with
permissive shapes and **no** `science:merge` annotation (so each defaults to
`MergePolicy.REPLACE`, which `_classify_entity` routes to the canonical bucket):

- `provided_capabilities`: `{type: array}` (item shape stays loose — the
  `{assay, modality}` contract remains enforced by the capability gate's
  `_capability_shape_issue`, not duplicated into the schema).
- `capability_scope`: `{type: string}` (the valid-value set stays owned by the
  in-code `capability_scope.py::VALID_SCOPES` framework registry — the schema
  does not re-encode the enum, keeping one source of truth).
- `identity_context`: `{type: object}` (detailed sub-shape remains owned by
  `extension-bio-identity_context-1.0.json` for profiles that compose it; the
  mixin declaration only guarantees preservation for dataset profiles that do
  not compose the extension, which is where HMCL's drop occurred).

Consequence: on the next promotion these fields route to the canonical bucket
and appear in `science-commons/datasets/<slug>/entity.md`. They are still
excluded from the overlay (not overlay-1.1 keys), so the overlay stays strict.
No `MergePolicy.CANONICAL` value is invented — `REPLACE`-into-canonical is the
existing, correct routing.

**Why P2 (a separate overlay-merge-policy step) is unnecessary.** `merge_entity`
(`commons/overlay.py:271`) seeds `merged = dict(canonical.frontmatter)` and only
*overrides* fields that are present on the overlay. Canonical-only intrinsic
fields therefore surface into `merged_frontmatter` automatically, tagged source
`canonical`. The `OverlayMergeError` path (`overlay.py:279`) fires only for a
field **present on the overlay** with no policy — which these fields never are.
So P1 alone makes overlay resolution well-formed for the intrinsic fields; no
overlay-side policy change is required.

### P3 — Capability gate resolves overlay → commons (scoped resolver)

Because the overlay is dropped by the `kind` filter before the gate runs (root
cause #3), the fix is not a map over `entity_frontmatters` — it must **discover
the overlay dataset descriptors separately and inject their resolved provision**
into the record set. `entity_frontmatters` stays the raw project-local view for
every other check (access/acquisition/location checks legitimately want the raw
overlay).

`effective_dataset_frontmatter(overlay_fm, *, resolver=resolve_entity)` contract,
applied to a discovered overlay descriptor (`overlay_of` present):

- **Resolves cleanly** → return the **canonical** commons frontmatter
  (`resolve_entity(overlay_fm["overlay_of"], project=None).merged_frontmatter`)
  with `_path` re-injected from the overlay and `related` unioned
  (canonical ∪ overlay, for dataset-side reach). `project=None` is deliberate:
  the three intrinsic fields are canonical-only (the overlay cannot carry them),
  so the canonical view already holds the effective provision — no overlay
  merge, hence no `OverlayMergeError` path and no project-registration lookup.
  The canonical carries `kind: dataset`, so the record now enters the gate's
  dataset branch.
- **Commons store genuinely unreachable** (`CommonsRootNotFoundError`) → raise
  `CommonsUnavailable` (a new, narrow signal). The gate **defers**: it simply
  does not add that dataset to the record set, so no `provided-missing` fires.
  An overlay's provision lives in commons by definition, so its raw frontmatter
  is *never* treated as "missing". P4's promote-time guard is the real
  enforcement point, so validate stays quiet and correct in environments without
  the commons mount.
- **Resolution otherwise fails** (`CommonsEntityError` — dangling `overlay_of` —
  or any other `CommonsError`) → raise `OverlayResolutionError`. The gate
  surfaces this as an **explicit `Severity.ERROR` result, no raw fallback**
  (`dataset-capabilities.overlay-unresolved`) — a real defect, not an
  environmental gap. This is the check's first non-WARN result, and is intended.

Adoption is in exactly **one** check, `check_dataset_capabilities`: it appends
the resolved overlay dataset records to `entity_frontmatters(ctx)` before calling
`evaluate_dataset_capabilities`. Owner datasets (in `entities/datasets/`, which
carry `kind`) already flow through `entity_frontmatters`; an owner and its
overlay never coexist for one id, so appending resolved overlays introduces no
duplicate records.

The promotion-contract check (`dataset_promotion_contract`, reading via
`dataset_frontmatters`, `_helpers.py:111`) is **explicitly out of P3**. It does
not inspect capability fields today — for a pinned overlay it loads the commons
canonical only for pin/version/class and then validates the source — so routing
it through the effective resolver would add blast radius with no behavioral need.
It keeps its current raw view.

The distinct `CommonsUnavailable` vs `OverlayResolutionError` types are what
reconcile the two review directives ("defer if unresolvable" vs "fail the check
explicitly, no raw fallback"): environmental-unreachable defers; structural
defect fails.

### P4 — Fail-early promotion guard

After `_classify_entity` in `plan_promote`, assert that every intrinsic field
present in the source frontmatter landed in the **canonical** bucket. If any did
not, raise a promotion error naming the field. With P1 this never fires in normal
flow; it is the backstop that makes silent capability loss *structurally
impossible* — e.g. if a schema declaration is later removed, or an
identity-bearing dataset uses a profile that does not preserve `identity_context`,
promotion fails loudly instead of dropping provision.

`INTRINSIC_DATASET_FIELDS = frozenset({"provided_capabilities",
"capability_scope", "identity_context"})` is defined once and shared by P4 and
the P3 resolver's documentation.

### Adoption / cleanup

- **Backfill HMCL.** Re-promote `hmcl-drug-screen` (or patch + commit the commons
  entity) so `science-commons/datasets/hmcl-drug-screen/entity.md` carries
  `provided_capabilities: [{assay: drug-sensitivity, modality: cell-line-viability}]`
  and `identity_context: {taxon: 9606}`; reindex the commons store.
- **Rescope `t871`.** Remove the stale clinical-warning framing from the task
  brief; the "intentionally no molecular capability" state is already shipped and
  adopted (`capability_scope`, MM30 t856). The residual task is exactly this
  promotion-preservation fix.
- **Correct the stale memory note** claiming clinical warnings are standing.

## Testing

Upstream (`science/tests/`), one assertion per seam:

- **P1 plan** (`test_commons_promote_dataset_plan.py`): a source frontmatter with
  all three intrinsic fields classifies them into the **canonical** bucket, not
  project-only.
- **P1 apply** (`test_commons_promote_dataset_apply.py`): the written commons
  `entity.md` contains all three; the written overlay contains **none** (schema
  stays strict).
- **P1 `identity_context` composition** (`model/tests/`): a dataset profile
  *without* the bio-identity extension preserves and validates a simple
  `identity_context` (e.g. `{taxon: 9606}`) via the permissive mixin
  declaration; a profile that *does* compose
  `extension-bio-identity_context-1.0.json` still enforces the deep shape
  (a malformed `identity_context` fails validation under that profile). Confirms
  the `allOf` composition preserves-without-loosening.
- **P3 resolver** (new `test_effective_dataset_frontmatter.py` or in the gate
  test): (a) a non-overlay dataset returns raw frontmatter unchanged; (b) an
  overlay whose commons canonical provides `provided_capabilities` yields merged
  frontmatter carrying it; (c) the overlay cannot override the canonical
  intrinsic value; (d) `CommonsRootNotFoundError` → `CommonsUnavailable` → gate
  defers (no `provided-missing`); (e) dangling `overlay_of` /
  `OverlayMergeError` → `OverlayResolutionError` → explicit check failure.
- **P3 gate** (`validate/test_checks_dataset_capabilities.py`): an overlay
  dataset reaching a live target emits **no** `provided-missing` when its commons
  source provides the capability; still emits `provided-missing` when the commons
  source genuinely lacks it and no `capability_scope` applies.
- **P4 guard** (`test_commons_promote_dataset_apply.py` or plan): a source that
  carries an intrinsic field which would be dropped (simulate by removing the
  schema declaration in-test) raises the promotion guard error.

## Risks and boundaries

- **Blast radius contained.** Only two checks change behavior (both intentionally);
  `entity_frontmatters` and all other validators keep the raw project-local view.
- **Commons-offline correctness.** The defer branch prevents CI/headless
  environments without the commons mount from emitting false `provided-missing`
  warnings; the promote-time guard, which runs where the commons store *is*
  present, remains the fail-closed enforcement point.
- **No enum duplication.** `capability_scope` valid values and the
  `{assay, modality}` shape stay single-sourced (in-code registry + gate),
  not re-encoded in JSON schema.
- **Out of scope.** No change to `capability_scope` semantics, the overlay
  schema, the capability vocabulary, or the coverage-state enumeration.
  `identity_context` deep-shape ownership stays with its bio-identity extension;
  the mixin declaration only guarantees non-drop.
