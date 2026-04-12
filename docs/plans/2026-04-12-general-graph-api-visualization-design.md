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

The exported JSON payload should have these top-level sections:

- `schema_version`
- `nodes`
- `edges`
- `layers`
- `scopes`
- `overlays`
- `warnings`

`schema_version` is required. `warnings` is optional and is used for partial-export diagnostics such as missing claim referents.

### Base Graph Core

The base graph core should stay generic and reusable. It should answer:

- what nodes exist
- what edges exist
- which layer each came from
- which scopes they belong to
- core descriptive metadata such as label, type, status, confidence, and source refs

This layer should not encode causal meaning directly.

### Stable Identity

#### Node IDs

V1 should use the canonical graph URI string as the exported node id. We already treat URIs as the stable identity in both `science-tool` and the dashboard graph loader, so inventing a second synthetic node key would add unnecessary translation risk.

#### Edge IDs

V1 should assign a deterministic edge id derived from:

- subject URI
- predicate URI
- object URI
- graph layer

This keeps edge identity stable across runs and distinguishes otherwise identical triples that appear in different layers.

Multiple proposition-backed claims can support the same exported edge. Those claims should not create separate base edges.

### Scope Shape

`scopes` should be an explicit typed list, not an unstructured bucket. V1 should support:

- `project` scope
- `inquiry/<slug>` scope

Each scope record should include:

- `id`
- `kind`
- `label`
- `node_ids`
- `edge_ids`
- optional metadata such as treatment/outcome for inquiry scopes

This lets callers ask for a full-project export while still understanding inquiry-local subgraphs.

### Typed Overlays

Overlays carry domain-specific semantics without distorting the base graph model.

#### `causal` overlay

Should encode:

- causal edge kind (`causes`, `confounds`, later possibly more)
- inquiry membership keyed by inquiry scope id
- treatment and outcome keyed by inquiry scope id
- boundary roles keyed by node id and inquiry scope id
- inquiry-local scope membership

The `causal` overlay should be inquiry-keyed. A project can contain multiple causal inquiries, so treatment/outcome cannot live at the overlay root as a single pair.

#### `evidence` overlay

V1 is explicitly **edge-centric**. It should encode proposition-backed edge support and caveats, including:

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

V1 does **not** attempt a separate node-level evidence model beyond base node metadata such as status, confidence, and source refs. If we later want node-level claim bundles for hypotheses or propositions, that should be a separate overlay extension rather than implicit scope creep.

#### `encodings` overlay

Not required for v1 and not part of the initial implementation plan. We can leave the overlay namespace open-ended without shipping an `encodings` overlay now.

### Error Policy

The export path should follow the project’s fail-early preference for structural mistakes, while still tolerating some incomplete project graphs.

V1 policy:

- invalid export parameters or malformed internal graph structure: fail the export
- missing optional evidence referents for an otherwise valid edge: skip that referent and emit a warning
- missing proposition metadata fields: export the claim with partial metadata

This is especially important because some projects can contain unresolved references. We should not silently invent replacement objects, but we also should not fail the whole export because one attached claim ref is broken.

### Payload Size And Performance

The evidence overlay can become large. V1 should control this by:

- exporting the base graph without overlays unless overlays are explicitly requested
- supporting repeated overlay selection such as `--overlay causal --overlay evidence`
- supporting scope narrowing by inquiry and layer
- keeping evidence overlay records edge-centric rather than duplicating the full base graph

V1 does not need lazy loading, but it should avoid unconditional full-project evidence expansion.

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
- warning emission for skipped broken evidence refs

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
- Make stable ids and scope membership part of the export contract, not caller-side convention.

### `dashboard` backend

- Use the shared graph export contract as the API returned to the frontend.
- Avoid silently re-implementing causal/evidence semantics in dashboard-only code.
- Preserve dashboard-owned `lod`, `lens_values`, `style_values`, `encoding_metadata`, and `reference_date` handling as a post-processing wrapper around the shared export.
- Maintain the current dashboard response shape as an additive extension of the shared graph payload rather than a forked semantic model.

### `dashboard` frontend

- Keep using the existing graph route.
- Add overlay-aware filtering and inspection rather than creating a second explorer.
- Make node/edge detail panels show typed evidence metadata when present.
- Treat overlays as optional so partial payloads still render.

## Testing

We should verify:

- stable node and edge ids across repeated exports
- scope membership and inquiry-keyed causal overlay semantics
- evidence overlay correctness for proposition-backed edges, including bridge metadata and skipped broken refs
- dashboard backend adaptation preserves `lod`, `lens_values`, `style_values`, `encoding_metadata`, and activity/reference-date behavior
- dashboard/frontend integration consumes the shared payload correctly
- dashboard UI changes build cleanly and pass a manual golden-path check if no frontend component harness exists yet

## Risks

- overdesigning the generic contract before the first real consumer stabilizes
- leaking dashboard-specific visualization concerns into `science-tool`
- duplicating semantics if the dashboard backend shortcuts around the shared export builder
- breaking the dashboard mid-migration if backend and frontend contract changes land out of sync

## Guiding Principle

The graph API should be **general in structure, typed in semantics, and conservative in scope**. We want one reusable graph contract, not a speculative graph platform.
