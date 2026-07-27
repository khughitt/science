# Data Boundary

Science projects separate durable source records from bulky or regenerable data
payloads. The convention is:

- Keep durable records in git-tracked source locations such as `entities/`,
  `results/`, `papers/references.bib`, `knowledge/graph.trig`, and project
  configuration.
- Keep bulky or regenerable payload bytes under ignored data roots such as
  `data/raw/`, `data/processed/`, and `data/external/`.
- Record enough metadata, hashes, and interpretation in tracked files for a
  future reader to understand what payloads were used.

The goal is not to hide research state from git. The goal is to make the
tracked/ignored boundary legible: lightweight evidence, labels, summaries,
datapackages, QA reports, and interpretations should be tracked; large payloads
should stay ignored and be hash-inventoried by workflows that need
reproducibility.

## Policy

`science data audit` uses a single data policy to classify project paths:

- `record`: lightweight durable material that belongs in tracked source.
- `payload`: large or regenerable material that belongs under ignored data
  roots.
- `flag`: ambiguous material that needs a human decision.

The default policy is intentionally conservative. It recognizes record-like
patterns such as datapackage descriptors, result reports, QA JSON, rubrics,
worksheets, verdicts, labels, notes, and interpretations. It recognizes common
payload extensions such as `.parquet`, `.feather`, `.pkl`, `.pdf`, `.npy`,
`.npz`, archives, videos, and MATLAB files. Unknown small files are flagged;
unknown large files are treated as payloads.

Projects may override the defaults in `science.yaml`:

```yaml
data_policy:
  record_patterns:
    - datapackage.json
    - datapackage.yaml
    - RESULTS*.md
    - "**/qa/*.json"
  payload_extensions:
    - .parquet
    - .feather
    - .npy
  size_threshold: 150000
```

Absent a `data_policy:` block, Science uses the framework default. Unknown keys
inside `data_policy:` are invalid.

## Audit

Run:

```bash
science data audit [--project <root>] [--fix] [--json]
```

Without `--project`, the command uses `SCIENCE_PROJECT_ROOT` or the current
directory. The read-only audit exits `1` when it reports violations and `0` when
clean.

The audit reports these quadrants:

| Quadrant | Meaning | Automatic fix |
|---|---|---|
| `stranded_record` | A record-like file is under a data root. | Move to `results/` when a target is unambiguous. |
| `leaked_payload` | A payload-like file is git-tracked outside data roots. | Never moved automatically; flag for manual untracking or relocation. |
| `tracked_payload` | A payload-like file is git-tracked inside a data root. | Never moved automatically; flag for manual `git rm --cached`. |
| `flag` | The policy could not safely classify the file. | Never moved automatically. |

The JSON report has `version: 1` and a `violations` array with `quadrant`,
`path`, `class`, `action`, `target`, and `performed`. With `--fix`, entries also
include any available move outcome details such as `basepath` and
`rewritten_resources`.

## Fixes

`science data audit --fix` is intentionally narrow. It only moves
`stranded_record` files out of data roots and into `results/` when the target can
be proposed safely. It stages the result and never commits.

For tracked stranded records, the fixer uses git-aware moves. For untracked
stranded records, it performs a filesystem move and stages the target. If the
record is a `datapackage.yaml` or `datapackage.json`, the fixer rewrites relative
`resources[].path` entries only when it can preserve their resolution after the
move. If the source sits under a symlinked data directory, the destination
already exists with different content, or the datapackage cannot be rewritten
safely, the item is flagged instead.

Payload-like files are never auto-moved. In particular, a `tracked_payload`
under `data/` should usually be remediated with `git rm --cached <path>` after
confirming the payload remains available locally or through the project's data
provisioning workflow.

## Related Workflows

`science project serialize` depends on this boundary. Serialization copies
tracked source files into a deterministic bundle and records excluded data
payload hashes in `manifest.json`; it does not include payload bytes. See
[`docs/user-guide/project-packaging.md`](../user-guide/project-packaging.md).

Deferred follow-ups include a pre-commit size guard that consumes the same
policy, validate-time warnings for ignored provenance or evidence records,
project health summaries for boundary violations, scaffold and `.gitignore`
template updates, and downstream cleanup sweeps.
