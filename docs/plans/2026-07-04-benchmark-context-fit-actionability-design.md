# Benchmark Context-Fit Actionability Design

## Context

The benchmark catalog work has made several benchmark records concrete and
runnable, including `l1000-cmap` and `cptac-gbm-2021-proteogenomics`. A
2026-07-04 calibration pass across active projects showed that this helped, but
the remaining actionability problem is no longer only access or task metadata.

Sampled projects:

- `~/d/cancer/cancer-types/multiple-myeloma`
- `~/d/health/processes/post-acute-infection`
- `~/d/natural-systems`
- `~/d/cancer/data-sources/cbioportal`

Observed current behavior:

- CPTAC GBM now contributes runnable concrete `protein-rna-cross-modal` rows in
  multiple myeloma and cBioPortal, but not in post-acute infection or natural
  systems.
- Multiple myeloma has many concrete runnable rows, but many are BRCA or broad
  cancer benchmarks that are methodologically useful while biologically
  adjacent.
- Natural systems has no concrete runnable benchmark-test rows and still gets
  biology fallback noise.
- `benchmark gaps` remains dominated by fallback-only candidates:
  - multiple myeloma: 1,350 / 1,509 candidate rows are fallback.
  - post-acute infection: 210 / 213 candidate rows are fallback.
  - natural systems: 477 / 480 candidate rows are fallback.
  - cBioPortal: 168 / 173 candidate rows are fallback.
- MMRF CoMMpass is blocked for a real task-support reason
  (`open-metadata-missing-progression-endpoint`), so treating it as a generic
  high-quality fallback adds noise.

The current scoring stack answers "does this entity share any benchmark facet
tokens?" and "is this benchmark generally useful?" It does not separately answer
"is this benchmark biologically and project-context appropriate?" That missing
axis is why good benchmarks can still produce weak action queues.

## Goals

- Add a deterministic context-fit projection that distinguishes benchmark
  quality from project/entity relevance.
- Make `science benchmark tests`, `science benchmark test-triage`, and related
  review artifacts easier to act on without changing raw matching semantics.
- Preserve existing scores, raw rows, and calibration surfaces so context-fit
  behavior can be audited against the current reports.
- Reduce default prominence of cross-context and generic fallback rows without
  hiding them from explicit diagnostic views.
- Keep v1 local-first, deterministic, and metadata/text based. No embeddings,
  live ontology lookup, or model calls.

## Non-Goals

- Do not change `relative_score`, `candidate_score`, `baseline_score`, or the
  existing opportunity/gap matching algorithms in v1.
- Do not rewrite benchmark metadata or project entities as part of this slice.
- Do not infer disease ontology equivalence from free text beyond explicit,
  local token/facet rules.
- Do not make fallback rows disappear from raw reports. Suppression or demotion
  belongs in actionability projections and triage views.
- Do not solve all benchmark relevance; v1 should expose enough structure to
  calibrate the next round.

## Approach

Add a context-fit classification layer over existing benchmark-test rows.

The layer consumes the same row data already produced by
`benchmark_tests_report()` and the project context already loaded for benchmark
matching. It emits additive fields on benchmark-test rows and uses those fields
for triage sorting/grouping.

Raw matching remains the source of truth for "what matched." Context-fit is a
separate projection for "how actionable is this match in this project?"

## Context-Fit Vocabulary

Add a small ordered vocabulary:

| Value | Meaning | Example |
| --- | --- | --- |
| `direct-fit` | Benchmark context and task are aligned with the project/entity context. | CPTAC GBM for cBioPortal cross-sectional tumor omics questions; MM-specific benchmark for MM questions. |
| `adjacent-fit` | Benchmark is biologically adjacent and methodologically relevant, but not the same disease/system/context. | BRCA outcome benchmark for multiple myeloma outcome questions. |
| `method-fit` | Benchmark task type or modality is useful, but biological context is weak or absent. | A generic network-reconstruction benchmark for a project that mentions temporal mechanisms but not the benchmark's biological system. |
| `generic-fallback` | Candidate appears because it is a high-quality fallback, with little entity/project-specific evidence. | Baseline-quality fallback rows selected by rotation. |
| `blocked-fit` | Benchmark appears relevant but task support/access/runtime blocks actionability. | MMRF progression-risk rows with blocked task support. |
| `out-of-context` | Benchmark is likely poor project fit despite a token/facet match. | Broad biology benchmark rows in a non-biology project, unless task/facet evidence is explicit. |

Ordering for actionability:

1. `direct-fit`
2. `adjacent-fit`
3. `method-fit`
4. `blocked-fit`
5. `generic-fallback`
6. `out-of-context`

`blocked-fit` ranks above `generic-fallback` because it can represent a real
future work item, but below runnable method-fit rows because it cannot be acted
on immediately.

## Row Contract

Add fields to each `BenchmarkTestRow`:

```json
{
  "context_fit": "direct-fit",
  "context_fit_reasons": [
    "project-domain:cancer",
    "entity-token:cross-sectional",
    "benchmark-modality:proteomics",
    "task-support:supported"
  ],
  "context_fit_warnings": []
}
```

