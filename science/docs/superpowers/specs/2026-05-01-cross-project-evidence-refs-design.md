# Cross-Project Evidence Refs Design

**Date:** 2026-05-01
**Status:** Approved design
**Scope:** Add first-class graph support for cross-project evidence provenance without
weakening existing local `source_refs` validation.

## Decision

Add a new markdown frontmatter field named `evidence_refs`.

`source_refs` remains strict and local. `evidence_refs` carries provenance references
that may be local project entities, external references, or cross-project addresses.
This lets child projects cite evidence that lives in another registered project while
still keeping typo detection strong for existing `source_refs`.

## Problem

During the Phase 4 cancer federation bootstrap, a new `mechanisms/evolution` child
needed to cite evidence anchors in `multiple-myeloma` and `cbioportal`. Putting those
anchors in `source_refs` caused graph materialization to fail, because `source_refs`
are audited through the local project resolver before graph output is written.

The temporary content workaround was to keep cross-project anchors in a report body
table. That preserves human-readable evidence but loses machine-queryable provenance.

## Goals

1. Preserve current `source_refs` behavior and strict local unresolved-reference
   failures.
2. Let authors put cross-project evidence anchors in frontmatter without blocking
   local graph builds.
3. Materialize cross-project evidence refs as `prov:wasDerivedFrom` edges to stable
   `cancer://<project>/<artifact>` URIs.
4. Continue to support local evidence refs that resolve to local graph entities.
5. Keep the initial change small enough for Phase 4.1 and useful before the Phase 6
   literature manifest work.

## Non-Goals

- Do not relax `source_refs`.
- Do not require local child graph builds to load or validate every registered child
  graph.
- Do not implement full cross-project address resolution against federated graph
  contents in this change.
- Do not introduce a compatibility alias or old field name.

## Field Semantics

`evidence_refs` accepts a list of strings:

- Local entity refs such as `paper:smith-2024` or `hypothesis:h01-demo`.
- External refs already accepted by the graph layer, such as `doi:...`, `url:...`, or
  ontology-backed CURIEs.
- Cross-project addresses that use the existing address shape:
  `<project-id>:<artifact-id>`, for example
  `cbioportal:doc/background/papers/Mina2020.md`.

Cross-project refs are treated as federation addresses. They are not required to
resolve inside the current local project. They should render to the existing
`cancer://` URI scheme using `science_tool.addressing`.

## Graph Behavior

For each entity:

- `source_refs` continues to emit local or external provenance exactly as it does now.
- `evidence_refs` emits `prov:wasDerivedFrom` edges.
- A local `evidence_refs` target resolves through the local resolver and emits a
  provenance edge to the local entity URI.
- An external `evidence_refs` target emits the same bridge-style external reference
  used by current external references.
- A cross-project `evidence_refs` target emits a provenance edge to a URI rendered
  from the address, such as `cancer://cbioportal/doc/background/papers/Mina2020.md`.

## Validation Behavior

Local unresolved refs in `evidence_refs` should still fail materialization. Cross-project
addresses in `evidence_refs` should not fail local materialization.

`source_refs` with a cross-project address should continue to fail unless the target is
also a valid local alias. That preserves the existing meaning of `source_refs`.

## Testing

Add focused tests in `tests/test_graph_materialize.py`:

1. `source_refs` with a cross-project address still fails materialization.
2. `evidence_refs` with a cross-project address builds successfully.
3. The graph contains `prov:wasDerivedFrom` from the citing entity to the
   `cancer://...` URI.
4. Local `evidence_refs` resolve to local entity URIs and produce provenance edges.

## Rollout

After this lands, Phase 4 cancer evolution content can move its cross-project anchors
from the report body table into `evidence_refs`. Phase 6 can then use `evidence_refs`
for literature and evidence assignment without relying on prose-only manifests.
