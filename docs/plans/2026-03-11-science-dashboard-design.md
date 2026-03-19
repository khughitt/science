# Science Dashboard — Design Spec

A local web application for visualizing, managing, and exploring a user's collection of Science research projects. Runs alongside the `science` CLI plugin — complements it with spatial/visual capabilities that a terminal cannot provide.

**Separate repository** from `science-tool`. The dashboard reads project directories and imports `science_tool` as a Python dependency for data access and write-back.

## Use Cases

1. **Orientation** — "Where was I?" Return to a project after days/weeks; see what's active, stale, and blocked at a glance.
2. **Cross-project awareness** — See how entities (concepts, papers, hypotheses) connect across projects. Spot shared themes and divergent approaches.
3. **Knowledge graph exploration** — Visually navigate entities, trace provenance, identify knowledge gaps and bottlenecks, find learning edges.

## Architecture: Filesystem + Lightweight Index (Approach B)

### Source of truth

The filesystem. Project directories with `science.yaml`, markdown + YAML frontmatter, and `knowledge/graph.trig`.

### Index layer

At startup, the backend:

1. Reads the config file (`~/.config/science-dashboard/config.yaml`) listing project paths.
2. For each project: parses `science.yaml`, scans entity directories, parses `knowledge/graph.trig` via rdflib.
3. Builds an in-memory index: entities (with type, status, dates, relations), full-text content, cross-project entity deduplication (by URI or label).
4. Stores in SQLite (in-memory or file-backed — configurable) for fast querying + FTS.

**Scanned directories** (resolved via `science_tool.paths.resolve_paths()`):
- `doc/` — questions, topics, inquiries, interpretations, discussions, plans, methods, meta (pre-registrations, bias audits)
- `specs/` — research question, scope, hypotheses
- `papers/summaries/` — paper summary documents
- `notes/` — topic notes, article notes (informal convention, not in ProjectPaths but used across projects)
- `knowledge/graph.trig` — RDF knowledge graph (parsed separately via rdflib)

**Excluded:** `templates/`, `.venv`, `data/`, `.git`, `__pycache__`

**Special parsing:** Tasks (`tasks/active.md`, `tasks/done/*.md`) use a custom markdown format — not YAML frontmatter — and must be parsed via `science_tool.tasks.parse_tasks()`, not the generic frontmatter scanner.

**Body-text cross-references:** In addition to frontmatter `related:` lists, the indexer harvests inline references from document bodies using patterns from `science_tool.refs`: hypothesis references (`H01`, `H02`), citation keys (`@Author2024`), and markdown links. These augment the relationship graph with connections that frontmatter alone misses.

### Cache invalidation

`watchfiles` monitors project directories. On file change:

- Re-parse only the changed file's frontmatter/content.
- If `graph.trig` changed, reload that project's graph.
- Update index incrementally.

### Data access interface

```python
class DataStore(Protocol):
    # Read
    def list_projects(self) -> list[Project]: ...
    def get_project(self, slug: str) -> ProjectDetail: ...
    def get_entity(self, project: str, entity_id: str) -> Entity: ...
    def list_entities(self, entity_type: str | None, project: str | None) -> list[Entity]: ...
    def search(self, query: str, filters: Filters) -> list[SearchResult]: ...
    def get_graph(self, project: str, lod: float) -> GraphData: ...
    def recent_activity(self, limit: int, project: str | None) -> list[ActivityItem]: ...

    # Write
    def create_task(self, project: str, task: TaskCreate) -> Task: ...
    def update_task(self, project: str, task_id: str, update: TaskUpdate) -> Task: ...
    def update_entity(self, project: str, entity_id: str, update: EntityUpdate) -> Entity: ...

    # Admin
    def rescan(self, project: str | None = None) -> None: ...
    def get_config(self) -> DashboardConfig: ...
    def update_config(self, update: ConfigUpdate) -> DashboardConfig: ...
```

This protocol can later be swapped for a triplestore-backed implementation (Approach C).

### Write-back

Mutations (task creation, status changes) go through `science_tool` directly — calling the same functions the CLI uses — so file format consistency is guaranteed. The dashboard uses `science_tool.paths.resolve_paths(project_root)` to obtain `ProjectPaths` per project and passes the relevant directories (e.g., `paths.tasks_dir`) to write-back functions.

## Backend API

### REST endpoints

