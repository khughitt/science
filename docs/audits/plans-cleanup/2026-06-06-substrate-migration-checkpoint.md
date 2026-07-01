# Substrate Migration Checkpoint

This checkpoint preserves the durable rationale from the June 6-9 substrate
identity, compiled-model migration, and aggregate-retirement plan cluster. The
implementation is now represented by code, tests, and user-guide documentation,
so the original plan files no longer need to sit in `docs/plans/` as active
work.

## Identity Model

The source loader records row-based identity declarations while loading project
sources. Each declaration carries:

- `canonical_id`
- `participation_mode`: `owner`, `borrower`, or `external-reference`
- `owner_scope`
- adapter name and `SourceRef`
- a `deprecated` flag for transitional owners

`IdentityTable` is the compiled view over those declarations. A collision is
two owner rows with the same `(owner_scope, canonical_id)`. Borrower and
external-reference rows do not own identities and therefore do not participate in
collisions.

Collision severity is centralized on `IdentityCollision.is_genuine`: two or more
non-deprecated owners are a hard error, while a collision involving only one real
owner plus a deprecated aggregate or datapackage owner is carried as transitional
debt and surfaced as a warning. This grade is shared by graph audit, validation,
freshness/build gates, and the entity-layout migrator.

`strict_identity=True` remains the default source-load behavior and raises on
duplicate ownership early. Audit and migration paths that need to diagnose or
carry transitional state load non-strictly so the compiled identity table can
record all rows and produce structured findings.

## Scope-Aware References

Owner scope is part of identity. A project owner and a commons owner of the same
canonical id are different identity keys, not a same-scope collision. When a bare
reference is owned in more than one loaded scope, scope-aware resolution emits an
`ambiguous_reference` audit failure. A scoped form such as
`commons:topic:single-cell-foundation-models` resolves to the named owner scope.

The commons loader records the cross-scope commons owner row without adding a
second project entity. That lets the resolver see the ambiguity while keeping
the local owner as the single materialized project entity.

## Compiled-Model Migration Gate

The v2-to-v3 entity-layout migrator validates the post-move state by compiling a
virtual post-move `ProjectSources` through the canonical loader. The gate loads
with `strict_core_schema=False` and `strict_identity=False` so it can inspect
structured diagnostics instead of crashing on the first duplicate or undated
sentinel.

Apply blockers include:

- genuine identity collisions, meaning at least two non-deprecated owners share
  one `(owner_scope, canonical_id)`;
- graph-audit failures such as unresolved references and ambiguous aliases;
- non-undated `core_schema_validation_failed` rows;
- dangling project-authored `mappings.yaml` alias targets.

Transitional owner shadows are returned under
`transitional_owner_collisions` and do not block apply. The previous
simulate-and-mask date workaround is retired; undated entities use the dedicated
undated guard instead.

## Aggregate Retirement

`science entities triage-aggregate` is the operator surface for retiring
aggregate rows from `entities.yaml`, `terms.yaml`, and single-type aggregate
files such as `doc/<plural>/<plural>.yaml`. With no bucket flags it is read-only
decision support. With `--apply`, it is layout-version gated to v3 projects.

The classifier reads the compiled source model and row metadata. Current buckets
are:

- `shadow`: an aggregate row whose id already has a real owner;
- `coined`: a row that can promote to a first-class owner file;
- `decision-log`: a decision row backed by `core/decisions.md`;
- `external-ref`: a bibliography-backed external reference;
- `curie-external-ref`: a row with `primary_external_id` that migrates to the
  CURIE authority;
- `cruft`: unreferenced migration-artifact rows;
- `referenced-orphan`: migration-artifact rows still structurally referenced;
- `question-deferred`: question stubs that need epistemic authoring;
- `ambiguous`: rows that still need a human identity decision.

Bucket flags control mutations explicitly:

- `--promote-coined` promotes coined rows to owner files and uses marker-gated
  recovery for already-written shadow rows.
- `--delete-cruft` deletes unreferenced migration artifacts.
- `--delete-shadow` deletes rows that already have real owners.
- `--promote-decisions` promotes decision-log sections to `entities/decision/`.
- `--retire-external-refs` deletes bibliography-backed paper/article rows after
  confirming `papers/references.bib` is the authority.
- `--migrate-curie-refs` writes durable CURIE authority rows to
  `knowledge/sources/<profile>/external_refs.yaml`, then drops the aggregate
  row.

`science entities generate-decisions` renders `core/decisions.md` from
`entities/decision/*.md`. The generated view is derived from owner files; the
owner files are authoritative.

## External Reference Authorities

Bibliography and CURIE-reference inputs are external-reference declarations, not
owners. `papers/references.bib` synthesizes lightweight paper/book records so
`paper:` and `cite:` references resolve and minimal paper metadata can
materialize. `knowledge/sources/<profile>/external_refs.yaml` synthesizes
lightweight records for CURIE-backed entities and carries `same_as` mappings so
materialization can emit exact-match links.

Both authorities fail loudly on malformed authority data. They are durable
replacement surfaces for rows previously held in aggregate manifests.

## Dataset Resource Follow-Up

The substrate dataset reconciliation follow-up split dataset identity from
runtime datapackage resources. Datapackages may defer as owners when a Markdown
or aggregate owner already exists, but their resource metadata remains available
for materialization. Local dataset resources can materialize into the datasets
named graph as DCAT distribution and PROV entity triples. Commons-scope dataset
resources remain owned by the commons scope and are not materialized as local
project resources.

The same reconciliation family moved paper-level dataset mentions toward
canonical `dataset_usage` records and kept runtime reconciliation focused on
entity/runtime drift for the supported fields: `license`, `update_cadence`, and
`ontology_terms`.

The transitional identity-collision warning policy is intentional here: a
half-retired aggregate or datapackage shadow should be visible but should not
brick graph build when there is only one real owner.

## Remaining Triage

This checkpoint does not claim every speculative substrate idea is complete.
Still-active or deferred follow-ups include remote/federated scopes, broader
cross-project reference syntax, final removal of remaining aggregate manifests
from downstream projects, and human adjudication for ambiguous aggregate rows.
