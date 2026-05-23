# store.py Decomposition — Design

**Status:** Approved design (2026-05-23), revised after review (rev b). Next: implementation plan via writing-plans, then subagent-driven-development.

**Goal:** Break the 4,773-line `science/src/science_tool/graph/store.py` monolith into a `store/` package of focused, single-responsibility submodules — a behavior-preserving code-move — before starting evidence-aggregation Phase 2.

**Scope:** `store.py` only. The other large graph modules (`health.py`, `materialize.py`, `sources.py`) are cohesive single-responsibility files and are explicitly out of scope.

**Non-goals:** No behavior change. No signature change. No constant-value change. No deduplication of code that happens to be triplicated elsewhere (e.g. `_graph_uri` also exists in `io.py` and `materialize.py` — left alone). No new feature work. No changes to `graph/__init__.py`. No `query_uncertainty` belief-unification (deferred to Phase 2).

**Single deliberate exception to "verbatim move":** `_copy_viz_notebook`'s `Path(__file__).resolve().parents[2]` becomes `parents[3]` — see notebooks.py below. This is the only edit to a moved function body.

---

## Motivation

`store.py` is a god-module spanning six distinct responsibilities: graph mutation (`add_*`), export/serialization, inquiry render/validate, the read/query-summary layer, graph validation, and low-level dataset I/O. The ~1,300-line read/query-summary region is both the largest single chunk and the exact region evidence-aggregation Phase 2 will keep editing (numeric belief weights, `query_uncertainty` unification, snapshots, posteriors). Splitting it out first lets Phase 2 land in clean, focused modules instead of compounding the monolith.

## Architecture

`store.py` (module) becomes `store/` (package). Code moves into focused submodules arranged as a **strict linear-topological dependency order**: a module may import only from modules that appear earlier in the order below (plus external deps: `science_model.*`, `graph.io`, `graph.export_types`, `graph.belief`, `graph.sources`). This guarantees acyclicity. `store/__init__.py` re-exports the complete current public-and-used symbol surface, so every existing importer keeps working unchanged.

**Dependency order (earlier modules cannot import later ones):**

```
graph/store/
  __init__.py          # re-exports the public+used surface (incl. private helpers)

  1.  constants.py         # no intra-package deps
  2.  types.py             # no intra-package deps
  3.  graphutil.py         # no intra-package deps   (pure edge-list algorithms: _has_cycle)
  4.  identity.py          # ← constants
  5.  notebooks.py         # ← constants            (viz-notebook scaffolding)
  6.  dataset.py           # ← constants, identity, notebooks, io
  7.  evidence_signals.py  # ← constants, types, identity, dataset
  8.  mutations.py         # ← foundation (1–6)      (largest, ~1000 ln; all graph writes)
  9.  export.py            # ← evidence_signals + foundation
  10. inquiry.py           # ← graphutil + foundation
  11. snapshot.py          # ← dataset, io
  12. validation.py        # ← graphutil + foundation
  13. queries.py           # ← evidence_signals + foundation
  14. summary.py           # ← evidence_signals + foundation   (independent of queries)
  15. dot.py               # ← queries + foundation            (build_graph_dot calls query_neighborhood)
```

Key edges this ordering encodes (each verified against current code):
- `dataset.init_graph_file` → `notebooks._copy_viz_notebook` ⇒ notebooks before dataset.
- `inquiry.validate_inquiry` and `validation.validate_graph` → `graphutil._has_cycle` ⇒ graphutil before both. (`validation` and `inquiry` have **no** edge to each other.)
- `export.export_graph_payload` → `evidence_signals._collect_evidence_signals`/`_source_strings`/`_load_proposition_*` ⇒ evidence_signals before export.
- `queries`/`summary` → `evidence_signals` ⇒ evidence_signals before both. (`summary` does **not** call `queries`.)
- `dot.build_graph_dot` → `queries.query_neighborhood` + `dataset._load_dataset` ⇒ dot last.

No submodule imports `graph.materialize` (materialize depends on store, never the reverse — this invariant must hold to avoid a cycle). `store/__init__.py` imports from all submodules; nothing inside the package imports `store/__init__.py`.

## Component responsibilities & exact symbol assignment

Line numbers refer to the pre-refactor `store.py`.

