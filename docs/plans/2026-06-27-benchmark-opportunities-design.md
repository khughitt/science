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
- Highlight project entities that have no matching benchmark signal.
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
shared benchmark seed catalog through the same discovery path used by
`science benchmark list`, but it needs a richer internal row than the current
`BenchmarkRow`. `science_tool.benchmark_catalog.BenchmarkRow` carries facets,
`task_count`, and `task_ids`; opportunity scoring also needs task fields,
`notes`, `limitations`, and enough frontmatter to reuse dataset readiness. The
implementation should either enrich `BenchmarkRow` additively or introduce a
separate internal `BenchmarkOpportunityDataset` loaded from the same local and
commons frontmatter sources.

`--calibration-report` is part of the v1.5/Phase 2 bridge, not a separate
workflow. It adds a calibration section to normal table output and adds a
`calibration` object to JSON output. It prints the evidence the scorer used:
token overlaps, dropped tokens, unmatched tokens, facet coverage, and score
components. This is deliberately boring output that lets maintainers see whether
the method is using the right signals before they trust the ranked rows.

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
      "relative_score": 80,
      "score_components": {
        "baseline": {
          "task_completeness": 25,
          "signal_value": 20,
          "modality_value": 12,
          "readiness": 10,
          "limitations": 5
        },
        "relative": {
          "related_belief_id": 35,
          "facet_overlap": 20,
          "kind_signal_fit": 15,
          "diversity_added": 10,
          "readiness_penalty": 0
        }
      },
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
  "calibration": {
    "enabled": false
  },
  "commons_notice": null
}
```

Scores are additive component sums, clamped to 0-100 for readability. They are
report-ordering hints, not truth values. The command must expose component
points and notes so a row's number can be reconstructed without reading code.

Default row ordering is stable and explicit:

1. `matched_opportunities`: `relative_score` descending, then `baseline_score`
   descending, then `entity_id`, then `benchmark_id`, then `task_id`.
2. `available_unmapped_benchmarks`: `baseline_score` descending, then
   `benchmark_id`.
3. `coverage_gaps` and `unmapped_project_entities`: `entity_id`, then the
   rendered missing facet strings.

JSON preserves this order.

## Two-score model

Each benchmark opportunity has two separate scores:

### Baseline score

The baseline score estimates general benchmark usefulness independent of the
current project. It is derived only from benchmark metadata:

- `task_completeness` (0-30): concrete `tasks[]` entries with prediction target,
  held-out unit, metric, baseline, and ground truth.
- `signal_value` (0-25): fixed editorial weights for high-value signal types
  such as perturbation, time-series, longitudinal, and cross-context
  generalization.
- `modality_value` (0-20): fixed editorial weights for modalities that diversify
  the benchmark catalog, such as proteomics, spatial, multimodal, perturbation,
  and single-cell.
- `readiness` (0-15): readiness/access contribution derived consistently from
  dataset readiness; implementation should reuse `readiness_weight()` from
  `science_tool.dataset_prioritize` or extract its shared core rather than
  re-deriving access semantics.
- `limitations` (0-10): specific notes/limitations increase trust in the
  record; sparse benchmark records without limitations score lower.

This is a benchmark-quality / informativeness estimate. It should not look at
project text or at the current catalog distribution. "Underrepresented" in this
score means a fixed editorial list, not "rare among rows returned by this
particular command." Catalog-relative diversity belongs in the relative score
and coverage-gap output.

### Relative score

The relative score estimates usefulness for the current project. It is derived
from transparent project-to-benchmark evidence:

- `related_belief_id` (0-40): project entity id detected as an exact token
  inside free-text `benchmark.related_beliefs` strings. This is not list
  equality: entries may be prose such as `"hypothesis:h1 predicts response
  shifts."`.
- `facet_overlap` (0-25): exact-token overlap between project entity titles /
  `content_preview` text and benchmark facets.
- `kind_signal_fit` (0-20): coverage of benchmark kinds likely to test the
  entity's language, such as perturbation-response for perturbation claims or
  time-series for dynamic claims.
- `diversity_added` (0-15): modalities or signal types not already present in
  matched opportunities for the same project entity.
- `readiness_penalty` (0 to -20): access/readiness penalty when a row is not
  usable for near-term testing, derived consistently with dataset readiness.

This score can only rank candidate opportunities; it cannot assert that a
benchmark actually tests a belief. Rows with only weak token overlap should be
clearly marked as low-confidence candidates.

The exact weights above are initial bounded components for implementation. They
are calibration targets, not settled science; if real-project calibration shows
that a component creates noisy output, adjust the component weight and document
the observed failure mode.

## Matching method

The first implementation should use deterministic matching only:

1. Load project entities from `entities/questions`, `entities/hypotheses`, and
   `entities/propositions`. Tokenize `id`, `title`, and `content_preview`
   (first 200 body characters, already produced by frontmatter parsing). Do not
   tokenize full `content` by default; it is too noisy for the first matching
   pass. Mechanism `summary` is not part of this command's initial target kinds.
2. Normalize benchmark ids, titles, `related_beliefs`, `domains`, `modalities`,
   `signal_types`, `benchmark_kinds`, source datasets, task fields, notes, and
   limitations into tokens.
3. Apply a stoplist and token gates before matching. The initial stoplist should
   remove generic science/project words such as `data`, `dataset`, `analysis`,
   `model`, `result`, `evidence`, `cell`, and `response` unless they appear as
   part of a controlled facet phrase. Ignore tokens shorter than three
   characters except known shorthand ids such as `h1` / `q63`.
4. Build an id-token set for each project entity: canonical id, local id,
   shortform references where resolvable, deprecated ids, and aliases if present.
   Reuse `science_tool.entities.resolve_entity_ref()` for user-supplied
   `--entity` values and for local/shortform reconciliation where possible.
   Then detect these ids as exact tokens inside each free-text
   `related_beliefs` string.
5. Match exact tokens between project text and benchmark facets.
6. Apply a small domain synonym table only for obvious local vocabulary variants
   already present in the benchmark seed set, such as `rna-seq` /
   `transcriptomics`, `single-cell` / `single-cell-rna-seq`, and
   `perturbation` / `intervention`.
7. Emit match reasons for every positive signal and emit dropped-token evidence
   in calibration mode.

The method intentionally avoids embeddings and LLM judgments at this stage. A
future implementation can add semantic matching after the calibration report has
shown which deterministic signals are weak.

## Modality diversity

The report should prioritize diverse benchmark coverage. A project does not
benefit much from seeing a tenth RNA-seq static-association benchmark before it
sees its first proteomics, spatial, perturbation, time-series, or multimodal
candidate.

Use diversity in two places:

- Baseline scoring gives modest credit to fixed high-information modalities and
  signal types named in the score recipe.
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
- Tune the stoplist, synonym table, and bounded component weights based on
  observed failures. Calibration changes should preserve reconstructable
  component scores.
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
- Relative score detects canonical/local/shorthand ids inside free-text
  `related_beliefs` prose.
- Stoplist and minimum-token gating suppress generic token-only matches.
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
