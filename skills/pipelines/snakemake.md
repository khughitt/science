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
5. Document each rule using the framework `pipeline-step.md` template (or a project override in `.ai/templates/`)