```
POST /api/projects/rescan          # force re-index
GET  /api/projects                  # list all projects (summary)
GET  /api/projects/{slug}           # project detail (dashboard data)
GET  /api/projects/{slug}/graph     # KG data for visualization
GET  /api/projects/{slug}/activity  # recent activity feed

GET  /api/entities                  # cross-project entity list (filterable by type, domain, project)
GET  /api/entities/{id}             # entity detail + cross-project references

GET  /api/hypotheses                # all hypotheses across projects
GET  /api/questions                 # all questions across projects
GET  /api/tasks                     # all tasks across projects

GET  /api/search?q=...&project=...&type=...  # full-text search with filters

POST /api/projects/{slug}/tasks     # create task
PATCH /api/projects/{slug}/tasks/{id}     # update task (status, priority)
PATCH /api/projects/{slug}/entities/{id}  # update entity metadata (status, priority)

GET  /api/config                    # current dashboard config (colorscheme, etc.)
PATCH /api/config                   # update dashboard preferences

WS   /api/ws                        # websocket for file-watcher push updates
```

Entity endpoints are cross-project by default, with `?project=foo` as a filter. The graph endpoint accepts `?lod=0.3` (0–1 float) to control level-of-detail. Task and entity mutation endpoints are scoped under `/projects/{slug}/` to avoid ID collisions (e.g., two projects both having `t001`). Entity IDs within a project use the `type:slug` format from frontmatter (e.g., `hypothesis:h01-attention-improves`).

**Project slugs** are derived from the directory basename (e.g., `/home/keith/d/seq-feats` → `seq-feats`).

**WebSocket message format:**

```json
{"event": "entity_updated", "project": "seq-feats", "entity_id": "hypothesis:h01", "data": {...}}
{"event": "project_reindexed", "project": "seq-feats", "data": null}
{"event": "file_changed", "project": "seq-feats", "path": "doc/questions/q01.md", "data": null}
```

Events: `entity_updated`, `entity_created`, `entity_deleted`, `project_reindexed`, `file_changed`. The `data` field carries the updated entity when available; `null` signals the frontend should refetch.

**Error responses:**

```json
{"error": "not_found", "detail": "Entity hypothesis:h99 not found in project seq-feats"}
{"error": "validation_error", "detail": "Task title is required"}
```

Standard HTTP status codes: 404 (not found), 422 (validation), 500 (internal). Task/entity writes return the updated entity for optimistic frontend updates.

### Frontend routes

```
/                              # home — three-view switcher (projects / entities / activity)
/projects/{slug}               # project dashboard (focused 3-4 items)
/projects/{slug}/graph         # full KG explorer (2D/3D toggle, LoD slider, lenses)
/projects/{slug}/hypotheses    # project hypotheses list
/projects/{slug}/questions     # project questions list
/projects/{slug}/tasks         # project tasks list
/entities/{id}                 # entity detail (cross-project view)
/search?q=...                  # search results
```

## Frontend Architecture

### Layout

Minimal chrome — narrow top bar with project name/breadcrumbs, search (`/`), and lens indicator. Main content area takes full remaining space. No sidebar — keyboard-driven navigation.

### Keyboard navigation

| Key | Action |
|-----|--------|
| `p` | Switch to projects view |
| `e` | Switch to entities view |
| `q` | Switch to questions view |
| `t` | Switch to tasks view |
| `h` | Switch to hypotheses view |
| `/` | Focus search |
| `g` | Open graph explorer (or expand minimap) |
| `,d` | Domain lens (color by ontology domain) |
| `,a` | Activity lens (color by recency/frequency) |
| `,s` | Status lens (color by status) |
| `,u` | Uncertainty lens (color by confidence/evidence coverage) |
| `2` / `3` | Toggle 2D / 3D graph |
| `Esc` | Back / close overlay |
| `j` / `k` | Navigate lists |
| `Enter` | Open selected item |

Single-key shortcuts are only active when no text input has focus. When a text field, command palette, or modal is focused, shortcuts are suppressed.

### Home page (`/`)

Three peer views of the same data, switchable via keyboard:

1. **Projects view** (`p`) — Each project as a card showing its top items; cross-project entities highlighted.
2. **Entities view** (`e`) — Flat view of all hypotheses, questions, tasks across projects, grouped by type, with project as a tag/filter.
3. **Activity view** — Timeline of what's happening across all projects, most recent first, filterable by project/type.

### Project dashboard (`/projects/{slug}`)

Focused, no-scroll layout with 3–4 cards:

