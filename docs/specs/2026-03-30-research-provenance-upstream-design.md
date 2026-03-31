# Research Provenance: Upstream to Science Framework

**Date**: 2026-03-30
**Status**: Draft (rev 2)
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
| Provenance target | `data-package` → `workflow-run` (not `workflow`) | Package is the product of a specific execution, not an abstract definition |
| Reuse over invention | No `analysis` entity — reuse `workflow-step` | Avoids semantic overlap with existing core kinds |

---

## 1. Semantic Boundaries

The core profile already defines several entity kinds related to workflows and research processes. This section clarifies how each one fits and what the new additions cover.

| Entity kind | What it represents | Lifecycle | Example |
|-------------|-------------------|-----------|---------|
| `method` | An abstract methodology or approach | Authored once, referenced by workflows | "CKA convergence validation" |
| `workflow` | A reusable, versioned workflow definition | Authored, evolves over time | The Snakefile + config for theme validation |
| `workflow-step` | A discrete step within a workflow | Part of a workflow definition | "compute kappa scores" (wraps `per-theme-kappa.ts`) |
| `workflow-run` | A concrete execution of a workflow | Created each time a workflow is run | "theme-validation run on 2026-03-30 at commit abc123" |
| `experiment` | An investigative activity that tests a hypothesis | Created per investigation | "Test whether structural capabilities predict theme membership" |
| `data-package` | **NEW.** A Frictionless research package containing results, prose, and provenance | Produced by a workflow-run, committed as artifact | `research/packages/theme/instability-bifurcation/` |
| `artifact` | **NEW.** A downstream consumer of a data package | Derived from a data-package | A web page at `/guide/theme/instability-bifurcation/src` |

### Key distinctions

- **`workflow` vs `workflow-run`**: A workflow is the Snakefile; a workflow-run is a specific invocation that produced specific outputs. The data package attaches to the run, not the definition.
- **`workflow-step` vs `experiment`**: A workflow-step is a mechanical computation (run this script); an experiment is an investigative activity (test this hypothesis). A workflow can realize an experiment, but they are different concerns.
- **`workflow-step`**: Carries a `script_path` property identifying the script or tool it wraps. This is metadata on the entity, not a graph relation.

### How they connect (existing + new relations)

```
method
  ^
  | realizes (workflow -> method)
  |
workflow
  |-- contains -> workflow-step [script_path: "scripts/per-theme-kappa.ts"]
  |-- contains -> workflow-step [script_path: "scripts/structural-capability-validation.ts"]
  ^
  | executes (workflow-run -> workflow)
  |
workflow-run [last_run, git_commit]
  |
  | produced_by (data-package -> workflow-run)  [NEW]
  v
data-package
  |
  | derived_from (artifact -> data-package)  [NEW]
  v
artifact [artifact_type: "web_route", target: "/guide/theme/..."]
```

---

## 2. Core Profile Extensions (science-model)

### New entity kinds (2)

Added to `CORE_PROFILE` in `science-model/src/science_model/profiles/core.py`:

| Name | Prefix | Layer | Description |
|------|--------|-------|-------------|
| `data-package` | `data-package` | `layer/core` | A Frictionless research package containing analysis results, prose, and provenance metadata |
| `artifact` | `artifact` | `layer/core` | A downstream consumer of research results (web page, figure, report section). Uses an open `artifact_type` property for subtype semantics |

These join the existing `workflow`, `workflow-run`, `workflow-step`.

### New relation kinds (2)

| Name | Predicate | Sources | Targets | Description |
|------|-----------|---------|---------|-------------|
| `derived_from` | `sci:derivedFrom` | `artifact` | `data-package` | An artifact is derived from a data package |
| `produced_by` | `sci:producedBy` | `data-package` | `workflow-run` | A data package was produced by a specific workflow run |

### Entity type enum

Add to `EntityType` in `science-model/src/science_model/entities.py`:

```python
DATA_PACKAGE = "data-package"
ARTIFACT = "artifact"
```

### ID and naming conventions

All identifiers use hyphens consistently, matching existing core kinds (`workflow-run`, `workflow-step`):

| Aspect | Convention | Example |
|--------|-----------|---------|
| Entity kind name | `data-package` | As in `EntityKind(name="data-package", ...)` |
| Canonical prefix | `data-package` | As in `EntityKind(canonical_prefix="data-package", ...)` |
| EntityType enum | `DATA_PACKAGE = "data-package"` | Hyphenated string value |
| Graph URI | `data-package/{slug}` | `http://example.org/project/data-package/theme-instability-bifurcation` |
| PROJECT_ENTITY_PREFIXES | `"data-package"` | Hyphenated, matching prefix |
| Canonical ID in sources | `data-package:theme-instability-bifurcation` | Prefix + colon + slug |

Same convention applies to `artifact`:

| Aspect | Convention | Example |
|--------|-----------|---------|
| Entity kind name | `artifact` | |
| Canonical prefix | `artifact` | |
| Graph URI | `artifact/{slug}` | `http://example.org/project/artifact/guide-theme-instability-bifurcation` |
| Canonical ID | `artifact:guide-theme-instability-bifurcation` | |

---

## 3. Research Package Schema (science-model)

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
    path: str           # Path within package to the extracted excerpt file
    source: str          # Original source file path (relative to project root)
    lines: tuple[int, int]
    github_permalink: str = ""   # Empty when repo is not GitHub-hosted

class VegaLiteSpec(BaseModel):
    name: str
    path: str            # Path within package to the .vl.json file
    caption: str | None = None

class ProvenanceInput(BaseModel):
    path: str
    sha256: str

class Provenance(BaseModel):
    workflow: str        # Path to Snakefile (relative to project root)
    config: str          # Path to config.yaml
    last_run: str        # ISO 8601 timestamp
    git_commit: str      # Full commit SHA at time of run
    repository: str      # Repository URL (may be empty for non-hosted repos)
    inputs: list[ProvenanceInput]
    scripts: list[str]   # Paths to scripts used by the workflow

class ResearchExtension(BaseModel):
    target_route: str | None = None       # For web-app artifacts
    cells: str                             # Path to cells.json within the package
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
    content: str                  # File path within the package (e.g., "prose/01-intro.md")

class DataTableCell(BaseModel):
    type: Literal["data-table"]
    resource: str                 # Must match a name in resources[]
    columns: list[str] | None = None
    caption: str | None = None

class FigureCell(BaseModel):
    type: Literal["figure"]
    ref: str                      # Must match a name in figures[]

class VegaLiteCell(BaseModel):
    type: Literal["vegalite"]
    ref: str                      # Must match a name in vegalite_specs[]
    caption: str | None = None

class CodeReferenceCell(BaseModel):
    type: Literal["code-reference"]
    excerpt: str                  # Must match a name in code_excerpts[]
    description: str | None = None

class ProvenanceCell(BaseModel):
    type: Literal["provenance"]

Cell = NarrativeCell | DataTableCell | FigureCell | VegaLiteCell | CodeReferenceCell | ProvenanceCell
```

All `str` fields on cells that reference package contents are **file paths relative to the package root**, not inline content. The validation function verifies that every path resolves to an existing file.

### Validation (`validation.py`)

```python
def validate_package(package_dir: Path) -> ValidationResult:
    """Validate a research package directory.

    Checks:
    - datapackage.json exists and conforms to ResearchPackageDescriptor
    - cells.json exists and all cells conform to Cell union
    - All resource paths resolve to existing files
    - All figure paths resolve
    - All vegalite spec paths resolve
    - All code excerpt paths resolve
    - All narrative content paths (cell.content) resolve
    - All cell cross-references match declarations:
      - data-table.resource matches a name in resources[]
      - figure.ref matches a name in figures[]
      - vegalite.ref matches a name in vegalite_specs[]
      - code-reference.excerpt matches a name in code_excerpts[]
    """