### 1. constants.py
Module-level constants and namespace re-exports.
- `DEFAULT_GRAPH_PATH` (50), `VALID_INQUIRY_TYPES` (251), `GRAPH_LAYERS` (253), `GRAPH_EXPORT_SCHEMA_VERSION` (260), `GRAPH_EXPORT_VISIBLE_LAYERS` (261), `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` (267), `CURIE_PREFIXES` (385), `PROJECT_ENTITY_PREFIXES` (400), `PROJECT_ENTITY_PREFIX_KINDS` (422), `_RELATION_KIND_BY_PREDICATE` (430), `STRUCTURED_PROPOSITION_PREDICATES` (474), `EVIDENCE_STANCE_PREDICATES` (486), `INITIAL_GRAPH_TEMPLATE` (493), `PREDICATE_REGISTRY` (2762).
- Namespace re-exports from `graph.io`: `CITO_NS`, `PROJECT_NS`, `SCI_NS`, `SCHEMA_NS`, `SCIC_NS`, `BIOLINK_NS`, `DCTERMS_NS`, `REVISION_URI`.

### 2. types.py
All `TypedDict` definitions (53–243): `InquiryEdge`, `InquiryInfo`, `ClaimSummaryData`, `NeighborhoodSummaryData`, `QuestionSummaryData`, `PropositionEvidenceLine`, `PropositionPhase1Metadata`, `PropositionEvidenceSemantics`, `PropositionInteractionTerm`, `FalsificationRecord`, `EvidenceClaimBundle`, `EvidenceEdgeOverlay`, `EvidenceOverlayData`, `InquirySummaryData`, `ProjectSummaryData`, `EvidenceSignalSummary`.

### 3. graphutil.py
Pure, dependency-free edge-list algorithms.
- `_has_cycle` (4533). (Extracted from its incidental adjacency to `build_graph_dot`; the two are unrelated — `build_graph_dot` never calls `_has_cycle`.)

### 4. identity.py
URI / canonical-id / token / relation-claim-URI helpers (`← constants`).
- `_entity_kind_from_uri` (437), `canonical_id_from_entity_uri` (451), `_slug` (4562), `_graph_uri` (4566), `_derive_relation_claim_text` (4570), `_relation_claim_label` (4578), `_edge_claims` (4622), `_edge_statement_uri` (4635), `_resolve_term` (4645), `_resolve_center_entity` (4690), `_about_tokens` (4696), `shorten_uri` (4715), `_short_name` (4768).

### 5. notebooks.py
Viz-notebook scaffolding (`← constants`).
- `_uv_lock` (4727), `_NOTEBOOKS_PYPROJECT` (4735), `_copy_viz_notebook` (4750).
- **Required edit:** inside `_copy_viz_notebook`, `import_root = Path(__file__).resolve().parents[2]` becomes `parents[3]`. Rationale: from `graph/store.py` the path was `…/science_tool/graph/store.py` so `parents[2]` = `science/src`; after the move to `…/science_tool/graph/store/notebooks.py` the file is one segment deeper, so the same `science/src` root is now `parents[3]`. Without this change the `__SCIENCE_TOOL_IMPORT_ROOT__` substitution in the generated notebook would point at `…/science_tool` instead of `…/src`, breaking notebook imports. A regression test should assert the substituted root ends in `/src` (or that `viz.py` imports resolve).

### 6. dataset.py
Dataset construction / load / save / stats (`← constants, identity, notebooks, io`).
- `init_graph_file` (520; calls `notebooks._copy_viz_notebook`), `read_graph_stats` (531), `_load_dataset` (4668), `_save_dataset` (4677), `save_graph_dataset` (4681).

### 7. evidence_signals.py
Evidence/proposition data-gathering shared by `export`, `queries`, `summary` (`← constants, types, identity, dataset`).
- `_linked_claims_for_hypothesis` (3331), `_source_strings` (3343), `_load_proposition_phase1_metadata` (3350), `_load_proposition_evidence_semantics` (3406), `_load_proposition_pre_registrations` (3444), `_load_proposition_interaction_terms` (3448), `_load_proposition_bridge_hypotheses` (3463), `_load_proposition_falsifications` (3467), `_json_literal` (3486), `_evidence_targets_for_uri` (3501), `_collect_evidence_signals` (3507), `_apply_phase1_metadata_to_bundle` (3545), `_apply_evidence_semantics_to_bundle` (3571), `_evidence_type_strings` (3593), `_collect_evidence_types` (3600).

