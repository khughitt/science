# Benchmark Gap Calibration V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science benchmark gaps` more actionable by adding entity-specific facet hints, per-entity near-miss candidates, gap calibration evidence, and stricter token hygiene.

**Architecture:** Keep `science_tool.benchmark_opportunities` as the single report assembly module. Extract a private `_opportunity_analysis()` helper that caches entities, dataset contexts, and the public `OpportunityReport`; then make `opportunity_report()` and `gaps_report()` project from that helper. Add deterministic diagnostic helpers for hint inference, candidate scoring, and calibration output without changing positive opportunity matching semantics.

**Tech Stack:** Python 3.12/3.13, Click, Rich, pytest/CliRunner, existing Science benchmark catalog/opportunity helpers, ruff, pyright.

---

## Design References

- `docs/plans/2026-06-28-benchmark-gap-calibration-v2-design.md`
- `docs/plans/2026-06-28-benchmark-gaps-design.md`
- `docs/plans/2026-06-27-benchmark-opportunities-design.md`
- `science/src/science_tool/benchmark_opportunities.py`
- `science/src/science_tool/cli.py`
- `science/tests/test_benchmark_opportunities.py`

## File Structure

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add `BENCHMARK_GAP_HINT_FACETS`, entity-token suppression, expanded dataset broad-facet exclusions, hint lexicon, and deterministic facet/note sorting helpers.
  - Extend `TokenEvidence`, gap candidate row contracts, and gap report contracts.
  - Extract `_opportunity_analysis()` so public reports share cached entities and dataset contexts.
  - Add per-entity facet hints, near-miss candidate scoring, and optional gap calibration payload.
- Modify `science/src/science_tool/cli.py`
  - Add `--calibration-report` to `science benchmark gaps`.
  - Pass the flag into `gaps_report()`.
  - Render a compact calibration table after the normal gap table.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add direct report tests for facet hint inference, valid facet drift, near-miss candidates, scoring independence, token hygiene, and calibration payload.
  - Add CLI tests for `--facet single-cell-rna-seq` and `benchmark gaps --calibration-report`.

## Public Contract Additions

`science benchmark gaps --format json` gains:

```json
{
  "calibration": {
    "enabled": false
  }
}
```

Each `candidate_benchmarks[]` row keeps the existing v1 fields and adds:

```json
{
  "candidate_score": 0,
  "matched_hint_facets": [],
  "reason_notes": []
}
```

With `--calibration-report`, the top-level `calibration` object includes:

```json
{
  "enabled": true,
  "gap_entity_evidence": {},
  "candidate_evidence": []
}
```

---

### Task 1: Constants, Facet Validation, and Token Hygiene

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing tests for facet drift and broad token suppression**

Append these tests near the existing gap tests in `science/tests/test_benchmark_opportunities.py`:

```python
def test_gap_hint_facets_are_the_facet_filter_valid_set(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import BENCHMARK_GAP_HINT_FACETS, gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0011-single-cell",
        """
id: hypothesis:0011-single-cell
type: hypothesis
title: Single-cell longitudinal benchmark gap
""",
        body="Single-cell longitudinal data would test the model.",
    )

    for facet in BENCHMARK_GAP_HINT_FACETS:
        payload = gaps_report(tmp_path, facet=facet)
        assert payload["summary"]["entities_total"] == 1


def test_broad_dataset_and_entity_tokens_do_not_create_opportunity_matches(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0012-broad",
        """
id: hypothesis:0012-broad
type: hypothesis
title: Cancer hypothesis summary
status: active
""",
        body="Summary statement about cancer biology varies by cohort.",
    )
    _write_dataset(
        tmp_path,
        "broad",
        """
id: dataset:broad
type: dataset
title: Broad Dataset
benchmark:
  domains: [biology, cancer]
  modalities: [varies]
  signal_types: [static]
  benchmark_kinds: [association]
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False, calibration_report=True)

    assert payload["matched_opportunities"] == []
    assert payload["unmapped_project_entities"][0]["entity_id"] == "hypothesis:0012-broad"
    dropped = payload["calibration"]["dropped_tokens"]
    assert "summary" in dropped["broad_entity"]["hypothesis:0012-broad"]
    benchmark_tokens = payload["calibration"]["benchmark_controlled_facet_tokens"]["dataset:broad"]
    assert "cancer" in benchmark_tokens
    assert "varies" in benchmark_tokens
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gap_hint_facets_are_the_facet_filter_valid_set \
  science/tests/test_benchmark_opportunities.py::test_broad_dataset_and_entity_tokens_do_not_create_opportunity_matches -q
```

Expected: FAIL because `BENCHMARK_GAP_HINT_FACETS` is not defined and broad-token calibration buckets are not present.

- [ ] **Step 3: Add constants and extend token evidence**

In `science/src/science_tool/benchmark_opportunities.py`, replace the current broad/stop constant block with:

```python
HIGH_VALUE_SIGNALS = frozenset(HIGH_VALUE_SIGNAL_POINTS)
HIGH_VALUE_MODALITIES = frozenset(HIGH_VALUE_MODALITY_POINTS)
GAP_MODALITIES = ("proteomics", "spatial", "multimodal")
GAP_SIGNAL_TYPES = ("perturbation", "time-series", "cross-context-generalization")
GAP_FACETS = frozenset((*GAP_MODALITIES, *GAP_SIGNAL_TYPES))
BENCHMARK_GAP_HINT_FACETS = (
    "proteomics",
    "spatial",
    "multimodal",
    "perturbation",
    "time-series",
    "cross-context-generalization",
    "longitudinal",
    "multi-omic",
    "single-cell-rna-seq",
)
BENCHMARK_GAP_HINT_FACET_SET = frozenset(BENCHMARK_GAP_HINT_FACETS)
BROAD_NON_SCOREABLE_FACETS = frozenset({"biology", "cancer", "varies"})
ENTITY_SUPPRESSED_TOKENS = frozenset(
    {
        "claim",
        "statement",
        "summary",
        "question",
        "hypothesis",
        "proposition",
    }
)
```

