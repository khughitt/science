# General Graph API And Visualization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reusable `science-tool` JSON graph export with typed `causal` and `evidence` overlays, then make the existing dashboard graph explorer consume that shared contract.

**Architecture:** `science-tool` owns the base graph payload and overlay semantics. The dashboard reuses that payload on its existing project graph route and keeps ownership of renderer-specific visual encoding and interaction behavior.

**Tech Stack:** Python, Click, rdflib, FastAPI, Pydantic, React 19, TypeScript, Vite

---

### Task 1: Define Shared Export Types In `science-tool`

**Files:**
- Modify: `science-tool/src/science_tool/graph/__init__.py`
- Create: `science-tool/src/science_tool/graph/export_types.py`
- Test: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing test**

```python
def test_export_types_roundtrip_minimal_payload() -> None:
    payload = GraphExportPayload(
        nodes=[],
        edges=[],
        layers=[],
        scopes=[],
        overlays={},
    )
    assert payload.model_dump()["nodes"] == []
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
- Keep the base contract generic.
- Reserve typed overlay containers for `causal` and `evidence`.

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_types_roundtrip_minimal_payload -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/export_types.py science-tool/src/science_tool/graph/__init__.py science-tool/tests/test_graph_export.py
git commit -m "feat: add graph export payload types"
```

### Task 2: Export Base Graph Nodes, Edges, Layers, And Scopes

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing test**

```python
def test_export_graph_payload_includes_base_nodes_edges_layers(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path)
    assert payload["nodes"]
    assert payload["edges"]
    assert payload["layers"]
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

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_base_nodes_edges_layers -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_export.py
git commit -m "feat: add base graph export payload"
```

### Task 3: Add `causal` Overlay Export

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing test**

```python
def test_export_graph_payload_includes_causal_overlay_for_inquiry(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["causal"])
    assert "causal" in payload["overlays"]
    assert payload["overlays"]["causal"]["treatment"] == "concept/drug"
```

**Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_causal_overlay_for_inquiry -q`

Expected: FAIL because the `causal` overlay is missing.

**Step 3: Write minimal implementation**

- Add `causal` overlay assembly to `export_graph_payload(...)`.
- Include:
  - causal edge kind
  - inquiry membership
  - treatment/outcome
  - boundary roles
  - confound edges where present
- Keep overlay references keyed by exported node/edge ids rather than duplicating full base records.

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_causal_overlay_for_inquiry -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_export.py
git commit -m "feat: add causal overlay to graph export"
```

### Task 4: Add `evidence` Overlay Export

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_export.py`

**Step 1: Write the failing test**

```python
def test_export_graph_payload_includes_evidence_overlay_for_claim_backed_edge(graph_path: Path) -> None:
    payload = export_graph_payload(graph_path, overlays=["evidence"])
    evidence = payload["overlays"]["evidence"]
    assert evidence["edge_claims"]
    assert evidence["edge_claims"][0]["bridge_between"] == ["hypothesis/h1", "hypothesis/h2"]
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

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_export.py::test_export_graph_payload_includes_evidence_overlay_for_claim_backed_edge -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_export.py
git commit -m "feat: add evidence overlay to graph export"
```

### Task 5: Add JSON CLI Export In `science-tool`

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

**Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_graph_cli.py::test_graph_export_json_emits_selected_overlays -q`

Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add graph json export command"
```

### Task 6: Adapt Dashboard Backend To Shared Payload

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
```

**Step 2: Run test to verify it fails**

Run: `cd ../dashboard && uv run --frozen pytest tests/test_api_projects.py::test_project_graph_api_returns_overlay_aware_payload -q`

Expected: FAIL because the backend still returns the old payload shape.

**Step 3: Write minimal implementation**

- Replace or wrap dashboard-local graph loading so it emits the shared payload shape.
- Prefer importing the shared builder from `science-tool` rather than re-implementing semantics.
- Preserve dashboard-local visual encoding derivation as a post-processing step.

**Step 4: Run test to verify it passes**

Run: `cd ../dashboard && uv run --frozen pytest tests/test_api_projects.py::test_project_graph_api_returns_overlay_aware_payload -q`

Expected: PASS

**Step 5: Commit**

```bash
git add ../dashboard/backend/graph.py ../dashboard/backend/store.py ../dashboard/backend/routes/projects.py ../dashboard/tests/test_api_projects.py ../dashboard/tests/test_store.py
git commit -m "feat: adapt dashboard graph api to shared export"
```

### Task 7: Add Overlay Types To Dashboard Frontend

**Files:**
- Modify: `../dashboard/frontend/src/types/index.ts`
- Modify: `../dashboard/frontend/src/api/client.ts`
- Test: `../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx`

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

**Step 4: Run type/lint check to verify it passes**

Run: `cd ../dashboard/frontend && npm run build`

Expected: PASS

**Step 5: Commit**

```bash
git add ../dashboard/frontend/src/types/index.ts ../dashboard/frontend/src/api/client.ts
git commit -m "feat: add graph overlay types to dashboard frontend"
```

### Task 8: Surface Overlay Controls In Existing Graph Explorer

**Files:**
- Modify: `../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx`
- Modify: `../dashboard/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx`
- Modify: `../dashboard/frontend/src/routes/ProjectGraph.tsx`

**Step 1: Write the failing behavior test or focused rendering assertion**

Use the smallest existing frontend test path available. If no component test harness exists yet, create a narrow component test or document a temporary build-first verification.

Example target behavior:

```tsx
expect(screen.getByText("Overlays")).toBeInTheDocument()
expect(screen.getByText("Causal")).toBeInTheDocument()
expect(screen.getByText("Evidence")).toBeInTheDocument()
```

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

**Step 4: Run verification to verify it passes**

Run: `cd ../dashboard/frontend && npm run build`

Expected: PASS

**Step 5: Commit**

```bash
git add ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx ../dashboard/frontend/src/routes/ProjectGraph.tsx
git commit -m "feat: add overlay-aware controls to graph explorer"
```

### Task 9: Show Typed Evidence Details In Selection Panels

**Files:**
- Modify: `../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx`
- Modify: `../dashboard/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx`

**Step 1: Write the failing behavior test or rendering assertion**

Example target behavior:

```tsx
expect(screen.getByText("Pre-registrations")).toBeInTheDocument()
expect(screen.getByText("Bridge Hypotheses")).toBeInTheDocument()
```

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

**Step 5: Commit**

```bash
git add ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer.tsx ../dashboard/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx
git commit -m "feat: add typed evidence details to graph explorer"
```

### Task 10: Run End-To-End Verification And Clean Up

**Files:**
- Modify: `science-tool/tests/test_graph_export.py`
- Modify: `science-tool/tests/test_graph_cli.py`
- Modify: `../dashboard/tests/test_api_projects.py`
- Modify: `../dashboard/tests/test_store.py`

**Step 1: Add any missing regression coverage**

- Add a cross-repo smoke test checklist in the doc if automation is incomplete.
- Keep tests focused on contract shape and critical semantics.

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

**Step 5: Commit**

```bash
git add science-tool ../dashboard
git commit -m "feat: wire shared graph export into dashboard explorer"
```
