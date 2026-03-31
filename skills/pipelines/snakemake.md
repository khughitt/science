---
name: pipeline-snakemake
description: Snakemake workflow construction and best practices. Use when creating computational pipelines, writing Snakefiles, connecting data acquisition to analysis, or the user mentions Snakemake, pipelines, workflows, or reproducible analysis.
---

# Snakemake Pipelines

## When To Use

- Building a reproducible analysis pipeline
- Connecting data download -> preprocessing -> analysis -> output
- When a workflow has multiple steps with file dependencies
- When intermediate results should be cached and reusable

For interactive exploration, prefer marimo notebooks instead.

## Project Structure

```
code/workflows/
├── Snakefile           # Main workflow definition
├── config.yaml         # Parameters (linked to inquiry AnnotatedParams)
├── envs/               # Conda environment specs per rule
│   ├── preprocessing.yaml
│   └── analysis.yaml
├── rules/              # Modular rule files (for complex pipelines)
│   ├── download.smk
│   ├── preprocess.smk
│   └── analyze.smk
└── scripts/            # Scripts called by rules
    ├── preprocess.py
    └── analyze.py
```

## Writing a Snakefile

### Minimal template

```python
configfile: "config.yaml"

rule all:
    input:
        "data/processed/results.csv"

rule download:
    output:
        "data/raw/{accession}_data.csv"
    shell:
        """
        uv run science-tool datasets download \
            {config[source]}:{wildcards.accession} --dest data/raw/
        """

rule preprocess:
    input:
        "data/raw/{accession}_data.csv"
    output:
        "data/processed/{accession}_clean.csv"
    script:
        "scripts/preprocess.py"

rule analyze:
    input:
        expand("data/processed/{acc}_clean.csv", acc=config["accessions"])
    output:
        "data/processed/results.csv"
    script:
        "scripts/analyze.py"
```

### Config file

```yaml
# config.yaml — linked to inquiry parameters
source: geo
accessions:
  - GSE12345
  - GSE67890
parameters:
  normalization: "quantile"
  min_samples: 3
```

## Best Practices

### Rule naming
- Use verb phrases: `download_data`, `normalize_counts`, `fit_model`
- Prefix with step number for clarity: `s01_download`, `s02_normalize`

### Wildcards
- Use wildcards for sample/accession variation
- Keep wildcard names descriptive: `{sample}`, `{accession}`, `{gene}`
- Constrain wildcards when needed: `wildcard_constraints: sample="[A-Za-z0-9]+"`

### Input/output
- All paths relative to Snakefile location
- Raw data: `data/raw/`
- Processed data: `data/processed/`
- Results: `results/` or `data/processed/`
- Use `temp()` for large intermediate files that can be deleted
- Use `protected()` for expensive-to-compute outputs

### Scripts vs shell
- **Shell:** simple commands, tool invocations
- **Scripts:** anything needing Python logic (access `snakemake.input`, `snakemake.output`, `snakemake.params`)

### Environments
- One conda env YAML per distinct tool set
- Pin versions for reproducibility

## Running

```bash
# Dry run (show what would execute)
snakemake -n

# Run with N cores
snakemake --cores 4

# Run specific target
snakemake data/processed/results.csv

# Generate DAG visualization
snakemake --dag | dot -Tpng > dag.png
```

## Connecting to Science Workflow

1. **Data acquisition rules** call `science-tool datasets download`
2. **Config parameters** map to inquiry `AnnotatedParam` values
3. **Validation rules** call `science-tool datasets validate`
4. **Output** goes to `data/processed/` with its own `datapackage.json`
5. Document each rule using the framework `workflow-step.md` template (or a project override in `.ai/templates/`)

## Manifest Generation

Every workflow should produce a `datapackage.json` manifest in its output
directory. Use a Snakemake `onsuccess` handler or a dedicated final rule:

### Option A: onsuccess handler (recommended for simple workflows)

```python
onsuccess:
    from datetime import datetime
    from pathlib import Path
    import json

    manifest = {
        "name": config.get("analysis_slug", "unnamed"),
        "title": config.get("title", ""),
        "created": datetime.now().isoformat(),
        "resources": [],  # populated from rule outputs
        "workflow": {
            "name": workflow.basedir.name,
            "path": str(workflow.basedir),
        },
        "entities": config.get("entities", {}),
        "provenance": {"steps": [], "environment": {}},
    }

    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "datapackage.json").write_text(
        json.dumps(manifest, indent=2)
    )
```

### Option B: Final rule (for complex workflows)

```python
rule generate_manifest:
    input:
        # all terminal outputs from the workflow
    output:
        "results/{workflow}/{slug}/datapackage.json"
    run:
        # build manifest from snakemake DAG + config
```

### Resource Entries

Each output file becomes a resource entry:

```json
{
  "name": "descriptive-name",
  "path": "relative/path/from/analysis/dir",
  "format": "parquet",
  "mediatype": "application/vnd.apache.parquet",
  "description": "What this file contains"
}
```

For FASTA sequence files, add EDAM annotations:

```json
{
  "edam": {
    "data": "http://edamontology.org/data_2044",
    "format": "http://edamontology.org/format_1929"
  }
}
```

## Research Package Integration

Use `science-tool research-package build` as a terminal Snakemake rule to bundle
analysis results, narrative context, and execution provenance into a standardized
research package.

### Terminal rule

```python
rule build_package:
    input:
        results=directory("results")
    output:
        "research/packages/{lens}/{section}/datapackage.json"
    shell:
        "science-tool research-package build --results {input.results} --config config.yaml --output research/packages/{config[lens]}/{config[section]}/"
```

### Config structure for research packages

```yaml
# config.yaml
lens: theme          # top-level grouping (used in package path)
section: chaos       # section slug (used in package path)

prose_dir: prose/                  # directory of narrative .md files
cells_file: cells.json             # ordered cell sequence for rendering
provenance_inputs:                 # files tracked by SHA-256 for freshness
  - data/raw/dataset.csv
scripts:                           # scripts contributing to the analysis
  - scripts/analyze.py
code_excerpts:                     # extracted code snippets to embed
  - name: model-fit
    source: scripts/analyze.py
    lines: "10-45"
repository: "https://github.com/org/repo"  # empty string for non-GitHub repos
```

### Workflow-step traceability

`workflow-step` entities should carry a `script_path` property pointing to the
script file that implements the step. This enables downstream provenance tools to
generate accurate GitHub permalinks and cross-reference code excerpts.

```yaml
# In a workflow-step entity doc
script_path: code/workflows/scripts/analyze.py
```

For full schema documentation — including `cells.json` structure, cell types, and
the `science-research-package` datapackage profile — see the
`skills/research/provenance.md` skill.
