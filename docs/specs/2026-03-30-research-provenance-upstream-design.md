# Research Provenance: Upstream to Science Framework

**Date**: 2026-03-30
**Status**: Draft
**Origin**: Validated in natural-systems project; now generalizing for all science projects

## Problem

Science projects produce research analyses that drive downstream artifacts — web pages, paper figures, reports — but there is no framework-level support for tracking the dependency chain from analysis to output, packaging results in a standardized format, or making the evidence chain transparent and reproducible.

The natural-systems project built a project-specific implementation: Snakemake workflows produce Frictionless data packages rendered as notebook-like "view source" pages in a web app. This design generalizes that implementation into the science framework so any project can adopt it.

## Architecture

Two-layer design:

1. **Reproducible workflow layer** (universal) — Entity types, data package schema, CLI commands, and skills for producing standardized research packages from Snakemake workflows.
2. **Lab notebook layer** (web-app projects) — Skills and patterns for rendering research packages as notebook-like views in web applications.

Schema definitions live in science-model. CLI commands live in science-tool. Skills provide guidance for both layers.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Layering | Layer 1 (reproducible workflow) + Layer 2 (lab notebook) | Separates universal concern from web-specific UI |
| Schema location | science-model (Pydantic), commands in science-tool | Matches existing architecture split |
| Profile placement | All new types in core profile | Universal research concepts; no opt-in needed |
| Artifact generalization | Minimal `artifact` type with open `artifact_type` string | Flexible for web routes, figures, reports, notebooks |
| Data package format | Frictionless with `science-research-package` profile | Extensible standard, validated in natural-systems |
| Interactive charts | Vega-Lite cell type alongside static figures | Declarative, portable, renders in any web context |

---

## 1. Core Profile Extensions (science-model)

### New entity kinds

Added to `CORE_PROFILE` in `science-model/src/science_model/profiles/core.py`:

| Name | Prefix | Layer | Description |
|------|--------|-------|-------------|
| `data-package` | `data_package` | `layer/core` | A Frictionless research package containing analysis results, prose, and provenance metadata |
| `analysis` | `analysis` | `layer/core` | A discrete analysis step — a script or computation that produces results |
| `artifact` | `artifact` | `layer/core` | A downstream consumer of research results (web page, figure, report section, notebook). Uses an open `artifact_type` string field for subtype semantics |

These join the existing `workflow`, `workflow-run`, `workflow-step`.

### New relation kinds

Added to `CORE_PROFILE` in the same file:

| Name | Predicate | Sources | Targets | Description |
|------|-----------|---------|---------|-------------|
| `derived_from` | `sci:derivedFrom` | `artifact` | `data-package` | An artifact is derived from a data package |
| `produced_by` | `sci:producedBy` | `data-package` | `workflow` | A data package is produced by a workflow |
| `has_step` | `sci:hasStep` | `workflow` | `analysis` | A workflow contains analysis steps |
| `implements` | `sci:implements` | `analysis` | (any) | An analysis step implements a specific script or method |

### Entity type enum

Add to `EntityType` in `science-model/src/science_model/entities.py`:

```python
DATA_PACKAGE = "data-package"
ANALYSIS = "analysis"
ARTIFACT = "artifact"
```

---

## 2. Research Package Schema (science-model)

New module at `science-model/src/science_model/packages/`.

### Module structure

```
science_model/packages/
  __init__.py              # Re-exports schemas and validation
  schema.py                # Pydantic models for package descriptor
  cells.py                 # Pydantic models for cell definitions
  validation.py            # Package validation logic
```

### Package descriptor (`schema.py`)

```python
class ResourceSchema(BaseModel):
    name: str
    path: str
    schema_: dict[str, Any] | None = Field(None, alias="schema")

class FigureRef(BaseModel):
    name: str
    path: str
    caption: str

class CodeExcerpt(BaseModel):
    name: str
    path: str
    source: str
    lines: tuple[int, int]
    github_permalink: str

class VegaLiteSpec(BaseModel):
    name: str
    path: str
    caption: str | None = None

class ProvenanceInput(BaseModel):
    path: str
    sha256: str

class Provenance(BaseModel):
    workflow: str
    config: str
    last_run: str
    git_commit: str
    repository: str
    inputs: list[ProvenanceInput]
    scripts: list[str]

class ResearchExtension(BaseModel):
    target_route: str | None = None
    cells: str
    figures: list[FigureRef] = []
    vegalite_specs: list[VegaLiteSpec] = []
    code_excerpts: list[CodeExcerpt] = []
    provenance: Provenance

class ResearchPackageDescriptor(BaseModel):
    name: str
    title: str
    profile: Literal["science-research-package"]
    version: str
    resources: list[ResourceSchema]
    research: ResearchExtension
```

