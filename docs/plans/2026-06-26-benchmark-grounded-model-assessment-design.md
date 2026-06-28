---
id: "plan:2026-06-26-benchmark-grounded-model-assessment-design"
type: "plan"
title: "Benchmark-grounded model assessment for Science"
status: "proposed"
created: "2026-06-26"
updated: "2026-06-27"
related:
  - "plan:2026-06-26-dataset-catalog-triage-pack-design"
  - "plan:2026-06-26-feedback-telemetry-adaptation-design"
  - "plan:2026-06-21-catalog-datasets-design"
  - "plan:2026-05-31-belief-profile-design"
---

# Benchmark-grounded model assessment for Science

## Revision note (2026-06-27)

Phase 1's `benchmark` metadata block is refined and narrowed for a first
implementable v1:

- **Descriptive-only.** v1 ships the catalog metadata block plus a commons seed
  catalog. It adds **no** `RelationKind`, no materialize changes, and no belief
  scoring. A benchmark still reaches belief only the existing way — via an
  evidence-line with `evidence_type: benchmark` and `dataset_usage`. Belief
  mapping, belief-tests, gap maps, and outcomes (Phases 2–3 below) are
  unchanged and deferred.
- The block becomes plural, adds `signal_types` and an optional `tasks[]`, drops
  `scope`, defers the `informativeness` rubric, and treats `related_beliefs` /
  `source_datasets` as **free-text references only** (documentation, not graph
  edges).
- A new **Commons seed catalog** section defines a diversity-first seed set of
  shared `dataset:*` records.

See the updated *Benchmark metadata* and *Commons seed catalog* sections; the
remainder of this design (belief mapping, belief-tests, cross-project analysis)
is the post-v1 roadmap.

## Purpose

Science is strong at building computational workflows and aggregating evidence
from multiple sources. It is weaker at testing whether the resulting beliefs,
mechanistic models, and project-level representations actually predict or
explain held-out empirical structure.

This design adds benchmark-grounded model assessment: a way to catalog known
benchmark datasets, map them to project beliefs and mechanisms, identify gaps
where no suitable benchmark exists, and run explicit belief tests against
benchmarks. The goal is to make Science projects more empirically accountable:
not just "what does the literature suggest?" but "what should this model predict,
and where can we test that prediction?"

## Goals

- Catalog benchmark datasets relevant to a project, topic, or wider field.
- Represent what each benchmark can and cannot test.
- Link benchmarks to hypotheses, propositions, mechanisms, prediction tasks, and
  known failure modes.
- Make benchmark gaps visible as first-class research needs.
- Support small benchmark evaluation plans that test project beliefs or models.
- Use benchmark outcomes to study which Science project patterns correlate with
  successful prediction or explanation.
- Treat perturbation and time-series datasets as high-value benchmarks because
  they test causal and temporal structure more directly than static association
  datasets.

## Non-goals

- No claim that benchmark performance is the only measure of scientific value.
- No automatic truth assignment to hypotheses based on one benchmark.
- No benchmark leaderboard in v1.
- No requirement that every project have runnable benchmark evaluations before
  it can proceed.
- No broad benchmark data hosting. Science catalogs and routes benchmarks; it
  does not become a data warehouse.

## Core concept

A benchmark is a dataset plus an evaluation interpretation.

The same raw dataset may be a normal `dataset:*` in one context and a benchmark
in another. Benchmark status depends on what question it tests, what target is
held out, what label or endpoint is treated as ground truth, and what baseline
or competing model defines meaningful performance.

Therefore, do not create a separate top-level entity kind in v1. Instead, model
benchmark information as structured metadata attached to `dataset:*` records and
as evaluation-plan documents that reference those datasets.

## Benchmark metadata

Extend dataset catalog semantics with an optional, additive `benchmark` block on
`dataset:*` entities. The block is descriptive: it says what a dataset can test
and how well, so a human or agent can decide what to use for evaluation. It does
not change the graph or belief in v1.