1. **Hypotheses** — Top 3 by activity, showing status badge + one-line statement.
2. **Open questions** — Top 3 by priority/staleness.
3. **Active tasks** — Top 3, blockers highlighted.
4. **KG minimap** — Small force-directed graph, clickable to expand to full explorer.

Each card has a "see all" link to the full list view.

## Knowledge Graph Explorer

### Rendering

- **2D:** `react-force-graph-2d` — canvas-based, custom node painting via `nodeCanvasObject`.
- **3D:** `react-force-graph-3d` — Three.js/WebGL, custom geometries via `nodeThreeObject`.

### Visual encoding

**Shape = entity type:**

| Type | 2D Shape | 3D Geometry | Notes |
|------|----------|-------------|-------|
| Concept | Circle | Sphere | Generic, most common |
| Hypothesis | Triangle | Tetrahedron | Directional claim |
| Question | Diamond | Octahedron | Open/unresolved |
| Paper | Square | Box | External reference |
| Claim | Hexagon | Dodecahedron | Factual assertion |
| Inquiry | Star | Icosahedron | Active investigation |
| Topic | Rounded rect | Rounded box | Background/context |
| Interpretation | Down-triangle | Inverted tetrahedron | Results analysis |
| Discussion | Speech bubble | Hemisphere | Critical evaluation |
| Model | Gear/cog | TorusKnot | Mathematical model (natural-systems-guide has 247) |
| Pre-registration | Checkmark | Prism | Expectation formalization |
| Plan | Arrow-right | Wedge | Implementation plan |
| Assumption | Pentagon | Cone | Inquiry assumption |
| Transformation | Chevron | Torus | Computation step |
| Variable | Small circle | Small sphere | Causal/inquiry variable |
| Dataset | Cylinder | Cylinder | Data source |
| Method | Wrench | Capsule | Analytical method |
| Task | Rounded rect (dashed) | Rounded box (wireframe) | Actionable item (not in KG) |
| *(unknown)* | Circle (dashed) | Sphere (wireframe) | Fallback for unrecognized types |

Note: Tasks are not graph entities — they live in `tasks/active.md` and are rendered in the dashboard but not as KG nodes. They appear in the entity views and project dashboard but not in the graph explorer unless explicitly linked to graph entities via `related:` fields.

**Color = domain:** Assigned from user-selected palette. Top ~12 domains by frequency get stable colors; remainder get neutral gray.

**Size = importance score:** Degree + recency blend (see LoD section).

**Edges:** Color = relation type (supports, disputes, feedsInto, causes, confounds, etc.). Dashes = provenance-layer or low-confidence edges. Thickness is uniform by default (no weight data in RDF source); could later encode predicate frequency or computed importance.

### 3D-specific channels (experimental)

- **Material:** Solid vs wireframe (confidence/evidence strength).
- **Opacity:** Full vs translucent (priority/status).
- **Emissive glow:** Activity recency.
- **Texture/pattern:** Available for future encoding needs.

### Lenses

Lenses remap the color channel orthogonally to view:

- **Domain** (default): Color = ontology domain.
- **Activity**: Heatmap from cold (stale) to hot (recent).
- **Status**: Green = resolved, yellow = active, red = blocked, gray = proposed.
- **Uncertainty**: High confidence = solid color, low = faded/desaturated.

Shape and size remain constant across lenses — only color changes.

### Interaction

- **Click node** — Side panel: entity detail, related entities, cross-project references, contextual actions.
- **Right-click node** — Context menu: "Create task about this", "View in project", "Find across projects".
- **Hover** — Tooltip: label, type, domain, last updated.

### Graph layers and inquiry subgraphs

The RDF graph contains multiple named graphs (layers) with distinct semantics:

- **`graph/knowledge`** — entities, types, labels, definitions, citation relations
- **`graph/causal`** — causal relationships (`scic:causes`, `scic:confounds`), causal variables (`scic:Variable`), observability flags
- **`graph/provenance`** — source attribution (`prov:wasDerivedFrom`), confidence scores
- **`graph/datasets`** — dataset references and coverage
- **`inquiry/{slug}`** — each inquiry gets its own named graph with boundary nodes, flow edges, assumptions, unknowns, transformations

The graph explorer should allow filtering by layer (toggle layers on/off) and visually distinguish them. Causal edges could use directed arrows with special styling; provenance edges could be thin/dashed; inquiry subgraphs could be highlighted as clusters.

When viewing an inquiry, the explorer can render its subgraph with boundary nodes (inputs/outputs) pinned to the edges and interior nodes laid out between them — making the data flow structure visible.

### Pluggable layout strategy