Keep the existing `_STOP_TOKENS` set unchanged. Workflow words such as
`analysis`, `cell`, `data`, `dataset`, `evidence`, `model`, `result`, and
`response` should continue to land in the `stop` evidence bucket. The new
`ENTITY_SUPPRESSED_TOKENS` set is only for entity/document boilerplate that
should land in the `broad_entity` bucket.

Update `TokenEvidence`:

```python
@dataclass(frozen=True)
class TokenEvidence:
    kept: frozenset[str]
    stop: frozenset[str]
    broad: frozenset[str]
    short: frozenset[str]
```

Replace `_token_evidence_from_text()` with:

```python
def _token_evidence_from_text(
    *values: str,
    include_stop_tokens: bool = False,
    broad_tokens: frozenset[str] = frozenset(),
) -> TokenEvidence:
    kept: set[str] = set()
    stop: set[str] = set()
    broad: set[str] = set()
    short: set[str] = set()
    for value in values:
        for raw in _TOKEN_RE.findall(value):
            token = _normalize_token(raw)
            if token in broad_tokens:
                broad.add(token)
                continue
            if not include_stop_tokens and token in _STOP_TOKENS:
                stop.add(token)
                continue
            if len(token) < 3 and not re.fullmatch(r"[hq]\d+", token):
                short.add(token)
                continue
            kept.add(token)
    return TokenEvidence(kept=frozenset(kept), stop=frozenset(stop), broad=frozenset(broad), short=frozenset(short))
```

Replace `_tokens_from_text()` with:

```python
def _tokens_from_text(
    *values: str,
    include_stop_tokens: bool = False,
    broad_tokens: frozenset[str] = frozenset(),
) -> frozenset[str]:
    return _token_evidence_from_text(
        *values,
        include_stop_tokens=include_stop_tokens,
        broad_tokens=broad_tokens,
    ).kept
```

Update `load_project_entities()` so entity tokens suppress entity-side broad tokens:

```python
tokens = _tokens_from_text(entity_id, title, content_preview, broad_tokens=ENTITY_SUPPRESSED_TOKENS)
```

- [ ] **Step 4: Update facet validation and scoreable facets**

Replace `_normalized_gap_facet()` with:

```python
def _normalized_gap_facet(facet: str | None) -> str | None:
    if facet is None:
        return None
    normalized = _normalize_token(facet)
    if not normalized:
        raise ValueError("facet must not be blank")
    if normalized not in BENCHMARK_GAP_HINT_FACET_SET:
        raise ValueError(f"unknown benchmark gap facet: {facet}")
    return normalized
```

Keep `_scoreable_facet_tokens()` as the dataset-side exclusion point; it will now exclude `biology`, `cancer`, and `varies` because the constant changed:

```python
def _scoreable_facet_tokens(controlled_facet_tokens: frozenset[str]) -> frozenset[str]:
    return frozenset(token for token in controlled_facet_tokens if token not in BROAD_NON_SCOREABLE_FACETS)
```

- [ ] **Step 5: Update calibration dropped-token shape**

Replace `DroppedTokenPayload` with:

```python
class DroppedTokenPayload(TypedDict):
    stop: dict[str, list[str]]
    broad_entity: dict[str, list[str]]
    broad_dataset_facet: dict[str, list[str]]
    short: dict[str, list[str]]
```

In `_calibration_payload()`, compute entity and benchmark evidence separately:

```python
entity_token_evidence = {
    entity.id: _token_evidence_from_text(
        entity.id,
        entity.title,
        entity.content_preview,
        broad_tokens=ENTITY_SUPPRESSED_TOKENS,
    )
    for entity in entities
}
benchmark_token_evidence = {
    context.dataset.id: _token_evidence_from_text(*_dataset_evidence_values(context.dataset))
    for context in contexts
}
benchmark_facet_evidence = {
    context.dataset.id: _token_evidence_from_text(
        *context.dataset.domains,
        *context.dataset.modalities,
        *context.dataset.signal_types,
        *context.dataset.benchmark_kinds,
        broad_tokens=BROAD_NON_SCOREABLE_FACETS,
    )
    for context in contexts
}
```

Replace the `dropped_tokens` mapping in the returned payload with:

```python
"dropped_tokens": {
    "stop": {
        stable_id: sorted(evidence.stop)
        for stable_id, evidence in {**entity_token_evidence, **benchmark_token_evidence}.items()
        if evidence.stop
    },
    "broad_entity": {
        stable_id: sorted(evidence.broad)
        for stable_id, evidence in entity_token_evidence.items()
        if evidence.broad
    },
    "broad_dataset_facet": {
        stable_id: sorted(evidence.broad)
        for stable_id, evidence in benchmark_facet_evidence.items()
        if evidence.broad
    },
    "short": {
        stable_id: sorted(evidence.short)
        for stable_id, evidence in {**entity_token_evidence, **benchmark_token_evidence}.items()
        if evidence.short
    },
},
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gap_hint_facets_are_the_facet_filter_valid_set \
  science/tests/test_benchmark_opportunities.py::test_broad_dataset_and_entity_tokens_do_not_create_opportunity_matches -q
```

Expected: PASS.

Commit:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): define gap hint facets"
```

### Task 2: Shared Opportunity Analysis Helper

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add a regression test that opportunities and gaps share commons notice and entity filtering**

Append:

```python
def test_gap_report_uses_shared_opportunity_analysis_for_entity_filter(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report, opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0013-target",
        """
id: hypothesis:0013-target
type: hypothesis
title: Target perturbation benchmark gap
""",
        body="Perturbation benchmark coverage is missing.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0014-other",
        """
id: hypothesis:0014-other
type: hypothesis
title: Other spatial benchmark gap
""",
        body="Spatial benchmark coverage is missing.",
    )

    opportunity = opportunity_report(tmp_path, entity_id="hypothesis:0013-target")
    gaps = gaps_report(tmp_path, entity_id="hypothesis:0013-target")

    assert [row["entity_id"] for row in opportunity["unmapped_project_entities"]] == ["hypothesis:0013-target"]
    assert [row["entity_id"] for row in gaps["benchmark_gaps"]] == ["hypothesis:0013-target"]
    assert gaps["summary"]["entities_total"] == 1
