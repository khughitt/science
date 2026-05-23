# store.py Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose `science/src/science_tool/graph/store.py` (4,773 lines) into a `store/` package of 15 focused submodules plus a re-export `__init__.py`, as a behavior-preserving move.

**Architecture:** `store.py` → `store/__init__.py` (verbatim), then extract submodules bottom-up in strict dependency order, each extraction replacing moved code in `__init__.py` with a `from .<module> import (...)` re-export. Two static guard tests (re-export completeness, dependency order) are added first and act as continuous CI for every subsequent extraction. The full design — including the exact symbol→module assignment with original line numbers — is the authoritative reference: `docs/plans/2026-05-23-store-decomposition-design.md` (rev b).

**Tech Stack:** Python 3.12+, rdflib, click, pytest, uv. Package `science_tool` lives at `science/src/science_tool/`; tests at `science/tests/`. Run tests with `cd science && uv run pytest`.

---

## Prerequisites (controller sets up before Task 1)

- Create a git worktree under `.worktrees` on a new branch `store-decomposition` off `main`.
- **Every subagent dispatch MUST:** `cd` into the worktree path, run `git rev-parse --abbrev-ref HEAD` and confirm it prints `store-decomposition` (NOT `main`), and stage with explicit `git add <paths>` — never `git add -A` or `git add .`. (Prevents commits leaking to `main`.)
- No pushing to origin at any point. Commit locally only.
- No AI attribution in commit messages.

## Baseline facts (true before any change)

- `store.py` uses only absolute imports (`from science_tool.graph.X import ...`); it has **no** relative imports. So moving it to `store/__init__.py` needs zero import edits.
- The only `__file__` usage in the file is inside `_copy_viz_notebook` (`Path(__file__).resolve().parents[2]`).
- 28 test files and ~15 source modules import from `science_tool.graph.store`; several import private (underscore) helpers. The re-export `__init__.py` must keep all of them importable.

## Extraction Procedure (applies to Tasks 4–14, and the extraction half of Task 15)

> **The controller MUST paste this procedure into each extraction task dispatch.** Every extraction task is the same mechanical move; only the module name, symbol list, and re-export line differ.

For a target submodule `M` with a named symbol list `S` (functions/classes/constants):

1. **Create `science/src/science_tool/graph/store/M.py`.** Start it with `from __future__ import annotations`, then the imports the moved code actually references (a subset of the original `store.py` top-of-file imports — e.g. `from pathlib import Path`, `from rdflib import ...`, `from science_tool.graph.io import ...`), plus `from .<earlier_module> import (...)` for any sibling symbols `S` depends on (siblings are always *earlier* in the dependency order — never later). **Move the definitions in `S` verbatim** from `store/__init__.py` into `M.py` (no body changes, except the one documented edit in Task 6).
   - **The per-task "Imports" list is a starting FLOOR, not exhaustive.** The authoritative rule: `M.py` must import *every* free name its moved bodies reference — external libs, `science_model.*`, `science_tool.graph.io`/`.belief`/`.export_types`, and earlier siblings. Step 3 makes any omission fail loudly and immediately.