### 8. mutations.py  (largest, ~1,000 lines — kept whole; all graph writes)
- All `add_*`: `add_concept` (541), `add_article` (581), `add_proposition` (594), `add_observation` (737), `add_evidence_edge` (775), `add_finding` (826), `add_interpretation` (866), `add_discussion` (903), `add_falsification` (940), `add_mechanism` (979), `add_story` (1044), `add_paper_entity` (1081), `add_hypothesis` (1118), `add_question` (1137), `add_edge` (1212), `add_inquiry` (1305), `add_inquiry_node` (1370), `add_inquiry_edge` (1398), `add_assumption` (1442), `add_transformation` (1468), `add_data_package` (1508).
- `set_boundary_role` (1344), `set_param_metadata` (1531).
- `migrate_addresses_direction` (1264), `_warn_on_relation_direction_mismatch` (1172), `_attach_edge_claims` (4587).
- (`set_treatment_outcome` belongs to inquiry.py, not here.)

### 9. export.py  (`← evidence_signals + foundation`)
- `export_graph_payload` (1558) and its export-layer helpers `_export_graph_layers` (326), `_canonical_export_layer_id` (331), `_export_layer_graph_map` (345), `_sort_export_layers` (369).

### 10. inquiry.py  (`← graphutil + foundation`)
- `list_inquiries` (1891), `get_inquiry` (1943), `set_treatment_outcome` (2024), `render_inquiry_doc` (2057), `validate_inquiry` (2297; calls `graphutil._has_cycle`).

### 11. snapshot.py  (`← dataset, io`)
- `import_snapshot` (2713), `stamp_revision` (2750).

### 12. validation.py  (`← graphutil + foundation`)
- `query_predicates` (2989), `validate_graph` (2993; calls `graphutil._has_cycle`), `diff_graph_inputs` (3111).

### 13. queries.py  (`← evidence_signals + foundation`)
- `query_neighborhood` (3152), `query_claims` (3198), `query_evidence` (3224), `_append_evidence_rows` (3265), `_append_row` (3290).

### 14. summary.py  (`← evidence_signals + foundation`; independent of queries)
- `_summary_targets` (3617), `_claim_summary_data` (3633), `_format_claim_summary_row` (3753), `_claim_summaries` (3785), `query_dashboard_summary` (3794), `_hypotheses_for_claim` (3810), `_claim_summary_adjacency` (3820), `_neighborhood_summary_data_rows` (3848), `_format_neighborhood_summary_row` (3896), `query_neighborhood_summary` (3911), `_question_claims` (3928), `_inquiry_claims` (3946), `_rollup_claim_group` (3967), `_question_summary_data` (4024), `_format_question_summary_row` (4062), `query_question_summary` (4077), `_inquiry_summary_data` (4103), `_format_inquiry_summary_row` (4142), `query_inquiry_summary` (4159), `_project_summary_data` (4194), `_format_project_summary_row` (4224), `query_project_summary` (4240), `query_coverage` (4282), `query_gaps` (4324), `query_uncertainty` (4406).

### 15. dot.py  (`← queries + foundation`)
- `build_graph_dot` (4487; calls `queries.query_neighborhood` and `dataset._load_dataset`).

## The `store/__init__.py` re-export contract

`store/__init__.py` MUST make importable as `from science_tool.graph.store import <name>` **every name currently imported from `graph.store` anywhere in `science/src` or `science/tests`**, so all importers keep working with zero edits. Private (underscore) names are excluded from `import *`, so they are imported **explicitly** by name; the package must not rely on `__all__` to surface them.

**Authoritative definition (mechanical, not hand-maintained):** the required set is the union of all names appearing in `from science_tool.graph.store import (...)` statements across `science/src` and `science/tests`. The implementation plan computes this set by grep/AST over the repo and ensures `__init__.py` exposes every member. The list below is the **verified floor** as of this design; the mechanical check is authoritative if they ever diverge.