```

- [ ] **Step 2: Run the regression test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gap_report_uses_shared_opportunity_analysis_for_entity_filter -q
```

Expected before refactor: PASS. This is a lock-in test before changing internals.

- [ ] **Step 3: Add analysis dataclass and report builder**

In `science/src/science_tool/benchmark_opportunities.py`, add after `OpportunityReport`:

```python
@dataclass(frozen=True)
class OpportunityAnalysis:
    entities: list[ProjectBenchmarkEntity]
    contexts: list[DatasetOpportunityContext]
    report: OpportunityReport
```

Extract the body of `opportunity_report()` into two helpers:

```python
def _build_opportunity_report(
    entities: list[ProjectBenchmarkEntity],
    contexts: list[DatasetOpportunityContext],
    notice: str | None,
    *,
    calibration_report: bool,
) -> OpportunityReport:
    seen_facets: set[tuple[str, str]] = set()
    matched: list[OpportunityRow] = []
    for entity in entities:
        for context in contexts:
            matched.extend(_rows_for_match(entity, context, seen_facets))
    matched.sort(
        key=lambda row: (
            -row["relative_score"],
            -row["baseline_score"],
            row["entity_id"],
            row["benchmark_id"],
            "" if row["task_id"] is None else row["task_id"],
        )
    )
    matched_entity_ids = {row["entity_id"] for row in matched}
    matched_benchmark_ids = {row["benchmark_id"] for row in matched}
    return {
        "matched_opportunities": matched,
        "coverage_gaps": _coverage_gaps(entities, matched),
        "available_unmapped_benchmarks": _available_unmapped_benchmarks(contexts, matched_benchmark_ids),
        "unmapped_project_entities": [
            {"entity_id": entity.id, "entity_title": entity.title, "observed_tokens": sorted(entity.tokens)}
            for entity in entities
            if entity.id not in matched_entity_ids
        ],
        "calibration": _calibration_payload(entities, contexts, matched, enabled=calibration_report),
        "commons_notice": notice,
    }
```

Add:

```python
def _opportunity_analysis(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    calibration_report: bool = False,
    include_prose_tokens: bool | None = None,
) -> OpportunityAnalysis:
    entities = load_project_entities(project_root)
    if entity_id is not None:
        entities = [entity for entity in entities if entity.id == entity_id]
    datasets, notice = load_opportunity_datasets(project_root, include_commons=include_commons)
    if domain is not None:
        datasets = [dataset for dataset in datasets if domain in dataset.domains]
    should_include_prose = calibration_report if include_prose_tokens is None else include_prose_tokens
    contexts = [_dataset_context(dataset, include_prose_tokens=should_include_prose) for dataset in datasets]
    report = _build_opportunity_report(
        entities,
        contexts,
        notice,
        calibration_report=calibration_report,
    )
    return OpportunityAnalysis(entities=entities, contexts=contexts, report=report)
```

- [ ] **Step 4: Make `opportunity_report()` delegate to `_opportunity_analysis()`**

Replace `opportunity_report()` with:

```python
def opportunity_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    calibration_report: bool = False,
) -> OpportunityReport:
    return _opportunity_analysis(
        project_root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
        calibration_report=calibration_report,
    ).report
```

- [ ] **Step 5: Make `gaps_report()` use the shared analysis**

At the start of `gaps_report()`, replace:

```python
opportunity = opportunity_report(
    project_root,
    include_commons=include_commons,
    entity_id=entity_id,
    domain=domain,
)
```

with:

```python
analysis = _opportunity_analysis(
    project_root,
    include_commons=include_commons,
    entity_id=entity_id,
    domain=domain,
)
opportunity = analysis.report
```

- [ ] **Step 6: Run focused and full benchmark tests, then commit**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gap_report_uses_shared_opportunity_analysis_for_entity_filter -q
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -q
```

Expected: PASS.

Commit:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "refactor(benchmark): share opportunity analysis"
```

### Task 3: Entity Facet Hints and Suggested Search Facets

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing tests for inferred hints and facet filtering**

Append:

```python
def test_gaps_report_infers_suggested_facets_for_uncovered_entity(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0015-longitudinal",
        """
id: hypothesis:0015-longitudinal
type: hypothesis
title: Dynamic single-cell proteomics gap
""",
        body="Longitudinal perturbation trajectories require proteomics and single-cell data.",
    )

    payload = gaps_report(tmp_path)

    row = payload["benchmark_gaps"][0]
    assert row["gap_level"] == "uncovered"
    assert row["suggested_search_facets"] == [
        "proteomics",
        "perturbation",
        "time-series",
        "longitudinal",
        "single-cell-rna-seq",
    ]


def test_gaps_report_facet_filter_uses_inferred_hints(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0016-single-cell",
        """
id: hypothesis:0016-single-cell
type: hypothesis
title: Single-cell benchmark gap
""",
        body="Single-cell assays are needed.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0017-proteomics",
        """
id: hypothesis:0017-proteomics
type: hypothesis
title: Proteomics benchmark gap
""",
        body="Proteomics assays are needed.",
    )

    payload = gaps_report(tmp_path, facet="single-cell-rna-seq")

    assert [row["entity_id"] for row in payload["benchmark_gaps"]] == ["hypothesis:0016-single-cell"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_infers_suggested_facets_for_uncovered_entity \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_facet_filter_uses_inferred_hints -q
```

Expected: FAIL because uncovered rows only use existing `coverage_gaps` missing facets.

