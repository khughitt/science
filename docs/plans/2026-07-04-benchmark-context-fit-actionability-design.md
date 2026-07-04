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

Context-fit is computed **at row-build time**, not as a projection over the
returned public rows. The classifier needs benchmark source metadata (`domains`,
`modalities`, `signal_types`, `source_datasets`, `limitations`) that lives on the
`OpportunityDataset` (`context.dataset.*`) and is deliberately *not* carried on
`BenchmarkTestRow`. That `context` object is already in scope inside
`_benchmark_test_row` / `_rows_for_context_tasks` / `_rows_for_gap_candidate`,
which is where classification runs. The additive fields are then surfaced on the
row for downstream consumers; nothing downstream needs to reload benchmark
sources or re-derive context.

Raw matching remains the source of truth for "what matched." Context-fit is a
separate axis for "how actionable is this match in this project?" — additive and
frozen against the scoring stack, but populated where the evidence is available,
not bolted on after the row is finalized.

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

Classification must be **total and deterministic**: every well-formed row
receives exactly one value, and the same inputs always yield the same value.
The narrative rules below are the intent; the following decision table is the
normative spec, defined over four deterministic predicates:

- `strong_context` — the row shares at least one **specific** (non-broad)
  context token between the project/entity token set and the benchmark token
  set (see [Context Token Sets](#context-token-sets)). Broad tokens
  (`biology`, `cancer`, …) never satisfy this predicate.
- `broad_context` — no specific shared token, but the row shares a
  domain-level/broad context token *or* carries at least one cross-* warning
  cue (see Rule 4). This is what separates "biologically adjacent" from "no
  context at all."
- `task_signal` — at least one task/modality signal is present: a high-value
  modality or signal type in `matched_facets`, `task_support_state ==
  "supported"`, task type matching the entity need, or an
  `opportunity-relative` row with nonzero facet overlap. **The mere presence of
  a `task_type` string is not a signal** — the task type counts only when its
  tokens intersect the entity's need tokens. Treating any task as a signal makes
  `task_signal` true for nearly every row and collapses the `method-fit` /
  `out-of-context` boundary (Rule 5 vs Rule 7).
- `domain_conflict` — the benchmark's domain and the project's domain are both
  present and disjoint (e.g. a biology-only benchmark in a non-biology project).
  **Implementation note:** this predicate must compare a small **coarse
  domain-label set** (e.g. `biology`, `cancer`, `health`, `natural-systems`,
  `physical`) that is matched *before* broad-token stripping — because the very
  tokens that name a domain (`biology`, `cancer`) are the ones on the broad
  suppression set. If `domain_conflict` is computed over already-broad-stripped
  tokens it is vestigial: the benchmark domain set is almost always empty and
  the predicate never fires. Absence of a shared domain is *not* a conflict
  unless both sides carry an explicit coarse domain label.

  V1 consequence to accept or revisit: with `domain_conflict` scoped to this
  coarse set, a biology benchmark surfacing in a project whose *only* domain
  signal is also "biology" (via a broad token) will land in `method-fit`, not
  `out-of-context`. That still removes it from `direct-fit`/actionable queues
  (meeting the natural-systems success criterion), but it does not label it as
  an outright mismatch. If v1 calibration shows biology `method-fit` noise
  dominating non-biology projects, tighten the coarse domain comparison in a
  follow-up rather than in this slice.

Evaluate top to bottom; first matching row wins. `—` means the predicate is not
consulted for that row.

| # | `priority_source` / block | `strong_context` | `broad_context` | `task_signal` | `domain_conflict` | → class |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | blocked, with any project/entity evidence | — | — | — | — | `blocked-fit` |
| 1b | blocked, fallback-only, no evidence | — | — | — | — | `generic-fallback` (+ `blocked-support-fallback`) |
| 2 | `gap-fallback`, no specific context token | — | — | — | — | `generic-fallback` |
| 3 | any non-fallback | yes | — | yes | — | `direct-fit` |
| 6 | any non-fallback | — | — | — | yes | `out-of-context` |
| 4 | any non-fallback | no | yes | yes | no | `adjacent-fit` |
| 5 | any non-fallback | no | no | yes | no | `method-fit` |
| 7 | **terminal default** (matched no row above) | — | — | — | — | `out-of-context` |

Rule 6 is placed above 4/5 so a genuine domain conflict always wins over a
broad-context adjacency claim. Rule 7 is an **unconditional** catch-all: any
non-fallback row not matched by Rules 3–6 is `out-of-context`. This makes the
table total by construction — note in particular that a row with context but no
`task_signal` (nothing runnable) lands here, since without a task signal the
match is not actionable regardless of context strength. Implementations must
assert totality (see [Testing](#testing)).

(The `### N` subsections below give the narrative intent per class; where prose
and table disagree, the table governs.)

### 1. Blocked Override

If `task_support_state == "blocked"` or `readiness_label == "blocked"`, classify
as `blocked-fit` unless the row has no project/entity evidence and is fallback
only. In that fallback-only case classify as `generic-fallback` and retain a
warning:

- `blocked-support-fallback`

This preserves the useful fact that MMRF is blocked while avoiding hundreds of
blocked fallback action items.

### 2. Generic Fallback

If `priority_source == "gap-fallback"` and the row shares **no specific
(non-broad) context token** between its benchmark token set and the
project/entity token set, classify as `generic-fallback`.

Note that `gap-fallback` is *defined* as "carries a `fallback:` reason note"
(`_is_fallback_candidate`), which is already mutually exclusive with an
entity-matched `gap-candidate`. The context-token clause is therefore the real
discriminator: it rescues the rare fallback row that coincidentally shares a
specific disease/system/source token with the project, letting it fall through
to Rules 3–5 rather than being labeled generic. Do **not** treat baseline/task
metadata quality as context evidence here.

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

These warnings are inferred by comparing **specific tokens**, never domain-level
broad tokens. `cross-disease` in particular cannot use the shared `cancer`
domain (it is on the broad-exclusion set): it fires only when a specific disease
token on the benchmark side (from `benchmark_id`/`benchmark_title`/
`source_datasets`, e.g. `brca`, `breast`) differs from a specific disease token
on the project/entity side (e.g. `myeloma`, `mm`), with both present. Each
warning names its two sources explicitly:

- `cross-disease` — benchmark disease token vs project/entity disease token.
- `cross-tissue` — benchmark tissue/system token vs project/entity tissue token.
- `cell-line-vs-primary` — benchmark `source_datasets`/`limitations` cue (e.g.
  `cell-line`) vs a primary-tissue cue in the entity.
- `simulated-vs-observed` — benchmark `signal_types`/`limitations` cue (e.g.
  `simulated`, `synthetic`) vs observed-data context in the entity.

V1 infers these from those explicit metadata cues only. If both specific tokens
are not present, omit the warning rather than guessing.

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

V1 should avoid a large curated ontology. Instead, derive small deterministic
sets from the **existing** normalization pipeline and keep scoring-facing broad
tokens separate from context-fit-only broad tokens:

- Reuse `_normalize_token` / `_SYNONYMS`, `_STOP_TOKENS`, and
  `_token_evidence_from_text` for tokenization (same pipeline as benchmark
  matching, so the sets agree with what already matched).
- Reuse the existing scoring-facing broad-token suppression sets —
  `ENTITY_SUPPRESSED_TOKENS` and `BROAD_NON_SCOREABLE_FACETS` — as the base
  definition of "broad."
- Add a small `CONTEXT_BROAD_TOKENS` extension for broad context terms that
  should not promote `direct-fit` (`clinical`, `genomics`, `multi-omic`, etc.).
  This set is intentionally **not** used by `_scoreable_facet_tokens`, because
  context-fit must not change raw opportunity matching or scores.

Then define:

- `project_context_tokens`: derived from project root leaf, `science.yaml` `id`
  and `name`, and entity id stems (this reuses the existing
  `project_context_tokens` derivation in `_opportunity_analysis`).
- `entity_context_tokens`: high-signal entity tokens after `ENTITY_SUPPRESSED_TOKENS`
  filtering.
- `benchmark_context_tokens`: tokens from benchmark id/title/domains/source
  datasets/limitations, minus `CONTEXT_BROAD_TOKENS`.

A token that survives the context broad/stop filters is "specific"; a token
these sets suppress is "broad." The `strong_context` predicate requires a
*specific* shared token.

If a term is genuinely broad but not yet in the shared suppression sets (e.g.
`cross-sectional`, `multi-omic`), add it to `CONTEXT_BROAD_TOKENS`, not
`BROAD_NON_SCOREABLE_FACETS`, so benchmark matching stays stable.
Terms to verify are covered by the shared sets before implementation:

- `biology`, `cancer`, `model`, `data`, `analysis`, `cross-sectional`,
  `clinical`, `genomics`, `multi-omic`.

These can remain useful facets, but must not alone promote a row to
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

Note that `_benchmark_test_triage_bucket` already routes on `priority_source`
and `task_support_state`: `gap-fallback` → `fallback-diagnostic`, blocked →
`blocked-or-reference`. So the `generic-fallback` and `blocked-fit` labels
largely restate bucket membership, and those two buckets will be near-uniform in
`context_fit`. Context-fit ordering therefore does its real work inside the
`run-now`, `stage-next`, and `metadata-needed` buckets, where it adds the
biological/context axis the buckets do not encode. The labels are still worth
emitting on fallback/blocked rows for the JSON counts and cross-view
consistency, but the design does not expect them to re-sort those buckets
meaningfully.

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
- blocked fallback-only row with no context evidence classifies as
  `generic-fallback` and carries the `blocked-support-fallback` warning
  (Rule 1b), not `blocked-fit`.
- totality: over a representative row corpus, every row receives exactly one
  context-fit value and never an empty/unset value.
- classification reads benchmark source metadata (`domains`/`modalities`/
  `limitations`) that is not present on `BenchmarkTestRow`, guarding against a
  refactor that reduces classification to a post-hoc projection over public rows.
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
