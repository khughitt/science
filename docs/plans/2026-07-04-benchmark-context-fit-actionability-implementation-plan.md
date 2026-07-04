# Benchmark Context-Fit Actionability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic context-fit labels to benchmark test and triage reports so generic fallback and cross-context benchmark rows are easier to separate from actionable project-fit rows.

**Architecture:** Compute context-fit at benchmark-test row build time, while `DatasetOpportunityContext`, `OpportunityDataset`, `OpportunityTask`, and project entity context are still available. Keep existing raw matching and scores unchanged; add row fields, filters, summaries, and triage sorting as a projection over the existing reports.

**Tech Stack:** Python 3.12, Click, Rich tables, TypedDict/dataclasses, pytest, ruff, existing `science_tool.benchmark_opportunities` report pipeline.

---

## File Structure

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Owns context-fit types, classifier helpers, benchmark-test row construction, filtering, summary counts, and triage sorting.
  - Do not create a second benchmark-source loading path. The classifier must run from `_benchmark_test_row(...)` using `DatasetOpportunityContext`.
- Modify `science/src/science_tool/cli.py`
  - Adds `--context-fit` to `benchmark tests` and `benchmark test-triage`.
  - Adds compact context-fit columns to relevant tables.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Unit/report tests for classifier behavior, summaries, filters, and triage ordering.
- Modify `science/tests/test_benchmark_cli.py`
  - CLI tests for JSON/table behavior and invalid filter values.
- Modify `docs/plans/2026-07-04-benchmark-context-fit-actionability-design.md`
  - Only if implementation discovers a design inconsistency. Do not broaden scope.

## Ground Rules

- Keep raw matching unchanged:
  - no edits to `_relative_score`;
  - no edits to `_candidate_score`;
  - no edits to `baseline_score`;
  - no edits that change which rows `benchmark_tests_report()` produces before context-fit filtering.
- Context-fit is additive:
  - every `BenchmarkTestRow` has `context_fit`, `context_fit_reasons`, and `context_fit_warnings`;
  - existing fields and score values stay stable unless a test proves they already changed upstream.
- The broad-context predicate and cross-* warnings are coupled:
  - `broad_context` can be true when a cross-* warning cue exists;
  - adjacent-fit depends on `broad_context`;
  - build `_context_fit_warning_cues(...)` before or in the same task as `_context_fit_predicates(...)`.
- Reuse existing token/broad sets without changing matching:
  - `_normalize_token`, `_token_evidence_from_text`, `_STOP_TOKENS`, `ENTITY_SUPPRESSED_TOKENS`, and `BROAD_NON_SCOREABLE_FACETS`;
  - keep `BROAD_NON_SCOREABLE_FACETS` scoring-facing; if `cross-sectional`, `clinical`, `genomics`, or `multi-omic` are still able to promote `direct-fit` alone, add them to a context-fit-only `CONTEXT_BROAD_TOKENS` extension that is not used by `_scoreable_facet_tokens`.
- Use `~/d/` paths in docs and code comments.
- Use `rtk` command prefix.
- In a worktree, verify imports resolve to the worktree source before trusting RED/GREEN test output.

---

### Task 0: Create Isolated Implementation Worktree

**Files:**
- No source edits.

- [ ] **Step 1: Create a worktree from the design branch**

Run from `~/d/science`:

```bash
rtk git worktree add .worktrees/benchmark-context-fit-v1 -b benchmark-context-fit-v1
```

Expected: worktree is created at `.worktrees/benchmark-context-fit-v1`.

- [ ] **Step 2: Enter the worktree**

```bash
cd ~/d/science/.worktrees/benchmark-context-fit-v1
```

- [ ] **Step 3: Verify package import resolution**

```bash
rtk uv run --frozen --project science python -c "import science_tool, pathlib; print(pathlib.Path(science_tool.__file__).resolve())"
```

Expected: printed path starts with:

```text
~/d/science/.worktrees/benchmark-context-fit-v1/science/src/science_tool/
```

If it points at the main checkout, use this prefix for all test commands in this plan:

```bash
PYTHONPATH=science/src rtk uv run --frozen --project science ...
```

- [ ] **Step 4: Confirm initial status**

```bash
rtk git status --short
```

Expected: clean worktree, or only already-known plan/spec edits from the parent branch.

---

### Task 1: Add Context-Fit Types and Row Contract

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing report-contract test**

Append this test near the existing benchmark-test report tests in `science/tests/test_benchmark_opportunities.py`:

```python
def test_benchmark_tests_report_projects_context_fit_fields(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0500-perturbation",
        """
id: hypothesis:0500-perturbation
type: hypothesis
title: Perturbation benchmark hypothesis
""",
        body="Sci-plex drug perturbation should shift response states.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    payload = benchmark_tests_report(tmp_path)

    assert payload["summary"]["context_fit_counts"] == {
        "direct-fit": 1,
        "adjacent-fit": 0,
        "method-fit": 0,
        "blocked-fit": 0,
        "generic-fallback": 0,
        "out-of-context": 0,
    }
    row = payload["benchmark_tests"][0]
    assert row["context_fit"] == "direct-fit"
    assert "task-support:supported" in row["context_fit_reasons"]
    assert row["context_fit_warnings"] == []
```

- [ ] **Step 2: Add failing CLI JSON contract assertion**

In `science/tests/test_benchmark_cli.py`, update `test_benchmark_tests_cli_json_output` by adding these assertions after `row = payload["benchmark_tests"][0]` or after the existing row assertions:

```python
    row = payload["benchmark_tests"][0]
    assert row["context_fit"] == "direct-fit"
    assert "context_fit_reasons" in row
    assert row["context_fit_warnings"] == []
    assert payload["summary"]["context_fit_counts"]["direct-fit"] == 1
```

If the test currently does not assign `row`, insert:

```python
    row = payload["benchmark_tests"][0]
```

before these assertions.

- [ ] **Step 3: Run tests to verify RED**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_projects_context_fit_fields \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_json_output \
  -q
```

Expected: FAIL with missing `context_fit` / `context_fit_counts` fields.

- [ ] **Step 4: Add context-fit types**

In `science/src/science_tool/benchmark_opportunities.py`, near the existing benchmark-test type aliases:

```python
ContextFit = Literal[
    "direct-fit",
    "adjacent-fit",
    "method-fit",
    "blocked-fit",
    "generic-fallback",
    "out-of-context",
]

