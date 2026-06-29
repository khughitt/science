# Phase 3 Completion Checkpoint

Date checkpointed: 2026-06-28

This note preserves the durable context from
`docs/plans/2026-03-07-phase3-completion-design.md` before that active plan was
deleted. It is a historical phase-gate record, not current user workflow
guidance.

## Closure Event

Phase 3 closed on 2026-03-07 in commit `c32c515e`:

`feat: close Phase 3 gate - exemplar evidence, OpenAlex snapshot, starter profile`

That commit added:

- `data/snapshots/openalex-science-map.ttl`
- `data/snapshots/manifest.ttl`
- `docs/biomedical-starter-profile.md`
- `docs/exemplar-evidence/README.md`
- `docs/exemplar-evidence/graph-stats.json`
- `docs/exemplar-evidence/graph-validate.json`
- `docs/exemplar-evidence/graph-diff.json`
- `docs/exemplar-evidence/query-neighborhood.json`
- `docs/exemplar-evidence/query-claims.json`
- `docs/exemplar-evidence/query-coverage.json`
- `docs/exemplar-evidence/validate-sh.log`
- `docs/plan.md` Phase 3 status updates

Commit `1318cab7` later removed the exemplar evidence bundle, biomedical
starter profile, and old `docs/plan.md` during planning-doc cleanup. The
OpenAlex snapshot and manifest remain in the current tree.

## Gate That Closed

The Phase 3 gate required one real project to demonstrate that Science could:

- construct a knowledge graph from prose;
- import a distilled public snapshot;
- run use-case graph queries with structured output;
- detect changes with hybrid graph diff;
- pass graph validation and project validation;
- archive exemplar evidence.

The exemplar project was `~/d/3d-attention-bias/`, titled "3D
Structure-Aware Attention Bias for Nucleic Acid Foundation Models."

The archived evidence README from `c32c515e` recorded these results:

- graph construction from prose: 2,761 triples total;
- local project graph content: 35 concepts, 25 papers, and 27 claims;
- distilled OpenAlex import: 1,684 triples;
- graph validation: 4 of 4 checks passed;
- project validation: passed with two expected warning classes for in-progress
  research markers and citation markers.

## Snapshot Artifact

The current tree still contains the generated OpenAlex snapshot:

- `data/snapshots/openalex-science-map.ttl`
- `data/snapshots/manifest.ttl`

The manifest records:

- source: `https://api.openalex.org/subfields`
- generated at: `2026-03-07T15:51:31+00:00`
- version: `openalex:subfields`
- size: `282 nodes, 1684 triples`
- SHA-256:
  `ee46e42b1a53d27f4c289e7d02d5b53e620f472e87a09b9c0cee06a77dae6fd0`

Current operational guidance for distilling and importing public snapshots lives
in `docs/user-guide/graph-and-derived-state.md`.

## Retired Starter Profile

The deleted biomedical starter profile was derived from the same exemplar. It
documented practical graph-building vocabulary that was useful for a
genomics/deep-learning project:

- common prefixes: `skos:`, `cito:`, `prov:`, `schema:`, `sci:`, and optional
  `biolink:`;
- core graph types: concepts, papers, claims, hypotheses, and questions;
- optional biomedical types such as genes, biological processes, molecular
  activities, chemical entities, nucleic acid entities, information content
  entities, and procedures;
- citation and concept predicates such as `cito:discusses`, `cito:supports`,
  `cito:extends`, `skos:broader`, `skos:narrower`, and `skos:related`;
- validation expectations for graph parseability, provenance completeness,
  causal acyclicity, and orphan checks.

Do not restore that profile as current guidance without updating it for the
modern source-authored entity model. The durable current graph model is
documented in `docs/user-guide/graph-and-derived-state.md` and related
user-guide chapters.

## Cleanup Decision

The active Phase 3 completion plan can be deleted because the historical closure
facts above are preserved here, the reusable snapshot distill/import behavior is
documented in the user guide, and the remaining generated snapshot artifacts
continue to live under `data/snapshots/`.
