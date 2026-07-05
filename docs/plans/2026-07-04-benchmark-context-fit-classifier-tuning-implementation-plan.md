# Benchmark Context-Fit Classifier Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Demote misleading `direct-fit` benchmark rows with specific cross-context warnings while preserving legitimate same-context direct-fit rows.

**Architecture:** This is a small classifier refinement inside `_context_fit_for_row(...)`. Keep matching, scoring, CLI contracts, JSON row shape, and commons metadata unchanged. Add focused regression tests for the observed `cbioportal` / CPTAC-GBM leakage, then implement private helper functions that gate the existing direct-fit branch.

**Tech Stack:** Python 3.13, pytest, Click CLI test runner, existing `science_tool.benchmark_opportunities` helpers.

---

## File Map

- Modify: `science/tests/test_benchmark_opportunities.py`
  - Add three focused context-fit classifier tests near `test_context_fit_classifies_adjacent_cross_disease_rows(...)`.
- Modify: `science/src/science_tool/benchmark_opportunities.py`
  - Add private constants/helpers near `_context_fit_warning_cues(...)`.
  - Update only the `direct-fit` branch inside `_context_fit_for_row(...)`.
- Read: `docs/plans/2026-07-04-benchmark-context-fit-classifier-tuning-design.md`
  - Source design; no implementation edits needed.
- Do not modify CLI files, schema files, scoring functions, fallback selection, or commons metadata.

## Task 0: Confirm Worktree and Baseline

**Files:**
- Read only.

- [ ] **Step 1: Confirm branch and clean state**

Run from the worktree root:

```bash
rtk git status --short --branch
```

Expected output includes:

```text
* benchmark-context-fit-classifier-tuning-design
clean — nothing to commit
```

If the worktree is dirty, inspect the dirty files before continuing.

- [ ] **Step 2: Confirm Python imports resolve to this worktree**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python -c "import science_tool, pathlib; print(pathlib.Path(science_tool.__file__).resolve())"
```

Expected: printed path contains:

```text
.worktrees/benchmark-context-fit-classifier-tuning-design/science/src/science_tool
```

- [ ] **Step 3: Run the current context-fit regression baseline**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_context_fit_classifies_adjacent_cross_disease_rows \
  science/tests/test_benchmark_opportunities.py::test_context_fit_coarse_domain_tokens_are_broad_context \
  science/tests/test_benchmark_opportunities.py::test_context_fit_broad_tokens_do_not_promote_direct_fit \
  -q
```

Expected: PASS. If this fails before edits, stop and inspect because the baseline differs from the design.

## Task 1: Add Focused Failing Tests

**Files:**
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add a warned-direct demotion test**

In `science/tests/test_benchmark_opportunities.py`, immediately after
`test_context_fit_classifies_adjacent_cross_disease_rows(...)`, add:

```python
def test_context_fit_demotes_warned_direct_fit_without_specific_context_override(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    (tmp_path / "science.yaml").write_text("id: cbioportal\nname: cbioportal\n", encoding="utf-8")
    _write_entity(
        tmp_path,
        "hypotheses",
        "0502-breast-cptac-proteogenomics",
        """
id: hypothesis:0502-breast-cptac-proteogenomics
type: hypothesis
title: Breast cancer CPTAC proteogenomics benchmark hypothesis
""",
        body="Breast cancer CPTAC proteogenomics questions need supported benchmark evidence.",
    )
    _write_dataset(
        tmp_path,
        "cptac-gbm-2021-proteogenomics",
        """
id: dataset:cptac-gbm-2021-proteogenomics
type: dataset
title: CPTAC GBM proteogenomics
dataset_class: deposit
local_path: data/cptac-gbm
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [cross-modal]
  benchmark_kinds: [protein-rna-cross-modal]
  source_datasets: [cptac-gbm]
  tasks:
    - id: protein-rna-cross-modal
      task_type: protein rna cross modal prediction
      prediction_target: protein abundance
      held_out_unit: gene
      metric: spearman
      baseline: transcript-only ridge
      ground_truth:
        type: measured-outcome
        description: protein abundance
      support:
        state: supported
""",
    )

    row = benchmark_tests_report(tmp_path)["benchmark_tests"][0]

    assert row["context_fit"] == "adjacent-fit"
    assert "cross-disease:gbm-vs-breast" in row["context_fit_warnings"]
    assert "context-warning:demoted-direct-fit" in row["context_fit_reasons"]
    assert "specific-context:cptac" in row["context_fit_reasons"]
    assert "specific-context:proteogenomics" in row["context_fit_reasons"]
```