def check_freshness(package_dir: Path, project_root: Path) -> ValidationResult:
    """Check provenance input freshness.

    Computes SHA-256 of each provenance input file and compares to the
    stored hash in provenance.inputs[].sha256. Returns warnings for
    mismatches (input has changed since last workflow run).
    """

@dataclass
class ValidationResult:
    """Structured validation output, serializable to JSON."""
    package_dir: str
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "package_dir": self.package_dir,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
        }
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
from .validation import validate_package, check_freshness, ValidationResult
```

---

## 4. science-tool Commands

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
- `cells.json` with empty array `[]`
- `data/`, `figures/`, `prose/`, `excerpts/` directories
- If `--workflow` provided, reads `config.yaml` to pre-fill provenance inputs and scripts

#### `validate`

```
science-tool research-package validate <package-dir-or-parent> [--check-freshness] [--project-root PATH] [--json]
```

Runs `validate_package()` from science-model. If given a parent directory, validates all packages found recursively (any directory containing `datapackage.json` with `profile: "science-research-package"`).

- `--check-freshness` also runs `check_freshness()` (requires `--project-root`)
- `--json` outputs `ValidationResult.to_dict()` as JSON (one object per package, or array for recursive)
- Exits with code 0 if all packages are valid, code 1 if any errors

Default (non-JSON) output follows the existing science-tool CLI style:

```
✓ research/packages/theme/instability-bifurcation (6 resources, 7 cells)
⚠ research/packages/theme/transport-diffusion: input "src/registry/foo.ts" has changed
✗ research/packages/theme/broken: missing resource file "data/scores.csv"
```

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
7. Generates commit-pinned GitHub permalinks via `git rev-parse HEAD` (skipped gracefully if not in a Git repo or if no `repository` is configured)
8. Writes `datapackage.json`
9. Copies `cells.json` from the workflow directory
10. Runs `validate` on the assembled package

---

## 5. Source-of-Truth and Materialization

### How research provenance enters the knowledge graph

The science framework materializes the knowledge graph deterministically from authored source files via `load_project_sources()` → `materialize_graph()`. Research provenance entities follow this same path.

### Authored sources

Research packages (`research/packages/{name}/datapackage.json`) are the primary authored source. They are committed artifacts produced by `science-tool research-package build`.

### Export to canonical source files

A project's KG export script (e.g., `scripts/export_kg_model_sources.py` in natural-systems) reads the committed packages and workflow configs and generates YAML source files:

```
knowledge/sources/project_specific/
  data-packages.yaml      # One entry per data-package entity
  artifacts.yaml           # One entry per artifact entity
  workflows.yaml           # One entry per workflow entity (already supported)
