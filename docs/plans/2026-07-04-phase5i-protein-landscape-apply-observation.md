# Phase 5i Protein Landscape Apply Observation

Date: 2026-07-04

Status: observed on real project

Project: `~/d/protein-landscape`

Protein-landscape commit: `16af102 feat(dag): migrate protein landscape retired edges`

## Context

Phase 5g planned retired-edge migration candidates. Phase 5h scaffolded a reviewed
workbench. Phase 5i compiled and applied that workbench into proposition and
evidence-line entities.

This note records the first real-project apply against
`h01-multi-manifold-protein-universe`, using the six retired edges from
`doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml`.

## Result

The apply path behaved as intended:

- `scaffold-retired-edge-workbench` wrote one workbench file with 6 rows and 10
  inline evidence stubs.
- `apply-workbench` created 6 proposition entities, 10 evidence-line entities,
  and canonicalized the workbench file.
- `dag workbench --check` accepted the committed workbench as canonical.
- `dag validate --dag h01-multi-manifold-protein-universe --format json`
  returned no findings.
- A second `apply-workbench` run returned `status: no-op` and
  `changed_path_count: 0`.

The broader project-level `science validate --verbose` still fails on existing
aggregate-retirement backlog (`aggregate-not-retired-at-v3`). That is unrelated
to the Phase 5i apply; the DAG-specific gates passed.

## Generated Surface

The six proposition ids are:

- `proposition:snapshots-affects-pc1`
- `proposition:lenses-affects-orthogonality`
- `proposition:pc1-affects-residualization`
- `proposition:residualization-affects-coherence`
- `proposition:orthogonality-affects-interaction`
- `proposition:interaction-affects-robust`

The ten evidence-line ids follow the workbench-generated `-evN` convention and
target the generated propositions.

## What The Dogfood Revealed

The compile/apply boundary is sound. The writer produced deterministic files,
preserved idempotency, and did not require hand edits to satisfy the DAG
validator.

The main remaining review cost is semantic, not mechanical: all six rows were
reported as `predicate_review_required` because the retired-edge labels
(`biases`, `yields`, `motivates`, `improves`, `reframes`, `estimates`) do not
map to a richer predicate vocabulary today. The scaffold conservatively emitted
`predicate: affects` for each row. This is acceptable as a migration default,
but it leaves a real review task for the project owner if those relations need
more precise proposition predicates later.

The generated proposition and evidence-line bodies are intentionally sparse
templates. This is acceptable for migration closure, but if these propositions
become user-facing claims, the next refinement is prose authoring rather than
another structural migration phase.

## Follow-Up

Phase 5j should close the retired-edge loop:

- record that these six retired edges have been migrated to proposition/evidence
  entities;
- prevent already-migrated retired edges from resurfacing as actionable
  migration candidates;
- keep the closure tied to generated proposition ids and legacy edge ids, not to
  fragile file paths;
- leave predicate/body polishing as separate project review work.

The acceptance fixture for Phase 5j should include the six
`h01-multi-manifold-protein-universe` rows now migrated in `~/d/protein-landscape`.