CONTEXT_FITS: tuple[ContextFit, ...] = (
    "direct-fit",
    "adjacent-fit",
    "method-fit",
    "blocked-fit",
    "generic-fallback",
    "out-of-context",
)

CONTEXT_FIT_ORDER: dict[ContextFit, int] = {value: index for index, value in enumerate(CONTEXT_FITS)}
```

Place this after `ReadinessLabel` and before `TaskSupportCountKey`.

- [ ] **Step 5: Extend `BenchmarkTestRow` and `BenchmarkTestSummary`**

Add these fields to `BenchmarkTestRow`:

```python
    context_fit: ContextFit
    context_fit_reasons: list[str]
    context_fit_warnings: list[str]
```

Add this field to `BenchmarkTestSummary`:

```python
    context_fit_counts: dict[ContextFit, int]
```

- [ ] **Step 6: Add temporary direct-fit classifier**

Add these helpers before `_benchmark_test_row(...)`:

```python
def _empty_context_fit_counts() -> dict[ContextFit, int]:
    return {context_fit: 0 for context_fit in CONTEXT_FITS}


def _context_fit_counts(rows: Sequence[BenchmarkTestRow]) -> dict[ContextFit, int]:
    counts = _empty_context_fit_counts()
    for row in rows:
        counts[row["context_fit"]] += 1
    return counts


def _initial_context_fit_for_row(
    *,
    task: OpportunityTask | None,
) -> tuple[ContextFit, list[str], list[str]]:
    reasons: list[str] = []
    support = task.support if task is not None else None
    if support is not None and support.state == "supported":
        reasons.append("task-support:supported")
    return "direct-fit", reasons, []
```

This is intentionally minimal for Task 1. Later tasks replace it with the full classifier.

- [ ] **Step 7: Populate row fields**

Inside `_benchmark_test_row(...)`, before the returned dict:

```python
    context_fit, context_fit_reasons, context_fit_warnings = _initial_context_fit_for_row(task=task)
```

Add these keys to the returned row:

```python
        "context_fit": context_fit,
        "context_fit_reasons": context_fit_reasons,
        "context_fit_warnings": context_fit_warnings,
```

- [ ] **Step 8: Add summary counts**

In `_benchmark_test_summary(...)`, add:

```python
        "context_fit_counts": _context_fit_counts(rows),
```

to the returned dictionary.

- [ ] **Step 9: Run tests to verify GREEN**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_projects_context_fit_fields \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_json_output \
  -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat: add benchmark context fit row fields"
```

---

### Task 2: Implement Context Token Extraction and Warning Cues

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing direct/adjacent/method tests**

Append these tests near `test_benchmark_tests_report_projects_context_fit_fields` in `science/tests/test_benchmark_opportunities.py`:

```python
def test_context_fit_classifies_adjacent_cross_disease_rows(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    (tmp_path / "science.yaml").write_text("id: multiple-myeloma\nname: mm30\n", encoding="utf-8")
    _write_entity(
        tmp_path,
        "hypotheses",
        "0501-myeloma-outcome",
        """
id: hypothesis:0501-myeloma-outcome
type: hypothesis
title: Myeloma outcome benchmark hypothesis
""",
        body="Multiple myeloma survival risk needs clinical benchmark evidence.",
    )
    _write_dataset(
        tmp_path,
        "brca-metabric",
        """
id: dataset:brca-metabric
type: dataset
title: BRCA METABRIC breast cancer outcomes
dataset_class: deposit
local_path: data/brca-metabric
benchmark:
  domains: [biology]
  modalities: [clinical]
  signal_types: [clinical-outcome]
  benchmark_kinds: [outcome-prediction]
  source_datasets: [breast-cancer-metabric]
  tasks:
    - id: survival
      task_type: outcome prediction
      prediction_target: survival
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: measured-outcome
        description: survival outcome
      support:
        state: supported
""",
    )

    row = benchmark_tests_report(tmp_path)["benchmark_tests"][0]

    assert row["context_fit"] == "adjacent-fit"
    # The benchmark tokenizes to {brca, breast}; `_context_fit_warning_cues`
    # picks `sorted(...)[0]` == "brca" deterministically. Keep the fixture body
    # free of any token the benchmark also carries (e.g. "outcome"/"outcomes")
    # so the row cannot pick up a shared specific token and promote to direct-fit.
    assert "cross-disease:brca-vs-myeloma" in row["context_fit_warnings"]
    assert "task-support:supported" in row["context_fit_reasons"]


def test_context_fit_classifies_method_fit_without_specific_context(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0502-temporal",
        """
id: hypothesis:0502-temporal
type: hypothesis
title: Temporal mechanism hypothesis
""",
        body="Temporal mechanism predictions need a time-series benchmark.",
    )
    _write_dataset(
        tmp_path,
        "dream4-in-silico-network",
        """
id: dataset:dream4-in-silico-network
type: dataset
title: DREAM4 in silico network
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [simulated-gene-expression]
  signal_types: [time-series, perturbation]
  benchmark_kinds: [network-reconstruction]
  limitations: [simulated benchmark]
  tasks:
    - id: network-reconstruction
      task_type: network reconstruction
      prediction_target: regulatory edges
      held_out_unit: edge
      metric: auprc
      baseline: random ranking
      ground_truth:
        type: simulated-network
        description: simulated regulatory network
      support:
        state: candidate
        reason: requires-challenge-package-staging
""",
    )

    row = benchmark_tests_report(tmp_path)["benchmark_tests"][0]

    assert row["context_fit"] == "method-fit"
    assert "context:weak" in row["context_fit_warnings"]
    assert "task-signal:time-series" in row["context_fit_reasons"]


def test_context_fit_uses_dataset_metadata_not_public_row_only(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0503-hidden-source",
        """
id: hypothesis:0503-hidden-source
type: hypothesis
title: Hidden source context
""",
        body="Sci-plex perturbation response should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "source-hidden",
        """
id: dataset:source-hidden
type: dataset
title: Perturbation response benchmark
dataset_class: deposit
local_path: data/source-hidden
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )

    row = benchmark_tests_report(tmp_path)["benchmark_tests"][0]

    assert row["context_fit"] == "direct-fit"
    assert "specific-context:sci-plex" in row["context_fit_reasons"]
```