Force-directed as default. The layout engine is an interface with slots for future alternatives: TDA (mapper, persistent homology skeletons), spectral embeddings, hypergraph layouts, categorical perspectives.

## Level-of-Detail (LoD) Subgraph Computation

### Importance scoring (per node)

Each entity gets a composite score:

- **Degree** — Number of edges (normalized within project).
- **Recency** — Exponential decay from `updated` date, half-life ~14 days.
- **Status weight** — Active/in-progress entities scored higher than resolved/deferred.
- **Evidence density** — For hypotheses/claims: ratio of supporting/disputing evidence links.

Default weights: `0.4 * degree + 0.3 * recency + 0.2 * status + 0.1 * evidence_density`. Configurable.

### Subgraph extraction for LoD value `t`

1. Sort nodes by importance score descending.
2. Select top `ceil(t * N)` nodes (N = total). At `t=0.1`, ~10% shown; at `t=1.0`, all.
3. Include all edges between selected nodes.
4. **Bridge rule:** If removing a node would disconnect two selected components, include it (preserves graph connectivity).
5. Return node list + edge list + metadata.

Importance scores computed at index time and cached. Subgraph extraction is a threshold + connectivity check — no precomputation needed.

The scoring function is pluggable — future slot for TDA-based importance (persistence), spectral centrality, or hypergraph-aware scoring.

## Domain Color System

### Color assignment pipeline

1. At index time, extract domain terms: `ontology_terms` from frontmatter, `rdf:type` from graph, `tags` from documents.
2. Select top ~12 domains by term frequency across all projects (simple count + rank, not ML clustering).
3. Assign each domain a color from the selected palette. Mapping stored in config for stability across sessions.
4. Entities with no domain get neutral color.

### Palette system

Ship with built-in palettes: `onedark`, `catppuccin`, `dracula`, `solarized`, `nord`. User selects in config. Palette defines ~12 assignable colors + background/foreground/neutral. Domain-to-color mapping regenerated on palette change; domain ordering stays stable.

### Consistency rule

Wherever a domain appears — graph nodes, entity list badges, breadcrumb accents, card borders, search result tags — it uses the same color.

## Shared Data Model (`science-model`)

The data models below are the canonical representations of science entities. To prevent drift between `science` (CLI plugin) and `science-web` (dashboard), these models live in a shared package: **`science-model`**.

**Package structure:**
- `science-model/` — lightweight Python package (Pydantic models only, no business logic)
- Contains: entity models, graph models, task models, config models, type enums
- No dependencies beyond `pydantic` and standard library
- Both `science-tool` and `science-web` depend on `science-model`

**Migration path:** Currently `science-tool` has its own `Task` dataclass and implicit entity schemas (frontmatter conventions + graph store types). The first implementation step extracts these into `science-model` as Pydantic models, then `science-tool` imports from the shared package. This is a refactor of `science-tool`, not a rewrite — the dataclass in `tasks.py` becomes a re-export of the shared model, and the implicit frontmatter field expectations become explicit model definitions.

**Package location options:**
- **A) Subdirectory of `science`** — `science-model/` as a sibling to `science-tool/` in the same repo. Simplest to develop; both packages evolve together.
- **B) Separate repo** — Full independence but more coordination overhead.

Recommendation: **A** — keep it in the `science` repo for now. Extract to its own repo only if a third consumer appears.

## Data Models

Core Pydantic models that define the API contract. These live in `science-model` and are imported by both `science-tool` and `science-web`.

