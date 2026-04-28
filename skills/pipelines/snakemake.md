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
- Use `protected()` for expensive-to-compute outputs (with the caveat below)

### `protected()` does NOT prevent rerun-cleanup

`protected()` only sets file mode 444 *after a successful write* and only blocks
`--forceall`. It does **not** prevent snakemake's normal pre-rule cleanup, which
removes existing output files at the moment snakemake decides to re-run a rule
(for any reason: code/mtime/params change, fresh `out_dir` metadata, etc.). By
the time the rule body runs, the files are already gone — script-level
idempotency checks (`if Path(out).exists(): sys.exit(0)`) defend the wrong
window.

This is a real-world footgun for **network-fetch rules** (e.g., downloading
public datasets from URLs) whose source endpoints can fail, rate-limit, or
return 4xx errors. If the rule fails after cleanup but before re-acquiring
the data, the original on-disk copy is gone and may be hard or impossible to
recover.

**Pattern to avoid**:

```python
rule download_study:
    output:
        protected("/data/raw/{id}/data_mutations.txt"),
        protected("/data/raw/{id}/data_clinical_sample.txt"),
    script:
        "scripts/download_study.py"      # idempotency check inside is too late
```

A fresh `out_dir` for the workflow has no metadata for these outputs, so
snakemake decides to re-run; cleanup removes the existing files; the
download fails with HTTP 403; the original raw data is permanently lost.

**Pattern to use**: emit a per-`out_dir` *marker file* under the workflow's
own output tree. The marker is the only thing snakemake can clean up; the
script populates `data_dir/` as a side effect, with an explicit "skip if
already present" guard *inside the script*.

```python
rule stage_study_raw:
    output:
        out_dir / "metadata/raw_studies/{id}.staged"
    script:
        "scripts/stage_study_raw.py"

# scripts/stage_study_raw.py
study_dir = Path(data_dir) / wildcards.id
required = ["data_mutations.txt", "data_clinical_sample.txt"]

if all((study_dir / f).exists() for f in required):
    Path(snakemake.output[0]).write_text(f"{wildcards.id}\n")
    raise SystemExit(0)

download_and_extract(study_id, data_dir)   # the actual fetch
Path(snakemake.output[0]).write_text(f"{wildcards.id}\n")
```

Downstream rules consume the canonical raw paths from `data_dir/` directly
(unchanged); they additionally take the marker as an input dependency so
the staging rule runs first when needed. The marker is per-`out_dir`, so
switching to a fresh `out_dir` causes a no-op rerun (the staging script
short-circuits on existence) instead of a destructive re-download attempt.

The same pattern applies to any rule whose output points outside the
`out_dir` tree — shared filesystems, cloud-mounted volumes, vendor data
directories. Keep snakemake-managed outputs strictly inside the workflow's
own tree; if other tooling needs the data at a canonical location, treat
that location as a side effect of the rule body, not as the declared
output.

### Invocation discipline (failsafes for executing existing pipelines)

The patterns above (marker files, `protected()` caveats) target **workflow
authors**. They cannot defend a pipeline that an author has already shipped
with declared outputs at canonical paths — and they do nothing if the runner
invokes snakemake with hazardous defaults. Two snakemake defaults are
particularly destructive on production pipelines and must be neutralized
**at the project level**, not per-invocation:

**1. `--use-singularity` / `--use-apptainer` / `--use-conda` are opt-in.**
Without these flags, snakemake silently ignores `container:`, `conda:`, and
`singularity:` rule directives and runs every rule in the host environment.
The log line `Singularity containers: ignored` is the only warning. This is
the dominant cause of "mysterious R/Python package missing" errors when an
existing pipeline is run from a workstation that doesn't have the project's
full env — and it cascades into the next failsafe failure:

**2. `--keep-incomplete` is opt-in.** Without it, when a rule fails,
snakemake removes ALL declared outputs of that rule — including pre-existing
files that were not modified by the failed run, on the principle that "if
the rule failed, its outputs are suspect." For rules whose outputs sit at
canonical paths (vendor data preprocessing, expensive intermediates that
other rules consume directly), a transient runtime error then permanently
destroys the on-disk copy — even when the actual failure was something
trivially recoverable like a missing R package.

The combination is especially dangerous for **rules that have a `container:`
directive but were invoked without `--use-singularity`**. The container is
silently ignored, the rule runs in a host env it was never meant to run in,
the rule fails for env reasons, and existing outputs are deleted. We have
seen this destroy multiple GB of pre-computed intermediates in real
projects.

**Pattern: codify safe defaults in a project profile.** Both flags are
project-level decisions, not per-invocation. Set them once and make them
the default for every run.

```yaml
# profile/config.yaml
keep-incomplete: true
software-deployment-method:
  - apptainer
```

Then either invoke explicitly with `--profile profile/`:

```bash
snakemake --profile profile/ <target>
```

Or wrap snakemake in `bin/snakemake` that applies the profile automatically:

```bash
#!/usr/bin/env bash
# bin/snakemake — wraps `snakemake` to force the project profile.
set -euo pipefail
PROFILE="${PROJECT_SNAKEMAKE_PROFILE:-profile/}"
for arg in "$@"; do
  case "$arg" in
    --profile|--profile=*) exec snakemake "$@" ;;
  esac
done
exec snakemake --profile "$PROFILE" "$@"
```

Project AGENTS.md / README should forbid bare `snakemake` and direct all
invocations through `bin/snakemake` (or the project's container wrapper).
Bare `snakemake` is acceptable only inside containers where the env is
guaranteed and the worktree is ephemeral.

**When to apply this:** any project with R rules, conda/container
directives, or expensive intermediates on shared filesystems. The cost is
one config file plus one shell wrapper.

**Cross-reference:** the marker-file pattern above (`protected()` caveats)
targets *unrecoverable* outputs (network downloads). The profile pattern
here targets the *cleanup default* for *recoverable* outputs. Both
failsafes are needed; they cover different failure modes.

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
`skills/research/research-package-spec.md` skill.

## Companion Skills

- [`SKILL.md`](SKILL.md) - shared pipeline conventions and workflow artifact expectations.
- [`../data/frictionless.md`](../data/frictionless.md) - data-package descriptors for workflow inputs and outputs.
- [`../research/research-package-spec.md`](../research/research-package-spec.md) - research-package schema and validation commands.
