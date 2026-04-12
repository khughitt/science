# General Graph API And Visualization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reusable `science-tool` JSON graph export with typed `causal` and `evidence` overlays, then make the existing dashboard graph explorer consume that shared contract.

**Architecture:** `science-tool` owns the base graph payload and overlay semantics. The dashboard reuses that payload on its existing project graph route and keeps ownership of renderer-specific visual encoding and interaction behavior.

**Tech Stack:** Python, Click, rdflib, FastAPI, Pydantic, React 19, TypeScript, Vite

---

### Task 1: Define Shared Export Types And Fixture Strategy In `science-tool`

**Files:**
- Modify: `science-tool/src/science_tool/graph/__init__.py`
- Create: `science-tool/src/science_tool/graph/export_types.py`
- Test: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing test**

```python
def test_export_types_roundtrip_minimal_payload() -> None:
    payload = GraphExportPayload(
        schema_version="1",
        nodes=[],
        edges=[],
        layers=[],
        scopes=[],
        overlays={},
        warnings=[],
    )
    assert payload.model_dump()["schema_version"] == "1"
```

**Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_types_roundtrip_minimal_payload -q`

Expected: FAIL because `export_types.py` does not exist yet.

**Step 3: Write minimal implementation**

- Create Pydantic models or `TypedDict`-backed serializers for:
  - `GraphExportPayload`
  - `GraphExportNode`
  - `GraphExportEdge`
  - `GraphExportLayer`
  - `GraphExportScope`
  - `GraphExportOverlays`
- Keep the base contract generic, but include `schema_version` and `warnings`.
- Define v1 terminology once in this module:
  - `base edge` = one exported `(subject, predicate, object, layer)` edge
  - `supporting claim` = one proposition attached to a base edge
- In `tests/test_graph_export.py`, build explicit fixture graphs inside the tests using the same fresh-graph pattern as `tests/test_causal.py`; do not rely on an implicit `graph_path` state containing `concept/drug`.

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_types_roundtrip_minimal_payload -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/export_types.py science-tool/src/science_tool/graph/__init__.py science-tool/tests/test_graph_export.py
git commit -m "feat: add graph export payload types"
```

### Task 2: Lock Stable ID And Scope Semantics

**Files:**
- Modify: `science-tool/src/science_tool/graph/export_types.py`
- Test: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing tests**

```python
def test_export_node_ids_are_stable_across_runs(graph_path: Path) -> None:
    payload_a = export_graph_payload(graph_path)
    payload_b = export_graph_payload(graph_path)
    assert [node["id"] for node in payload_a["nodes"]] == [node["id"] for node in payload_b["nodes"]]


def test_export_scopes_include_inquiry_membership(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path)
    inquiry_scope = next(scope for scope in payload["scopes"] if scope["kind"] == "inquiry")
    assert inquiry_scope["id"] == "inquiry/test-dag"
    assert inquiry_scope["node_ids"]
```

**Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_node_ids_are_stable_across_runs tests/test_graph_export.py::test_export_scopes_include_inquiry_membership -q`

Expected: FAIL because stable id and scope semantics are not defined yet.

**Step 3: Write minimal implementation**

- Use canonical URI strings as node ids.
- Create deterministic edge ids from `(subject, predicate, object, graph_layer)`.
- Define explicit scope objects with:
  - `id`
  - `kind`
  - `label`
  - `node_ids`
  - `edge_ids`
  - optional metadata
- Keep these types in the shared export contract, not ad hoc dictionaries.

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_node_ids_are_stable_across_runs tests/test_graph_export.py::test_export_scopes_include_inquiry_membership -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/export_types.py science-tool/tests/test_graph_export.py
git commit -m "feat: define stable graph export ids and scopes"
```

### Task 3: Export Base Graph Nodes, Edges, Layers, And Scopes

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing test**

```python
def test_export_graph_payload_includes_base_nodes_edges_layers(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path)
    drug = next(node for node in payload["nodes"] if node["id"] == "http://example.org/project/concept/drug")
    edge = next(edge for edge in payload["edges"] if edge["predicate"] == "http://example.org/science/vocab/causal/causes")
    assert drug["label"] == "Drug"
    assert edge["graph_layer"] == "graph/causal"
```

**Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_base_nodes_edges_layers -q`

Expected: FAIL because `export_graph_payload` does not exist yet.

**Step 3: Write minimal implementation**

- Add `export_graph_payload(...)` in `store.py`.
- Reuse existing graph loading/query helpers.
- Populate:
  - generic nodes with label, type, status, confidence, source refs, graph layer
  - generic edges with source, target, predicate, graph layer
  - layer summaries
  - scopes for whole-project and inquiry-local membership where available
- Do not add overlay-specific fields yet.
- Add at least one explicit semantic assertion in the tests for a known node label and a known causal edge.

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_base_nodes_edges_layers -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_export.py
git commit -m "feat: add base graph export payload"
```

### Task 4: Add `causal` Overlay Export

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing test**

```python
def test_export_graph_payload_includes_causal_overlay_for_inquiry(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["causal"])
    inquiry = payload["overlays"]["causal"]["inquiries"]["inquiry/test-dag"]
    edge = inquiry["edges"][0]
    assert inquiry["treatment"] == "http://example.org/project/concept/drug"
    assert edge["kind"] == "causes"
```

**Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_causal_overlay_for_inquiry -q`

Expected: FAIL because the `causal` overlay is missing.

**Step 3: Write minimal implementation**

- Add `causal` overlay assembly to `export_graph_payload(...)`.
- Include:
  - causal edge kind
  - inquiry-keyed membership
  - inquiry-keyed treatment/outcome
  - inquiry-keyed boundary roles
  - confound edges where present
- Keep overlay references keyed by exported node/edge ids rather than duplicating full base records.
- Do not place a single treatment/outcome pair at the overlay root.

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_causal_overlay_for_inquiry -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_export.py
git commit -m "feat: add causal overlay to graph export"
```

### Task 5: Add Edge-Centric `evidence` Overlay Export

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing test**

```python
def test_export_graph_payload_includes_evidence_overlay_for_claim_backed_edge(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["evidence"])
    edge_id = next(edge["id"] for edge in payload["edges"] if edge["predicate"].endswith("/causes"))
    edge_evidence = payload["overlays"]["evidence"]["edges"][edge_id]
    assert edge_evidence["claims"][0]["bridge_between"] == ["hypothesis/h1", "hypothesis/h2"]


def test_export_graph_payload_skips_missing_claim_refs_with_warning(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["evidence"])
    assert any("missing claim ref" in warning for warning in payload["warnings"])
```

**Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_evidence_overlay_for_claim_backed_edge -q`

Expected: FAIL because the `evidence` overlay is missing.

**Step 3: Write minimal implementation**

- Reuse existing proposition enrichment helpers already used by causal exporters.
- Export typed evidence metadata for attached claims:
  - support/dispute counts
  - evidence semantics
  - compositional metadata
  - platform heterogeneity and dataset effects
  - evidence lines
  - pre-registrations
  - interaction terms
  - falsifications
  - bridge metadata
- Keep overlay structure edge-centric for v1.
- Skip broken claim refs and emit export warnings rather than failing the whole export.
- Do not add a separate node-level evidence overlay in v1.

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_evidence_overlay_for_claim_backed_edge -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_export.py
git commit -m "feat: add evidence overlay to graph export"
```

### Task 6: Add JSON CLI Export In `science-tool`

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing test**

```python
def test_graph_export_json_emits_selected_overlays() -> None:
    result = runner.invoke(main, ["graph", "export-json", "--overlay", "causal", "--overlay", "evidence"])
    payload = json.loads(result.output)
    assert "causal" in payload["overlays"]
    assert "evidence" in payload["overlays"]
    assert payload["schema_version"] == "1"
```

**Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_graph_cli.py::test_graph_export_json_emits_selected_overlays -q`

Expected: FAIL because the CLI command does not exist.

**Step 3: Write minimal implementation**

- Add a `graph export-json` command.
- Support flags for:
  - `--overlay`
  - `--inquiry`
  - `--layer`
  - `--path`
- Emit only JSON to stdout.
- Use repeatable `--overlay` flags rather than comma-separated parsing so Click keeps the interface simple and additive.
- Make the default export base-only unless overlays are explicitly requested.

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_cli.py::test_graph_export_json_emits_selected_overlays -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add graph json export command"
```

### Task 7: Adapt Dashboard Backend To Shared Payload Without Losing Existing Graph Semantics

**Files:**
- Modify: `../dashboard/backend/graph.py`
- Modify: `../dashboard/backend/store.py`
- Modify: `../dashboard/backend/routes/projects.py`
- Test: `../dashboard/tests/test_api_projects.py`
- Test: `../dashboard/tests/test_store.py`

**Step 1: Write the failing test**

```python
def test_project_graph_api_returns_overlay_aware_payload(client):
    payload = client.get("/api/projects/demo/graph").json()
    assert "overlays" in payload
    assert "lens_values" in payload["nodes"][0]
```

**Step 2: Run test to verify it fails**

Run: `cd ../dashboard && uv run --frozen pytest tests/test_api_projects.py::test_project_graph_api_returns_overlay_aware_payload -q`

Expected: FAIL because the backend still returns the old payload shape and does not yet preserve dashboard enrichments.

**Step 3: Write minimal implementation**

- Replace or wrap dashboard-local graph loading so it emits the shared payload shape.
- Prefer importing the shared builder from `science-tool` rather than re-implementing semantics.
- Preserve dashboard-local `lod`, `lens_values`, `style_values`, `encoding_metadata`, and `reference_date` handling as a post-processing step.
- Keep the dashboard response additive: shared graph payload plus dashboard-owned visual fields.
- Do not change the dashboard route in a way that requires the frontend to be updated in a separate broken commit.

**Step 4: Run test to verify it passes**

Run: `cd ../dashboard && uv run --frozen pytest tests/test_api_projects.py::test_project_graph_api_returns_overlay_aware_payload -q`

Expected: PASS

**Step 5: Commit**

```bash
git add ../dashboard/backend/graph.py ../dashboard/backend/store.py ../dashboard/backend/routes/projects.py ../dashboard/tests/test_api_projects.py ../dashboard/tests/test_store.py
git commit -m "feat: adapt dashboard graph api to shared export"
```

### Task 8: Add Dashboard Backend Regression Coverage For Lens And Style Preservation

**Files:**
- Modify: `../dashboard/tests/test_store.py`
- Modify: `../dashboard/tests/test_api_projects.py`

**Step 1: Write the failing regression test**

```python
def test_project_graph_preserves_dashboard_visual_fields_after_shared_export(store):
    payload = store.get_graph("demo", lod=1.0)
    node = payload.nodes[0]
    assert node.lens_values is not None
    assert node.style_values is not None
    assert payload.encoding_metadata["size"].available in {True, False}
```

**Step 2: Run test to verify it fails**

Run: `cd ../dashboard && uv run --frozen pytest tests/test_store.py::test_project_graph_preserves_dashboard_visual_fields_after_shared_export -q`

Expected: FAIL because the migration path is not preserving current dashboard graph enrichment yet.

**Step 3: Write minimal implementation**

- Add regression coverage for:
  - `lod`
  - `lens_values`
  - `style_values`
  - `encoding_metadata`
  - `reference_date`-driven activity behavior
- Prefer behavior-level assertions over byte-for-byte snapshot comparisons.

**Step 4: Run test to verify it passes**

Run: `cd ../dashboard && uv run --frozen pytest tests/test_store.py::test_project_graph_preserves_dashboard_visual_fields_after_shared_export -q`

Expected: PASS

**Step 5: Commit**

```bash
git add ../dashboard/tests/test_store.py ../dashboard/tests/test_api_projects.py
git commit -m "test: cover dashboard graph migration regressions"
```

### Task 9: Add A Cross-Repo Integration Check

