# Graph Checks in validate.sh — Design

**Date:** 2026-03-06
**Status:** Approved

## Problem

`validate.sh` has 12 prose/structure checks but zero graph checks. Projects with `knowledge/graph.trig` get no validation feedback during the standard `bash validate.sh` workflow.

## Design

### Gate condition

Graph checks only run if `knowledge/graph.trig` exists. When it does, `science-tool` must be on PATH — error if not found.

### Checks

| # | Check | Source | Severity | Details |
|---|---|---|---|---|
| 13a | Parseable TriG | `graph validate` | Error | Parse failure = graph is broken |
| 13b | Provenance completeness | `graph validate` | Error | Claims/hypotheses without `prov:wasDerivedFrom` |
| 13c | Causal acyclicity | `graph validate` | Error | Cycle in `scic:causes` edges |
| 13d | Orphaned nodes | `graph validate` (new) | Warning | Entities with no edges beyond their type triple |
| 13e | Graph-prose sync staleness | `graph diff` | Warning | Prose files changed since last `stamp-revision` |

### Implementation

**Reuse `graph validate`** — single call, parse JSON output, map `status: "fail"` to error or warn by check name. Checks 13a-13c already exist in `validate_graph()`. Add orphaned node check (13d) to `validate_graph()` in store.py.

**Reuse `graph diff`** — single call, any rows in output = stale files = warning with file list.

### Orphaned node check (new in store.py)

Scan `graph/knowledge` for all entities that have an `rdf:type` triple but no other triples as subject or object (excluding the type triple itself). These are "stub" entities that were created but never connected.

### Changes

1. `science-tool/src/science_tool/graph/store.py` — add orphaned node check to `validate_graph()`
2. `science-tool/tests/test_graph_cli.py` — add test for orphaned node detection
3. `scripts/validate.sh` — add section 13 (graph checks)
