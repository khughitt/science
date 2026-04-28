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
with declared outputs at canonical paths, and they cannot prevent a runner
from invoking snakemake with hazardous defaults. Two snakemake defaults are
particularly destructive on production pipelines:

**1. `--use-singularity` / `--use-apptainer` / `--use-conda` are opt-in.**
Without these flags, snakemake silently ignores `container:`, `conda:`, and
`singularity:` rule directives and runs every rule in the host environment.
The log line `Singularity containers: ignored` is the only warning. This is
the dominant cause of "mysterious R/Python package missing" errors when an
existing pipeline is run from a workstation that doesn't have the project's
full env. It cascades into the next failure mode:

**2. Pre-rule output cleanup ALWAYS runs (no flag disables it).** When
snakemake decides to re-run a rule (for any reason: code/mtime/params
change, fresh `out_dir` metadata, etc.), it removes the rule's declared
outputs *before the rule body executes*. Combined with #1, this means: a
host invocation of a `container:`-bearing rule silently runs in the wrong
env, fails in some trivial way (missing R package), and the canonical
outputs are gone before the rule body even started.

> **Critical clarification:** `--keep-incomplete` does NOT prevent the
> pre-rule cleanup. It addresses a different mechanism: post-failure
> cleanup of partially-written outputs (so you can debug them). The
> deletion that destroys canonical outputs happens BEFORE the rule body
> writes anything — it is the pre-rule clear-the-slate step. There is no
> snakemake flag that disables pre-rule cleanup.

This makes the marker-file pattern above the **only structural defense**
for canonical outputs that other rules consume directly. The pattern is
required, not optional, for any rule whose declared outputs sit at paths
that downstream rules treat as stable inputs.

**Two-layer fix.** Both layers are needed; either alone leaves the
incident class open:

**Layer A (invocation discipline) — codify in a project profile + wrapper.**
Even with marker-file rules, you want runtime invocation to fail closed
when the env can't satisfy `container:` directives. Snakemake won't fail
loudly on its own — it just runs in the wrong env. So:

```yaml
# profile/config.yaml
# Note: keep-incomplete only protects against post-failure cleanup of
# partial writes — a useful but narrow property. It does NOT protect
# against pre-rule cleanup; that requires Layer B (marker-file pattern).
keep-incomplete: true
```

Wrap snakemake in `bin/snakemake` (fail-closed pattern):

```bash
#!/usr/bin/env bash
# bin/snakemake — refuse non-informational invocations on host.
set -euo pipefail
PROFILE="${PROJECT_SNAKEMAKE_PROFILE:-profile/}"

is_informational=false
for arg in "$@"; do
  case "$arg" in
    -n|--dryrun|--lint|--list|--summary|--detailed-summary|--printshellcmds|\
    --version|--help|-h|--dag|--rulegraph|--filegraph|--report)
      is_informational=true ;;
  esac
done

if [[ "$is_informational" == "false" \
      && "${BYPASS_HOST_GUARD:-0}" != "1" \
      && ! -f /.dockerenv ]]; then
  echo "ERROR: refusing non-informational invocation on host." >&2
  echo "  Container: directives are silently ignored without --use-singularity." >&2
  echo "  Use docker/<project>-run.sh or set BYPASS_HOST_GUARD=1 (rare)." >&2
  exit 1
fi
for arg in "$@"; do
  case "$arg" in --profile|--profile=*) exec snakemake "$@" ;; esac
done
exec snakemake --profile "$PROFILE" "$@"
```

The wrapper is fail-closed: it does NOT try to detect container directives
via dry-run probes (which can fail for unrelated reasons and silently let
hazardous runs through). It refuses ALL non-informational host invocations
by default. Production runs go through the project's container wrapper.

**Layer B (workflow author) — marker-file pattern.** For any rule whose
canonical outputs are consumed by downstream rules, use the marker-file
pattern in the section above. This is the only defense against pre-rule
cleanup. Layer A protects against the silent-ignore-container failure
mode at the invocation level; Layer B protects against the cleanup
mechanism at the rule level. Both are needed.

**When to apply this:** any project with R rules, conda/container
directives, or expensive intermediates on shared filesystems. The cost
is one config file, one shell wrapper, and a marker-file refactor for
each canonical-output rule. Cheap relative to a single destroyed
intermediate.

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