- [ ] **Step 3: Add hint lexicon and sorting helpers**

Add near the constants:

```python
FACET_HINT_TERMS: dict[str, str] = {
    "intervention": "perturbation",
    "drug": "perturbation",
    "compound": "perturbation",
    "knockout": "perturbation",
    "perturb": "perturbation",
    "perturbation": "perturbation",
    "time-series": "time-series",
    "timeseries": "time-series",
    "temporal": "time-series",
    "dynamic": "time-series",
    "longitudinal": "longitudinal",
    "trajectory": "time-series",
    "proteomic": "proteomics",
    "proteomics": "proteomics",
    "protein": "proteomics",
    "phosphoproteomic": "proteomics",
    "phosphoproteomics": "proteomics",
    "spatial": "spatial",
    "region": "spatial",
    "microenvironment": "spatial",
    "neighborhood": "spatial",
    "multimodal": "multimodal",
    "multi-modal": "multimodal",
    "multiomic": "multi-omic",
    "multi-omic": "multi-omic",
    "proteogenomic": "multimodal",
    "proteogenomics": "multimodal",
    "single-cell": "single-cell-rna-seq",
    "singlecell": "single-cell-rna-seq",
    "scrna": "single-cell-rna-seq",
    "scrna-seq": "single-cell-rna-seq",
    "single-cell-rna-seq": "single-cell-rna-seq",
    "transfer": "cross-context-generalization",
    "generalization": "cross-context-generalization",
    "cross-context": "cross-context-generalization",
    "external": "cross-context-generalization",
    "validation": "cross-context-generalization",
}
```

Add helpers near `_normalized_gap_facet()`:

```python
def _facet_sort_key(facet: str) -> tuple[int, str]:
    try:
        return (BENCHMARK_GAP_HINT_FACETS.index(facet), facet)
    except ValueError:
        return (len(BENCHMARK_GAP_HINT_FACETS), facet)


def _sorted_facets(facets: set[str] | list[str]) -> list[str]:
    return sorted({_normalize_token(facet) for facet in facets}, key=_facet_sort_key)


def _entity_facet_hints(entity: ProjectBenchmarkEntity) -> list[str]:
    hints: set[str] = set()
    for token in entity.tokens:
        hint = FACET_HINT_TERMS.get(token)
        if hint is not None and hint in BENCHMARK_GAP_HINT_FACET_SET:
            hints.add(hint)
    return _sorted_facets(hints)
```

- [ ] **Step 4: Use inferred hints in gap rows and filters**

Inside the `for current_entity_id in entity_ids:` loop in `gaps_report()`, add an entity lookup before the loop:

```python
entity_by_id = {entity.id: entity for entity in analysis.entities}
```

Inside the loop, after `missing_facets`:

```python
entity = entity_by_id.get(current_entity_id)
hint_facets = set(_entity_facet_hints(entity)) if entity is not None else set()
weak_match_facets: set[str] = set()
if _is_weak_gap(current_matches):
    for match in current_matches:
        weak_match_facets.update(_normalize_token(value) for value in match["modalities"])
        weak_match_facets.update(_normalize_token(value) for value in match["signal_types"])
    weak_match_facets &= BENCHMARK_GAP_HINT_FACET_SET
suggested_facets = _sorted_facets(missing_facets | hint_facets | weak_match_facets)
```

Replace the facet filter condition:

```python
if normalized_facet is not None and normalized_facet not in missing_facets:
    continue
```

with:

```python
if normalized_facet is not None and normalized_facet not in suggested_facets:
    continue
```

Replace:

```python
"suggested_search_facets": sorted(missing_facets),
```

with:

```python
"suggested_search_facets": suggested_facets,
```

- [ ] **Step 5: Run tests and commit**

Before running the focused tests, update these existing assertions because
inferred hints now enrich `suggested_search_facets` beyond the original
coverage-gap-only list.

In `test_gaps_report_projects_existing_coverage_gaps_as_missing_facet`, replace:

```python
assert row["suggested_search_facets"] == ["proteomics"]
```

with:

```python
assert row["suggested_search_facets"] == ["proteomics", "spatial", "cross-context-generalization"]
```

In `test_gaps_report_prefers_taskless_weak_over_missing_facet`, replace:

```python
assert row["suggested_search_facets"] == ["proteomics"]
```

with:

```python
assert row["suggested_search_facets"] == ["proteomics", "spatial", "cross-context-generalization"]
```

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_infers_suggested_facets_for_uncovered_entity \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_facet_filter_uses_inferred_hints \
  science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_facet_filter_uses_report_normalization -q
```

Expected: PASS.

Commit:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): infer gap search facets"
```

### Task 4: Per-Entity Near-Miss Candidate Scoring

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing tests for per-entity candidates and score components**

Use hint-only vocabulary in these near-miss fixtures. Do not put scoreable
controlled facet tokens such as `perturbation` or `proteomics` in the entity
title/body when the candidate dataset declares those facets; exact facet overlap
would make the dataset a positive `current_match` and exclude it from
`candidate_benchmarks`.

Append:

```python
def test_gaps_report_candidates_are_entity_specific_near_misses(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0018-perturbation",
        """
id: hypothesis:0018-perturbation
type: hypothesis
title: Drug screen benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0019-proteomics",
        """
id: hypothesis:0019-proteomics
type: hypothesis
title: Protein abundance benchmark gap
""",
        body="Phosphoproteomic protein abundance should be tested.",
    )
    _write_dataset(
        tmp_path,
        "sciplex",
        """
id: dataset:sciplex
type: dataset
title: Sci-Plex
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: response
      prediction_target: response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured response
""",
    )
    _write_dataset(
        tmp_path,
        "cptac",
        """
id: dataset:cptac
type: dataset
title: CPTAC
benchmark:
  domains: [biology]
  modalities: [proteomics, multimodal]
  signal_types: [multi-omic]
  benchmark_kinds: [mechanism-discrimination]
  tasks:
    - id: subtype
      prediction_target: subtype
      held_out_unit: cohort
      metric: auroc
      baseline: clinical-only
      ground_truth:
        type: measured-outcome
        description: curated subtype
""",
    )

    payload = gaps_report(tmp_path)
    by_entity = {row["entity_id"]: row for row in payload["benchmark_gaps"]}

    perturbation_candidates = by_entity["hypothesis:0018-perturbation"]["candidate_benchmarks"]
    proteomics_candidates = by_entity["hypothesis:0019-proteomics"]["candidate_benchmarks"]
    assert perturbation_candidates[0]["benchmark_id"] == "dataset:sciplex"
    assert "perturbation" in perturbation_candidates[0]["matched_hint_facets"]
    assert proteomics_candidates[0]["benchmark_id"] == "dataset:cptac"
    assert "proteomics" in proteomics_candidates[0]["matched_hint_facets"]
    assert perturbation_candidates[0]["candidate_score"] > 0
    assert proteomics_candidates[0]["candidate_score"] > 0


def test_candidate_score_does_not_double_count_task_readiness_in_baseline_quality(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import _candidate_score, _dataset_context, load_opportunity_datasets

    _write_dataset(
        tmp_path,
        "task-ready-only",
        """
id: dataset:task-ready-only
type: dataset
title: Task Ready Only
benchmark:
  domains: [biology]
  modalities: [assay]
  signal_types: [unrelated]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
    )

    dataset = load_opportunity_datasets(tmp_path, include_commons=False)[0][0]
    context = _dataset_context(dataset, include_prose_tokens=False)
    score = _candidate_score(context, missing_facets=set(), hint_facets=set())

    assert score.components["hint_facet_overlap"] == 0
    assert score.components["missing_facet_overlap"] == 0
    assert score.components["task_readiness"] > 0
    assert score.components["baseline_quality"] == 0
    assert score.total == score.components["task_readiness"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_candidates_are_entity_specific_near_misses \
  science/tests/test_benchmark_opportunities.py::test_candidate_score_does_not_double_count_task_readiness_in_baseline_quality -q
```

Expected: FAIL because `_candidate_score`, `candidate_score`, and `matched_hint_facets` do not exist.

- [ ] **Step 3: Extend candidate contracts**

In `science/src/science_tool/benchmark_opportunities.py`, replace `GapCandidateBenchmarkRow` with:

```python
class GapCandidateBenchmarkRow(TypedDict):
    benchmark_id: str
    benchmark_title: str
    baseline_score: int
    candidate_score: int
    matched_missing_facets: list[str]
    matched_hint_facets: list[str]
    reason_notes: list[str]
```

Add:

```python
@dataclass(frozen=True)
class CandidateScore:
    total: int
    components: dict[str, int]
    reason_notes: list[str]
    matched_missing_facets: list[str]
    matched_hint_facets: list[str]
```

Add a score index type alias near `CandidateScore`:

```python
CandidateScoreIndex = dict[tuple[str, str], CandidateScore]
```

- [ ] **Step 4: Add candidate scoring helpers**

Add near `_candidate_rows()`:

```python
def _context_declared_facets(context: DatasetOpportunityContext) -> set[str]:
    return {
        _normalize_token(value)
        for value in (
            *context.dataset.modalities,
            *context.dataset.signal_types,
        )
    } & BENCHMARK_GAP_HINT_FACET_SET


def _reason_note_sort_key(note: str) -> tuple[int, str]:
    family_order = {
        "missing-facet": 0,
        "entity-hint": 1,
        "task-ready": 2,
        "high-baseline": 3,
        "high-baseline-fallback": 4,
    }
    family = note.split(":", 1)[0]
    return (family_order.get(family, 99), note)


def _candidate_score(
    context: DatasetOpportunityContext,
    *,
    missing_facets: set[str],
    hint_facets: set[str],
) -> CandidateScore:
    declared_facets = _context_declared_facets(context)
    matched_missing = set(missing_facets) & declared_facets
    matched_hints = set(hint_facets) & declared_facets
    baseline_components = context.baseline.components
    missing_points = min(len(matched_missing) * 10, 30)
    hint_points = min(len(matched_hints) * 10, 35)
    task_completeness = baseline_components.get("task_completeness", 0)
    readiness = baseline_components.get("readiness", 0)
    task_readiness = round(((task_completeness / 30) * 12) + ((readiness / 15) * 8))
    baseline_quality = round(
        (
            (
                baseline_components.get("signal_value", 0)
                + baseline_components.get("modality_value", 0)
                + baseline_components.get("limitations", 0)
            )
            / 55
        )
        * 15
    )
    components = {
        "missing_facet_overlap": missing_points,
        "hint_facet_overlap": hint_points,
        "task_readiness": task_readiness,
        "baseline_quality": baseline_quality,
    }
    reason_notes = [f"missing-facet:{facet}" for facet in _sorted_facets(matched_missing)]
    reason_notes.extend(f"entity-hint:{facet}" for facet in _sorted_facets(matched_hints))
    if task_readiness >= 12:
        reason_notes.append("task-ready")
    if baseline_quality >= 8:
        reason_notes.append("high-baseline")
    return CandidateScore(
        total=min(sum(components.values()), 100),
        components=components,
        reason_notes=sorted(set(reason_notes), key=_reason_note_sort_key),
        matched_missing_facets=_sorted_facets(matched_missing),
        matched_hint_facets=_sorted_facets(matched_hints),
    )
```

This intentionally allows the same facet to contribute to both
`missing_facet_overlap` and `hint_facet_overlap` when it is both an existing
coverage gap and independently inferred from entity text. The duplicate signal
is treated as stronger evidence, and both notes should be emitted.

- [ ] **Step 5: Replace `_candidate_rows()` with per-entity context scoring**

Replace `_candidate_rows()` with:

```python
def _candidate_rows(
    entity_id: str,
    contexts: list[DatasetOpportunityContext],
    current_matches: list[OpportunityRow],
    missing_facets: set[str],
    hint_facets: set[str],
    score_index: CandidateScoreIndex,
    *,
    limit: int = 5,
) -> list[GapCandidateBenchmarkRow]:
    matched_benchmark_ids = {row["benchmark_id"] for row in current_matches}
    scored: list[tuple[GapCandidateBenchmarkRow, CandidateScore]] = []
    fallback: list[GapCandidateBenchmarkRow] = []
    for context in contexts:
        dataset = context.dataset
        if dataset.id in matched_benchmark_ids:
            continue
        score = _candidate_score(context, missing_facets=missing_facets, hint_facets=hint_facets)
        score_index[(entity_id, dataset.id)] = score
        row: GapCandidateBenchmarkRow = {
            "benchmark_id": dataset.id,
            "benchmark_title": dataset.title,
            "baseline_score": context.baseline.total,
            "candidate_score": score.total,
            "matched_missing_facets": score.matched_missing_facets,
            "matched_hint_facets": score.matched_hint_facets,
            "reason_notes": score.reason_notes,
        }
        if score.total > 0:
            scored.append((row, score))
        else:
            fallback.append(
                {
                    **row,
                    "reason_notes": ["high-baseline-fallback"],
                }
            )
    if scored:
        ordered = [row for row, _score in sorted(
            scored,
            key=lambda item: (
                -item[0]["candidate_score"],
                -len(item[0]["matched_hint_facets"]),
                -item[0]["baseline_score"],
                item[0]["benchmark_id"],
            ),
        )]
        return ordered[:limit]
    return sorted(
        fallback,
        key=lambda row: (-row["baseline_score"], row["benchmark_id"]),
    )[: min(3, limit)]
```

- [ ] **Step 6: Update `gaps_report()` to call the new candidate helper**

Inside each gap row, replace:

```python
"candidate_benchmarks": _candidate_rows(
    opportunity["available_unmapped_benchmarks"],
    missing_facets,
),
```

with:

```python
"candidate_benchmarks": _candidate_rows(
    current_entity_id,
    analysis.contexts,
    current_matches,
    missing_facets,
    hint_facets,
    candidate_score_index,
),
```

Before the gap-row loop in `gaps_report()`, initialize the index:

```python
candidate_score_index: CandidateScoreIndex = {}
```

- [ ] **Step 7: Run tests and update old candidate helper test**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_candidates_are_entity_specific_near_misses \
  science/tests/test_benchmark_opportunities.py::test_candidate_score_does_not_double_count_task_readiness_in_baseline_quality -q
```

Expected: PASS for the new tests. The old `test_candidate_rows_sort_by_matched_facets_score_then_id` will fail because `_candidate_rows()` changed signature. Replace that old test with a direct `_candidate_score()` unit test:

```python
def test_candidate_score_caps_missing_facet_overlap(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import _candidate_score, _dataset_context, load_opportunity_datasets

    _write_dataset(
        tmp_path,
        "broad-gap",
        """
id: dataset:broad-gap
type: dataset
title: Broad Gap
benchmark:
  domains: [biology]
  modalities: [proteomics, spatial, multimodal]
  signal_types: [perturbation, time-series, cross-context-generalization]
  benchmark_kinds: [static-association]
""",
    )

    dataset = load_opportunity_datasets(tmp_path, include_commons=False)[0][0]
    context = _dataset_context(dataset, include_prose_tokens=False)
    score = _candidate_score(
        context,
        missing_facets={
            "proteomics",
            "spatial",
            "multimodal",
            "perturbation",
            "time-series",
            "cross-context-generalization",
        },
        hint_facets=set(),
    )

    assert score.components["missing_facet_overlap"] == 30
    assert score.total <= 100
```

- [ ] **Step 8: Run full benchmark tests and commit**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -q
```

Expected: PASS.

Commit:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): score gap near-miss candidates"
```

### Task 5: Gap Calibration Payload and CLI Flag

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing tests for gap calibration JSON and CLI flag**

Append:

```python
def test_gaps_report_calibration_payload_explains_gap_and_candidates(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0021-calibration",
        """
id: hypothesis:0021-calibration
type: hypothesis
title: Drug screen summary gap
""",
        body="Summary response needs drug compound screening evidence.",
    )
    _write_dataset(
        tmp_path,
        "sciplex",
        """
id: dataset:sciplex
type: dataset
title: Sci-Plex
benchmark:
  domains: [biology, cancer]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: response
      prediction_target: response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured response
""",
    )

    payload = gaps_report(tmp_path, calibration_report=True)

    assert payload["calibration"]["enabled"] is True
    evidence = payload["calibration"]["gap_entity_evidence"]["hypothesis:0021-calibration"]
    assert "perturbation" in evidence["facet_hints"]
    assert "response" in evidence["dropped_tokens"]["stop"]
    assert "summary" in evidence["dropped_tokens"]["broad_entity"]
    candidate = payload["calibration"]["candidate_evidence"][0]
    assert candidate["entity_id"] == "hypothesis:0021-calibration"
    assert candidate["benchmark_id"] == "dataset:sciplex"
    assert candidate["candidate_score"] == sum(candidate["components"].values())
    assert candidate["components"]["hint_facet_overlap"] > 0
    assert "cancer" in candidate["dropped_dataset_facets"]


