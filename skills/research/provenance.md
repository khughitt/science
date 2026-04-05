# Research Provenance

Research packages bundle analysis results, narrative context, and execution provenance into a standardized format. Any science project can produce and validate these packages.

## When to Use

- After a Snakemake workflow produces analysis outputs
- When packaging research results for transparency
- When connecting analysis outputs to the knowledge graph

## Package Structure

```
research/packages/{name}/
  datapackage.json          # Frictionless descriptor + research extension
  cells.json                # Ordered cell sequence for narrative rendering
  data/*.csv                # Tabular data resources
  figures/*.png             # Static figures
  figures/*.vl.json         # Vega-Lite interactive chart specs
  prose/*.md                # Narrative markdown files
  excerpts/*.ts|*.py        # Extracted code snippets
```

## Schema

The `datapackage.json` uses profile `"science-research-package"` with a `research` extension block containing:
- `cells`: path to cells.json
- `figures`: array of {name, path, caption}
- `vegalite_specs`: array of {name, path, caption?}
- `code_excerpts`: array of {name, path, source, lines, github_permalink}
- `provenance`: {workflow, config, last_run, git_commit, repository, inputs[], scripts[]}

Each provenance input has a `sha256` hash for freshness checking.

## Cell Types

| Type | Purpose | Key Fields |
|------|---------|------------|
| narrative | Markdown prose | content (file path) |
| data-table | Sortable table from CSV | resource, columns?, caption? |
| figure | Static image | ref (figure name) |
| vegalite | Interactive Vega-Lite chart | ref (spec name), caption? |
| code-reference | Collapsible code excerpt | excerpt (name), description? |
| provenance | Auto-rendered metadata | (reads from datapackage.json) |

## CLI Commands

### Initialize a package
```bash
science-tool research-package init --name <slug> --title <title> [--workflow <dir>] --output <dir>
```

### Validate packages
```bash
science-tool research-package validate <dir> [--check-freshness --project-root <root>] [--json]
```

### Build from workflow results
```bash
science-tool research-package build --results <dir> --config <yaml> --output <dir>
```

## Workflow Integration

Terminal Snakemake rule:

```python
rule build_package:
    input: results=directory("results")
    output: "research/packages/{lens}/{section}/datapackage.json"
    shell: "science-tool research-package build --results {input.results} --config config.yaml --output research/packages/{config[lens]}/{config[section]}/"
```

## Knowledge Graph Integration

New entity types in core profile:
- `data-package` (with `type: result`): produced by a `workflow-run`, contains analysis results
- `data-package` (with `type: downstream`): grounded by a source `data-package`, represents downstream consumers

Relations:
- `produced_by` (sci:producedBy): data-package → workflow-run
- `grounded_by` (sci:groundedBy): downstream data-package → source data-package

## Provenance Model

- Input files tracked via SHA-256 hashes
- Git commit pinned at build time
- GitHub permalinks generated when repository URL is configured (empty string for non-GitHub repos)
- Freshness checking: `science-tool research-package validate --check-freshness` compares stored hashes against current files

## Vega-Lite Support

Produce interactive charts from Python analysis scripts using Altair:

```python
import altair as alt
chart = alt.Chart(df).mark_bar().encode(x='theme', y='kappa')
chart.save("results/figures/kappa-by-theme.vl.json")
```

The `.vl.json` files are copied into the package's `figures/` directory and referenced via `vegalite` cells.