### Cell schema (`cells.py`)

```python
class NarrativeCell(BaseModel):
    type: Literal["narrative"]
    content: str

class DataTableCell(BaseModel):
    type: Literal["data-table"]
    resource: str
    columns: list[str] | None = None
    caption: str | None = None

class FigureCell(BaseModel):
    type: Literal["figure"]
    ref: str

class VegaLiteCell(BaseModel):
    type: Literal["vegalite"]
    ref: str
    caption: str | None = None

class CodeReferenceCell(BaseModel):
    type: Literal["code-reference"]
    excerpt: str
    description: str | None = None

class ProvenanceCell(BaseModel):
    type: Literal["provenance"]

Cell = NarrativeCell | DataTableCell | FigureCell | VegaLiteCell | CodeReferenceCell | ProvenanceCell
```

### Validation (`validation.py`)

```python
def validate_package(package_dir: Path) -> list[str]:
    """Validate a research package directory.

    Returns a list of error strings. Empty list means valid.

    Checks:
    - datapackage.json exists and conforms to ResearchPackageDescriptor
    - cells.json exists and all cells conform to Cell union
    - All resource paths resolve to existing files
    - All figure paths resolve
    - All vegalite spec paths resolve
    - All code excerpt paths resolve
    - All narrative content paths resolve
    - All cell cross-references match declarations in datapackage.json
    """
```

```python
def check_freshness(package_dir: Path, project_root: Path) -> list[str]:
    """Check provenance input freshness.

    Returns a list of warning strings for stale inputs.
    Computes SHA-256 of each provenance input and compares to stored hash.
    """
```

### Re-exports (`__init__.py`)

```python
from .schema import (
    ResearchPackageDescriptor,
    ResearchExtension,
    Provenance,
    ProvenanceInput,
    FigureRef,
    CodeExcerpt,
    VegaLiteSpec,
    ResourceSchema,
)
from .cells import (
    Cell,
    NarrativeCell,
    DataTableCell,
    FigureCell,
    VegaLiteCell,
    CodeReferenceCell,
    ProvenanceCell,
)
from .validation import validate_package, check_freshness
```

---

## 3. science-tool Commands

### New command group: `research-package`

#### `init`

```
science-tool research-package init \
  --name <package-name> \
  --title <human-readable-title> \
  [--workflow <workflow-dir>] \
  --output <package-dir>
```

Scaffolds a package directory:
- `datapackage.json` pre-filled with profile `"science-research-package"`, name, title, provenance skeleton
- `cells.json` with empty array
- `data/`, `figures/`, `prose/`, `excerpts/` directories
- If `--workflow` provided, reads `config.yaml` to pre-fill provenance inputs and scripts

#### `validate`

```
science-tool research-package validate <package-dir-or-parent>
```

Runs `validate_package()` from science-model. If given a parent directory, validates all packages found recursively. Supports `--json` for machine-readable output. Supports `--check-freshness` with `--project-root` to also run `check_freshness()`. Exits non-zero on errors.

#### `build`

```
science-tool research-package build \
  --results <results-dir> \
  --config <workflow-config-yaml> \
  --output <package-dir>
```

Assembles a data package from workflow results:
1. Copies CSVs from `results/` to `data/`
2. Copies PNGs from `results/figures/` to `figures/`
3. Copies `.vl.json` from `results/figures/` to `figures/`
4. Copies prose from the workflow's prose directory
5. Extracts code excerpts per config (line ranges from source files)
6. Computes SHA-256 hashes of provenance inputs
7. Generates commit-pinned GitHub permalinks via `git rev-parse HEAD`
8. Writes `datapackage.json`
9. Copies `cells.json` from the workflow directory
10. Runs `validate` on the assembled package

---

## 4. Graph Store Extensions (science-tool)

### `PROJECT_ENTITY_PREFIXES`

Add to the set in `store.py`:

```python
"data_package",
"analysis",
"artifact",
```

### New `add_*` functions

#### `add_data_package`

```python
def add_data_package(
    graph_path: Path,
    package_id: str,           # e.g., "theme-instability-bifurcation"
    title: str,
    *,
    lens: str | None = None,
    section: str | None = None,
    produced_by: str | None = None,  # workflow canonical ID
) -> None:
```