```python
class Project(BaseModel):
    slug: str                          # directory basename
    name: str                          # from science.yaml `name:` field (falls back to slug)
    path: Path                         # absolute path on disk
    summary: str | None                # from science.yaml `summary:`
    status: str | None                 # from science.yaml `status:` (e.g. "active")
    aspects: list[str]                 # e.g. ["hypothesis-testing", "causal-modeling"]
    tags: list[str]                    # from science.yaml `tags:`
    entity_counts: dict[str, int]      # {"hypothesis": 4, "question": 13, ...}
    created: date | None               # from science.yaml `created:`
    last_modified: date | None         # from science.yaml `last_modified:`
    last_activity: datetime | None     # most recent mtime across all project files
    staleness_days: int | None         # days since last_activity

class ProjectDetail(Project):
    hypotheses: list[Entity]           # top N by activity
    questions: list[Entity]            # top N by priority/staleness
    tasks: list[Task]                  # top N active
    graph_summary: GraphSummary        # node/edge counts, top domains

class Entity(BaseModel):
    id: str                            # "type:slug" e.g. "hypothesis:h01-attention"
    type: str                          # hypothesis, question, concept, paper, topic, interpretation, ...
    title: str
    status: str | None                 # proposed, active, supported, resolved, ...
    project: str                       # project slug (computed, not from frontmatter)
    domain: str | None                 # computed from ontology_terms/tags for coloring
    tags: list[str]
    ontology_terms: list[str]          # CURIEs e.g. ["MONDO:0016419", "GO:0006915"]
    created: date | None
    updated: date | None
    related: list[str]                 # IDs of related entities (from frontmatter + body-text refs)
    source_refs: list[str]
    content_preview: str               # first ~200 chars of body (computed at index time)
    # Type-specific fields (populated when applicable)
    maturity: str | None               # questions: open, partially-resolved, resolved
    confidence: float | None           # claims: 0-1
    datasets: list[str] | None         # associated dataset names
    file_path: str                     # relative path within project (for linking/editing)

class Task(BaseModel):
    id: str                            # e.g. "t001"
    project: str                       # project slug (computed)
    title: str
    description: str                   # task body text
    type: str                          # research, analysis, writing, ... (required in code, defaults to "")
    priority: str                      # P0, P1, P2, P3
    status: str                        # proposed, active, done, deferred, blocked
    blocked_by: list[str]
    related: list[str]
    created: date                      # always set by add_task (date.today())
    completed: date | None

class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    domains: dict[str, str]            # domain -> color hex
    lod: float                         # requested LoD level
    total_nodes: int                   # total before LoD filtering

class GraphNode(BaseModel):
    id: str                            # entity URI (e.g. "http://example.org/project/concept/foo")
    label: str                         # from skos:prefLabel
    type: str                          # entity type (for shape): Concept, Hypothesis, ...
    domain: str | None                 # computed from ontology_terms/tags (for color)
    importance: float                  # 0-1 composite score
    status: str | None                 # from sci:projectStatus
    maturity: str | None               # questions only: open, partially-resolved, resolved
    confidence: float | None           # claims only: 0-1
    updated: date | None
    graph_layer: str                   # which named graph: knowledge, causal, inquiry/{slug}
    inquiry: str | None                # if node belongs to an inquiry subgraph
    boundary_role: str | None          # for inquiry nodes: "in", "out", or null

class GraphEdge(BaseModel):
    source: str                        # node ID
    target: str                        # node ID
    predicate: str                     # e.g. "cito:supports", "sci:feedsInto", "scic:causes"
    graph_layer: str                   # knowledge, causal, provenance, inquiry/{slug}
    provenance: str | None             # prov:wasDerivedFrom source document, if available

class GraphSummary(BaseModel):
    node_count: int
    edge_count: int
    top_domains: list[str]             # top 5 domains by node count

class ActivityItem(BaseModel):
    project: str
    entity_id: str | None              # null for raw file changes
    entity_type: str | None
    title: str
    action: str                        # created, updated, status_changed
    timestamp: datetime
    detail: str | None                 # e.g. "status: proposed → supported"

class SearchResult(BaseModel):
    entity: Entity
    score: float
    highlights: list[str]              # matching text snippets

class DashboardConfig(BaseModel):
    projects: list[str]                # project root paths
    palette: str                       # e.g. "onedark"
    domain_colors: dict[str, str]      # domain -> color hex (auto-generated, user-overridable)
    lod_weights: LodWeights
    sqlite_path: str | None            # null = in-memory

class LodWeights(BaseModel):
    degree: float = 0.4
    recency: float = 0.3
    status: float = 0.2
    evidence_density: float = 0.1

# --- Input models (for mutations) ---

class TaskCreate(BaseModel):
    title: str
    type: str | None = None            # research, analysis, writing, ...
    priority: str = "P2"
    related: list[str] = []
    blocked_by: list[str] = []
    description: str = ""

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    status: str | None = None          # proposed, active, done, deferred, blocked
    type: str | None = None
    related: list[str] | None = None
    blocked_by: list[str] | None = None

class EntityUpdate(BaseModel):
    status: str | None = None
    tags: list[str] | None = None

class ConfigUpdate(BaseModel):
    projects: list[str] | None = None
    palette: str | None = None
    domain_colors: dict[str, str] | None = None
    lod_weights: LodWeights | None = None
    sqlite_path: str | None = None

class Filters(BaseModel):
    project: str | None = None
    entity_type: str | None = None
    status: str | None = None
    domain: str | None = None
    tags: list[str] | None = None
```