**Verified public surface:**
`DEFAULT_GRAPH_PATH`, `GRAPH_LAYERS`, `VALID_INQUIRY_TYPES`, `CURIE_PREFIXES`, `PROJECT_ENTITY_PREFIXES`, `PREDICATE_REGISTRY`, `GRAPH_EXPORT_EDGE_METADATA_PREDICATES`, `INITIAL_GRAPH_TEMPLATE`, `CITO_NS`, `PROJECT_NS`, `SCI_NS`, `SCHEMA_NS`, `SCIC_NS`, `PropositionEvidenceLine`, `PropositionInteractionTerm`, `PropositionPhase1Metadata`, `PropositionEvidenceSemantics`, `FalsificationRecord`, `EvidenceClaimBundle`, `add_article`, `add_assumption`, `add_concept`, `add_discussion`, `add_edge`, `add_evidence_edge`, `add_falsification`, `add_finding`, `add_hypothesis`, `add_inquiry`, `add_inquiry_edge`, `add_inquiry_node`, `add_interpretation`, `add_mechanism`, `add_observation`, `add_paper_entity`, `add_proposition`, `add_question`, `add_story`, `add_transformation`, `set_boundary_role`, `set_param_metadata`, `set_treatment_outcome`, `migrate_addresses_direction`, `export_graph_payload`, `get_inquiry`, `list_inquiries`, `render_inquiry_doc`, `validate_inquiry`, `import_snapshot`, `init_graph_file`, `stamp_revision`, `read_graph_stats`, `query_claims`, `query_coverage`, `query_dashboard_summary`, `query_evidence`, `query_gaps`, `query_inquiry_summary`, `query_neighborhood`, `query_neighborhood_summary`, `query_predicates`, `query_project_summary`, `query_question_summary`, `query_uncertainty`, `validate_graph`, `diff_graph_inputs`, `build_graph_dot`, `canonical_id_from_entity_uri`, `shorten_uri`, `save_graph_dataset`.

**Verified private helpers (must be explicitly re-exported):**
`_resolve_term`, `_resolve_center_entity`, `_evidence_targets_for_uri`, `_graph_uri`, `_load_dataset`, `_save_dataset`, `_collect_evidence_signals`, `_edge_claims`, `_source_strings`, `_claim_summary_data`, `_load_proposition_bridge_hypotheses`, `_load_proposition_evidence_semantics`, `_load_proposition_falsifications`, `_load_proposition_interaction_terms`, `_load_proposition_phase1_metadata`, `_load_proposition_pre_registrations`, `_slug`.

(Pytest collection across all 28 store-touching test files plus an import smoke check is the executable gate: a missing re-export fails at import time, before any logic runs.)

## Data flow / error handling

- **Data flow** is the dependency order above; no runtime control flow changes.
- **Error handling** is unchanged. `click.echo` warnings, raised exceptions, and `strict` flags move verbatim with their functions. (The lone body edit is the notebooks `parents` index.)

## Testing strategy

Behavior-preserving move ⇒ **no test edits** (the single allowed exception is *adding* a regression test for the notebooks import-root, since that line changed). Zero churn is itself the proof of correctness:
- `cd science && uv run pytest` — green.
- `cd science/model && uv run pytest` — green (sanity; model package shouldn't be affected).
- Import smoke check for the private re-exports, e.g.:
  `python -c "from science_tool.graph.store import _collect_evidence_signals, _load_dataset, _resolve_term, _graph_uri, _claim_summary_data, _edge_claims, _resolve_center_entity; print('ok')"`
- Mechanical re-export completeness check (grep/AST of all `from science_tool.graph.store import` sites vs. the names `store/__init__.py` exposes).
- New regression test asserting `_copy_viz_notebook` writes an import root ending in `/src`.

## Migration mechanics

- Done as its own behavior-preserving pass in a git worktree (`.worktrees`), executed via subagent-driven-development, mirroring Phase 0/1.
- Incremental, each commit green, following the dependency order: foundation first (`constants`, `types`, `graphutil`, `identity`, `notebooks`, `dataset`), then `evidence_signals`, then operations (`mutations`, `export`, `inquiry`, `snapshot`, `validation`, `queries`, `summary`), then `dot`, finalizing `store/__init__.py` and removing the old monolith.
- Subagents must `cd` to the worktree path, verify branch, and use explicit `git add <paths>` (never `-A`/`.`) to avoid leaking commits to `main`.
- Standing constraints: no AI attribution in commits; commit locally only (no push without explicit confirmation); use `~/d/` (not absolute) paths in any docs/code; no "legacy"/"compatibility" layer beyond the package `__init__`; no "Unified" prefixes.

## Exit criteria

1. `store.py` is gone; `store/` package exists with the 15 submodules above plus `__init__.py`.
2. No submodule exceeds its single responsibility; `mutations.py` (~1,000 lines) is the largest and is acceptable (cohesive: all graph writes).
3. Both test suites pass; the only test change is the *added* notebooks import-root regression test (no existing test edited).
4. No source importer outside `store/` changed (verified by `git diff --stat` touching only `graph/store*` and the one new test).
5. The dependency order holds (no module imports a later one; no import of `graph.materialize`), confirmed by an import of the package succeeding and by inspection.
6. The mechanical re-export completeness check passes (every `graph.store` import site across src+tests resolves).