Creates `data_package/{package_id}` entity with `skos:prefLabel`, `schema:identifier`, optional `sci:producedBy` edge to workflow.

#### `add_analysis`

```python
def add_analysis(
    graph_path: Path,
    analysis_id: str,          # e.g., "per-theme-kappa"
    title: str,
    *,
    script_path: str | None = None,
) -> None:
```

Creates `analysis/{analysis_id}` entity with `skos:prefLabel`, optional `sci:implements` edge.

#### `add_artifact`

```python
def add_artifact(
    graph_path: Path,
    artifact_id: str,          # e.g., "guide-theme-instability-bifurcation"
    title: str,
    *,
    artifact_type: str,        # e.g., "web_route", "figure", "report_section"
    target: str | None = None, # e.g., "/guide/theme/instability-bifurcation"
    derived_from: str | None = None,  # data_package canonical ID
) -> None:
```

Creates `artifact/{artifact_id}` entity with `skos:prefLabel`, `sci:artifactType`, optional `sci:derivedFrom` edge.

---

## 5. Skills

### Update: `skills/pipelines/snakemake.md`

Add a new section on research package integration:
- Terminal rule pattern: `rule build_package` that calls `science-tool research-package build`
- Config structure for code excerpts, prose, provenance inputs
- Link to the research provenance skill for full schema documentation
- Example `onsuccess` handler as alternative to a terminal rule

### New: `skills/research/provenance.md` (Layer 1)

Contents:
- What is a research package and why use one
- Package directory structure and schema reference
- Cell types: narrative, data-table, figure, vegalite, code-reference, provenance
- Workflow integration: producing packages from Snakemake
- CLI commands: `init`, `validate`, `build`
- KG integration: `data_package`, `analysis`, `artifact` entity types and their relationships
- Provenance model: input hashing, git commit pinning, freshness checking
- Altair/Vega-Lite: producing `.vl.json` specs from Python analysis scripts

### New: `skills/research/lab-notebook.md` (Layer 2)

Contents:
- What is a lab notebook view (rendering packages as notebook-like web pages)
- Cell rendering: mapping each cell type to a web component
  - `narrative` → markdown renderer
  - `data-table` → sortable/filterable table
  - `figure` → image with caption
  - `vegalite` → Vega-Lite embed with `vega-embed` library
  - `code-reference` → collapsible code block with GitHub permalink
  - `provenance` → metadata summary
- Routing pattern: sub-routes at `{path}/src`
- Manifest pattern: prebuild script that validates/copies packages and generates a route manifest
- ViewSourceButton pattern: conditional rendering based on manifest
- DataPackageLoader pattern: runtime fetching and validation
- Artifact entity: using `artifact_type: "web_route"` with `target` pointing to the route

---

## 6. natural-systems Migration

After the upstream changes land:

1. Update `datapackage.json` profile from `natural-systems-research-package` to `science-research-package`
2. Replace project-local Zod schemas (`src/research/types.ts`) with imports from science-model's JSON Schema export (or keep Zod for runtime validation in the TypeScript app, aligned to the canonical schema)
3. Replace `generate-research-packages.ts` validation logic with calls to `science-tool research-package validate`
4. Replace `workflows/common/scripts/build_package.py` with `science-tool research-package build`
5. Remove project-local entity type definitions from `scripts/export_kg_model_sources.py` (use the core profile types directly)
6. Add `vegalite` cell type support to the React cell renderer (optional, when interactive charts are ready)

---

## 7. Scope

### In scope

1. science-model: 3 entity kinds + 4 relation kinds in core profile + `EntityType` enum additions
2. science-model: `packages/` module (schema, cells, validation)
3. science-tool: `research-package` command group (`init`, `validate`, `build`)
4. science-tool: `add_data_package`, `add_analysis`, `add_artifact` graph store functions
5. science-tool: `PROJECT_ENTITY_PREFIXES` updates
6. skills: Update `pipelines/snakemake.md`
7. skills: New `research/provenance.md` (layer 1)
8. skills: New `research/lab-notebook.md` (layer 2)
9. natural-systems: Profile migration + tooling convergence

### Out of scope

- Automated Snakemake execution from science-tool
- Vega-Lite rendering implementation in any specific project
- CI/CD integration for package freshness
- `science-tool research-package publish` for cross-project sharing
- Shared Vega-Lite theme/styling

### Non-goals

- Replacing Snakemake as workflow engine
- Building a universal notebook runtime
- Runtime KG queries from web applications