**Entity write-back note:** Task mutations map directly to `science_tool.tasks` functions (`add_task`, `edit_task`, `complete_task`, etc.). General entity updates (e.g., changing hypothesis status) require editing YAML frontmatter in the entity's markdown file — the dashboard handles this directly since the format is well-defined. There is no unified `update_entity` in science-tool today; if this becomes a common pattern, we can extract one into science-tool later.

## Config File

Located at `~/.config/science-dashboard/config.yaml`:

```yaml
projects:
  - ~/d/seq-feats
  - ~/d/mindful/natural-systems-guide
  - ~/d/3d-attention-bias

palette: onedark

# Optional overrides (auto-generated if absent)
domain_colors:
  molecular-biology: "#e06c75"
  computational-methods: "#61afef"
  statistics: "#c678dd"

lod_weights:
  degree: 0.4
  recency: 0.3
  status: 0.2
  evidence_density: 0.1

# null = in-memory (default), or path for persistent index
sqlite_path: null
```

## Tech Stack

### Backend

- Python 3.12+, managed with `uv`
- FastAPI + uvicorn
- `science-tool` as dependency
- `rdflib` for TriG parsing
- `watchfiles` for filesystem monitoring
- `aiosqlite` for index + FTS
- WebSocket via FastAPI built-in

### Frontend

- React 19 + TypeScript
- Vite for bundling/dev
- `react-force-graph-2d` / `react-force-graph-3d`
- `react-router` for routing
- `zustand` for state management
- Tailwind CSS
- `cmdk` or similar for command palette

### Project layout

```
science-dashboard/
├── pyproject.toml
├── config.example.yaml
├── backend/
│   ├── app.py                  # FastAPI entry
│   ├── config.py               # config loader
│   ├── index.py                # indexer
│   ├── watcher.py              # file watcher
│   ├── store.py                # DataStore protocol + impl
│   ├── graph.py                # graph queries, LoD computation
│   ├── routes/
│   │   ├── projects.py
│   │   ├── entities.py
│   │   ├── tasks.py
│   │   ├── search.py
│   │   └── ws.py
│   └── models.py               # pydantic models
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── routes/
│   │   ├── components/
│   │   │   ├── GraphExplorer/
│   │   │   ├── Dashboard/
│   │   │   ├── EntityDetail/
│   │   │   └── CommandBar/
│   │   ├── stores/
│   │   ├── hooks/
│   │   ├── themes/
│   │   └── types/
│   └── index.html
├── docker-compose.yaml         # optional containerized deploy
└── Makefile                    # dev commands
```

### Dev workflow

- `make dev` starts FastAPI (hot reload) + Vite dev server (HMR) concurrently.
- Vite proxies `/api` to FastAPI during dev.
- Production: Vite builds static assets, FastAPI serves them + API.

## Quality Monitoring

The dashboard can surface project health signals by integrating `science_tool.refs.check_refs()`:

- **Broken references** — Hypothesis IDs (H01, H02) that don't match any file in `specs/hypotheses/`, citation keys that aren't in `references.bib`, markdown links to nonexistent files.
- **Unresolved markers** — `[UNVERIFIED]` and `[NEEDS CITATION]` flags in documents indicate incomplete work.
- **Stale entities** — Hypotheses or questions that haven't been updated in >30 days while still in active status.
- **Orphaned entities** — Graph nodes with zero edges (isolated concepts that were added but never connected).

These can be shown as a small quality indicator on the project dashboard card and expanded into a full quality report view.

## Design Decisions & Future Slots

| Decision | Rationale | Future alternative |
|----------|-----------|-------------------|
| SQLite index | Fast, zero-infra, sufficient for 100s of entities | Triplestore (Oxigraph/Fuseki) for SPARQL |
| Filesystem as source of truth | Consistency with CLI, version-controlled | Bidirectional sync with triplestore |
| Force-directed default layout | Works well at 10s–100s nodes, familiar | TDA, spectral, hypergraph layouts |
| Composite importance score | Simple, interpretable, configurable | Persistence-based (TDA), learned scoring |
| Single-user, no auth | Localhost app, matches current workflow | Auth layer for team access |
| `science_tool` direct import | Zero re-implementation of data logic | API-based if science-tool becomes a service |

## Non-Goals (v1)

- Multi-user / authentication
- Cloud deployment
- Real-time collaboration
- Full SPARQL query interface
- Automated analysis triggering from the dashboard
- Mobile support