Why this fixture fails before implementation:

- `breast` and `gbm` create `cross-disease:gbm-vs-breast`;
- shared `cptac` / `proteogenomics` create `strong_context`;
- `support.state: supported` creates `task_signal`;
- the current direct-fit branch returns `direct-fit` before considering the warning.

- [ ] **Step 2: Add an explicit source-study override preservation test**

Immediately after the demotion test, add:

```python
def test_context_fit_preserves_direct_fit_with_explicit_source_study_override(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    (tmp_path / "science.yaml").write_text("id: cbioportal\nname: cbioportal\n", encoding="utf-8")
    _write_entity(
        tmp_path,
        "hypotheses",
        "0503-breast-cptac-gbm-proteogenomics",
        """
id: hypothesis:0503-breast-cptac-gbm-proteogenomics
type: hypothesis
title: Breast cancer CPTAC-GBM benchmark hypothesis
""",
        body="Breast cancer CPTAC-GBM proteogenomics questions need supported benchmark evidence.",
    )
    _write_dataset(
        tmp_path,
        "cptac-gbm-2021-proteogenomics",
        """
id: dataset:cptac-gbm-2021-proteogenomics
type: dataset
title: CPTAC GBM proteogenomics
dataset_class: deposit
local_path: data/cptac-gbm
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [cross-modal]
  benchmark_kinds: [protein-rna-cross-modal]
  source_datasets: [cptac-gbm]
  tasks:
    - id: protein-rna-cross-modal
      task_type: protein rna cross modal prediction
      prediction_target: protein abundance
      held_out_unit: gene
      metric: spearman
      baseline: transcript-only ridge
      ground_truth:
        type: measured-outcome
        description: protein abundance
      support:
        state: supported
""",
    )

    row = benchmark_tests_report(tmp_path)["benchmark_tests"][0]

    assert row["context_fit"] == "direct-fit"
    assert "cross-disease:gbm-vs-breast" in row["context_fit_warnings"]
    assert "specific-context:cptac-gbm" in row["context_fit_reasons"]
    assert "context-warning:demoted-direct-fit" not in row["context_fit_reasons"]
```

This fixture explicitly contains `cptac-gbm`, which the tokenizer keeps as a
single token (`_TOKEN_RE` retains hyphens). `cptac-gbm` is a **declared
`source_datasets` token** for this benchmark, so it — and only it — is the
source-study override. Plain `cptac` / `proteogenomics` is intentionally not
enough: they are not declared provenance tokens.

- [ ] **Step 3: Add a modality-compound non-override guard test**

Immediately after the preservation test, add a test proving that a shared
*modality/method* compound token does **not** preserve `direct-fit`. This guards
against the rejected "any hyphenated shared token overrides" heuristic; the
override must key on declared benchmark provenance, not on the presence of a
hyphen.

```python
def test_context_fit_shared_modality_compound_does_not_override_warning(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    (tmp_path / "science.yaml").write_text("id: cbioportal\nname: cbioportal\n", encoding="utf-8")
    _write_entity(
        tmp_path,
        "hypotheses",
        "0504-breast-single-cell-cross-modal",
        """
id: hypothesis:0504-breast-single-cell-cross-modal
type: hypothesis
title: Breast cancer single-cell cross-modal benchmark hypothesis
""",
        body="Breast cancer single-cell cross-modal questions need supported benchmark evidence.",
    )
    _write_dataset(
        tmp_path,
        "cptac-gbm-2021-proteogenomics",
        """
id: dataset:cptac-gbm-2021-proteogenomics
type: dataset
title: GBM single-cell cross-modal proteogenomics
dataset_class: deposit
local_path: data/cptac-gbm
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [cross-modal]
  benchmark_kinds: [protein-rna-cross-modal]
  source_datasets: [cptac-gbm]
  tasks:
    - id: protein-rna-cross-modal
      task_type: protein rna cross modal prediction
      prediction_target: protein abundance
      held_out_unit: gene
      metric: spearman
      baseline: transcript-only ridge
      ground_truth:
        type: measured-outcome
        description: protein abundance
      support:
        state: supported
""",
    )

    row = benchmark_tests_report(tmp_path)["benchmark_tests"][0]

    # `single-cell` / `cross-modal` are shared compound tokens, but they are NOT
    # declared `source_datasets` provenance, so they must not override the
    # cross-disease warning. The entity never names `cptac-gbm`, so no override
    # applies and the row demotes.
    assert row["context_fit"] == "adjacent-fit"
    assert "cross-disease:gbm-vs-breast" in row["context_fit_warnings"]
    assert "context-warning:demoted-direct-fit" in row["context_fit_reasons"]
    assert "specific-context:cross-modal" in row["context_fit_reasons"]
    assert "specific-context:cptac-gbm" not in row["context_fit_reasons"]
```

