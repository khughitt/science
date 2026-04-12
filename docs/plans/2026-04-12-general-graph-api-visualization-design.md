# General Graph API And Visualization Design

## Goal

Define a reusable graph API owned by `science-tool` that can serve both project-local knowledge graph inspection and causal/evidence visualization in `~/d/dashboard/`.

## Context

We already have:

- project TriG graphs in `science-tool`
- causal export logic with enriched proposition-backed claim metadata
- a dashboard graph route with working 2D/3D exploration and backend graph loading

What is missing is a shared semantic contract. Right now, the dashboard derives a generic graph payload directly from project TriG data, while the richer causal/evidence semantics live mostly inside `science-tool` query and export paths.

## Approaches Considered

### 1. Causal-Only Payload

Expose a dedicated causal DAG payload from `science-tool` and leave the dashboard’s generic graph handling separate.

Pros:

- fast initial delivery
- minimal new abstraction

Cons:

- duplicates graph semantics once non-causal project views need the same structure
- encourages a split product model between “graph” and “causal graph”

### 2. Fully Generic Graph Payload With Flat Metadata

Expose a single general graph payload and attach every causal/evidence detail as ad hoc metadata.

Pros:

- simple top-level shape
- one API surface

Cons:

- loses semantic structure
- makes frontend behavior harder to reason about
- risks flattening causal/evidence distinctions into opaque blobs

### 3. General Graph Core Plus Typed Overlays

Expose one general graph payload from `science-tool`, then attach typed overlays for specialized semantics such as causal structure and evidence framing.

Pros:

- reusable across project KG, inquiry DAGs, and dashboard
- preserves causal/evidence semantics as first-class structured data
- fits the existing dashboard graph explorer without creating a second graph product

Cons:

- slightly more up-front design than a causal-only payload

## Decision

Use **general graph core plus typed overlays**.

`science-tool` becomes the semantic source of truth for graph export. The dashboard becomes the first richer consumer of that contract.

## Contract

The exported JSON payload should have five top-level sections:

- `nodes`
- `edges`
- `layers`
- `scopes`
- `overlays`

### Base Graph Core

The base graph core should stay generic and reusable. It should answer:

- what nodes exist
- what edges exist
- which layer each came from
- which scopes they belong to
- core descriptive metadata such as label, type, status, confidence, and source refs

This layer should not encode causal meaning directly.

### Typed Overlays

Overlays carry domain-specific semantics without distorting the base graph model.

#### `causal` overlay

Should encode:

- causal edge kind (`causes`, `confounds`, later possibly more)
- inquiry membership
- treatment and outcome
- boundary roles
- inquiry-local scope membership

#### `evidence` overlay

Should encode proposition-backed edge support and caveats, including:

- supporting claim refs
- support/dispute counts
- compositional metadata
- platform heterogeneity and per-dataset effects
- evidence lines
- explicit evidence semantics
- pre-registrations
- interaction terms
- falsifications
- cross-hypothesis bridges

#### `encodings` overlay

Not required for v1, but reserved for future backend-provided visual hints or aggregate metrics if we decide the backend should participate in visual semantics.

## Consumers

### Project-Local Consumer

`science-tool` should provide a CLI command that emits the graph payload as JSON for inspection, scripting, and local visualization work. The CLI should allow choosing scopes and overlays rather than forcing one fixed graph view.

### Dashboard Consumer

The existing dashboard route at `/projects/:slug/graph` should become the first consumer of the new contract. This is a better long-term path than creating a separate causal-only explorer because:

- it keeps one graph exploration surface
- it reuses current layer controls and inspection UI
- it lets the frontend add overlay-aware controls incrementally

The dashboard should keep ownership of visual encoding and rendering behavior. `science-tool` should own graph semantics, not frontend-specific styling.

## V1 Scope

V1 should include:

- base graph payload
- `causal` overlay
- `evidence` overlay
- `science-tool` CLI JSON export
- dashboard backend adaptation to the new payload
- dashboard frontend updates so the existing graph explorer can surface overlay metadata

V1 should not include:

- a separate causal-only dashboard route
- backend-generated layout hints
- graph mutation/editing APIs
- a fully generalized visualization settings system

## Architecture

### `science-tool`

- Build a typed graph export layer on top of existing TriG data.
- Reuse current claim enrichment logic rather than re-deriving proposition semantics separately.
- Expose explicit scope selection so callers can ask for full-project, inquiry-scoped, or causal-focused views.

### `dashboard` backend

- Use the shared graph export contract as the API returned to the frontend.
- Avoid silently re-implementing causal/evidence semantics in dashboard-only code.
- Keep dashboard-specific graph encoding logic local to the dashboard backend.

### `dashboard` frontend

- Keep using the existing graph route.
- Add overlay-aware filtering and inspection rather than creating a second explorer.
- Make node/edge detail panels show typed evidence metadata when present.

## Testing

We should verify:

- JSON export shape and overlay selection in `science-tool`
- causal and evidence overlay correctness for proposition-backed claims
- dashboard backend adaptation preserves payload shape
- dashboard frontend renders overlay-aware controls and details without breaking existing graph exploration

## Risks

- overdesigning the generic contract before the first real consumer stabilizes
- leaking dashboard-specific visualization concerns into `science-tool`
- duplicating semantics if the dashboard backend shortcuts around the shared export builder

## Guiding Principle

The graph API should be **general in structure, typed in semantics, and conservative in scope**. We want one reusable graph contract, not a speculative graph platform.