- [ ] **Step 2: Run tests to verify RED**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_context_fit_classifies_adjacent_cross_disease_rows \
  science/tests/test_benchmark_opportunities.py::test_context_fit_classifies_method_fit_without_specific_context \
  science/tests/test_benchmark_opportunities.py::test_context_fit_uses_dataset_metadata_not_public_row_only \
  -q
```

Expected: FAIL because the Task 1 classifier returns `direct-fit` for all rows.

- [ ] **Step 3: Add context-only broad token coverage**

Keep `BROAD_NON_SCOREABLE_FACETS` unchanged because `_scoreable_facet_tokens(...)`
uses it for raw opportunity matching. Add this context-fit-only extension near
`BROAD_NON_SCOREABLE_FACETS`:

```python
BROAD_NON_SCOREABLE_FACETS = frozenset({"biology", "cancer", "varies"})

CONTEXT_BROAD_TOKENS = BROAD_NON_SCOREABLE_FACETS | frozenset(
    {
        "clinical",
        "cross-sectional",
        "data",
        "genomics",
        "model",
        "multi-omic",
    }
)
```

Use `CONTEXT_BROAD_TOKENS` only in context-fit helpers. Do not use it in
`_scoreable_facet_tokens(...)`, `_relative_score(...)`, `_candidate_score(...)`,
or `baseline_score(...)`.

- [ ] **Step 4: Add context-fit dataclasses and token helpers**

Add these after `TokenEvidence`:

```python
@dataclass(frozen=True)
class ContextFitEvidence:
    project_tokens: frozenset[str]
    entity_tokens: frozenset[str]
    benchmark_tokens: frozenset[str]
    broad_project_tokens: frozenset[str]
    broad_benchmark_tokens: frozenset[str]


@dataclass(frozen=True)
class ContextFitPredicates:
    strong_context: bool
    broad_context: bool
    task_signal: bool
    domain_conflict: bool
    warning_cues: list[str]
```

Add these helpers before `_benchmark_test_row(...)`:

```python
def _specific_tokens(tokens: set[str] | frozenset[str]) -> frozenset[str]:
    broad = set(CONTEXT_BROAD_TOKENS) | set(ENTITY_SUPPRESSED_TOKENS) | set(_STOP_TOKENS)
    return frozenset(token for token in tokens if token not in broad)


def _project_context_tokens(project_root: Path, entities: list[ProjectBenchmarkEntity]) -> frozenset[str]:
    return frozenset(_project_local_tokens(project_root, entities))


def _entity_context_tokens(entity: ProjectBenchmarkEntity) -> frozenset[str]:
    return _specific_tokens(entity.tokens | entity.id_tokens)


def _benchmark_context_tokens(context: DatasetOpportunityContext) -> frozenset[str]:
    dataset = context.dataset
    tokens = _tokens_from_text(
        dataset.id,
        dataset.title,
        *dataset.domains,
        *dataset.source_datasets,
        *dataset.limitations,
        include_stop_tokens=False,
    )
    return _specific_tokens(tokens)


def _benchmark_broad_context_tokens(context: DatasetOpportunityContext) -> frozenset[str]:
    dataset = context.dataset
    evidence = _token_evidence_from_text(
        dataset.id,
        dataset.title,
        *dataset.domains,
        *dataset.source_datasets,
        *dataset.limitations,
        broad_tokens=CONTEXT_BROAD_TOKENS,
    )
    return evidence.broad
```

- [ ] **Step 5: Add explicit cross-warning cues**

Add this helper near the context token helpers:

```python
COARSE_DOMAIN_LABELS = frozenset({"biology", "cancer", "health", "natural-systems", "physical"})

DISEASE_CONTEXT_TOKENS = frozenset(
    {
        "brca",
        "breast",
        "gbm",
        "glioblastoma",
        "melanoma",
        "myeloma",
    }
)
# Note: 2-char disease tokens (e.g. "mm") are intentionally omitted -- the
# tokenizer drops tokens under 3 chars, so they would be dead entries. Multiple
# myeloma is matched via "myeloma".


def _context_fit_warning_cues(
    *,
    project_entity_tokens: frozenset[str],
    benchmark_tokens: frozenset[str],
    context: DatasetOpportunityContext,
) -> list[str]:
    warnings: list[str] = []
    project_diseases = sorted(project_entity_tokens & DISEASE_CONTEXT_TOKENS)
    benchmark_diseases = sorted(benchmark_tokens & DISEASE_CONTEXT_TOKENS)
    if project_diseases and benchmark_diseases and set(project_diseases).isdisjoint(benchmark_diseases):
        warnings.append(f"cross-disease:{benchmark_diseases[0]}-vs-{project_diseases[0]}")

    dataset_values = _dataset_evidence_values(context.dataset)
    dataset_tokens = _tokens_from_text(*dataset_values, include_stop_tokens=False)
    if "cell-line" in dataset_tokens and "primary" in project_entity_tokens:
        warnings.append("cell-line-vs-primary")
    if {"simulated", "synthetic"} & dataset_tokens and {"observed", "measured"} & project_entity_tokens:
        warnings.append("simulated-vs-observed")
    return warnings
```

This is intentionally small and auditable. Do not turn it into a broad ontology.

- [ ] **Step 6: Replace temporary classifier with evidence-based classifier**

Replace `_initial_context_fit_for_row(...)` with:

```python
def _task_signal_reasons(
    *,
    task: OpportunityTask | None,
    priority_source: PrioritySource,
    source_components: dict[str, int],
    matched_facets: list[str],
    entity_need_tokens: frozenset[str],
) -> list[str]:
    reasons: list[str] = []
    high_value = (set(matched_facets) & (HIGH_VALUE_MODALITIES | HIGH_VALUE_SIGNALS | BENCHMARK_GAP_HINT_FACET_SET))
    for facet in sorted(high_value, key=_facet_sort_key):
        reasons.append(f"task-signal:{facet}")
    support = task.support if task is not None else None
    if support is not None and support.state == "supported":
        reasons.append("task-support:supported")
    if priority_source == "opportunity-relative" and int(source_components.get("facet_overlap", 0)) > 0:
        reasons.append("task-signal:facet-overlap")
    # Design: the task type is a signal only when it "directly matches the entity
    # need" -- NOT merely because the task carries a task_type. Gating on the
    # entity-token intersection keeps `task_signal` discriminating; treating any
    # task_type as a signal makes `task_signal` true for nearly every row and
    # collapses the method-fit / out-of-context boundary.
    if task is not None and task.task_type:
        task_type_tokens = _specific_tokens(_tokens_from_text(task.task_type, include_stop_tokens=False))
        if task_type_tokens & entity_need_tokens:
            reasons.append(f"task-type:{_normalize_token(task.task_type)}")
    return sorted(set(reasons))