Fields:

- `context_fit`: one of the vocabulary values above.
- `context_fit_reasons`: deterministic reason notes explaining positive
  evidence.
- `context_fit_warnings`: deterministic caveats that explain demotion or risk.

These fields are additive. Existing consumers can ignore them.

## Evidence Sources

Use only already-local information:

- Project root metadata:
  - `science.yaml` `id` and `name`;
  - project root leaf tokens;
  - optional project tags only if a later design introduces a dedicated
    identity/context field. V1 must not tokenize free-form `tags` as identity
    because prior hint-candidate cleanup showed tags are inconsistent across
    projects.
- Project entity text:
  - entity id tokens;
  - title tokens;
  - content preview tokens;
  - existing normalized token pipeline, stop lists, and phrase hints.
- Benchmark row fields:
  - `benchmark_id`, `benchmark_title`;
  - `matched_facets`;
  - `benchmark_kinds`;
  - `task_type`;
  - `priority_source`;
  - `readiness_label`;
  - `task_support_state`;
  - `reason_notes`;
  - `dataset_class`.
- Benchmark source metadata must be supplied by the same internal path that
  constructs benchmark-test rows. If a field is not available on the public row,
  the implementation should extend the row-building context rather than
  reloading benchmark sources a second time:
  - domains;
  - modalities;
  - signal types;
  - benchmark kinds;
  - source datasets;
  - limitations.

No network calls are allowed.

## Classification Rules

V1 uses ordered rules. Evaluate the blocked override first, then the remaining
rules in order. First match wins.

### 1. Blocked Override

If `task_support_state == "blocked"` or `readiness_label == "blocked"`, classify
as `blocked-fit` unless the row has no project/entity evidence and is fallback
only. In that fallback-only case classify as `generic-fallback` and retain a
warning:

- `blocked-support-fallback`

This preserves the useful fact that MMRF is blocked while avoiding hundreds of
blocked fallback action items.

### 2. Generic Fallback

If `priority_source == "gap-fallback"` and the row has no entity-specific
candidate evidence, classify as `generic-fallback`.

Use existing notes to distinguish the reason:

- `fallback:baseline-quality`
- `fallback:task-ready`
- `selected:generic-baseline`
- `selected:diversity-rotation`

Do not classify a row as direct or adjacent solely because it has strong
baseline/task metadata.

### 3. Direct Fit

Classify as `direct-fit` when at least one strong context signal and one task or
modality signal are present.

Strong context signals:

- exact project-context token appears in benchmark metadata or matched facets;
- benchmark title/id/source dataset carries a project disease/system token;
- entity id/title/body and benchmark metadata share a non-generic context token;
- project is a method/data-source project and benchmark is directly about that
  data source or method.

Task or modality signals:

- matched facet contains a high-value modality or signal type;
- task type directly matches the entity need;
- task support is `supported`;
- row is `opportunity-relative` with nonzero facet overlap.

Examples:

- `cptac-gbm-2021-proteogenomics` for cBioPortal cross-sectional omics
  questions: direct method/data-source fit.
- `cptac-gbm-2021-proteogenomics` for an entity explicitly discussing
  cross-sectional omics/proteomics in a cancer data-source project: direct
  method/modality fit.

### 4. Adjacent Fit

Classify as `adjacent-fit` when task/modality fit is good but context is broader
or nearby rather than exact.

Examples:

- BRCA outcome benchmarks for multiple myeloma outcome-prediction entities.
- GBM proteogenomics for general cancer cross-modal proteomics questions.

Adjacent fit should carry warnings such as:

- `cross-disease`
- `cross-tissue`
- `cell-line-vs-primary`
- `simulated-vs-observed`

V1 can infer these warnings from simple metadata cues only. If the evidence is
not present, omit the warning rather than guessing.

### 5. Method Fit

Classify as `method-fit` when the benchmark task/method is plausible but the
project/entity context is weak.

Examples:

- Network reconstruction benchmark for a project discussing causal or temporal
  mechanisms without matching disease/system context.
- Cross-modal prediction benchmark for a non-cancer project where the modality
  is useful but benchmark biology is not.

### 6. Out of Context

Classify as `out-of-context` when benchmark/project domains conflict or the row
exists only because of broad terms that should not imply actionability.

Examples:

- Biology-only fallback rows in `~/d/natural-systems` without explicit biology
  entity context.
- Disease-specific rows in a data-source project unless the entity concerns that
  disease/source.

## Context Token Sets

V1 should avoid a large curated ontology. Instead, define small deterministic
sets and keep them auditable:

- `project_context_tokens`: derived from project root leaf, `science.yaml` `id`
  and `name`, and entity id stems.
- `entity_context_tokens`: high-signal entity tokens after existing stop/broad
  filtering.
- `benchmark_context_tokens`: tokens from benchmark id/title/domains/source
  datasets/limitations, excluding existing broad facet stopwords.

Do not treat the following as context-fit evidence by themselves:

- `biology`
- `cancer`
- `model`
- `data`
- `analysis`
- `cross-sectional`
- `clinical`
- `genomics`
- `multi-omic`

These can remain useful facets, but they should not alone promote a row to
`direct-fit`.

## Sorting and Triage

`science benchmark tests` should preserve existing default sorting in v1 unless
we explicitly decide to change it during implementation review.

`science benchmark test-triage` should use context-fit inside existing buckets:

1. Existing bucket priority still wins (`run-now`, `stage-next`,
   `metadata-needed`, `blocked-or-reference`, `fallback-diagnostic`).
2. Within a bucket, sort by `context_fit` order.
3. Then sort by current score/readiness/source tie-breakers.

This keeps the triage queue action-focused without making raw reports unstable.

## CLI Surface

Add optional filters:

```bash
science benchmark tests --context-fit direct-fit
science benchmark test-triage --context-fit direct-fit
science benchmark test-triage --context-fit direct-fit --context-fit adjacent-fit
```

Filter semantics:

- Multiple `--context-fit` flags are ORed.
- Invalid values raise a Click error.
- `--context-fit` applies after existing filters such as `--source`,
  `--readiness`, `--state`, `--benchmark`, and `--facet`.

No new command is needed in v1.

## JSON Contract

`benchmark_tests_report()`:

- row-level `context_fit`, `context_fit_reasons`, `context_fit_warnings`;
- `summary.context_fit_counts`;
- `filters.context_fit` only when the filter is supplied.

`benchmark_test_triage_report()`:

- row-level fields preserved in buckets;
- `summary.context_fit_counts` computed over upstream filtered rows before
  triage-only suppression;
- `context_fit_counts_by_bucket`: a required mapping from triage bucket name to
  context-fit count mapping. Build it from the same bucketed rows used for
  output so it cannot disagree with visible bucket membership.

`benchmark gaps`:

- no v1 row changes required.
- Future work can project context fit onto gap candidates once benchmark-test
  behavior is calibrated.

## Error Handling

- Invalid context-fit filter values fail early with a clear CLI error.
- Missing project metadata degrades to root-leaf and entity-token evidence.
- Invalid benchmark metadata that prevents row construction should continue to
  fail through existing validation/report paths.
- If a row cannot be classified because required fields are missing, classify as
  `method-fit` only when task/method evidence exists; otherwise classify as
  `generic-fallback` for fallback rows or `out-of-context` for non-fallback rows
  with no context evidence.

No silent fallback to `direct-fit` is allowed.

## Testing

Unit tests:

- direct-fit row when project/entity context and task/modality evidence align.
- adjacent-fit row for cross-disease but same broad task/modality.
- method-fit row for task/modality match without biological context.
- generic-fallback row for fallback-only candidate selected by baseline/task
  quality.
- blocked-fit row for non-fallback blocked task support.
- broad tokens such as `biology`, `cancer`, `clinical`, and `genomics` do not
  promote direct-fit alone.
- context-fit filter OR semantics.
- triage sorting respects bucket first, then context-fit order.

CLI tests:

- `benchmark tests --context-fit direct-fit --format json`.
- `benchmark test-triage --context-fit adjacent-fit --format json`.
- invalid `--context-fit` value errors.
- table output includes context-fit in a compact way without making existing
  columns unreadable.

Calibration smoke:

- Run the four active projects with:
  - `science benchmark tests --commons --exclude-fallback --state concrete`
  - `science benchmark test-triage --commons`
  - `science benchmark tests --commons --context-fit direct-fit`
- Confirm CPTAC GBM remains visible for multiple myeloma/cBioPortal.
- Confirm natural systems does not get large direct-fit biology fallback output.
- Confirm MMRF blocked rows stay explainable but do not dominate run-now work.

## Alternatives Considered

### Add More Benchmark Recipes First

This remains useful, especially for `sciplex3`, but recent calibration shows
that adding one runnable benchmark can improve only a few rows while fallback
and cross-context noise remains. More recipes should follow clearer
actionability ranking.

### Expand the Hint Lexicon First

Hint lexicon improvements help entity-specific gap candidates, but they do not
solve disease/system context mismatch. They also risk promoting generic biology
terms if context-fit is not separated.

### Change Scoring Directly

Changing `relative_score` or `candidate_score` now would mix raw matching with
presentation policy. A projection layer is safer: it is visible, filterable, and
calibratable without invalidating existing reports.

## Success Criteria

- Existing benchmark tests/gaps reports remain available with additive fields.
- Triage rows become easier to interpret because generic fallback and
  cross-context rows are labeled explicitly.
- Multiple myeloma and cBioPortal retain useful CPTAC GBM rows.
- Natural systems no longer appears to have direct biology benchmark work unless
  entity text supplies explicit context evidence.
- The four-project calibration can explain the change in terms of
  `context_fit_counts`, not subjective table inspection.

## Open Follow-Up

After v1 calibration, decide whether to:

1. promote context-fit into gap-candidate ranking;
2. add dedicated project context metadata to `science.yaml`;
3. tune benchmark metadata for disease/system/source context;
4. stage another deposit such as `sciplex3`.