def test_benchmark_gaps_cli_calibration_report_json(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0022-cli-calibration",
        """
id: hypothesis:0022-cli-calibration
type: hypothesis
title: Perturbation CLI gap
""",
        body="Perturbation evidence is needed.",
    )

    result = _invoke_gaps(tmp_path, "--calibration-report", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["calibration"]["enabled"] is True
    assert "gap_entity_evidence" in payload["calibration"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_calibration_payload_explains_gap_and_candidates \
  science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_calibration_report_json -q
```

Expected: FAIL because `gaps_report()` has no `calibration_report` parameter and the CLI does not accept `--calibration-report`.

- [ ] **Step 3: Add gap calibration contracts**

In `science/src/science_tool/benchmark_opportunities.py`, add:

```python
class GapEntityDroppedTokens(TypedDict):
    stop: list[str]
    broad_entity: list[str]
    short: list[str]


class GapEntityEvidence(TypedDict):
    entity_tokens: list[str]
    dropped_tokens: GapEntityDroppedTokens
    facet_hints: list[str]
    gap_level_reason: str


class GapCandidateEvidence(TypedDict):
    entity_id: str
    benchmark_id: str
    candidate_score: int
    dropped_dataset_facets: list[str]
    components: dict[str, int]
    reason_notes: list[str]


class GapCalibrationPayload(TypedDict):
    enabled: bool
    gap_entity_evidence: NotRequired[dict[str, GapEntityEvidence]]
    candidate_evidence: NotRequired[list[GapCandidateEvidence]]
```

Extend `BenchmarkGapReport`:

```python
class BenchmarkGapReport(TypedDict):
    benchmark_gaps: list[BenchmarkGapRow]
    summary: BenchmarkGapSummary
    calibration: GapCalibrationPayload
    commons_notice: str | None
```

- [ ] **Step 4: Add calibration helper**

Add:

```python
def _dataset_broad_facets(context: DatasetOpportunityContext) -> list[str]:
    evidence = _token_evidence_from_text(
        *context.dataset.domains,
        *context.dataset.modalities,
        *context.dataset.signal_types,
        *context.dataset.benchmark_kinds,
        broad_tokens=BROAD_NON_SCOREABLE_FACETS,
    )
    return sorted(evidence.broad)


def _gap_calibration_payload(
    rows: list[BenchmarkGapRow],
    *,
    entities: list[ProjectBenchmarkEntity],
    contexts: list[DatasetOpportunityContext],
    candidate_scores: CandidateScoreIndex,
    enabled: bool,
) -> GapCalibrationPayload:
    if not enabled:
        return {"enabled": False}
    entity_by_id = {entity.id: entity for entity in entities}
    context_by_id = {context.dataset.id: context for context in contexts}
    gap_entity_evidence: dict[str, GapEntityEvidence] = {}
    candidate_evidence: list[GapCandidateEvidence] = []
    for row in rows:
        entity = entity_by_id.get(row["entity_id"])
        if entity is not None:
            evidence = _token_evidence_from_text(
                entity.id,
                entity.title,
                entity.content_preview,
                broad_tokens=ENTITY_SUPPRESSED_TOKENS,
            )
            gap_entity_evidence[row["entity_id"]] = {
                "entity_tokens": sorted(entity.tokens),
                "dropped_tokens": {
                    "stop": sorted(evidence.stop),
                    "broad_entity": sorted(evidence.broad),
                    "short": sorted(evidence.short),
                },
                "facet_hints": list(row["suggested_search_facets"]),
                "gap_level_reason": row["reason"],
            }
        for candidate in row["candidate_benchmarks"]:
            context = context_by_id.get(candidate["benchmark_id"])
            if context is None:
                continue
            score = candidate_scores[(row["entity_id"], candidate["benchmark_id"])]
            candidate_evidence.append(
                {
                    "entity_id": row["entity_id"],
                    "benchmark_id": candidate["benchmark_id"],
                    "candidate_score": score.total,
                    "dropped_dataset_facets": _dataset_broad_facets(context),
                    "components": dict(score.components),
                    "reason_notes": list(candidate["reason_notes"]),
                }
            )
    return {
        "enabled": True,
        "gap_entity_evidence": gap_entity_evidence,
        "candidate_evidence": candidate_evidence,
    }
```

- [ ] **Step 5: Add `calibration_report` parameter to `gaps_report()`**

Change signature:

```python
def gaps_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    facet: str | None = None,
    calibration_report: bool = False,
) -> BenchmarkGapReport:
```

Change the `_opportunity_analysis()` call to include prose tokens when gap calibration is requested:

```python
analysis = _opportunity_analysis(
    project_root,
    include_commons=include_commons,
    entity_id=entity_id,
    domain=domain,
    include_prose_tokens=calibration_report,
)
```

Before returning, compute:

```python
calibration = _gap_calibration_payload(
    rows,
    entities=analysis.entities,
    contexts=analysis.contexts,
    candidate_scores=candidate_score_index,
    enabled=calibration_report,
)
```

Return:

```python
return {
    "benchmark_gaps": rows,
    "summary": _gap_summary(rows, entities_total=len(entity_ids)),
    "calibration": calibration,
    "commons_notice": opportunity["commons_notice"],
}
```

- [ ] **Step 6: Add CLI option and table rendering**

In `science/src/science_tool/cli.py`, add the option above `--format` on `benchmark_gaps`:

```python
@click.option("--calibration-report", is_flag=True, help="Include gap token/candidate calibration details.")
```

Add `calibration_report: bool` to the `benchmark_gaps()` function parameters after `include_commons`.

Pass it into `gaps_report()`:

```python
payload = gaps_report(
    root,
    include_commons=include_commons,
    entity_id=entity_id,
    domain=domain,
    facet=facet,
    calibration_report=calibration_report,
)
```

Replace the whole table rendering block from:

```python
rows = payload["benchmark_gaps"]
if not rows:
    click.echo("No benchmark gaps.")
    return
table = Table(title="Benchmark Gaps", show_header=True, header_style="bold")
for col in ("entity", "level", "missing facets", "matches", "candidates", "reason"):
    table.add_column(col, overflow="fold", no_wrap=False)
for row in rows:
    missing = ", ".join(row["missing_modalities"] + row["missing_signal_types"]) or "-"
    candidates = ", ".join(candidate["benchmark_id"] for candidate in row["candidate_benchmarks"][:3]) or "-"
    table.add_row(
        row["entity_id"],
        row["gap_level"],
        missing,
        str(len(row["current_matches"])),
        candidates,
        row["reason"],
    )
Console(width=200).print(table)
```

with:

```python
rows = payload["benchmark_gaps"]
if not rows:
    click.echo("No benchmark gaps.")
else:
    table = Table(title="Benchmark Gaps", show_header=True, header_style="bold")
    for col in ("entity", "level", "missing facets", "matches", "candidates", "reason"):
        table.add_column(col, overflow="fold", no_wrap=False)
    for row in rows:
        missing = ", ".join(row["missing_modalities"] + row["missing_signal_types"]) or "-"
        candidates = ", ".join(candidate["benchmark_id"] for candidate in row["candidate_benchmarks"][:3]) or "-"
        table.add_row(
            row["entity_id"],
            row["gap_level"],
            missing,
            str(len(row["current_matches"])),
            candidates,
            row["reason"],
        )
    Console(width=200).print(table)

if calibration_report:
    calibration_table = Table(title="Gap Calibration", show_header=True, header_style="bold")
    calibration_table.add_column("field", overflow="fold", no_wrap=False)
    calibration_table.add_column("value", overflow="fold", no_wrap=False)
    for field, value in payload["calibration"].items():
        calibration_table.add_row(field, json.dumps(value, sort_keys=True))
    Console(width=200).print(calibration_table)
```

This keeps `No benchmark gaps.` as the empty-state message and still prints the
calibration table afterward when `--calibration-report` is set.

- [ ] **Step 7: Run focused tests and commit**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_calibration_payload_explains_gap_and_candidates \
  science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_calibration_report_json -q
```

Expected: PASS.

Commit:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(cli): calibrate benchmark gaps"
```

### Task 6: Compatibility, Full Verification, and Real-Project Smoke

**Files:**
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add compatibility and CLI table tests**

Append:

```python
def test_gap_candidate_rows_keep_v1_fields(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0023-compat",
        """
id: hypothesis:0023-compat
type: hypothesis
title: Protein abundance compatibility gap
""",
        body="Phosphoproteomic protein abundance is needed.",
    )
    _write_dataset(
        tmp_path,
        "cptac",
        """
id: dataset:cptac
type: dataset
title: CPTAC
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [multi-omic]
  benchmark_kinds: [mechanism-discrimination]
""",
    )

    payload = gaps_report(tmp_path)
    candidate = payload["benchmark_gaps"][0]["candidate_benchmarks"][0]

    assert set(candidate) >= {
        "benchmark_id",
        "benchmark_title",
        "baseline_score",
        "matched_missing_facets",
        "candidate_score",
        "matched_hint_facets",
        "reason_notes",
    }


def test_benchmark_gaps_cli_calibration_table(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0024-table",
        """
id: hypothesis:0024-table
type: hypothesis
title: Perturbation table gap
""",
        body="Perturbation evidence is needed.",
    )

    result = _invoke_gaps(tmp_path, "--calibration-report")

    assert result.exit_code == 0
    assert "Benchmark Gaps" in result.output
    assert "Gap Calibration" in result.output
```

- [ ] **Step 2: Run the compatibility tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gap_candidate_rows_keep_v1_fields \
  science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_calibration_table -q
```

Expected: PASS.

- [ ] **Step 3: Run full benchmark test suite**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 4: Run linters and type checks**

Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
rtk uv run --frozen --project science pyright science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
```

Expected: ruff reports no issues; pyright reports `0 errors`.

- [ ] **Step 5: Run real-project smoke checks**

Run:

```bash
rtk uv run --frozen --project science science benchmark gaps --project-root ~/d/health/processes/post-acute-infection --commons --domain biology --format json
rtk uv run --frozen --project science science benchmark gaps --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --domain biology --format json
rtk uv run --frozen --project science science benchmark gaps --project-root ~/d/natural-systems --commons --domain biology --calibration-report --format json
rtk uv run --frozen --project science science benchmark gaps --project-root ~/d/cancer/data-sources/cbioportal --commons --domain biology --format json
```

Expected: each command exits `0` and prints JSON with `benchmark_gaps`, `summary`, `calibration`, and `commons_notice`. Inspect the output manually for:

- `candidate_benchmarks` varies across entities with different hints.
- `suggested_search_facets` is populated for obvious perturbation, time-series, proteomics, spatial, multimodal, and single-cell language.
- No row uses `cancer`, `biology`, or `varies` as the only match reason.

- [ ] **Step 6: Commit final test/verification adjustments**

If Step 1 introduced only tests and all verification passes, commit:

```bash
rtk git add science/tests/test_benchmark_opportunities.py
rtk git commit -m "test(benchmark): verify gap calibration contract"
```

If implementation fixes were needed during verification, include the touched source files:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "fix(benchmark): stabilize gap calibration output"
```

## Self-Review Checklist

- Spec coverage:
  - Shared `_opportunity_analysis()` helper: Task 2.
  - `BENCHMARK_GAP_HINT_FACETS` and `--facet` drift guard: Task 1 and Task 3.
  - Entity facet hints and inferred suggested facets: Task 3.
  - Split token hygiene and calibration evidence: Task 1 and Task 5.
  - Near-miss candidate scoring with disjoint baseline components: Task 4.
  - Candidate row compatibility: Task 6.
  - Gap `--calibration-report`: Task 5.
  - Real-project calibration smoke: Task 6.
- Placeholder scan: no placeholder markers, no incomplete steps, no unspecified test commands.
- Type consistency:
  - `BenchmarkGapReport` includes `calibration`.
  - `GapCandidateBenchmarkRow` keeps v1 keys and adds v2 keys.
  - `DroppedTokenPayload` broad buckets are `broad_entity` and `broad_dataset_facet`.
  - `gaps_report` uses `calibration_report=False` as the default, matching the CLI flag name.