**Files:**
- Modify: `../dashboard/tests/test_store.py`
- Modify: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing integration test**

```python
def test_dashboard_can_consume_shared_graph_export_for_project(...) -> None:
    payload = export_graph_payload(graph_path, overlays=["causal", "evidence"])
    graph = adapt_shared_payload_for_dashboard(payload, ...)
    assert graph.overlays["causal"]
```

**Step 2: Run test to verify it fails**

Run: `cd ../dashboard && uv run --frozen pytest tests/test_store.py::test_dashboard_can_consume_shared_graph_export_for_project -q`

Expected: FAIL because there is not yet a verified integration path from shared export to dashboard payload.

**Step 3: Write minimal implementation**

- Add one real integration test that exercises the shared export builder and the dashboard adaptation layer together.
- This can be an in-process import path; it does not need to shell out to the CLI.
- Verify at least one known causal edge and one known evidence claim survive the boundary.

**Step 4: Run test to verify it passes**

Run: `cd ../dashboard && uv run --frozen pytest tests/test_store.py::test_dashboard_can_consume_shared_graph_export_for_project -q`

Expected: PASS

**Step 5: Commit**

```bash
git add ../dashboard/tests/test_store.py science-tool/tests/test_graph_export.py
git commit -m "test: add shared graph export integration coverage"
```

### Task 10: Add Overlay Types To Dashboard Frontend

**Files:**
- Modify: `../dashboard/frontend/src/types/index.ts`
- Modify: `../dashboard/frontend/src/api/client.ts`

**Step 1: Write the failing type/test change**

```ts
type GraphData = {
  overlays: Record<string, unknown>
}
```

Add the concrete overlay types the frontend needs and make TypeScript fail until consumers are updated.

**Step 2: Run type/lint check to verify it fails**

Run: `cd ../dashboard/frontend && npm run build`

Expected: FAIL because graph consumers still assume the older payload shape.

**Step 3: Write minimal implementation**

- Extend frontend graph types with:
  - `causal` overlay
  - `evidence` overlay
- Keep optional fields explicit.
- Update the API client type to return the richer payload.
- Preserve existing dashboard-specific fields on the frontend graph types.

**Step 4: Run type/lint check to verify it passes**

Run: `cd ../dashboard/frontend && npm run build`

Expected: PASS

**Step 5: Commit**

```bash
git add ../dashboard/frontend/src/types/index.ts ../dashboard/frontend/src/api/client.ts
git commit -m "feat: add graph overlay types to dashboard frontend"
```

### Task 11: Surface Overlay Controls In Existing Graph Explorer

**Files:**
- Modify: `../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx`
- Modify: `../dashboard/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx`
- Modify: `../dashboard/frontend/src/routes/ProjectGraph.tsx`

**Step 1: Define a manual golden-path checklist**

There is currently no Vitest/RTL harness in `../dashboard/frontend/package.json`, so v1 should use build-first verification plus a short manual checklist instead of pretending component tests exist.

Checklist:

- graph route loads without runtime errors
- overlay controls are visible
- user can toggle causal/evidence emphasis
- base layer controls still work
- selecting a graph element still opens detail state

**Step 2: Run test or build to verify it fails**

Run: `cd ../dashboard/frontend && npm run build`

Expected: FAIL or missing UI because overlay controls do not exist yet.

**Step 3: Write minimal implementation**

- Add overlay-aware controls to the existing explorer.
- Do not fork the route into a second explorer.
- Let users:
  - toggle overlay emphasis
- inspect overlay metadata on selected nodes/edges
- Keep the existing layer controls intact.
- If adding a real frontend test harness later seems justified, make that a separate plan item rather than silently expanding scope here.

**Step 4: Run verification to verify it passes**

Run: `cd ../dashboard/frontend && npm run build`

Expected: PASS

Manual: exercise the checklist above in the browser before closing the task.

**Step 5: Commit**

```bash
git add ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx ../dashboard/frontend/src/routes/ProjectGraph.tsx
git commit -m "feat: add overlay-aware controls to graph explorer"
```