def _context_fit_for_row(
    *,
    entity: ProjectBenchmarkEntity,
    project_context_tokens: frozenset[str],
    context: DatasetOpportunityContext,
    task: OpportunityTask | None,
    priority_source: PrioritySource,
    source_components: dict[str, int],
    reason_notes: list[str],
    matched_facets: list[str],
) -> tuple[ContextFit, list[str], list[str]]:
    entity_tokens = _entity_context_tokens(entity)
    project_entity_tokens = _specific_tokens(set(project_context_tokens) | set(entity_tokens))
    benchmark_tokens = _benchmark_context_tokens(context)
    shared_specific = sorted(project_entity_tokens & benchmark_tokens)
    warning_cues = _context_fit_warning_cues(
        project_entity_tokens=project_entity_tokens,
        benchmark_tokens=benchmark_tokens,
        context=context,
    )
    broad_shared = bool((set(entity.tokens) | set(project_context_tokens)) & _benchmark_broad_context_tokens(context))
    task_reasons = _task_signal_reasons(
        task=task,
        priority_source=priority_source,
        source_components=source_components,
        matched_facets=matched_facets,
        entity_need_tokens=entity_tokens,
    )
    is_blocked = (task.support.state == "blocked") if task is not None and task.support is not None else False
    is_fallback = priority_source == "gap-fallback" or any(note.startswith("fallback:") for note in reason_notes)
    has_evidence = bool(shared_specific or warning_cues or task_reasons)

    reasons: list[str] = []
    reasons.extend(f"specific-context:{token}" for token in shared_specific)
    reasons.extend(task_reasons)
    warnings = list(warning_cues)

    # Blocked/fallback ordering (design Rules 1, 1b, 2). The demotion of a
    # blocked fallback with no project/entity context is keyed on
    # `not shared_specific`, NOT on `has_evidence`: a blocked fallback can still
    # carry task evidence, and demoting only when task evidence is absent would
    # route MMRF-style rows to `blocked-fit` and drop the `blocked-support-fallback`
    # warning. Blocked-fit demotion for a fallback-only, no-context row wins first.
    if is_blocked and is_fallback and not shared_specific:
        return "generic-fallback", sorted(set(reasons)), sorted({*warnings, "blocked-support-fallback"})
    if is_blocked and has_evidence:
        return "blocked-fit", sorted(set(reasons)), sorted(set(warnings))
    if is_fallback and not shared_specific:
        return "generic-fallback", sorted(set(reasons)), sorted(set(warnings))

    task_signal = bool(task_reasons)
    if shared_specific and task_signal:
        return "direct-fit", sorted(set(reasons)), sorted(set(warnings))

    # domain_conflict compares a small COARSE label set matched BEFORE broad
    # stripping (design "Implementation note"). Both `dataset_domains` and
    # `project_domains` are read from RAW (non-`_specific_tokens`) tokens, because
    # the domain-naming tokens (`biology`, `cancer`) are exactly the ones broad
    # stripping removes -- comparing stripped sets makes this predicate vestigial.
    raw_project_tokens = set(project_context_tokens) | set(entity.tokens) | set(entity.id_tokens)
    dataset_domains = {_normalize_token(value) for value in context.dataset.domains} & COARSE_DOMAIN_LABELS
    project_domains = raw_project_tokens & COARSE_DOMAIN_LABELS
    domain_conflict = bool(dataset_domains and project_domains and dataset_domains.isdisjoint(project_domains))
    if domain_conflict:
        return "out-of-context", sorted(set(reasons)), sorted({*warnings, "domain-conflict"})

    broad_context = broad_shared or bool(warning_cues)
    if broad_context and task_signal:
        return "adjacent-fit", sorted(set(reasons)), sorted(set(warnings))
    if task_signal:
        return "method-fit", sorted(set(reasons)), sorted({*warnings, "context:weak"})
    return "out-of-context", sorted(set(reasons)), sorted(set(warnings))
```

- [ ] **Step 7: Pass entity/project context into row construction**

Change `_benchmark_test_row(...)` signature to include:

```python
    entity: ProjectBenchmarkEntity,
    project_context_tokens: frozenset[str],
```

Remove `entity_id: str` and `entity_title: str` parameters.

Inside `_benchmark_test_row(...)`, call:

```python
    context_fit, context_fit_reasons, context_fit_warnings = _context_fit_for_row(
        entity=entity,
        project_context_tokens=project_context_tokens,
        context=context,
        task=task,
        priority_source=priority_source,
        source_components=source_components,
        reason_notes=reason_notes,
        matched_facets=matched_facets,
    )
```

Update returned fields:

```python
        "entity_id": entity.id,
        "entity_title": entity.title,
```

and add:

```python
        "context_fit": context_fit,
        "context_fit_reasons": context_fit_reasons,
        "context_fit_warnings": context_fit_warnings,
```

- [ ] **Step 8: Update row helper signatures**

Change `_rows_for_context_tasks(...)` signature to:

```python
def _rows_for_context_tasks(
    opportunity: OpportunityRow,
    context: DatasetOpportunityContext,
    *,
    entity: ProjectBenchmarkEntity,
    project_context_tokens: frozenset[str],
) -> list[BenchmarkTestRow]:
```

Update each `_benchmark_test_row(...)` call inside it to pass:

```python
                entity=entity,
                project_context_tokens=project_context_tokens,
```

Change `_rows_for_gap_candidate(...)` signature to:

```python
def _rows_for_gap_candidate(
    *,
    entity: ProjectBenchmarkEntity,
    project_context_tokens: frozenset[str],
    context: DatasetOpportunityContext,
    priority_score: int,
    priority_source: PrioritySource,
    source_components: dict[str, int],
    reason_notes: list[str],
    matched_facets: list[str],
) -> list[BenchmarkTestRow]:
```

Update each `_benchmark_test_row(...)` call inside it to pass:

```python
            entity=entity,
            project_context_tokens=project_context_tokens,