2. **Edit `science/src/science_tool/graph/store/__init__.py`:** delete the moved definitions; add a re-export line `from .M import (<every name in S that any external importer or sibling needs>)`. Include underscore names explicitly (they don't come via `import *`). Remove any now-unused top-of-file import from `__init__.py`.
3. **Verify, fail-fast first:**
   - **Module import smoke (catches missing imports in `M.py` itself):** `cd science && uv run python -c "import science_tool.graph.store.M"` — must exit 0. A `NameError`/`ImportError` here names the exact missing import; add it and rerun until clean.
   - **Guards:** `cd science && uv run pytest tests/test_store_package_structure.py -q` — must pass.
   - **Full suite:** `cd science && uv run pytest -q` — must pass, zero failures.
   - The smoke check + guards + suite together are the proof the move is clean.
4. **Commit** with explicit paths:
   `git add science/src/science_tool/graph/store/M.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract <M> submodule"`

Because extraction is strictly bottom-up, `M.py` only ever imports from already-extracted earlier siblings; it never references symbols still residing in `__init__.py`. This guarantees no circular import.

---

### Task 1: Convert store.py into the store/ package (baseline, still green)

**Files:**
- Move: `science/src/science_tool/graph/store.py` → `science/src/science_tool/graph/store/__init__.py`

- [ ] **Step 1: Confirm branch**

Run: `cd <worktree> && git rev-parse --abbrev-ref HEAD`
Expected: `store-decomposition`

- [ ] **Step 2: Move the module into a package**

```bash
cd <worktree>
mkdir -p science/src/science_tool/graph/store   # git mv does NOT create the destination dir
git mv science/src/science_tool/graph/store.py science/src/science_tool/graph/store/__init__.py
```

- [ ] **Step 3: Verify both test suites pass unchanged**

Run: `cd science && uv run pytest -q`
Expected: PASS, same counts as on `main` (no failures).
Run: `cd science/model && uv run pytest -q`
Expected: PASS.

- [ ] **Step 4: Verify the public import path still resolves**

Run: `cd science && uv run python -c "import science_tool.graph.store as s; print(hasattr(s, 'query_uncertainty'), hasattr(s, '_collect_evidence_signals'))"`
Expected: `True True`

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/__init__.py
git commit -m "refactor(store): convert store.py into store/ package (no code change)"
```

---

### Task 2: Add the re-export completeness guard test

**Files:**
- Create: `science/tests/test_store_package_structure.py`

- [ ] **Step 1: Write the test**

```python
"""Structural guard tests for the graph.store package decomposition."""
from __future__ import annotations

import ast
from pathlib import Path

import science_tool.graph.store as store

# science/tests/test_store_package_structure.py -> parents[1] == science/
SCIENCE_ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = [SCIENCE_ROOT / "src", SCIENCE_ROOT / "tests"]


def _names_imported_from_store() -> set[str]:
    names: set[str] = set()
    for root in SEARCH_ROOTS:
        for py in root.rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "science_tool.graph.store":
                    for alias in node.names:
                        if alias.name != "*":
                            names.add(alias.name)
    return names


def test_store_reexports_every_imported_name():
    imported = _names_imported_from_store()
    assert imported, "expected to find imports from science_tool.graph.store"
    missing = sorted(name for name in imported if not hasattr(store, name))
    assert not missing, f"store/__init__.py must re-export these names: {missing}"
```

- [ ] **Step 2: Run it — expect PASS (everything is still in `__init__`)**

Run: `cd science && uv run pytest tests/test_store_package_structure.py -q`
Expected: PASS. (At this point all symbols still live in `__init__`, so the check passes; its job is to fail the moment a later extraction drops a re-export.)

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_store_package_structure.py
git commit -m "test(store): guard that __init__ re-exports every imported name"
```

---

### Task 3: Add the dependency-order guard test

**Files:**
- Modify: `science/tests/test_store_package_structure.py`

- [ ] **Step 1: Append the test**

```python
STORE_DIR = SCIENCE_ROOT / "src" / "science_tool" / "graph" / "store"

# Canonical dependency order: a submodule may import only siblings EARLIER in this list.
CANONICAL_ORDER = [
    "constants", "types", "graphutil", "identity", "notebooks", "dataset",
    "evidence_signals", "mutations", "export", "inquiry", "snapshot",
    "validation", "queries", "summary", "dot",
]


def _sibling_imports(tree: ast.AST) -> set[str]:
    sibs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level >= 1 and mod in CANONICAL_ORDER:          # from .sibling import x
                sibs.add(mod)
            if node.level >= 1 and mod == "":                        # from . import sibling
                for alias in node.names:
                    if alias.name in CANONICAL_ORDER:
                        sibs.add(alias.name)
            if mod.startswith("science_tool.graph.store."):          # from ...store.sibling import x
                sibs.add(mod.split(".")[-1])
            if mod == "science_tool.graph.store":                    # from ...store import sibling
                for alias in node.names:
                    if alias.name in CANONICAL_ORDER:
                        sibs.add(alias.name)
        if isinstance(node, ast.Import):                             # import ...store.sibling
            for alias in node.names:
                if alias.name.startswith("science_tool.graph.store."):
                    sibs.add(alias.name.split(".")[-1])
    return sibs


def _imports_materialize(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("science_tool.graph.materialize"):
            return True
        if isinstance(node, ast.Import):
            if any(a.name.startswith("science_tool.graph.materialize") for a in node.names):
                return True
    return False


def test_no_upward_or_materialize_imports():
    for index, module_name in enumerate(CANONICAL_ORDER):
        path = STORE_DIR / f"{module_name}.py"
        if not path.exists():
            continue  # not yet extracted
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert not _imports_materialize(tree), f"{module_name}.py must not import graph.materialize"
        for sib in _sibling_imports(tree):
            assert CANONICAL_ORDER.index(sib) < index, (
                f"{module_name}.py imports later sibling '{sib}' — upward dependency edge"
            )
```

- [ ] **Step 2: Run it — expect PASS (no submodules exist yet, scan is vacuous)**

Run: `cd science && uv run pytest tests/test_store_package_structure.py -q`
Expected: PASS (both tests). The dependency-order test passes trivially until submodules exist, then enforces on every extraction.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_store_package_structure.py
git commit -m "test(store): guard the submodule dependency order"
```

---

### Task 4: Extract foundation definitions — constants.py, types.py, graphutil.py

> Apply the **Extraction Procedure** three times (these three have no intra-package dependencies and are independent of each other). One commit.

**Files:**
- Create: `store/constants.py`, `store/types.py`, `store/graphutil.py`
- Modify: `store/__init__.py`

- [ ] **Step 1: Extract `constants.py`**

Move these definitions (design doc §1) verbatim: `DEFAULT_GRAPH_PATH`, `VALID_INQUIRY_TYPES`, `GRAPH_LAYERS`, `GRAPH_EXPORT_SCHEMA_VERSION`, `GRAPH_EXPORT_VISIBLE_LAYERS`, `GRAPH_EXPORT_EDGE_METADATA_PREDICATES`, `CURIE_PREFIXES`, `PROJECT_ENTITY_PREFIXES`, `PROJECT_ENTITY_PREFIX_KINDS`, `_RELATION_KIND_BY_PREDICATE`, `STRUCTURED_PROPOSITION_PREDICATES`, `EVIDENCE_STANCE_PREDICATES`, `INITIAL_GRAPH_TEMPLATE`, `PREDICATE_REGISTRY`.
`constants.py` imports: `from pathlib import Path`, `from rdflib import Namespace, URIRef`, `from rdflib.namespace import PROV, RDF, SKOS, XSD` (only those actually referenced by the constants), `from science_model.profiles.schema import RelationKind`, `from science_model.profiles import CORE_PROFILE` (required — `_RELATION_KIND_BY_PREDICATE` iterates `CORE_PROFILE.relation_kinds`, store.py:432), and the namespace re-exports `from science_tool.graph.io import BIOLINK_NS, CITO_NS, DCTERMS_NS, PROJECT_NS, REVISION_URI, SCHEMA_NS, SCI_NS, SCIC_NS`.
In `__init__.py` add: `from .constants import (DEFAULT_GRAPH_PATH, VALID_INQUIRY_TYPES, GRAPH_LAYERS, GRAPH_EXPORT_SCHEMA_VERSION, GRAPH_EXPORT_VISIBLE_LAYERS, GRAPH_EXPORT_EDGE_METADATA_PREDICATES, CURIE_PREFIXES, PROJECT_ENTITY_PREFIXES, PROJECT_ENTITY_PREFIX_KINDS, _RELATION_KIND_BY_PREDICATE, STRUCTURED_PROPOSITION_PREDICATES, EVIDENCE_STANCE_PREDICATES, INITIAL_GRAPH_TEMPLATE, PREDICATE_REGISTRY, BIOLINK_NS, CITO_NS, DCTERMS_NS, PROJECT_NS, REVISION_URI, SCHEMA_NS, SCI_NS, SCIC_NS)`.

- [ ] **Step 2: Extract `types.py`**

Move all `TypedDict` definitions (design doc §2) verbatim: `InquiryEdge`, `InquiryInfo`, `ClaimSummaryData`, `NeighborhoodSummaryData`, `QuestionSummaryData`, `PropositionEvidenceLine`, `PropositionPhase1Metadata`, `PropositionEvidenceSemantics`, `PropositionInteractionTerm`, `FalsificationRecord`, `EvidenceClaimBundle`, `EvidenceEdgeOverlay`, `EvidenceOverlayData`, `InquirySummaryData`, `ProjectSummaryData`, `EvidenceSignalSummary`.
`types.py` imports: `from typing import NotRequired, TypedDict` (and any rdflib types referenced in annotations, e.g. `from rdflib import URIRef`).
In `__init__.py` add: `from .types import (InquiryEdge, InquiryInfo, ClaimSummaryData, NeighborhoodSummaryData, QuestionSummaryData, PropositionEvidenceLine, PropositionPhase1Metadata, PropositionEvidenceSemantics, PropositionInteractionTerm, FalsificationRecord, EvidenceClaimBundle, EvidenceEdgeOverlay, EvidenceOverlayData, InquirySummaryData, ProjectSummaryData, EvidenceSignalSummary)`.

- [ ] **Step 3: Extract `graphutil.py`**

Move `_has_cycle` (design doc §3) verbatim. `graphutil.py` imports: nothing from the package (pure stdlib — keep whatever `_has_cycle` references, likely none beyond builtins).
In `__init__.py` add: `from .graphutil import _has_cycle`.

- [ ] **Step 4: Run guards + full suite**

Run: `cd science && uv run pytest tests/test_store_package_structure.py -q` → PASS
Run: `cd science && uv run pytest -q` → PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/constants.py science/src/science_tool/graph/store/types.py science/src/science_tool/graph/store/graphutil.py science/src/science_tool/graph/store/__init__.py
git commit -m "refactor(store): extract constants, types, graphutil submodules"
```

---

### Task 5: Extract identity.py

> Apply the **Extraction Procedure** for `M = identity`.

**Files:** Create `store/identity.py`; Modify `store/__init__.py`.

Symbols (design doc §4): `_entity_kind_from_uri`, `canonical_id_from_entity_uri`, `_slug`, `_graph_uri`, `_derive_relation_claim_text`, `_relation_claim_label`, `_edge_claims`, `_edge_statement_uri`, `_resolve_term`, `_resolve_center_entity`, `_about_tokens`, `shorten_uri`, `_short_name`.
Likely imports for `identity.py`: `from rdflib import URIRef`, `from science_tool.graph.io import PROJECT_NS` (or `from .constants import PROJECT_NS, ...`), plus `import re` if used. Depends only on `constants` (earlier).
`__init__.py` re-export: `from .identity import (_entity_kind_from_uri, canonical_id_from_entity_uri, _slug, _graph_uri, _derive_relation_claim_text, _relation_claim_label, _edge_claims, _edge_statement_uri, _resolve_term, _resolve_center_entity, _about_tokens, shorten_uri, _short_name)`.

- [ ] Step 1: Create `identity.py`, move the 13 symbols verbatim, wire imports.
- [ ] Step 2: Edit `__init__.py` (delete defs, add the re-export line, drop unused imports).
- [ ] Step 3: `cd science && uv run pytest tests/test_store_package_structure.py -q` → PASS; `cd science && uv run pytest -q` → PASS.
- [ ] Step 4: `git add science/src/science_tool/graph/store/identity.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract identity submodule"`

---

### Task 6: Extract notebooks.py (with the documented `parents` fix + regression test)

> Apply the **Extraction Procedure** for `M = notebooks`, plus the one allowed body edit and a new regression test.

**Files:** Create `store/notebooks.py`; Modify `store/__init__.py`; Modify `science/tests/test_store_package_structure.py`.

Symbols (design doc §5): `_uv_lock`, `_NOTEBOOKS_PYPROJECT`, `_copy_viz_notebook`.
`notebooks.py` imports: `import importlib.resources`, `from pathlib import Path`, `import subprocess` (whatever `_uv_lock`/`_copy_viz_notebook` reference), and `from .constants import _NOTEBOOKS_PYPROJECT`? — no, `_NOTEBOOKS_PYPROJECT` moves *into* notebooks.py itself. Depends only on `constants` if it references any constant.
`__init__.py` re-export: `from .notebooks import (_uv_lock, _NOTEBOOKS_PYPROJECT, _copy_viz_notebook)`.

- [ ] **Step 1: Write the regression test first (append to `test_store_package_structure.py`)**

```python
def test_copy_viz_notebook_import_root_is_src(tmp_path):
    import science_tool
    from science_tool.graph.store.notebooks import _copy_viz_notebook

    expected_root = Path(science_tool.__file__).resolve().parent.parent  # .../science/src
    buggy_root = expected_root / "science_tool"                          # what parents[2] would yield

    notebooks_dir = tmp_path / "notebooks"
    _copy_viz_notebook(notebooks_dir)
    content = (notebooks_dir / "viz.py").read_text(encoding="utf-8")

    assert "__SCIENCE_TOOL_IMPORT_ROOT__" not in content
    assert buggy_root.as_posix() not in content, "import root must be src/, not src/science_tool"
    assert expected_root.as_posix() in content
```

- [ ] **Step 2: Run it — expect FAIL (module `store.notebooks` does not exist yet)**

Run: `cd science && uv run pytest tests/test_store_package_structure.py::test_copy_viz_notebook_import_root_is_src -q`
Expected: FAIL (ImportError / collection error: no module `science_tool.graph.store.notebooks`).

- [ ] **Step 3: Create `notebooks.py`, move the 3 symbols verbatim, and apply the one edit**

Inside `_copy_viz_notebook`, change `import_root = Path(__file__).resolve().parents[2]` → `import_root = Path(__file__).resolve().parents[3]`. (notebooks.py sits one directory deeper than the old store.py.)

- [ ] **Step 4: Edit `__init__.py`** (delete the 3 defs, add the re-export line, drop unused imports).

- [ ] **Step 5: Run the regression test — expect PASS**

Run: `cd science && uv run pytest tests/test_store_package_structure.py::test_copy_viz_notebook_import_root_is_src -q`
Expected: PASS. (If it fails with `buggy_root ... not in content`, the `parents[3]` edit was missed.)

- [ ] **Step 6: Run guards + full suite**

Run: `cd science && uv run pytest tests/test_store_package_structure.py -q` → PASS
Run: `cd science && uv run pytest -q` → PASS

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/store/notebooks.py science/src/science_tool/graph/store/__init__.py science/tests/test_store_package_structure.py
git commit -m "refactor(store): extract notebooks submodule; fix viz import-root depth"
```

---

### Task 7: Extract dataset.py

> Apply the **Extraction Procedure** for `M = dataset`.

**Files:** Create `store/dataset.py`; Modify `store/__init__.py`.

Symbols (design doc §6): `init_graph_file`, `read_graph_stats`, `_load_dataset`, `_save_dataset`, `save_graph_dataset`.
Imports for `dataset.py`: `from pathlib import Path`, `from rdflib import Dataset, Graph`, `from science_tool.graph.io import save_canonical_graph_dataset, project_root_from_graph_path as _project_root_from_graph_path` (and any other `io` aliases these functions used), `from .constants import GRAPH_LAYERS, INITIAL_GRAPH_TEMPLATE`, `from .identity import _graph_uri`, `from .notebooks import _copy_viz_notebook` (`init_graph_file` calls it). Depends on constants, identity, notebooks (all earlier).
`__init__.py` re-export: `from .dataset import (init_graph_file, read_graph_stats, _load_dataset, _save_dataset, save_graph_dataset)`.

- [ ] Step 1: Create `dataset.py`, move the 5 symbols verbatim, wire imports.
- [ ] Step 2: Edit `__init__.py`.
- [ ] Step 3: guards PASS; `cd science && uv run pytest -q` PASS.
- [ ] Step 4: `git add science/src/science_tool/graph/store/dataset.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract dataset submodule"`

---

### Task 8: Extract evidence_signals.py

> Apply the **Extraction Procedure** for `M = evidence_signals`.

**Files:** Create `store/evidence_signals.py`; Modify `store/__init__.py`.

Symbols (design doc §7): `_linked_claims_for_hypothesis`, `_source_strings`, `_load_proposition_phase1_metadata`, `_load_proposition_evidence_semantics`, `_load_proposition_pre_registrations`, `_load_proposition_interaction_terms`, `_load_proposition_bridge_hypotheses`, `_load_proposition_falsifications`, `_json_literal`, `_evidence_targets_for_uri`, `_collect_evidence_signals`, `_apply_phase1_metadata_to_bundle`, `_apply_evidence_semantics_to_bundle`, `_evidence_type_strings`, `_collect_evidence_types`.
Imports for `evidence_signals.py`: `from rdflib import Literal, URIRef`, `import json`, the namespace constants `from .constants import CITO_NS, SCI_NS, PROJECT_NS, ...` (as referenced), `from .identity import canonical_id_from_entity_uri, shorten_uri, ...`, and `from .types import (PropositionPhase1Metadata, PropositionEvidenceSemantics, PropositionInteractionTerm, FalsificationRecord, EvidenceClaimBundle, EvidenceSignalSummary)` as referenced. Depends on constants, types, identity, dataset (all earlier).
`__init__.py` re-export: `from .evidence_signals import (_linked_claims_for_hypothesis, _source_strings, _load_proposition_phase1_metadata, _load_proposition_evidence_semantics, _load_proposition_pre_registrations, _load_proposition_interaction_terms, _load_proposition_bridge_hypotheses, _load_proposition_falsifications, _json_literal, _evidence_targets_for_uri, _collect_evidence_signals, _apply_phase1_metadata_to_bundle, _apply_evidence_semantics_to_bundle, _evidence_type_strings, _collect_evidence_types)`.

- [ ] Step 1: Create `evidence_signals.py`, move the 15 symbols verbatim, wire imports.
- [ ] Step 2: Edit `__init__.py`.
- [ ] Step 3: guards PASS; `cd science && uv run pytest -q` PASS.
- [ ] Step 4: `git add science/src/science_tool/graph/store/evidence_signals.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract evidence_signals submodule"`

---

### Task 9: Extract mutations.py (largest)

> Apply the **Extraction Procedure** for `M = mutations`.

**Files:** Create `store/mutations.py`; Modify `store/__init__.py`.

Symbols (design doc §8): `add_concept`, `add_article`, `add_proposition`, `add_observation`, `add_evidence_edge`, `add_finding`, `add_interpretation`, `add_discussion`, `add_falsification`, `add_mechanism`, `add_story`, `add_paper_entity`, `add_hypothesis`, `add_question`, `add_edge`, `add_inquiry`, `add_inquiry_node`, `add_inquiry_edge`, `add_assumption`, `add_transformation`, `add_data_package`, `set_boundary_role`, `set_param_metadata`, `migrate_addresses_direction`, `_warn_on_relation_direction_mismatch`, `_attach_edge_claims`.
Imports for `mutations.py`: `import click`, `from pathlib import Path`, `from rdflib import Dataset, Graph, Literal, URIRef`, `from rdflib.namespace import RDF, SKOS, XSD`, `from science_model.relations import relation_allows_kinds`, `from science_model.profiles.schema import RelationKind`, `from science_model.reasoning import MeasurementModel, RivalModelPacket` (passed to `_json_literal` at store.py:704/712), `from .constants import (...)`, `from .identity import (...)`, `from .dataset import _load_dataset, _save_dataset, save_graph_dataset` as referenced, and **`from .evidence_signals import _json_literal`** (used by `add_proposition`). Depends on **evidence_signals + foundation** — evidence_signals is module 7, earlier than mutations (8), so this is a legal downward edge.
`__init__.py` re-export: `from .mutations import (add_concept, add_article, add_proposition, add_observation, add_evidence_edge, add_finding, add_interpretation, add_discussion, add_falsification, add_mechanism, add_story, add_paper_entity, add_hypothesis, add_question, add_edge, add_inquiry, add_inquiry_node, add_inquiry_edge, add_assumption, add_transformation, add_data_package, set_boundary_role, set_param_metadata, migrate_addresses_direction, _warn_on_relation_direction_mismatch, _attach_edge_claims)`.

- [ ] Step 1: Create `mutations.py`, move the 26 symbols verbatim, wire imports.
- [ ] Step 2: Edit `__init__.py`.
- [ ] Step 3: guards PASS; `cd science && uv run pytest -q` PASS.
- [ ] Step 4: `git add science/src/science_tool/graph/store/mutations.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract mutations submodule"`

---

### Task 10: Extract export.py

> Apply the **Extraction Procedure** for `M = export`.

**Files:** Create `store/export.py`; Modify `store/__init__.py`.

Symbols (design doc §9): `_export_graph_layers`, `_canonical_export_layer_id`, `_export_layer_graph_map`, `_sort_export_layers`, `export_graph_payload`.
Imports for `export.py`: `from rdflib import Dataset, Graph, URIRef`, `from science_tool.graph.export_types import (GraphExportEdge, GraphExportLayer, GraphExportNode, GraphExportOverlays, GraphExportPayload, GraphExportScope, build_graph_export_edge_id, build_graph_export_node_id)`, `from science_tool.graph.io import project_root_from_graph_path as _project_root_from_graph_path` (required — used at store.py:1744), `from .constants import (...)`, `from .identity import (...)`, `from .dataset import _load_dataset`, `from .evidence_signals import (_collect_evidence_signals, _source_strings, _apply_phase1_metadata_to_bundle, _apply_evidence_semantics_to_bundle, _load_proposition_phase1_metadata, _load_proposition_evidence_semantics, _load_proposition_pre_registrations, _load_proposition_interaction_terms, _load_proposition_bridge_hypotheses, _load_proposition_falsifications)` as referenced, and `from .types import (...)`. Depends on evidence_signals + foundation (earlier).
`__init__.py` re-export: `from .export import export_graph_payload` (the 4 `_export_*` helpers are internal-only; re-export only if any importer/test needs them — completeness guard will tell).

- [ ] Step 1: Create `export.py`, move the 5 symbols verbatim, wire imports.
- [ ] Step 2: Edit `__init__.py`.
- [ ] Step 3: guards PASS; `cd science && uv run pytest -q` PASS.
- [ ] Step 4: `git add science/src/science_tool/graph/store/export.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract export submodule"`

---

### Task 11: Extract inquiry.py

> Apply the **Extraction Procedure** for `M = inquiry`.

**Files:** Create `store/inquiry.py`; Modify `store/__init__.py`.

Symbols (design doc §10): `list_inquiries`, `get_inquiry`, `set_treatment_outcome`, `render_inquiry_doc`, `validate_inquiry`.
Imports for `inquiry.py`: `from pathlib import Path`, `from rdflib import Dataset, Graph, Literal, URIRef`, `from .constants import (VALID_INQUIRY_TYPES, ...)`, `from .identity import (...)`, `from .dataset import _load_dataset, _save_dataset`, `from .graphutil import _has_cycle` (`validate_inquiry` calls it). Depends on graphutil + foundation (earlier).
`__init__.py` re-export: `from .inquiry import (list_inquiries, get_inquiry, set_treatment_outcome, render_inquiry_doc, validate_inquiry)`.

- [ ] Step 1: Create `inquiry.py`, move the 5 symbols verbatim, wire imports.
- [ ] Step 2: Edit `__init__.py`.
- [ ] Step 3: guards PASS; `cd science && uv run pytest -q` PASS.
- [ ] Step 4: `git add science/src/science_tool/graph/store/inquiry.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract inquiry submodule"`

---

### Task 12: Extract snapshot.py and validation.py

> Apply the **Extraction Procedure** twice (snapshot then validation; both depend only on earlier modules and not on each other). One commit.

**Files:** Create `store/snapshot.py`, `store/validation.py`; Modify `store/__init__.py`.

Snapshot symbols (design doc §11): `import_snapshot`, `stamp_revision`.
`snapshot.py` imports: `from pathlib import Path`, `from rdflib import Dataset`, `from science_tool.graph.io import build_input_manifest as _build_input_manifest, read_revision_manifest as _read_revision_manifest` (as referenced), `from .dataset import _load_dataset, _save_dataset`, `from .identity import _slug`. Depends on dataset/io (earlier).

Validation symbols (design doc §12): `query_predicates`, `validate_graph`, `diff_graph_inputs`.
`validation.py` imports: `from pathlib import Path`, `from rdflib import Dataset, URIRef`, `from science_tool.graph.io import read_revision_manifest as _read_revision_manifest, build_input_manifest as _build_input_manifest` (required — `diff_graph_inputs` uses both, store.py:3113), `from .constants import PREDICATE_REGISTRY`, `from .identity import (...)`, `from .dataset import _load_dataset`, `from .graphutil import _has_cycle` (`validate_graph` calls it). Depends on graphutil + foundation (earlier).

`__init__.py` re-exports: `from .snapshot import (import_snapshot, stamp_revision)` and `from .validation import (query_predicates, validate_graph, diff_graph_inputs)`.

- [ ] Step 1: Create `snapshot.py`, move its 2 symbols, wire imports.
- [ ] Step 2: Create `validation.py`, move its 3 symbols, wire imports.
- [ ] Step 3: Edit `__init__.py` (both re-export lines).
- [ ] Step 4: guards PASS; `cd science && uv run pytest -q` PASS.
- [ ] Step 5: `git add science/src/science_tool/graph/store/snapshot.py science/src/science_tool/graph/store/validation.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract snapshot and validation submodules"`

---

### Task 13: Extract queries.py

> Apply the **Extraction Procedure** for `M = queries`.

**Files:** Create `store/queries.py`; Modify `store/__init__.py`.

Symbols (design doc §13): `query_neighborhood`, `query_claims`, `query_evidence`, `_append_evidence_rows`, `_append_row`.
Imports for `queries.py`: `from rdflib import Dataset, Graph, URIRef`, `from .constants import (...)`, `from .identity import (canonical_id_from_entity_uri, shorten_uri, _resolve_center_entity, _about_tokens, ...)`, `from .dataset import _load_dataset`, `from .evidence_signals import (_collect_evidence_signals, _source_strings, ...)` as referenced. Depends on evidence_signals + foundation (earlier).
`__init__.py` re-export: `from .queries import (query_neighborhood, query_claims, query_evidence)` (the `_append_*` helpers are internal; re-export only if the guard flags them).

- [ ] Step 1: Create `queries.py`, move the 5 symbols verbatim, wire imports.
- [ ] Step 2: Edit `__init__.py`.
- [ ] Step 3: guards PASS; `cd science && uv run pytest -q` PASS.
- [ ] Step 4: `git add science/src/science_tool/graph/store/queries.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract queries submodule"`

---

### Task 14: Extract summary.py

> Apply the **Extraction Procedure** for `M = summary`.

**Files:** Create `store/summary.py`; Modify `store/__init__.py`.

Symbols (design doc §14): `_summary_targets`, `_claim_summary_data`, `_format_claim_summary_row`, `_claim_summaries`, `query_dashboard_summary`, `_hypotheses_for_claim`, `_claim_summary_adjacency`, `_neighborhood_summary_data_rows`, `_format_neighborhood_summary_row`, `query_neighborhood_summary`, `_question_claims`, `_inquiry_claims`, `_rollup_claim_group`, `_question_summary_data`, `_format_question_summary_row`, `query_question_summary`, `_inquiry_summary_data`, `_format_inquiry_summary_row`, `query_inquiry_summary`, `_project_summary_data`, `_format_project_summary_row`, `query_project_summary`, `query_coverage`, `query_gaps`, `query_uncertainty`.
Imports for `summary.py`: `from rdflib import Dataset, Graph, URIRef`, `from science_tool.graph.belief import aggregate_belief, collect_evidence_units` (used by `_claim_summary_data`), `from science_tool.graph.io import project_root_from_graph_path as _project_root_from_graph_path` (required — used by `query_project_summary` at store.py:4243), `from .constants import (...)`, `from .types import (ClaimSummaryData, NeighborhoodSummaryData, QuestionSummaryData, InquirySummaryData, ProjectSummaryData, ...)`, `from .identity import (...)`, `from .dataset import _load_dataset`, `from .evidence_signals import (_collect_evidence_signals, _evidence_targets_for_uri, _collect_evidence_types, ...)` as referenced. Depends on evidence_signals + foundation; does NOT import `queries`.
`__init__.py` re-export: `from .summary import (query_dashboard_summary, query_neighborhood_summary, query_question_summary, query_inquiry_summary, query_project_summary, query_coverage, query_gaps, query_uncertainty, _claim_summary_data)` (`_claim_summary_data` is imported by tests; other `_` helpers re-export only if the guard flags them).

- [ ] Step 1: Create `summary.py`, move the 25 symbols verbatim, wire imports.
- [ ] Step 2: Edit `__init__.py`.
- [ ] Step 3: guards PASS; `cd science && uv run pytest -q` PASS.
- [ ] Step 4: `git add science/src/science_tool/graph/store/summary.py science/src/science_tool/graph/store/__init__.py && git commit -m "refactor(store): extract summary submodule"`

---

### Task 15: Extract dot.py and finalize the package

> Apply the **Extraction Procedure** for `M = dot`, then finalize.

**Files:** Create `store/dot.py`; Modify `store/__init__.py`; Modify `docs/plans/2026-05-23-store-decomposition-design.md`.

Symbols (design doc §15): `build_graph_dot`.
Imports for `dot.py`: `from rdflib import URIRef`, `from .identity import _graph_uri, shorten_uri`, `from .dataset import _load_dataset`, `from .queries import query_neighborhood` (`build_graph_dot` calls it). Depends on queries + foundation (earlier) — `dot` is last in the order.
`__init__.py` re-export: `from .dot import build_graph_dot`.

- [ ] **Step 1: Extract `dot.py`**, move `build_graph_dot` verbatim, wire imports, add the re-export.

- [ ] **Step 2: Confirm `__init__.py` is now a pure re-export aggregator**

`store/__init__.py` should contain only: an optional module docstring, the `from .<module> import (...)` re-export lines, and nothing else (no function/class/constant definitions, no leftover top-level imports of rdflib/click/etc.).
Run: `cd science && uv run python -c "import ast,inspect,science_tool.graph.store as s; t=ast.parse(inspect.getsource(s)); print('defs:', [n.name for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))])"`
Expected: `defs: []` (no definitions remain in `__init__`).

- [ ] **Step 3: Run guards + the mechanical re-export check + both suites**

Run: `cd science && uv run pytest tests/test_store_package_structure.py -q` → PASS (all three tests).
Run: `cd science && uv run python -c "from science_tool.graph.store import _collect_evidence_signals, _load_dataset, _save_dataset, _resolve_term, _resolve_center_entity, _graph_uri, _claim_summary_data, _edge_claims, _source_strings, _slug, _load_proposition_phase1_metadata; print('private re-exports ok')"` → prints ok.
Run: `cd science && uv run pytest -q` → PASS (zero failures).
Run: `cd science/model && uv run pytest -q` → PASS.

- [ ] **Step 4: Verify the diff touched only the store package + the one new test**

Run: `cd <worktree> && git diff --name-only main HEAD -- science/src | grep -vE '^science/src/science_tool/graph/store(/|\.py$)'`
Expected: empty (the only changed `science/src` paths are the deleted `graph/store.py` and the new files under `graph/store/`; nothing else).
Run: `cd <worktree> && git diff --name-only main HEAD -- science/tests | cat`
Expected: only `science/tests/test_store_package_structure.py`.

- [ ] **Step 5: Update the design doc status line**

Change the `**Status:**` line in `docs/plans/2026-05-23-store-decomposition-design.md` to: `**Status:** Implemented (2026-05-23).`

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/store/dot.py science/src/science_tool/graph/store/__init__.py docs/plans/2026-05-23-store-decomposition-design.md
git commit -m "refactor(store): extract dot submodule; finalize store/ package"
```

---

## Final verification (controller, after all tasks)

- `cd science && uv run pytest -q` and `cd science/model && uv run pytest -q` both green.
- `git diff --name-only main HEAD -- science/src` shows only the deleted `graph/store.py` and new files under `graph/store/` (nothing else).
- `store/__init__.py` has zero definitions (pure re-export aggregator).
- All three structural tests in `test_store_package_structure.py` pass.
- Then hand off to superpowers:finishing-a-development-branch.

## Self-review notes (against the design, rev b)

- **Spec coverage:** every design §1–§15 module has an extraction task; the re-export contract → Task 2 guard + per-task re-export lines; the `parents[3]` edit + regression → Task 6; the dependency-order invariant → Task 3 guard; mechanical re-export completeness → Task 2 guard + Task 15 Step 3; "zero importer edits" → Task 15 Step 4 diff check; "no graph.materialize import" → Task 3 guard.
- **Bottom-up order** guarantees each submodule imports only already-extracted earlier siblings (no circular imports, no references to `__init__`-resident code).
- **Symbol-name consistency:** module names and the `CANONICAL_ORDER` list in Task 3 match the design's 15 modules exactly: constants, types, graphutil, identity, notebooks, dataset, evidence_signals, mutations, export, inquiry, snapshot, validation, queries, summary, dot.