```yaml
benchmark:
  # --- dataset-wide facets (the "catalog" layer; always allowed) ---
  domains: ["biology", "omics"]
  modalities: ["single-cell-rna-seq", "perturbation"]            # free-text v1
  signal_types: ["perturbation", "cross-context-generalization"] # empirical structure present
  benchmark_kinds: ["perturbation-response"]                     # intended evaluation (Benchmark classes table)
  source_datasets: ["GEO:GSE..."]                               # free-text refs to underlying data
  related_beliefs:                                              # OPTIONAL, free-text refs only (no edges in v1)
    - "hypothesis:0005-dynamic-homeostasis"
  notes:
    - "Strong perturbation-response signal; weak for temporal dynamics."
  limitations:
    - "L1000 landmark genes with inferred full profiles."

  # --- evaluable specifics: present ONLY when a task is actually defined ---
  tasks:
    - id: "l1000-drug-response"          # slug-like, unique within this dataset
      task_type: "perturbation-response"
      prediction_target: "post-treatment expression signature"
      held_out_unit: "compound"
      metric: "rank correlation"
      baseline: "nearest-neighbor signature baseline"
      ground_truth:
        type: "measured-outcome"
        description: "post-perturbation expression state"
      # optional, sparse structure-specific escape hatches (free-text v1):
      intervention: "small-molecule compound treatment"  # perturbation tasks
      timepoints: ["6h", "24h"]                          # time-series tasks
      contexts: ["A549 cell line"]                        # cohort/tissue/species/assay
      interpretation_limits:
        - "L1000 measures landmark genes."
```

Fields are sparse and additive. A record with only `domains`, `modalities`, and
`benchmark_kinds` is still useful; `tasks[]` is omitted until a task is actually
specified.

Design choices for v1:

- **Plural facets** (`domains`, `modalities`, `signal_types`) because most useful
  omics benchmarks cross boundaries.
- **`signal_types` vs `benchmark_kinds` are separate axes.** `signal_types`
  describes what empirical structure exists (perturbation, temporal,
  longitudinal, multimodal, spatial, cross-context, calibration); this is why a
  non-benchmark dataset can still be informative. `benchmark_kinds` describes how
  we intend to evaluate, drawing from the *Benchmark classes* table below.
- **`tasks[]` owns the evaluable specifics.** When a task is defined, the
  per-task fields (`task_type`, `prediction_target`, `held_out_unit`, `metric`,
  `baseline`, `ground_truth`, `interpretation_limits`) live there. The block does
  not duplicate them as block-level `endpoints` / `held_out_units` /
  `suitable_for`; those are dropped.
- **`held_out_unit` is included early** because it is the practical difference
  between "a dataset exists" and "a model can be tested."
- **Stable task identity.** `tasks[].id` is slug-like and unique *within* one
  dataset record. The canonical query/render identity of a task is
  `dataset:<slug>#<task-id>`, which is globally stable because dataset slugs are
  globally unique. Validation enforces local uniqueness and slug shape; the
  `#`-qualified form is what reports and CLI output emit.
- **Optional structure-specific task fields.** `intervention`, `timepoints`, and
  `contexts` are sparse, optional, free-text fields on a task. They give
  perturbation / time-series / cross-context tasks a place to record the metadata
  that makes them strong tests, without forcing it on simpler tasks. They are the
  fields the perturbation/time-series validation warning checks against.
- **`related_beliefs` and `source_datasets` are free-text reference lists only.**
  They are documentation, not graph edges, in v1. Phase 2 promotes the
  belief link to real typed edges and belief-tests.
- **No `scope` field.** It overlapped the existing `EntityScope` (project/shared)
  and the dataset `tier` (`use-now` / `evaluate-next` / `track`). A seed's
  commons-vs-local home and `tier` already carry that information.
- **`informativeness` rubric deferred.** A multi-axis qualitative score
  (causal/temporal/modality-novelty/etc.) is curation theater nobody will
  maintain consistently across a small seed set. v1 uses free-text `notes`;
  specific axes can be promoted to structure once the seed set shows which ones
  actually drive a decision.

### Vocabulary strategy

