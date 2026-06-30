# Benchmark Hint Candidates Design

## Status

Draft for review.

## Context

The benchmark actionability work made fallback-heavy gap reports easier to
inspect, but the calibration output still shows that most candidate rows are
fallback-only across active biology projects. The next bottleneck is lexicon
tuning: `science benchmark gaps --evidence-report` now exposes
`term_categories.domain_candidate_terms`, but there is no focused command for
reviewing those terms and deciding whether they should become benchmark facet
hints.

`science benchmark hint-candidates` should make that review loop explicit. It
does not change matching, scoring, benchmark metadata, or commons data. It
surfaces candidate terms, their evidence, and a review artifact that a human can
curate before any facet lexicon changes are made.

## Goals

- Provide a read-only default report of candidate terms that may deserve facet
  hint mappings.
- Reuse existing deterministic benchmark gap evidence instead of building a
  second matcher.
- Give reviewers enough context to decide whether a term is a useful benchmark
  hint, project-local noise, generic workflow vocabulary, or evidence for a new
  facet vocabulary.
- Optionally write a project-local YAML review queue under
  `docs/audits/benchmark-hint-candidates/`.
- Preserve local-first behavior and avoid automatic mutation of the hint
  lexicon.

## Non-Goals

- No automatic edits to `FACET_HINT_TERMS` or `FACET_HINT_PHRASES`.
- No commons metadata writes.
- No embeddings, semantic search, or LLM classification.
- No graph-aware belief mapping.
- No replacement of `science benchmark gaps --evidence-report`; this command is
  a narrower projection over that evidence.
- No attempt to decide final reviewer decisions in v1.

## Command Surface

```bash
science benchmark hint-candidates
science benchmark hint-candidates --commons --domain biology
science benchmark hint-candidates --project-root ~/d/cancer/cancer-types/multiple-myeloma
science benchmark hint-candidates --format json
science benchmark hint-candidates --write-review-file
science benchmark hint-candidates --write-review-file --output docs/audits/benchmark-hint-candidates/custom.yaml
```

Options:

- `--domain`: passed through to the underlying benchmark gap report.
- `--commons`: include commons benchmark datasets, matching the other benchmark
  commands.
- `--project-root`: defaults to `SCIENCE_PROJECT_ROOT` or cwd, matching the
  other benchmark commands.
- `--min-count`: optional integer threshold for candidate term count; default
  `1`.
- `--include-existing`: include terms that already map to a facet hint. Default
  false, because v1 is primarily for unmapped terms.
- `--format table|json`: default `table`.
- `--write-review-file`: explicitly write the YAML review artifact.
- `--output <path>`: override the review artifact path. This option requires
  `--write-review-file`; otherwise it should fail early with a Click error.

Default behavior is read-only. The only write path is `--write-review-file`.

## Data Flow

The command should call:

```python
gaps_report(
    project_root,
    include_commons=include_commons,
    domain=domain,
    evidence_report=True,
)
```

Then it should project over:

- `evidence_report.term_categories.domain_candidate_terms`;
- `evidence_report.term_categories.project_local_terms`;
- `evidence_report.term_categories.workflow_or_modeling_terms`;
- existing `FACET_HINT_TERMS`, only when `--include-existing` is set.

The command must not re-tokenize project text or benchmark facets. The evidence
report remains the single source of truth for which terms surfaced and which
entities exemplify them.

The evidence report currently exposes the top 10 terms per category. V1 accepts
that cap instead of adding a wider evidence-report API. Therefore this command
is a curated view over the visible evidence terms, not a complete inventory of
every unmapped token. `--min-count` filters within those capped category lists;
it does not request more terms from `gaps_report()`.

## Candidate Rows

Each row represents one candidate term.

JSON row shape:

```json
{
  "term": "cytogenetic",
  "count": 19,
  "category": "domain-candidate",
  "current_hint": null,
  "suggested_action": "review-for-hint",
  "suggested_facets": [],
  "example_entities": [
    "hypothesis:0002-cytogenetic-distinct-entities"
  ],
  "reason_notes": [
    "frequent-unmapped-domain-term",
    "fallback-heavy-project"
  ]
}
```