- [ ] **Step 4: Run the new tests and verify the red signal**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_context_fit_demotes_warned_direct_fit_without_specific_context_override \
  science/tests/test_benchmark_opportunities.py::test_context_fit_preserves_direct_fit_with_explicit_source_study_override \
  science/tests/test_benchmark_opportunities.py::test_context_fit_shared_modality_compound_does_not_override_warning \
  -q
```

Expected: FAIL on both `test_context_fit_demotes_warned_direct_fit_without_specific_context_override`
and `test_context_fit_shared_modality_compound_does_not_override_warning`, each with:

```text
E       AssertionError: assert 'direct-fit' == 'adjacent-fit'
```

The preservation test may already pass before implementation (the current
unconditional direct-fit branch returns `direct-fit`); the required red signal is
the two demotion tests.

- [ ] **Step 5: Commit the failing tests**

Run:

```bash
rtk git add science/tests/test_benchmark_opportunities.py
rtk git commit -m "test: cover warned context-fit direct demotion"
```

Expected: commit succeeds.

## Task 2: Implement Direct-Fit Safety Gate

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`

- [ ] **Step 1: Add the direct-fit safety-gate helpers**

In `science/src/science_tool/benchmark_opportunities.py`, near
`DISEASE_CONTEXT_TOKENS` and before `_context_fit_warning_cues(...)`, add:

```python
DIRECT_FIT_DEMOTION_REASON = "context-warning:demoted-direct-fit"
DIRECT_FIT_BLOCKING_WARNING_VALUES = frozenset({"cell-line-vs-primary", "simulated-vs-observed"})


def _direct_fit_blocking_warnings(warnings: Sequence[str]) -> list[str]:
    return sorted(
        warning
        for warning in warnings
        if warning.startswith("cross-disease:") or warning in DIRECT_FIT_BLOCKING_WARNING_VALUES
    )


def _benchmark_source_study_tokens(context: DatasetOpportunityContext) -> frozenset[str]:
    # The override axis is the benchmark's DECLARED provenance (`source_datasets`),
    # not "any hyphenated token". Disease tokens are excluded on purpose: sharing a
    # disease never clears a sample-provenance warning, and a genuinely shared
    # disease already self-defuses the cross-disease warning upstream (it makes the
    # disease token sets non-disjoint in `_context_fit_warning_cues`).
    tokens = _specific_tokens(_tokens_from_text(*context.dataset.source_datasets, include_stop_tokens=False))
    return tokens - DISEASE_CONTEXT_TOKENS


def _has_direct_context_override(
    *,
    shared_specific: Sequence[str],
    source_study_tokens: frozenset[str],
) -> bool:
    return bool(set(shared_specific) & source_study_tokens)
```

Design note: there is intentionally **no** disease-token override branch. A row
can only reach the direct-fit gate with a `cross-disease:*` warning present when
the shared/entity tokens do **not** include the benchmark disease (otherwise the
warning would not have fired). A disease-token override is therefore unreachable
by construction; only declared `source_datasets` provenance can preserve a warned
direct-fit. See the design doc's "Ideal Architecture / Deferred Keystone" for why
disease/subsumption overrides require the typed `ContextProfile` refactor.

No import change is required: the helpers use `Sequence` (already imported),
`DatasetOpportunityContext`, `_tokens_from_text`, `_specific_tokens`, and
`DISEASE_CONTEXT_TOKENS`, all already in scope.

- [ ] **Step 2: Update the direct-fit branch**

In `_context_fit_for_row(...)`, replace:

```python
    if predicates.strong_context and predicates.task_signal:
        return "direct-fit", sorted(set(reasons)), sorted(set(warnings))
```

with:

```python
    if predicates.strong_context and predicates.task_signal:
        blocking_warnings = _direct_fit_blocking_warnings(warnings)
        if not blocking_warnings or _has_direct_context_override(
            shared_specific=shared_specific,
            source_study_tokens=_benchmark_source_study_tokens(context),
        ):
            return "direct-fit", sorted(set(reasons)), sorted(set(warnings))
        reasons.append(DIRECT_FIT_DEMOTION_REASON)
        return "adjacent-fit", sorted(set(reasons)), sorted(set(warnings))
```