`modalities`, `signal_types`, `benchmark_kinds`, `task_type`, `metric`, and
`ground_truth.type` are **free-text strings in v1**. This is deliberate: the seed
set is a design stress set whose goal is to discover the real vocabulary before
hardening it. The codebase otherwise makes enums the SSOT (`EvidenceType`,
`dataset_class`, `tier`, `KindCategory`), so v2 should harvest the terms that
actually appear across seeds and promote the stable ones to `StrEnum`s with a
reconciliation gate, exactly as `EvidenceType` and the kind descriptors do today.
`benchmark_kinds` already has a strong candidate vocabulary in the *Benchmark
classes* table.

## Benchmark classes

These are the candidate controlled vocabulary for `benchmark_kinds` (free-text in
v1; promotion target for v2). Initial benchmark classes:

| Class | Purpose |
|---|---|
| `static-association` | Test cross-sectional associations, classifications, or signatures. |
| `perturbation-response` | Test response to interventions such as CRISPR, drug, knockdown, stimulation, or environmental shift. |
| `time-series` | Test temporal dynamics, ordering, trajectories, or delayed effects. |
| `longitudinal-cohort` | Test patient/sample trajectories across repeated measurements. |
| `cross-context-generalization` | Test whether a model learned in one cohort, tissue, species, assay, or project transfers to another. |
| `mechanism-discrimination` | Distinguish competing mechanisms that make different observable predictions. |
| `calibration` | Assess whether scores, probabilities, or uncertainty estimates are calibrated. |

Perturbation and time-series classes should be highlighted in reports because
they provide stronger tests of causal or dynamic claims than static benchmarks.

## Commons seed catalog (v1)

v1 ships a small, curated seed set of shared `dataset:*` records that carry a
`benchmark` block. These live in the commons (`~/d/science-commons/`); their
canonical entity files use `scope: shared` when the field is present, and the
inventory projection exposes them as `scope: cross-project` (per
`EntityScope.SHARED` in `science_tool.commons.inventory`). They are consumed by projects through
the existing overlay-merge path — `dataset` is already a commons type, so no new
mechanism is introduced. This is the first real population of the shared dataset
catalog.

**Goal: a design stress set, not a complete atlas.** The seed set is sized to
exercise the schema across different modalities, access patterns, and evaluation
styles before the vocabulary is hardened.

Composition target (~6–10 records), diversity-first:

- Span several **modalities** (e.g. perturbation single-cell, bulk expression,
  proteomics, spatial, multimodal).
- Span **access patterns** via the shipped `dataset_class`: some `deposit`
  (obtainable benchmark data), some `reference` (benchmark portals, challenge
  registries, leaderboards), optionally a `pointer` (tracked-but-not-yet-runnable
  benchmark candidate). Commons promotion already follows class rules, so
  reference benchmarks can be seeded without a materialized datapackage.
- Span **evaluation styles**: some records carry a fully-specified `tasks[]`
  entry; others are facets-only (benchmark-capable, no task yet) to verify the
  block is useful in its sparse form.
- Each record is sparse but high-quality enough to serve as an authoring example.

Provisional seed set (the deliberate stress-set under design; membership may be
adjusted in the implementation plan but the spread it covers should be
preserved):

| slug | resource | dataset_class | modalities | signal_types | benchmark_kinds | task completeness | why in the set |
|---|---|---|---|---|---|---|---|
| `sciplex3` | Srivatsan 2020 sci-Plex (drug perturbation scRNA-seq) | pointer | single-cell-rna-seq, perturbation | perturbation, cross-context-generalization | perturbation-response | full task | canonical perturbation-response with held-out compounds; tracked-but-not-yet-staged (a `pointer` carrying a full task) |
| `l1000-cmap` | LINCS L1000 Connectivity Map (clue.io portal) | reference | bulk-expression (landmark) | perturbation, cross-context-generalization | perturbation-response | full task | reduced-transcriptome benchmark via a portal; concrete GEO export becomes a deposit later |
| `dream-perturbation` | a DREAM challenge perturbation track | reference | varies | perturbation | perturbation-response, mechanism-discrimination | facets-only | challenge registry as a `reference`-class benchmark portal |
| `human-cell-atlas` | Human Cell Atlas | reference | single-cell-rna-seq, spatial, multimodal | cross-context-generalization | static-association, cross-context-generalization | facets-only | atlas/knowledgebase portal; multimodal breadth; no single task |
| `cptac-proteogenomics` | CPTAC proteogenomics (PDC portal) | reference | proteomics, bulk-expression, multimodal | multimodal, longitudinal | static-association, mechanism-discrimination | full task | proteomics + multimodal axis via a data-commons portal |
| `tahoe-100m` (or similar) | large perturbation atlas (pointer until staged) | pointer | single-cell-rna-seq, perturbation | perturbation, temporal | perturbation-response, time-series | facets-only | exercises `pointer` class + time-series signal not yet runnable |