```

- [ ] **Step 9: Update `benchmark_tests_report(...)` call sites**

Inside `benchmark_tests_report(...)`, create:

```python
    entity_by_id = {entity.id: entity for entity in analysis.entities}
    project_context_tokens = _project_context_tokens(project_root, analysis.entities)
```

In the matched opportunity loop, before extending rows:

```python
        entity = entity_by_id.get(opportunity["entity_id"])
        if entity is None:
            # Fail loud, do not `continue`: the current report emits this row
            # from `opportunity["entity_id"]`/`entity_title` directly, so silently
            # skipping would drop a row that `benchmark_tests_report()` produces
            # today (violating the no-row-change ground rule) and hide a real
            # entity/opportunity mismatch. This invariant must hold.
            raise ValueError(f"matched opportunity references unknown entity: {opportunity['entity_id']}")
```

Update the call:

```python
        rows.extend(
            _rows_for_context_tasks(
                opportunity,
                context,
                entity=entity,
                project_context_tokens=project_context_tokens,
            )
        )
```

In the gap loop, before candidates:

```python
        entity = entity_by_id.get(gap_row["entity_id"])
        if entity is None:
            # Fail loud, same rationale as the opportunity loop above.
            raise ValueError(f"gap row references unknown entity: {gap_row['entity_id']}")
```

Update `_rows_for_gap_candidate(...)` call:

```python
                    entity=entity,
                    project_context_tokens=project_context_tokens,
```

and remove `entity_id=` / `entity_title=`.

- [ ] **Step 10: Run tests to verify GREEN**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_projects_context_fit_fields \
  science/tests/test_benchmark_opportunities.py::test_context_fit_classifies_adjacent_cross_disease_rows \
  science/tests/test_benchmark_opportunities.py::test_context_fit_classifies_method_fit_without_specific_context \
  science/tests/test_benchmark_opportunities.py::test_context_fit_uses_dataset_metadata_not_public_row_only \
  -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat: classify benchmark context fit"
```

---

### Task 3: Implement Total Classification and Filter Semantics

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing totality and filter tests**

Append:

```python
def test_context_fit_totality_and_filter_or_semantics(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0504-mixed-context",
        """
id: hypothesis:0504-mixed-context
type: hypothesis
title: Mixed benchmark context
""",
        body="Drug perturbation and temporal mechanism evidence should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )
    _write_dataset(
        tmp_path,
        "dream4-in-silico-network",
        """
id: dataset:dream4-in-silico-network
type: dataset
title: DREAM4 in silico network
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [simulated-gene-expression]
  signal_types: [time-series]
  benchmark_kinds: [network-reconstruction]
  limitations: [simulated benchmark]
  tasks:
    - id: network-reconstruction
      task_type: network reconstruction
      prediction_target: regulatory edges
      held_out_unit: edge
      metric: auprc
      baseline: random ranking
      ground_truth:
        type: simulated-network
        description: simulated regulatory network
      support:
        state: candidate
        reason: requires-challenge-package-staging
""",
    )

    all_payload = benchmark_tests_report(tmp_path)
    direct_or_method = benchmark_tests_report(tmp_path, context_fit=("direct-fit", "method-fit"))

    assert all(row["context_fit"] for row in all_payload["benchmark_tests"])
    assert all_payload["summary"]["test_plan_rows"] >= 2
    assert {row["context_fit"] for row in direct_or_method["benchmark_tests"]} <= {"direct-fit", "method-fit"}
    assert direct_or_method["summary"]["test_plan_rows"] == len(direct_or_method["benchmark_tests"])
    assert direct_or_method["filters"]["context_fit"] == ["direct-fit", "method-fit"]
```

- [ ] **Step 2: Run test to verify RED**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_context_fit_totality_and_filter_or_semantics \
  -q
```

Expected: FAIL because `benchmark_tests_report()` has no `context_fit` parameter and no filters field.

- [ ] **Step 3: Add context-fit filter to report types**

Add to `BenchmarkTestReport`:

```python
    filters: dict[str, Any]
```

Add helper:

```python
def _normalize_context_fit_filters(values: Sequence[str] | None) -> tuple[ContextFit, ...] | None:
    if values is None:
        return None
    normalized: list[ContextFit] = []
    for value in values:
        if value not in CONTEXT_FITS:
            raise ValueError(f"unknown benchmark context-fit value: {value}")
        normalized.append(cast("ContextFit", value))
    return tuple(dict.fromkeys(normalized))
```

- [ ] **Step 4: Extend row filtering**

Change `_filter_benchmark_test_rows(...)` signature:

```python
    context_fit: Sequence[str] | None,
```

Inside the function, compute:

```python
    normalized_context_fit = _normalize_context_fit_filters(context_fit)
```

In the row loop, add:

```python
        if normalized_context_fit is not None and row["context_fit"] not in normalized_context_fit:
            continue
