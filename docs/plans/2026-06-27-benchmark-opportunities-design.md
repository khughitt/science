---
id: "plan:2026-06-27-benchmark-opportunities-design"
type: "plan"
title: "Read-only benchmark opportunity reports"
status: "proposed"
created: "2026-06-27"
updated: "2026-06-27"
related:
  - "plan:2026-06-26-benchmark-grounded-model-assessment-design"
  - "plan:2026-06-27-benchmark-catalog-v1-implementation-plan"
  - "plan:2026-06-21-catalog-datasets-design"
---

# Read-only benchmark opportunity reports

## Purpose

The benchmark catalog now has a descriptive v1 surface and a small commons seed
set of biology / omics benchmark-capable datasets. The next useful step is a
read-only project report that answers:

> Given this project's questions, hypotheses, propositions, and dataset catalog,
> which benchmark-capable datasets look potentially useful, and where are the
> obvious benchmark coverage gaps?

This is a cautious Phase 2 bridge. It should make benchmark metadata actionable
without pretending that text matching is belief mapping. The report suggests
candidate opportunities for human review; it does not create graph edges, score
belief truth, create benchmark outcomes, or author belief-test plans.

## Goals

- Show candidate benchmark datasets and tasks that may be relevant to project
  entities.
- Highlight important project entities that have no matching benchmark signal.
- Prefer modality diversity when choosing what to inspect next.
- Separate a benchmark's general informativeness from its usefulness in one
  project context.
- Keep every match explainable through deterministic, inspectable reasons.
- Include an exploratory calibration step so the matching method can be tuned
  before ranking becomes a strong recommendation surface.

## Non-goals

- No semantic embeddings or LLM ranking in the first implementation.
- No graph-aware `--related` semantics.
- No new `RelationKind` values or materialize changes.
- No automatic benchmark gap entities.
- No belief-test plan creation.
- No benchmark outcome or leaderboard scoring.

## Command surface

Add a read-only command:

```bash
science benchmark opportunities
science benchmark opportunities --commons
science benchmark opportunities --format json
science benchmark opportunities --entity hypothesis:0005-dynamic-homeostasis
science benchmark opportunities --domain biology
science benchmark opportunities --calibration-report
```

The command inspects local `question`, `hypothesis`, and `proposition`
frontmatter, plus benchmark metadata from local datasets. `--commons` adds the
shared benchmark seed catalog through the same helper path used by
`science benchmark list`.

`--calibration-report` is part of the v1.5/Phase 2 bridge, not a separate
workflow. It prints the evidence the scorer used: token overlaps, unmatched
tokens, facet coverage, and score components. This is deliberately boring output
that lets maintainers see whether the method is using the right signals before
they trust the ranked rows.

## Output contract

JSON is the stable contract. Table output may be concise, but JSON should expose
the full reasoning:

```json
{
  "matched_opportunities": [
    {
      "entity_id": "hypothesis:0005-dynamic-homeostasis",
      "entity_title": "Dynamic homeostasis predicts perturbation recovery",
      "benchmark_id": "dataset:sciplex3",
      "benchmark_title": "sci-Plex 3",
      "task_id": "dataset:sciplex3#compound-response",
      "match_reasons": ["related-belief-id", "title-token:perturbation"],
      "benchmark_kinds": ["perturbation-response"],
      "signal_types": ["perturbation", "cross-context-generalization"],
      "modalities": ["single-cell-rna-seq", "perturbation"],
      "baseline_score": 72,
      "relative_score": 88,
      "score_notes": [
        "Has a concrete benchmark task.",
        "Adds perturbation signal coverage for this entity."
      ]
    }
  ],
  "coverage_gaps": [
    {
      "entity_id": "hypothesis:0005-dynamic-homeostasis",
      "missing_signal_types": ["time-series"],
      "missing_modalities": ["proteomics"],
      "reason": "No matched benchmark has these facets."
    }
  ],
  "available_unmapped_benchmarks": [
    {
      "benchmark_id": "dataset:cptac-proteogenomics",
      "benchmark_title": "CPTAC proteogenomics",
      "baseline_score": 78,
      "unmapped_facets": ["proteomics", "multimodal"]
    }
  ],
  "unmapped_project_entities": [
    {
      "entity_id": "question:0010-example",
      "entity_title": "Example question",
      "observed_tokens": ["spatial", "progression"]
    }
  ],
  "commons_notice": null
}
```

Scores are integers from 0 to 100 for readability. They are report-ordering
hints, not truth values. The command must print score component notes so a row
can be audited without reading code.

## Two-score model

Each benchmark opportunity has two separate scores:

### Baseline score

The baseline score estimates general benchmark usefulness independent of the
current project. It is derived only from benchmark metadata:

- Concrete `tasks[]` entry with prediction target, held-out unit, metric,
  baseline, and ground truth.
- High-value signal types such as perturbation, time-series, longitudinal, and
  cross-context generalization.
- Modality breadth, with credit for multimodal, proteomics, spatial, and other
  underrepresented modalities.
- Dataset class and readiness: a `deposit` with a concrete task ranks above a
  `reference`, which ranks above a `pointer`, unless the reference is the
  canonical registry for the benchmark.
- Limitations present and specific; sparse benchmark records without limitations
  score lower.

This is a benchmark-quality / informativeness estimate. It should not look at
project text.

### Relative score

The relative score estimates usefulness for the current project. It is derived
from transparent project-to-benchmark evidence:

- Exact project entity id in `benchmark.related_beliefs`.
- Exact-token overlap between project entity titles / summaries and benchmark
  facets.
- Coverage of benchmark kinds likely to test the entity's language, such as
  perturbation-response for perturbation claims or time-series for dynamic
  claims.
- Added diversity relative to benchmarks already matched to the project.
- Access/readiness penalties when a row is not usable for near-term testing.

This score can only rank candidate opportunities; it cannot assert that a
benchmark actually tests a belief. Rows with only weak token overlap should be
clearly marked as low-confidence candidates.

## Matching method

The first implementation should use deterministic matching only:

1. Normalize entity ids, titles, summaries, and selected frontmatter text into
   lowercase tokens.
2. Normalize benchmark ids, titles, `related_beliefs`, `domains`, `modalities`,
   `signal_types`, `benchmark_kinds`, source datasets, task fields, notes, and
   limitations into tokens.
3. Match exact entity ids against `related_beliefs`.
4. Match exact tokens between project text and benchmark facets.
5. Apply a small domain synonym table only for obvious local vocabulary variants
   already present in the benchmark seed set, such as `rna-seq` /
   `transcriptomics`, `single-cell` / `single-cell-rna-seq`, and
   `perturbation` / `intervention`.
6. Emit match reasons for every positive signal.

The method intentionally avoids embeddings and LLM judgments at this stage. A
future implementation can add semantic matching after the calibration report has
shown which deterministic signals are weak.

## Modality diversity

The report should prioritize diverse benchmark coverage. A project does not
benefit much from seeing a tenth RNA-seq static-association benchmark before it
sees its first proteomics, spatial, perturbation, time-series, or multimodal
candidate.

Use diversity in two places:

- Baseline scoring gives modest credit to underrepresented high-information
  modalities and signal types.
- Relative scoring gives additional credit when a benchmark adds a modality or
  signal type not already present in the matched opportunity set for the same
  project entity.

Reports should also expose diversity gaps directly, for example:

```json
{
  "entity_id": "hypothesis:...",
  "missing_modalities": ["proteomics", "spatial"],
  "missing_signal_types": ["time-series"]
}
```

## Exploratory calibration phase

The first implementation should ship with a calibration-first posture:

- Add tests for deterministic behavior, output shape, and obvious scoring order.
- Run the command against at least one real project and the commons seed catalog.
- Inspect the calibration report for false positives, false negatives, noisy
  tokens, and missing fields.
- Record observed tuning needs in follow-up feedback or a design note before
  promoting stronger ranking semantics.

During calibration, the table output should avoid language such as "best" or
"recommended". Prefer "candidate", "matched", and "unmapped". The JSON score
fields exist so downstream tooling can sort and inspect, but the CLI should make
the provisional nature visible.

## Error handling

- Empty local catalogs return valid empty sections.
- Commons unavailable returns local rows plus `commons_notice`, matching
  `science benchmark list`.
- Invalid `--entity` values fail early with a Click error.
- Missing optional entity fields are treated as absent, not as empty evidence.
- Benchmark records with invalid metadata should already be caught by validation;
  the report should skip malformed optional fields rather than crash.

## Testing

Cover:

- Exact `related_beliefs` id match outranks token-only matches.
- Token/facet matching does not imply graph semantics.
- `--entity` filters the report to one project entity.
- Commons unavailable degrades to local rows plus notice.
- Empty catalogs return stable empty sections.
- Baseline score rewards concrete tasks and high-value signal types.
- Relative score rewards modality/signal diversity within one project context.
- Calibration output exposes score components and token evidence.

## Relationship to later Phase 2 work

This command is the read-only discovery layer before benchmark gaps and
belief-test plans become formal surfaces. Once the method is calibrated, Science
can add:

- `science benchmark gaps` for explicit gap reporting.
- `plan_kind: belief-test` templates.
- Typed graph links between project beliefs and benchmark tasks.
- Outcome summaries that turn benchmark runs into evidence.

Until then, opportunity rows remain suggestions for human review.