This table covers reference and pointer classes; single-cell, bulk, proteomics,
spatial, and multimodal modalities; perturbation, temporal, longitudinal,
cross-context, and multimodal signal types; and both fully-tasked and facets-only
records. That spread is the product decision; locking it here prevents it from
being re-decided under implementation pressure.

Schema note: the v1 commons seeds carry **no `deposit`** record. A canonical
commons deposit requires a content-addressed `datapackage.yaml` (relative `path` +
`hash` + `bytes`), which only exists once real data is staged — out of scope for a
descriptive benchmark catalog. So portal-backed benchmarks (`l1000-cmap`,
`cptac-proteogenomics`, the DREAM registry, the Human Cell Atlas) are `reference`,
and real-but-unstaged datasets (`sciplex3`, `tahoe-100m`) are `pointer`. The
`deposit` class is still exercised — by the model/schema/validation unit tests,
which use synthetic deposit frontmatter. The implementation also relaxes the
commons adapter so `reference`/`pointer` dataset directories no longer require a
`datapackage.yaml` sibling (it stays required for `deposit`), matching the
triage design's promotion rules.

The seed set is content, not schema: its exact membership can be finalized during
implementation. Its purpose is to validate the block shape and seed the commons
catalog, and to harvest the real vocabulary for the v2 enum-promotion step.

## Benchmark catalog workflow

Add a command/skill workflow, tentatively `/science:catalog-benchmarks`, with
four phases:

1. **Topic scan.** Given a project, field, or hypothesis cluster, find benchmark
   datasets already in the project catalog and likely external benchmarks.
2. **Benchmark classification.** For each candidate, classify benchmark kind,
   modality, endpoints, access, and limitations.
3. **Belief mapping.** Link each benchmark to hypotheses, propositions,
   mechanisms, or prediction tasks it can test.
4. **Gap map.** Identify important beliefs or mechanisms with no suitable
   benchmark, and classify the missing benchmark shape.

This command should reuse dataset catalog infrastructure. Benchmarks are a
specialized view over datasets, not a parallel data catalog.

## Benchmark gap map

Benchmark gaps are first-class outputs:

```yaml
id: "benchmark-gap:dynamic-immune-recovery-perturbation"
type: "benchmark-gap"
target:
  - "hypothesis:0005-dynamic-homeostasis"
missing_benchmark_kind:
  - "perturbation-response"
  - "time-series"
required_modalities:
  - "proteomics"
  - "single-cell-rna-seq"
required_context:
  species: "human"
  condition: "post-acute infection"
why_needed: "Current evidence is mostly observational; no benchmark tests recovery after controlled perturbation."
candidate_paths:
  - "search public perturbation repositories"
  - "compile derived benchmark from existing longitudinal cohorts"
```

Whether benchmark gaps should become a formal entity kind can be deferred. In
Phase 2 they can live as rows in reports or `docs/benchmark-gaps/*.md`
documents before Science promotes them to a formal entity kind.

## Belief tests

A belief test is a small evaluation plan that maps a project belief to a
benchmark prediction.

Example:

```yaml
id: "belief-test:stress-response-state-dependence"
type: "plan"
plan_kind: "belief-test"
beliefs:
  - "proposition:stress-response-is-state-dependent"
benchmarks:
  - "dataset:sciplex3"
prediction:
  statement: "Baseline cell state should predict perturbation response direction."
metric:
  name: "held-out response rank correlation"
  minimum_interpretable_effect: 0.2
baselines:
  - "cell-type-only model"
  - "random gene-set baseline"
outcomes:
  supports_if: "model exceeds cell-type-only baseline on held-out perturbations"
  disputes_if: "model fails to exceed baseline or reverses predicted direction"
```

Belief tests should route to existing workflow machinery:

- `catalog-benchmarks` finds and maps benchmark candidates.
- `plan-analysis` or `plan-pipeline` designs the runnable evaluation.
- `pre-register` locks prediction, metric, and interpretation thresholds when
  the test is confirmatory.
- `interpret-results` records outcome and updates propositions/evidence.

## Evaluation outputs

Benchmark evaluations should produce:

- A normal workflow output package when code runs.
- A `belief-test` or plan document tying the benchmark to the tested beliefs.
- Evidence lines or findings that support, dispute, or qualify propositions.
- A benchmark result summary:

```yaml
benchmark_result:
  benchmark: "dataset:sciplex3"
  belief_test: "belief-test:stress-response-state-dependence"
  outcome: "supports|disputes|mixed|inconclusive"
  metric_values:
    held_out_rank_correlation: 0.31
  baselines:
    cell_type_only: 0.12
  interpretation: "supports state-dependent perturbation response in this context"
```

This keeps benchmark results integrated with the existing proposition/evidence
model instead of creating a separate scoring universe.

## Cross-project success analysis

Once benchmark outcomes exist, Science can ask which project patterns correlate
with better benchmark performance.

Candidate explanatory features:

- Dataset access and stageability at planning time.
- Presence of perturbation/time-series benchmarks.
- Number of independent evidence lines per proposition.
- Whether hypotheses had explicit falsifiable predictions.
- Whether pre-registration existed before evaluation.
- Validation health at execution time.
- Feedback/telemetry friction around the workflow.
- Reuse of commons datasets or shared benchmark definitions.

Analysis must adjust for data availability and benchmark coverage. A project in
a field with no useful benchmarks should not be judged the same as a project
with abundant public perturbation datasets.

This is a later-phase analysis surface, not part of v1 implementation. The v1
requirement is to record enough structured benchmark metadata that such analysis
becomes possible once later phases add outcomes.

## Commands and surfaces

### `/science:catalog-benchmarks`

Agent workflow:

- discover field/project benchmarks;
- classify benchmark kinds and modalities;
- link to beliefs;
- create benchmark gap map;
- recommend next belief tests.

### `science benchmark list` (v1)

Read-only query over dataset benchmark metadata:

```bash
science benchmark list --domain biology
science benchmark list --kind perturbation-response
science benchmark list --belief-ref-text hypothesis:0005   # v1: free-text match
science benchmark list --format json
```

`--belief-ref-text` is honest about v1 semantics: it does a case-insensitive
exact-token match against the free-text `related_beliefs` strings on each block.
It does **not** resolve graph edges or validate that the referenced entity
exists. A graph-aware `--related` flag (real reference semantics) is deferred to
Phase 2, once `related_beliefs` is promoted to typed edges.

### `science benchmark gaps` (Phase 2)

Belief-gap reporting depends on the belief mapping introduced in Phase 2 and is
not part of the descriptive-only v1. Report benchmark gaps by project, domain,
mechanism, or hypothesis:

```bash
science benchmark gaps --entity hypothesis:0005
science benchmark gaps --facet time-series
```

### `science benchmark tests` (Phase 2)

Belief-test plans arrive in Phase 2; this command is not part of v1. List
belief-test plans and outcomes:

```bash
science benchmark tests --status planned|run|interpreted
science benchmark tests --benchmark dataset:sciplex3
```

These CLI surfaces are query/report tools. Authoring can initially happen via
normal dataset and plan creation until the model stabilizes.

## Integration with dataset catalog

The dataset catalog triage pack introduces dataset classes such as `deposit`,
`reference`, and `pointer`. Benchmarks compose with those classes:

- A runnable benchmark is usually a `deposit`.
- A benchmark registry or leaderboard can be a `reference`.
- A not-yet-materialized benchmark candidate can be a `pointer`.

Benchmark reports should include access and runtime stageability from the
dataset catalog. A benchmark that cannot be accessed or staged should not be
recommended for immediate belief testing without an acquisition step.

## Integration with feedback and telemetry

Telemetry should eventually answer:

- Which benchmark workflows fail most often?
- Which benchmark classes are often missing in a field?
- Which commands precede successful benchmark tests?
- Which validation failures predict failed or inconclusive benchmark outcomes?