```

Each YAML file follows the existing source format used by `load_project_sources()`:

```yaml
{
  "data_packages": [
    {
      "canonical_id": "data-package:theme-instability-bifurcation",
      "title": "Instability & Bifurcation Theme — Research Provenance",
      "profile": "project_specific",
      "source_path": "knowledge/sources/project_specific/data-packages.yaml",
      "relations": [
        {
          "predicate": "sci:producedBy",
          "target": "workflow-run:theme-validation-2026-03-30"
        }
      ]
    }
  ]
}
```

### Materialization path

```
research/packages/*/datapackage.json   (committed authored source)
  → export script generates YAML source files
    → science-tool graph build reads sources via load_project_sources()
      → materialize_graph() emits triples into graph.trig
```

This is the architectural path. The `add_*` store functions described below exist as convenience for interactive use (e.g., `science-tool graph add data-package ...` from the CLI) but are not the primary materialization mechanism.

### Graph store convenience functions

For interactive CLI use, add to `store.py`:

#### `add_data_package`

```python
def add_data_package(
    graph_path: Path,
    package_id: str,
    title: str,
    *,
    produced_by: str | None = None,  # workflow-run canonical ID
) -> None:
```

Creates `data-package/{package_id}` entity with `skos:prefLabel`, `schema:identifier`, optional `sci:producedBy` edge.

#### `add_artifact`

```python
def add_artifact(
    graph_path: Path,
    artifact_id: str,
    title: str,
    *,
    artifact_type: str,
    target: str | None = None,
    derived_from: str | None = None,  # data-package canonical ID
) -> None:
```

Creates `artifact/{artifact_id}` entity with `skos:prefLabel`, `sci:artifactType`, optional `sci:derivedFrom` edge.

### `PROJECT_ENTITY_PREFIXES`

Add to the set in `store.py`:

```python
"data-package",
"artifact",
```

---

## 6. Skills

### Update: `skills/pipelines/snakemake.md`

Add a new section on research package integration:
- Terminal rule pattern: `rule build_package` that calls `science-tool research-package build`
- Config structure for code excerpts, prose, provenance inputs
- Link to the research provenance skill for full schema documentation
- Example `onsuccess` handler as alternative to a terminal rule
- Note that `workflow-step` entities should carry a `script_path` property for traceability

### New: `skills/research/provenance.md` (Layer 1)

Contents:
- What is a research package and why use one
- Package directory structure and schema reference
- Cell types: narrative, data-table, figure, vegalite, code-reference, provenance
- Workflow integration: producing packages from Snakemake
- CLI commands: `init`, `validate`, `build`
- KG integration: `data-package`, `artifact` entity types, `workflow-run` linkage, and their relationships
- Semantic boundaries: how data-package relates to workflow, workflow-run, workflow-step, method, experiment
- Provenance model: input hashing, git commit pinning, freshness checking
- Non-GitHub repos: `github_permalink` and `repository` fields may be empty; code excerpts still work as embedded files
- Altair/Vega-Lite: producing `.vl.json` specs from Python analysis scripts

### New: `skills/research/lab-notebook.md` (Layer 2)

Contents:
- What is a lab notebook view (rendering packages as notebook-like web pages)
- Cell rendering: mapping each cell type to a web component
  - `narrative` → markdown renderer (content field is a file path, fetch and render)
  - `data-table` → sortable/filterable table
  - `figure` → image with caption
  - `vegalite` → Vega-Lite embed with `vega-embed` library
  - `code-reference` → collapsible code block with GitHub permalink (graceful fallback when no permalink)
  - `provenance` → metadata summary
- Routing pattern: sub-routes at `{path}/src`
- Manifest pattern: prebuild script that validates/copies packages and generates a route manifest
- ViewSourceButton pattern: conditional rendering based on manifest
- DataPackageLoader pattern: runtime fetching and validation
- Artifact entity: using `artifact_type: "web_route"` with `target` pointing to the route

---

## 7. natural-systems Migration

After the upstream changes land:

1. Update `datapackage.json` profile from `natural-systems-research-package` to `science-research-package`
2. Keep Zod schemas in `src/research/types.ts` for runtime validation in the TypeScript app, but align field names and types to the canonical Pydantic schema
3. Replace `generate-research-packages.ts` validation logic with calls to `science-tool research-package validate`
4. Replace `workflows/common/scripts/build_package.py` with `science-tool research-package build`
5. Update `scripts/export_kg_model_sources.py` to use canonical `data-package` prefix (not `data_package`) and link to `workflow-run` entities
6. Add `vegalite` cell type support to the React cell renderer (optional, when interactive charts are ready)

---

## 8. Scope

### In scope

1. science-model: 2 entity kinds + 2 relation kinds in core profile + `EntityType` enum additions
2. science-model: `packages/` module (schema, cells, validation with `ValidationResult`)
3. science-tool: `research-package` command group (`init`, `validate`, `build`)
4. science-tool: `add_data_package`, `add_artifact` graph store convenience functions
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