Fields:

- `term`: normalized token from the evidence report.
- `count`: number of entities where the term appears in the relevant evidence
  bucket. For evidence-derived categories this is an entity count because
  `_unmapped_high_value_terms()` emits each term at most once per entity. For
  `existing-hint` rows, `count` is `null` because existing hint terms are
  enumerated from `FACET_HINT_TERMS`, not observed in the evidence buckets.
- `category`: one of `domain-candidate`, `project-local`,
  `workflow-or-modeling`, or `existing-hint`.
- `current_hint`: the facet currently mapped by `FACET_HINT_TERMS`, if present.
  It is expected to be non-null only for `existing-hint` rows in v1, because
  evidence-derived rows exclude already-mapped hint terms upstream.
- `suggested_action`: one of:
  - `review-for-hint`: plausible unmapped domain term;
  - `project-local-or-alias`: likely project-local vocabulary;
  - `not-a-benchmark-facet`: workflow/modeling vocabulary or otherwise generic;
  - `already-mapped`: term already has a hint mapping;
  - `needs-new-facet-vocab`: term appears domain-relevant but no existing hint
    facet is a good fit.
- `suggested_facets`: conservative deterministic guesses, if any.
- `example_entities`: entity ids supplied by the underlying evidence term row.
  For `existing-hint` rows this is an empty list in v1.
- `reason_notes`: short deterministic explanations.

For v1, `suggested_facets` should be conservative. It may be empty. The command
should not infer a facet merely because a term is frequent.

## Classification Rules

Classification is deterministic and deliberately modest:

1. Terms already present in `FACET_HINT_TERMS` are excluded upstream from the
   evidence categories. When `--include-existing` is set, enumerate them
   directly from `FACET_HINT_TERMS` as `existing-hint` rows with
   `count: null`, `example_entities: []`, `current_hint` populated, and
   `suggested_action: already-mapped`. They are hidden by default.
2. Terms from `project_local_terms` become `project-local` rows with
   `suggested_action: project-local-or-alias`. They are hidden from the default
   table but included in JSON summary counts.
3. Terms from `workflow_or_modeling_terms` become `workflow-or-modeling` rows
   with `suggested_action: not-a-benchmark-facet`. They are hidden from the
   default table but included in JSON summary counts.
4. Terms from `domain_candidate_terms` become `domain-candidate` rows with
   `suggested_action: review-for-hint`.
5. If a domain term is repeatedly surfaced but no existing
   `BENCHMARK_GAP_HINT_FACETS` value is appropriate, reviewers can change the
   YAML `decision` field to `needs-new-facet-vocab`; the command should not make
   that decision automatically in v1.

The evidence report already emits disjoint categories using project-local,
workflow/modeling, then domain precedence. The command should read those lists
as-is and should not create a second categorization policy.

`FACET_HINT_PHRASES` is intentionally out of scope for v1 rows. It is a
multi-token phrase surface, while this command reviews single normalized terms.
Phrase-level candidates can be designed later if needed.

## Summary

JSON payload shape:

```json
{
  "project_root": "~/d/cancer/cancer-types/multiple-myeloma",
  "summary": {
    "candidate_terms": 18,
    "domain_candidate_terms": 10,
    "project_local_terms": 6,
    "workflow_or_modeling_terms": 2,
    "existing_hint_terms": 0,
    "term_bucket_cap": 10,
    "truncation_notice": "evidence categories are capped at top 10 terms per bucket",
    "fallback_only_gap_rows": 448,
    "entity_specific_gap_rows": 47
  },
  "hint_candidates": [],
  "review_file": null,
  "commons_notice": null
}
```

`fallback_only_gap_rows` and `entity_specific_gap_rows` should come from the
existing gap row `candidate_mode` counts. They explain why hint review is
needed, but they should not influence matching or scoring.