Feedback should capture benchmark workflow friction:

```bash
science feedback add \
  --target "command:catalog-benchmarks" \
  --category gap \
  --summary "No natural place to record perturbation benchmark limitations"
```

## Implementation phases

### Phase 1: benchmark metadata, commons seeds, and reports

Descriptive-only. No `RelationKind`, materialize, or belief changes.

- Add typed `BenchmarkBlock` + `BenchmarkTask` models in `science_model`
  (`entities.py`, next to `AccessBlock` / `DerivationBlock`), and an optional
  `DatasetEntity.benchmark` field (appended last, for snapshot/`_key` stability).
- Coerce the block in `frontmatter.py` (`_coerce_benchmark`), wired into the
  existing dataset-field extraction.
- Extend `mixin-dataset-1.0.json` with the optional `benchmark` object; keep the
  free-text fields unconstrained in v1.
- The block is **not emitted to `graph.trig`** in v1 — it is catalog metadata
  read by tooling/validators and humans, keeping the change behavior-neutral for
  the knowledge graph and belief.
- Author the commons seed set (see *Commons seed catalog*) as `scope: shared`
  dataset entities.
- Add query helpers for benchmark metadata and `science benchmark list`.
- Add a **catalog coverage summary** that reports benchmark *facets* only —
  counts of benchmark-capable datasets by `domains` / `modalities` /
  `benchmark_kinds` / `dataset_class`, and which records have tasks vs are
  facets-only. This is a metadata roll-up, **not** a belief-gap map: it never
  reports which hypotheses/propositions lack a benchmark.
- Add `/science:catalog-benchmarks` command doc covering the v1 scope only:
  discover, classify, and author benchmark metadata + facet coverage. The
  belief-mapping and gap-map steps described in the *Benchmark catalog workflow*
  section are Phase 2 and are flagged as such in the doc.

Belief-gap reporting (which hypotheses/propositions lack a suitable benchmark) is
explicitly **Phase 2**, since it depends on the belief mapping this phase does not
build.

### Phase 2: belief-test plans

- Define `plan_kind: belief-test` conventions.
- Add templates/examples for belief tests.
- Link belief tests to datasets, hypotheses, propositions, metrics, and
  baselines.
- Route confirmatory tests through `pre-register`.

### Phase 3: benchmark outcomes and cross-project analysis

- Add structured benchmark result summaries.
- Integrate outcomes with evidence/proposition updates.
- Add reports comparing project patterns to benchmark outcomes while adjusting
  for benchmark availability.

## Validation and quality checks

- Benchmark dataset with `benchmark.benchmark_kinds` but neither a `tasks[]`
  entry nor `notes`/`limitations` should warn (a kind asserted with no usable
  detail).
- Duplicate `tasks[].id` within one record should error.
- A `tasks[]` entry missing `task_type` or `prediction_target` should warn.
- `benchmark` block on a `dataset_class: pointer` record may warn (a pure pointer
  is rarely benchmark-capable yet) — info-level, not a hard error.
- `tasks[].id` must be slug-like and unique within the record (see *Stable task
  identity*); the canonical task identity in reports/queries is
  `dataset:<slug>#<task-id>`.
- A `perturbation-response` task missing `intervention`, or a `time-series` task
  missing `timepoints`, should warn (v1; checks the optional task fields).
- (Phase 2) Belief test without a benchmark should warn.
- (Phase 2) Confirmatory belief test without pre-registration should warn.
- (Phase 2) Benchmark result without baseline or metric should warn.

## Success criteria

- (v1) A project can list known benchmarks relevant to its topic or field and
  see a facet coverage summary by domain/modality/kind/class.
- (Phase 2) A project can see which hypotheses/propositions have no suitable
  benchmark.
- (v1) Perturbation and time-series datasets are visible as high-value tests
  rather than just ordinary datasets.
- (Phase 2) A project can write a belief-test plan that connects a proposition to a
  benchmark prediction, metric, baseline, and interpretation threshold.
- (Phase 3) Benchmark outcomes can update the proposition/evidence graph instead of
  living only in workflow logs.
- (Phase 3) Science can eventually study which project practices correlate with better
  benchmark-grounded performance, adjusted for data availability.