This is the only classifier behavior change in this task.

- [ ] **Step 3: Run the focused red-green tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_context_fit_demotes_warned_direct_fit_without_specific_context_override \
  science/tests/test_benchmark_opportunities.py::test_context_fit_preserves_direct_fit_with_explicit_source_study_override \
  science/tests/test_benchmark_opportunities.py::test_context_fit_shared_modality_compound_does_not_override_warning \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run context-fit regression tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_context_fit_classifies_adjacent_cross_disease_rows \
  science/tests/test_benchmark_opportunities.py::test_context_fit_readiness_blocked_rows_are_blocked_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_limitations_do_not_promote_direct_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_numeric_tokens_do_not_promote_direct_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_broad_tokens_do_not_promote_direct_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_blocked_fallback_without_context_is_generic \
  -q
```

Expected: PASS.

- [ ] **Step 5: Run static checks for touched source**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
```

Expected: PASS.

- [ ] **Step 6: Commit implementation**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "fix: demote warned benchmark direct fits"
```

Expected: commit succeeds.

## Task 3: Real-Project Smoke and Final Verification

**Files:**
- Read only unless a bug is found.

- [ ] **Step 1: Run cBioPortal direct-fit smoke check**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python -c "import json, subprocess; from pathlib import Path; project_root=str(Path('~/d/cancer/data-sources/cbioportal').expanduser()); command=['rtk','uv','run','--frozen','--project','science','science','benchmark','gaps','--commons','--context-fit','direct-fit','--format','json','--project-root',project_root]; completed=subprocess.run(command, text=True, capture_output=True, check=True); payload=json.loads(completed.stdout); rows=[(gap['entity_id'], candidate['benchmark_id'], candidate['context_fit_warnings']) for gap in payload['benchmark_gaps'] for candidate in gap['candidate_benchmarks'] if candidate['benchmark_id']=='dataset:cptac-gbm-2021-proteogenomics' and any(warning.startswith('cross-disease:') for warning in candidate['context_fit_warnings'])]; print(f'warned_direct_cptac_gbm_rows={len(rows)}'); raise SystemExit(1 if rows else 0)"
```

Expected output:

```text
warned_direct_cptac_gbm_rows=0
```

If this prints a positive count, inspect the first few rows with
`science benchmark gaps --commons --context-fit direct-fit --format json --project-root ~/d/cancer/data-sources/cbioportal`
before changing code.

- [ ] **Step 2: Run cBioPortal adjacent-fit smoke check**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python -c "import json, subprocess; from pathlib import Path; project_root=str(Path('~/d/cancer/data-sources/cbioportal').expanduser()); command=['rtk','uv','run','--frozen','--project','science','science','benchmark','gaps','--commons','--context-fit','adjacent-fit','--format','json','--project-root',project_root]; completed=subprocess.run(command, text=True, capture_output=True, check=True); payload=json.loads(completed.stdout); rows=[(gap['entity_id'], candidate['benchmark_id'], candidate['context_fit_reasons'], candidate['context_fit_warnings']) for gap in payload['benchmark_gaps'] for candidate in gap['candidate_benchmarks'] if candidate['benchmark_id']=='dataset:cptac-gbm-2021-proteogenomics' and 'context-warning:demoted-direct-fit' in candidate['context_fit_reasons']]; print(f'demoted_adjacent_cptac_gbm_rows={len(rows)}'); raise SystemExit(1 if not rows else 0)"
```

Expected output: a positive count, usually near the pass-1 warned direct-fit baseline:

```text
demoted_adjacent_cptac_gbm_rows=23
```

The exact count may change if project or commons metadata changed after the pass-1 report. The required property is positive demoted adjacent rows and zero warned direct CPTAC-GBM rows from Step 1.

- [ ] **Step 3: Project-wide surviving-direct-fit inspection (wrong-preservation guard)**

Steps 1–2 only inspect CPTAC-GBM. This step catches the failure mode where the
override wrongly preserves a warned row on *any* benchmark. Because the query
filters to `direct-fit`, every listed row survived the gate **while carrying a
blocking warning** — so each must be justified by declared benchmark provenance,
not by an incidental modality/broad compound.

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python -c "import json, subprocess; from pathlib import Path; pr=str(Path('~/d/cancer/data-sources/cbioportal').expanduser()); p=json.loads(subprocess.run(['rtk','uv','run','--frozen','--project','science','science','benchmark','gaps','--commons','--context-fit','direct-fit','--format','json','--project-root',pr], text=True, capture_output=True, check=True).stdout); blk=lambda ws:[w for w in ws if w.startswith('cross-disease:') or w in {'cell-line-vs-primary','simulated-vs-observed'}]; rows=[(g['entity_id'], c['benchmark_id'], c['context_fit_reasons'], c['context_fit_warnings']) for g in p['benchmark_gaps'] for c in g['candidate_benchmarks'] if blk(c['context_fit_warnings'])]; print(f'direct_fit_rows_with_blocking_warning={len(rows)}'); [print(r) for r in rows[:10]]"
```