```

- [ ] **Step 5: Add report filters helper**

Add:

```python
def _benchmark_test_filters(
    *,
    context_fit: Sequence[str] | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    normalized_context_fit = _normalize_context_fit_filters(context_fit)
    if normalized_context_fit is not None:
        filters["context_fit"] = list(normalized_context_fit)
    return filters
```

This helper only owns new filter output in v1. Existing test report did not expose a filters object before this slice.

- [ ] **Step 6: Extend `benchmark_tests_report(...)` signature**

Add parameter:

```python
    context_fit: Sequence[str] | None = None,
```

Pass it into `_filter_benchmark_test_rows(...)`:

```python
        context_fit=context_fit,
```

Return:

```python
        "filters": _benchmark_test_filters(context_fit=context_fit),
```

- [ ] **Step 7: Run test to verify GREEN**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_context_fit_totality_and_filter_or_semantics \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat: filter benchmark tests by context fit"
```

---

### Task 4: Add Triage Context-Fit Sorting and Counts

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing triage sorting/counts test**

Append:

```python
def test_benchmark_test_triage_sorts_with_context_fit_inside_bucket(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_test_triage_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0505-context-triage",
        """
id: hypothesis:0505-context-triage
type: hypothesis
title: Context triage
""",
        body="Sci-plex perturbation and temporal mechanism benchmarks should be considered.",
    )
    _write_dataset(
        tmp_path,
        "dream4-in-silico-network",
        """
id: dataset:dream4-in-silico-network
type: dataset
title: DREAM4 in silico network
dataset_class: deposit
local_path: data/dream4
benchmark:
  domains: [biology]
  modalities: [simulated-gene-expression]
  signal_types: [time-series]
  benchmark_kinds: [network-reconstruction]
  tasks:
    - id: network-reconstruction
      task_type: network reconstruction
      prediction_target: regulatory edges
      held_out_unit: edge
      metric: auprc
      baseline: random ranking
      ground_truth:
        type: simulated-network
        description: simulated regulatory network
      support:
        state: supported
""",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )

    payload = benchmark_test_triage_report(tmp_path)
    run_now = payload["buckets"]["run-now"]

    assert [row["context_fit"] for row in run_now][:2] == ["direct-fit", "method-fit"]
    assert payload["summary"]["context_fit_counts"]["direct-fit"] >= 1
    assert payload["context_fit_counts_by_bucket"]["run-now"]["direct-fit"] >= 1
    assert payload["context_fit_counts_by_bucket"]["fallback-diagnostic"] == {
        "direct-fit": 0,
        "adjacent-fit": 0,
        "method-fit": 0,
        "blocked-fit": 0,
        "generic-fallback": 0,
        "out-of-context": 0,
    }
```

- [ ] **Step 2: Run test to verify RED**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_sorts_with_context_fit_inside_bucket \
  -q
```

Expected: FAIL because triage rows are not sorted by `context_fit` and `context_fit_counts_by_bucket` is missing.

- [ ] **Step 3: Add context-fit sort helper**

Add:

```python
def _context_fit_sort_key(context_fit: ContextFit) -> int:
    return CONTEXT_FIT_ORDER[context_fit]
```

Change `_benchmark_test_sort_key(...)` only if tests require stable report ordering. For v1, keep test report ordering unchanged unless a failing test proves it is unstable.

Add:

```python
def _benchmark_test_triage_sort_key(row: BenchmarkTestTriageRow) -> tuple[int, int, int, int, str, str, str]:
    return (
        _context_fit_sort_key(row["context_fit"]),
        _benchmark_test_source_sort_key(row["priority_source"]),
        _benchmark_test_readiness_sort_key(row["readiness_label"]),
        -row["priority_score"],
        row["entity_id"],
        row["benchmark_id"],
        "" if row["task_id"] is None else row["task_id"],
    )
```

- [ ] **Step 4: Add bucket context-fit counts helper**

Add:

```python
def _context_fit_counts_by_bucket(
    buckets: dict[BenchmarkTestTriageBucket, list[BenchmarkTestTriageRow]],
) -> dict[BenchmarkTestTriageBucket, dict[ContextFit, int]]:
    return {bucket: _context_fit_counts(buckets[bucket]) for bucket in BENCHMARK_TEST_TRIAGE_BUCKETS}
```

Add to `BenchmarkTestTriageReport`:

```python
    context_fit_counts_by_bucket: dict[BenchmarkTestTriageBucket, dict[ContextFit, int]]
```

- [ ] **Step 5: Sort triage buckets and return counts**

In `benchmark_test_triage_report(...)`, after all rows are appended to `buckets`:

```python
    for bucket_rows in buckets.values():
        bucket_rows.sort(key=_benchmark_test_triage_sort_key)
```

Add to returned payload:

```python
        "context_fit_counts_by_bucket": _context_fit_counts_by_bucket(buckets),
```

- [ ] **Step 6: Pass context-fit filter through triage**

Add parameter to `benchmark_test_triage_report(...)`:

```python
    context_fit: Sequence[str] | None = None,
```

Pass into `benchmark_tests_report(...)`:

```python
        context_fit=context_fit,
```

Add `context_fit` to `_benchmark_test_triage_filters(...)` signature and output:

```python
    context_fit: Sequence[str] | None,
```

Inside helper:

```python
    normalized_context_fit = _normalize_context_fit_filters(context_fit)
    if normalized_context_fit is not None:
        filters["context_fit"] = list(normalized_context_fit)
```

Update the call in `benchmark_test_triage_report(...)`:

```python
            context_fit=context_fit,
```

- [ ] **Step 7: Run test to verify GREEN**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_sorts_with_context_fit_inside_bucket \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat: sort benchmark triage by context fit"
```

---

### Task 5: Add CLI Filters and Table Output

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing CLI filter tests**

Append near the benchmark-tests CLI tests:

```python
def test_benchmark_tests_cli_filters_context_fit_or_values(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0506-context-cli",
        """
id: hypothesis:0506-context-cli
type: hypothesis
title: Context CLI
""",
        body="Sci-plex perturbation and temporal benchmark evidence should be considered.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )

    result = _invoke_tests(
        tmp_path,
        "--context-fit",
        "direct-fit",
        "--context-fit",
        "method-fit",
        "--format",
        "json",
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["filters"]["context_fit"] == ["direct-fit", "method-fit"]
    assert {row["context_fit"] for row in payload["benchmark_tests"]} <= {"direct-fit", "method-fit"}


def test_benchmark_tests_cli_table_shows_context_fit(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0507-context-table",
        """
id: hypothesis:0507-context-table
type: hypothesis
title: Context table
""",
        body="Sci-plex perturbation should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )

    result = _invoke_tests(tmp_path)

    assert result.exit_code == 0
    assert "fit" in result.output
    assert "direct-fit" in result.output
```

Append near triage CLI tests:

```python
def test_benchmark_test_triage_cli_filters_context_fit(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0508-context-triage-cli",
        """
id: hypothesis:0508-context-triage-cli
type: hypothesis
title: Context triage CLI
""",
        body="Sci-plex perturbation should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )

    result = _invoke_test_triage(tmp_path, "--context-fit", "direct-fit", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["filters"]["context_fit"] == ["direct-fit"]
    assert payload["summary"]["context_fit_counts"]["direct-fit"] == 1
```

- [ ] **Step 2: Run tests to verify RED**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_filters_context_fit_or_values \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_table_shows_context_fit \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_filters_context_fit \
  -q
```

Expected: FAIL because `--context-fit` is not defined and table output lacks a fit column.

- [ ] **Step 3: Add Click options to `benchmark tests`**

In `science/src/science_tool/cli.py`, add this option before `--format` on `benchmark_tests`:

```python
@click.option(
    "--context-fit",
    "context_fit",
    multiple=True,
    type=click.Choice(
        ["direct-fit", "adjacent-fit", "method-fit", "blocked-fit", "generic-fallback", "out-of-context"]
    ),
    help="Filter by benchmark context-fit label. May be supplied more than once.",
)
```

Add function parameter:

```python
    context_fit: tuple[str, ...],
```

Pass to `benchmark_tests_report(...)`:

```python
            context_fit=context_fit or None,
```

- [ ] **Step 4: Add Click options to `benchmark test-triage`**

Add the same option before `--write-review-file` on `benchmark_test_triage`.

Add function parameter:

```python
    context_fit: tuple[str, ...],
```

Pass to `benchmark_test_triage_report(...)`:

```python
            context_fit=context_fit or None,
```

Add to `_test_triage_source_command(...)` signature:

```python
    context_fit: tuple[str, ...],
```

Inside `_test_triage_source_command(...)`, after `benchmark_ref` handling:

```python
    for value in context_fit:
        parts.extend(["--context-fit", value])
```

Pass from the call:

```python
                    context_fit=context_fit,
```

- [ ] **Step 5: Add compact table columns**

In `benchmark_tests`, change:

```python
    for col in ("entity", "state", "source", "readiness", "benchmark", "task", "score", "facets", "needs"):
```

to:

```python
    for col in ("entity", "state", "source", "readiness", "fit", "benchmark", "task", "score", "facets", "needs"):
```

Add `row["context_fit"]` to each table row between readiness and benchmark.

In `benchmark_test_triage`, change the non-fallback table columns from:

```python
        for col in ("entity", "benchmark", "task", "readiness", "score", "facets", "needs"):
```

to:

```python
        for col in ("entity", "benchmark", "task", "fit", "readiness", "score", "facets", "needs"):
```

Add `row["context_fit"]` between task and readiness in `table.add_row(...)`.

- [ ] **Step 6: Run tests to verify GREEN**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_filters_context_fit_or_values \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_table_shows_context_fit \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_filters_context_fit \
  -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat: expose benchmark context fit filters"
```

---

### Task 6: Lock Broad-Token and Blocked/Fallback Edge Cases

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing broad-token test**

Append:

```python
def test_context_fit_broad_tokens_do_not_promote_direct_fit(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0509-broad-only",
        """
id: hypothesis:0509-broad-only
type: hypothesis
title: Cancer genomics clinical model
""",
        body="Cancer genomics clinical data model analysis needs evidence.",
    )
    _write_dataset(
        tmp_path,
        "broad-cancer",
        """
id: dataset:broad-cancer
type: dataset
title: Cancer genomics clinical model
dataset_class: deposit
local_path: data/broad-cancer
benchmark:
  domains: [biology, cancer]
  modalities: [clinical, genomics, multi-omic]
  signal_types: [cross-sectional]
  benchmark_kinds: [static-association]
  tasks:
    - id: static
      task_type: static association
      prediction_target: association
      held_out_unit: sample
      metric: auroc
      baseline: majority class
      ground_truth:
        type: measured-outcome
        description: association
      support:
        state: supported
""",
    )

    row = benchmark_tests_report(tmp_path)["benchmark_tests"][0]

    assert row["context_fit"] != "direct-fit"
```

Append:

```python
def test_context_fit_blocked_fallback_without_context_is_generic(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0510-unmapped",
        """
id: hypothesis:0510-unmapped
type: hypothesis
title: Unmapped benchmark entity
""",
        body="No specific benchmark facet appears here.",
    )
    _write_dataset(
        tmp_path,
        "blocked-mmrf",
        """
id: dataset:blocked-mmrf
type: dataset
title: MMRF CoMMpass
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: outcome prediction
      prediction_target: progression
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: measured-outcome
        description: progression
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
""",
    )

    rows = benchmark_tests_report(tmp_path)["benchmark_tests"]
    fallback = next(row for row in rows if row["priority_source"] == "gap-fallback")

    assert fallback["context_fit"] == "generic-fallback"
    assert "blocked-support-fallback" in fallback["context_fit_warnings"]
```

- [ ] **Step 2: Run tests to verify edge behavior**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_context_fit_broad_tokens_do_not_promote_direct_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_blocked_fallback_without_context_is_generic \
  -q
```

Expected: these should PASS immediately. Both behaviors are already implemented by the Task 2 classifier — broad tokens are subtracted by `_specific_tokens(...)`, and the blocked/fallback ordering (`if is_blocked and is_fallback and not shared_specific: ... blocked-support-fallback`) is the first branch of `_context_fit_for_row(...)`. These tests are regression locks, not drivers of new code.

- [ ] **Step 3: Investigate only if a lock fails**

If `test_context_fit_broad_tokens_do_not_promote_direct_fit` fails, confirm the broad tokens are in `CONTEXT_BROAD_TOKENS` (Task 2, Step 3) and that `_specific_tokens(...)` subtracts that set.

If `test_context_fit_blocked_fallback_without_context_is_generic` fails, confirm the `_context_fit_for_row(...)` blocked/fallback branches from Task 2 are ordered so the fallback-only, no-context demotion wins first:

```python
    if is_blocked and is_fallback and not shared_specific:
        return "generic-fallback", sorted(set(reasons)), sorted({*warnings, "blocked-support-fallback"})
    if is_blocked and has_evidence:
        return "blocked-fit", sorted(set(reasons)), sorted(set(warnings))
```

Do not re-key this branch on `has_evidence` instead of `shared_specific` — that is the specific regression these locks guard against.

- [ ] **Step 4: Run focused tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_context_fit_broad_tokens_do_not_promote_direct_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_blocked_fallback_without_context_is_generic \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "test: lock benchmark context fit edge cases"
```

---

### Task 7: Full Verification and Active-Project Calibration

**Files:**
- Modify only if verification exposes a bug.

- [ ] **Step 1: Run benchmark opportunity test suite**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -q
```

Expected: PASS.

- [ ] **Step 2: Run benchmark CLI test suite**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run ruff**

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
```

Expected: PASS.

- [ ] **Step 4: Run active-project smoke checks**

Run these commands from the worktree root:

```bash
rtk uv run --frozen --project science science benchmark tests --commons --exclude-fallback --state concrete --context-fit direct-fit --format json --project-root ~/d/cancer/cancer-types/multiple-myeloma
rtk uv run --frozen --project science science benchmark tests --commons --exclude-fallback --state concrete --context-fit direct-fit --format json --project-root ~/d/cancer/data-sources/cbioportal
rtk uv run --frozen --project science science benchmark tests --commons --context-fit direct-fit --format json --project-root ~/d/natural-systems
rtk uv run --frozen --project science science benchmark test-triage --commons --format json --project-root ~/d/cancer/cancer-types/multiple-myeloma
```

Expected:

- commands exit 0;
- CPTAC GBM remains visible in at least one direct-fit row for cBioPortal or multiple myeloma if its project/entity context matches the final classifier;
- natural systems does not return a large direct-fit biology fallback set;
- `summary.context_fit_counts` appears in both `benchmark tests` and `benchmark test-triage` payloads;
- `context_fit_counts_by_bucket` appears in triage payloads.

- [ ] **Step 5: Capture calibration notes**

Run this script from the worktree root. It executes the same smoke commands,
extracts `context_fit_counts`, and writes a complete report with no hand-filled
cells.

```bash
rtk uv run --frozen --project science python - <<'PY'
import json
import subprocess
from pathlib import Path

PROJECTS = {
    "multiple-myeloma": "~/d/cancer/cancer-types/multiple-myeloma",
    "post-acute-infection": "~/d/health/processes/post-acute-infection",
    "natural-systems": "~/d/natural-systems",
    "cbioportal": "~/d/cancer/data-sources/cbioportal",
}

fits = ("direct-fit", "adjacent-fit", "method-fit", "blocked-fit", "generic-fallback", "out-of-context")
rows = []
for label, root in PROJECTS.items():
    tests = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--project",
            "science",
            "science",
            "benchmark",
            "tests",
            "--commons",
            "--exclude-fallback",
            "--state",
            "concrete",
            "--format",
            "json",
            "--project-root",
            str(Path(root).expanduser()),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    triage = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--project",
            "science",
            "science",
            "benchmark",
            "test-triage",
            "--commons",
            "--format",
            "json",
            "--project-root",
            str(Path(root).expanduser()),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    tests_payload = json.loads(tests.stdout)
    triage_payload = json.loads(triage.stdout)
    counts = tests_payload["summary"]["context_fit_counts"]
    triage_counts = triage_payload["summary"]["context_fit_counts"]
    rows.append(
        {
            "project": label,
            "test_counts": counts,
            "triage_counts": triage_counts,
            "test_rows": tests_payload["summary"]["test_plan_rows"],
            "triage_rows": triage_payload["summary"]["test_plan_rows"],
        }
    )

lines = [
    "# Benchmark Context-Fit Calibration - 2026-07-04",
    "",
    "## Commands",
    "",
    "- `science benchmark tests --commons --exclude-fallback --state concrete --format json`",
    "- `science benchmark test-triage --commons --format json`",
    "",
    "## Projects",
    "",
]
for label, root in PROJECTS.items():
    lines.append(f"- `{root}`")
lines.extend(
    [
        "",
        "## Concrete Non-Fallback Test Rows",
        "",
        "| Project | rows | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
)
for row in rows:
    counts = row["test_counts"]
    lines.append(
        "| {project} | {total} | {direct} | {adjacent} | {method} | {blocked} | {generic} | {out} |".format(
            project=row["project"],
            total=row["test_rows"],
            direct=counts["direct-fit"],
            adjacent=counts["adjacent-fit"],
            method=counts["method-fit"],
            blocked=counts["blocked-fit"],
            generic=counts["generic-fallback"],
            out=counts["out-of-context"],
        )
    )
lines.extend(
    [
        "",
        "## Full Triage Rows",
        "",
        "| Project | rows | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
)
for row in rows:
    counts = row["triage_counts"]
    lines.append(
        "| {project} | {total} | {direct} | {adjacent} | {method} | {blocked} | {generic} | {out} |".format(
            project=row["project"],
            total=row["triage_rows"],
            direct=counts["direct-fit"],
            adjacent=counts["adjacent-fit"],
            method=counts["method-fit"],
            blocked=counts["blocked-fit"],
            generic=counts["generic-fallback"],
            out=counts["out-of-context"],
        )
    )
lines.extend(
    [
        "",
        "## Decision",
        "",
        "Context-fit is ready to merge when direct-fit rows remain plausible for",
        "the active cancer/data-source projects and natural-systems is not dominated",
        "by direct-fit biology benchmark rows. If this condition is not met, revise",
        "the classifier before merging.",
        "",
    ]
)
path = Path("docs/reports/benchmark-context-fit-calibration-2026-07-04.md")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("\n".join(lines), encoding="utf-8")
print(path)
PY
```

Expected: the script prints `docs/reports/benchmark-context-fit-calibration-2026-07-04.md`, and that file contains complete numeric rows for all four projects.

- [ ] **Step 6: Commit verification report**

```bash
rtk git add docs/reports/benchmark-context-fit-calibration-2026-07-04.md
rtk git commit -m "docs: calibrate benchmark context fit"
```

- [ ] **Step 7: Final status**

```bash
rtk git status --short
```

Expected: clean worktree.

---

## Self-Review Checklist for Implementer

Before requesting review:

- [ ] No changes to raw scoring helpers: `_relative_score`, `_candidate_score`, `baseline_score`.
- [ ] Context-fit classification happens while `DatasetOpportunityContext` is available.
- [ ] `broad_context` and cross-* warning cues are implemented together.
- [ ] `BenchmarkTestRow` JSON includes `context_fit`, `context_fit_reasons`, and `context_fit_warnings`.
- [ ] `BenchmarkTestSummary` includes `context_fit_counts`.
- [ ] Triage JSON includes `context_fit_counts_by_bucket`.
- [ ] `--context-fit` supports repeated OR filters on both `benchmark tests` and `benchmark test-triage`.
- [ ] Fallback and blocked raw rows remain available unless explicitly filtered by existing flags.
- [ ] Active-project calibration has been run and summarized.
