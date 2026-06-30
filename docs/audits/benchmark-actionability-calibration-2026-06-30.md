# Benchmark Actionability Calibration - 2026-06-30

## Scope

Calibrated benchmark actionability across the active projects after making
`dataset:l1000-cmap` stageable in commons.

Projects:

- `~/d/health/processes/post-acute-infection`
- `~/d/cancer/cancer-types/multiple-myeloma`
- `~/d/natural-systems`
- `~/d/cancer/data-sources/cbioportal`

Reports used:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons science benchmark tests --commons --domain biology
SCIENCE_COMMONS_ROOT=~/d/science-commons science benchmark gaps --commons --domain biology --evidence-report
```

The raw aggregate JSON for this run was written to:

- `/tmp/benchmark-actionability-calibration.json`
- `/tmp/benchmark-gap-candidate-note-summary.json`

## Headline Results

Across all four projects, `science benchmark tests --exclude-fallback --state
concrete` produced:

| Measure | Count |
| --- | ---: |
| Concrete non-fallback rows | 248 |
| Runnable concrete non-fallback rows | 122 |
| Metadata-only concrete non-fallback rows | 126 |

Top runnable concrete benchmarks:

| Benchmark | Rows |
| --- | ---: |
| `dataset:brca-metabric` | 49 |
| `dataset:brca-tcga-pancanatlas` | 49 |
| `dataset:ctrpv2` | 9 |
| `dataset:oetjen-2018-bone-marrow-atlas` | 7 |
| `dataset:l1000-cmap` | 5 |
| `dataset:ccle-proteomics-nusinow-2020` | 3 |

Top metadata-only concrete benchmarks:

| Benchmark | Rows |
| --- | ---: |
| `dataset:mmrf-commpass` | 53 |
| `dataset:sciplex3` | 15 |
| `dataset:tahoe-100m` | 14 |
| `dataset:dream4-in-silico-network` | 12 |
| `dataset:mouse-gastrulation-atlas` | 12 |
| `dataset:human-cell-atlas` | 10 |
| `dataset:dream-perturbation` | 7 |
| `dataset:cptac-proteogenomics` | 3 |

## Project Notes

### Multiple Myeloma

This remains the strongest calibration project: 222 concrete non-fallback rows,
with 113 runnable and 109 metadata-only. `l1000-cmap` now contributes 4 runnable
concrete rows. The biggest metadata-only contributor is still
`dataset:mmrf-commpass` with 51 rows, followed by single-cell or portal-like
resources (`sciplex3`, `tahoe-100m`, `mouse-gastrulation-atlas`,
`human-cell-atlas`).

Interpretation: the next bottleneck is not missing task metadata. It is either
restricted/portal access or missing staged benchmark slices.

### Post-Acute Infection

Only 9 concrete non-fallback rows appear, with 2 runnable rows. Those runnable
rows are `dataset:ctrpv2` and `dataset:l1000-cmap`, both attached to
`proposition:0021-acute-antigen-burden-determines-pais-incidence`.

Interpretation: L1000 helped, but the project mostly lacks entity-specific
benchmark connections. The unmapped term report is dominated by project-local
terms such as `pais`, `post-infectious`, `covid`, and `lesion`.

### Natural Systems

The biology benchmark catalog is a poor fit: 4 concrete non-fallback rows, all
metadata-only, and 0 runnable rows. The top unmapped terms are mostly formal or
modeling vocabulary (`models`, `catalog`, `structure`, `lens`, `parameter`).

Interpretation: do not tune biology benchmark metadata for this project. It
needs either a non-biology benchmark catalog or project-specific model
validation benchmarks.

### cBioPortal

The project has 13 concrete non-fallback rows, 7 runnable and 6 metadata-only.
Runnable rows are mostly `ccle-proteomics-nusinow-2020`, `brca-metabric`,
`brca-tcga-pancanatlas`, and `ctrpv2`.

Interpretation: cBioPortal is useful as a sanity check for cancer benchmark
coverage, but the current row count is too small to drive commons-wide tuning.

## Gap Candidate Calibration

The gap candidate surface is still fallback-heavy:

| Measure | Count |
| --- | ---: |
| Gap candidate rows | 2327 |
| Fallback candidate rows | 2160 |
| Entity-specific candidate rows | 167 |

Fallback candidates are dominated by generic high-baseline/task-ready records:

| Benchmark | Fallback rows |
| --- | ---: |
| `dataset:mmrf-commpass` | 720 |
| `dataset:ccle-proteomics-nusinow-2020` | 487 |
| `dataset:cptac-proteogenomics` | 483 |
| `dataset:dream4-in-silico-network` | 470 |

This confirms that fallback rows remain useful as a coarse inventory signal, but
not as the main actionability surface. The most actionable defaults should favor
entity-specific evidence and keep fallback candidates visibly separated.

## Unmapped Term Calibration

The top unmapped terms are noisy. They include project-local labels
(`mm30`, `pais`, `cbioportal`), generic workflow terms (`models`, `catalog`,
`project`), and some potentially useful domain terms (`cytogenetic`,
`expression`, `mutation`, `post-infectious`, `lesion`).

Interpretation: the evidence extraction report is useful, but its unmapped-term
surface needs ranking hygiene before it should drive lexicon changes. Project
slugs, command/workflow words, and generic modeling vocabulary should be
demoted or separated from domain terms.

## Recommendation

Do not start by adding more commons seed metadata. The current metadata-only
leaders are mostly restricted deposits, portals, broad atlases, or raw archives
that should not be forced into runnable deposits without a real staged slice.

The next benchmark slice should tune report actionability:

1. Make fallback-only rows less prominent in the default benchmark-gap and
   benchmark-test triage views.
2. Add a cleaner unmapped-term evidence ranking that separates project-local,
   workflow/modeling, and domain-candidate terms.
3. Use the cleaned term evidence to tune only high-confidence facet hints.
4. Re-run this same four-project calibration and compare the entity-specific
   candidate ratio and top concrete runnable rows.

After that, revisit commons staging for a narrow target such as `sciplex3` only
if we can define a concrete processed slice or recipe. `mmrf-commpass` should
remain metadata-only unless access restrictions and staging terms are resolved.