Expected: usually `0` for `cbioportal`. A positive count is **not** an automatic
failure, but each row must be manually confirmed to share a real declared
`source_datasets` token (its `context_fit_reasons` should carry a
`specific-context:<source-study>` entry that matches the benchmark's provenance).
If any surviving row is justified only by a modality/method compound
(e.g. `specific-context:cross-modal`, `specific-context:single-cell`) or a broad
token (e.g. `specific-context:pan-cancer`), that is a bug in
`_benchmark_source_study_tokens(...)` — stop and inspect before proceeding.

- [ ] **Step 4: Project-wide demotion invariant (spurious-demotion guard)**

This asserts the reciprocal: every row that received the demotion reason actually
carried a blocking warning. A demoted row without a blocking warning would mean a
legitimate direct-fit row was demoted for the wrong reason.

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python -c "import json, subprocess; from pathlib import Path; pr=str(Path('~/d/cancer/data-sources/cbioportal').expanduser()); p=json.loads(subprocess.run(['rtk','uv','run','--frozen','--project','science','science','benchmark','gaps','--commons','--context-fit','adjacent-fit','--format','json','--project-root',pr], text=True, capture_output=True, check=True).stdout); blk=lambda ws:[w for w in ws if w.startswith('cross-disease:') or w in {'cell-line-vs-primary','simulated-vs-observed'}]; demoted=[c for g in p['benchmark_gaps'] for c in g['candidate_benchmarks'] if 'context-warning:demoted-direct-fit' in c['context_fit_reasons']]; bad=[c['benchmark_id'] for c in demoted if not blk(c['context_fit_warnings'])]; print(f'demoted_rows={len(demoted)} demoted_without_blocking_warning={len(bad)}'); [print(b) for b in bad[:10]]; raise SystemExit(1 if bad else 0)"
```

Expected output includes `demoted_without_blocking_warning=0` and exits `0`. A
non-zero `bad` count means the demotion branch is firing on rows with no blocking
warning — stop and inspect.

- [ ] **Step 5: Run the benchmark opportunity test file subset**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -q
```

Expected: PASS.

- [ ] **Step 6: Run diff and status checks**

Run:

```bash
rtk git diff --check
rtk git status --short --branch
```

Expected:

- no whitespace errors;
- branch is `benchmark-context-fit-classifier-tuning-design`;
- worktree is clean after Task 2 commit.

- [ ] **Step 7: Final handoff**

Report:

- the two commits created by this plan;
- focused tests and smoke commands run;
- cBioPortal direct-fit smoke count from Step 1;
- cBioPortal adjacent-fit demotion count from Step 2;
- the project-wide surviving-warned-direct-fit count from Step 3, with a note on
  whether any survivor was justified by non-provenance tokens;
- the project-wide demotion-invariant result from Step 4
  (`demoted_without_blocking_warning`);
- whether source/API/CLI/JSON contracts changed.

Do not merge to `main` until the implementation has been reviewed.

## Self-Review Checklist

- Spec coverage:
  - warned direct-fit demotion: Task 1 and Task 2;
  - explicit declared-source-study preservation: Task 1 and Task 2;
  - modality/broad compound does NOT override (provenance-only override): Task 1
    Step 3 and Task 2;
  - raw matching/scoring/metadata unchanged: File Map and Task 2 scope;
  - real-project smoke incl. project-wide wrong-preservation and
    spurious-demotion guards: Task 3;
  - deferred typed `ContextProfile` refactor: intentionally out of scope.
- Placeholder scan: this plan contains no incomplete requirement slots.
- Type consistency:
  - helpers use existing `Sequence` and `DatasetOpportunityContext`; no new
    imports are added (the earlier `Iterable`/hyphen-heuristic approach was
    dropped in favor of a declared-`source_datasets` override);
  - tests assert existing `BenchmarkTestRow` fields;
  - no new public TypedDict or CLI fields are introduced.