### Task 12: Show Typed Evidence Details In Selection Panels

**Files:**
- Modify: `../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx`
- Modify: `../dashboard/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx`

**Step 1: Extend the manual golden-path checklist**

Checklist additions:

- selected edge shows causal role when present
- selected edge shows support/dispute summary when present
- selected edge shows pre-registrations, falsifications, interaction terms, and bridge metadata when present

**Step 2: Run test or build to verify it fails**

Run: `cd ../dashboard/frontend && npm run build`

Expected: FAIL or missing details because overlay-driven inspection does not exist yet.

**Step 3: Write minimal implementation**

- Extend selection panels so edge/node inspection shows:
  - causal role
  - support/dispute summary
  - pre-registrations
  - falsifications
  - interaction terms
  - bridge metadata
- Prefer small helper renderers over one large JSX block.

**Step 4: Run verification to verify it passes**

Run: `cd ../dashboard/frontend && npm run build`

Expected: PASS

Manual: exercise the extended checklist above in the browser before closing the task.

**Step 5: Commit**

```bash
git add ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx
git commit -m "feat: add typed evidence details to graph explorer"
```

### Task 13: Run End-To-End Verification And Clean Up

**Files:**
- Modify: `science-tool/tests/test_graph_export.py`
- Modify: `science-tool/tests/test_graph_cli.py`
- Modify: `../dashboard/tests/test_api_projects.py`
- Modify: `../dashboard/tests/test_store.py`

**Step 1: Add any missing regression coverage**

- Add a cross-repo smoke test checklist in the doc if automation is incomplete.
- Keep tests focused on contract shape and critical semantics.
- Ensure at least one test covers skipped broken claim refs and one covers inquiry-keyed causal overlay semantics.

**Step 2: Run Python verification in `science-tool`**

Run:

```bash
cd science-tool
uv run --frozen pytest tests/test_graph_export.py tests/test_graph_cli.py tests/test_causal.py -q
uv run --frozen ruff check src/science_tool/graph/store.py src/science_tool/graph/export_types.py src/science_tool/cli.py tests/test_graph_export.py tests/test_graph_cli.py tests/test_causal.py
uv run --frozen ruff format --check src/science_tool/graph/store.py src/science_tool/graph/export_types.py src/science_tool/cli.py tests/test_graph_export.py tests/test_graph_cli.py tests/test_causal.py
```

Expected: PASS

**Step 3: Run Python verification in `dashboard`**

Run:

```bash
cd ../dashboard
uv run --frozen pytest tests/test_api_projects.py tests/test_store.py -q
uv run --frozen ruff check backend tests
uv run --frozen ruff format --check backend tests
```

Expected: PASS

**Step 4: Run frontend verification in `dashboard`**

Run:

```bash
cd ../dashboard/frontend
npm run build
npm run lint
```

Expected: PASS

Manual:

- open the dashboard graph route for one project with causal content
- confirm overlay controls work
- confirm one known backed causal edge exposes evidence metadata

**Step 5: Stage explicit files only and commit**

During execution, keep `dashboard` backend and frontend contract changes in one coordinated local slice. Do not create a commit that breaks `dashboard/main` between backend and frontend updates.

```bash
git add science-tool/src/science_tool/graph/export_types.py
git add science-tool/src/science_tool/graph/store.py
git add science-tool/src/science_tool/cli.py
git add science-tool/tests/test_graph_export.py
git add science-tool/tests/test_graph_cli.py
git add science-tool/tests/test_causal.py
git add ../dashboard/backend/graph.py
git add ../dashboard/backend/store.py
git add ../dashboard/backend/routes/projects.py
git add ../dashboard/tests/test_api_projects.py
git add ../dashboard/tests/test_store.py
git add ../dashboard/frontend/src/types/index.ts
git add ../dashboard/frontend/src/api/client.ts
git add ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx
git add ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx
git add ../dashboard/frontend/src/routes/ProjectGraph.tsx
git commit -m "feat: wire shared graph export into dashboard explorer"
```