`candidate_terms` is the number of rows emitted after category visibility and
`--min-count` filtering. The per-category summary counts are counts of emitted
rows, not uncapped corpus totals. `term_bucket_cap` documents the evidence
source cap so consumers do not mistake the report for a complete term
inventory.

## Table Output

Default table should show only actionable domain candidates:

```text
term          count  action           suggested facets  examples
cytogenetic   19    review-for-hint   -                 hypothesis:...
expression    21    review-for-hint   -                 question:...
```

Project-local, workflow/modeling, and existing-hint rows are available in JSON
and the review artifact, but should not dominate the default table. If no
actionable terms remain after filtering, print `No benchmark hint candidates.`

## Review Artifact

With `--write-review-file`, write YAML to:

```text
<project-root>/docs/audits/benchmark-hint-candidates/YYYY-MM-DD-<project>.yaml
```

The `<project>` segment is the project root leaf directory. For
`~/d/cancer/cancer-types/multiple-myeloma`, the default file is:

```text
docs/audits/benchmark-hint-candidates/2026-06-30-multiple-myeloma.yaml
```

The command should create parent directories as needed. If the file exists, fail
early unless an explicit `--force` option is added in the implementation plan.
The design does not require `--force` for v1, but it is acceptable if the plan
chooses to include it with tests.

YAML shape:

```yaml
project: multiple-myeloma
project_root: ~/d/cancer/cancer-types/multiple-myeloma
generated_at: "2026-06-30"
source_command: "science benchmark hint-candidates --commons --domain biology --write-review-file"
summary:
  candidate_terms: 18
  domain_candidate_terms: 10
  term_bucket_cap: 10
  truncation_notice: evidence categories are capped at top 10 terms per bucket
candidates:
  - term: cytogenetic
    count: 19
    category: domain-candidate
    current_hint: null
    suggested_action: review-for-hint
    suggested_facets: []
    decision: pending
    reviewer_notes: ""
    example_entities:
      - hypothesis:0002-cytogenetic-distinct-entities
    reason_notes:
      - frequent-unmapped-domain-term
```

Generated fields provide context. Human-editable fields are:

- `decision`: initial value `pending`;
- `reviewer_notes`: initial value `""`.

The command should not consume this YAML in v1. Applying accepted decisions to
the actual hint lexicon is a later, separate design.

Tests should inject or freeze the date used for `generated_at` and the default
filename. The implementation should not rely on the wall clock directly in
tests.

## Error Handling

- Unknown `--format` values are handled by Click.
- `--output` without `--write-review-file` fails with a Click error.
- Existing output file fails early unless an explicit overwrite flag is added.
- Commons loading failures should follow existing benchmark command behavior:
  continue with project-local data and emit `commons_notice`.
- Invalid project root handling should match existing benchmark commands.

## Testing

Implementation should add focused tests for:

- Report rows are projected from `evidence_report.term_categories` and do not
  re-tokenize text.
- Default rows include domain candidate terms and exclude project-local,
  workflow/modeling, and existing hints unless requested.
- JSON includes summary counts, row fields, and `commons_notice`.
- Summary and review artifact document the top-10-per-category evidence cap.
- Existing hint rows, when included, have `count: null`, no example entities,
  and populated `current_hint`.
- `--write-review-file` writes the expected YAML path under
  `docs/audits/benchmark-hint-candidates/`.
- `--output` requires `--write-review-file`.
- Existing output path fails without overwrite behavior.
- Table output includes actionable terms and prints a clear no-results message.
- Date-dependent output uses a deterministic date seam in tests.

## Success Criteria

- Running `science benchmark hint-candidates --commons --domain biology` on the
  active projects produces a concise candidate list focused on domain terms.
- The command is read-only by default.
- `--write-review-file` creates a reviewable YAML queue without mutating
  benchmark metadata or hint mappings.
- The report gives enough context to decide whether a term should become a hint,
  be treated as project-local noise, or motivate future facet vocabulary work.
