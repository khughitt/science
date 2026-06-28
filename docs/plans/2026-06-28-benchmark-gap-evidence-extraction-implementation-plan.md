# Benchmark Gap Evidence Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in benchmark gap evidence report that explains entity-specific vs fallback-only benchmark candidates and surfaces unmapped project terms for deterministic lexicon tuning.

**Architecture:** Extend `science_tool.benchmark_opportunities` with additive `EvidenceReport` typed dicts and pure projection helpers over existing `BenchmarkGapRow`, `ProjectBenchmarkEntity`, and `OpportunityRow` data. Add `--evidence-report` to `science benchmark gaps`; JSON receives a top-level `evidence_report`, and table output receives a compact diagnostic table. Keep matching and ranking behavior unchanged.

**Tech Stack:** Python, Click, Rich tables, pytest, existing science benchmark opportunity helpers.

---

## Files

- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_benchmark_opportunities.py`
- Modify: `science/tests/test_benchmark_cli.py`
- Add: `docs/plans/2026-06-28-benchmark-gap-evidence-extraction-design.md`
- Add: `docs/plans/2026-06-28-benchmark-gap-evidence-extraction-implementation-plan.md`

## Task 1: Evidence Report Contract and Projection

- [ ] **Step 1: Add failing evidence report unit tests**

Add tests to `science/tests/test_benchmark_opportunities.py`:

```python
def test_gaps_report_evidence_report_explains_fallback_only_unmapped_terms(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0035-organoid",
        """
id: hypothesis:0035-organoid
type: hypothesis
title: Organoid therapy benchmark gap
""",
        body="Organoid therapy clone validation should be tested.",
    )
    _write_dataset(
        tmp_path,
        "generic",
        """
id: dataset:generic
type: dataset
title: Generic benchmark
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [clinical-outcome]
  benchmark_kinds: [static-association]
  tasks:
    - id: outcome
      prediction_target: outcome
      held_out_unit: patient
      metric: auroc
      baseline: clinical-only
      ground_truth:
        type: measured-outcome
        description: outcome
""",
    )

    payload = gaps_report(tmp_path, evidence_report=True)

    evidence = payload["evidence_report"]
    assert evidence["enabled"] is True
    row = evidence["entities"]["hypothesis:0035-organoid"]
    assert row["candidate_mode"] == "fallback-only"
    assert row["facet_hints"] == []
    assert "organoid" in row["unmapped_high_value_terms"]
    assert "therapy" in row["unmapped_high_value_terms"]
    assert "no-facet-hints" in row["why_no_specific_candidate"]
    assert "only-fallback-candidates" in row["why_no_specific_candidate"]
    assert evidence["summary"]["entities_with_fallback_only_candidates"] == 1
    assert evidence["lexicon_candidates"][0]["term"] == "organoid"


def test_gaps_report_evidence_report_distinguishes_entity_specific_candidates(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0036-drug",
        """
id: hypothesis:0036-drug
type: hypothesis
title: Drug benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
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
        description: response
""",
    )

    payload = gaps_report(tmp_path, evidence_report=True)

    row = payload["evidence_report"]["entities"]["hypothesis:0036-drug"]
    assert row["candidate_mode"] == "entity-specific"
    assert row["facet_hints"] == ["perturbation"]
    assert "perturbation" in row["matched_facets"]
    assert "only-fallback-candidates" not in row["why_no_specific_candidate"]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -k evidence_report -q
```

Expected: FAIL because `gaps_report()` does not accept `evidence_report`.

- [ ] **Step 3: Add typed dicts and projection helpers**

In `science/src/science_tool/benchmark_opportunities.py`, add:

```python
CandidateMode = Literal["entity-specific", "fallback-only", "none"]


class TermCountRow(TypedDict):
    term: str
    count: int
    example_entities: list[str]


class EvidenceEntityRow(TypedDict):
    candidate_mode: CandidateMode
    tokens: list[str]
    facet_hints: list[str]
    matched_facets: list[str]
    suggested_search_facets: list[str]
    unmapped_high_value_terms: list[str]
    why_no_specific_candidate: list[str]


class EvidenceSummary(TypedDict):
    entities_total: int
    entities_with_no_facet_hints: int
    entities_with_fallback_only_candidates: int
    top_unmapped_project_terms: list[TermCountRow]


class EvidenceReport(TypedDict):
    enabled: bool
    summary: NotRequired[EvidenceSummary]
    entities: NotRequired[dict[str, EvidenceEntityRow]]
    lexicon_candidates: NotRequired[list[TermCountRow]]
```

Add helpers:

```python
_UNMAPPED_TERM_EXCLUSIONS = frozenset({
    *_STOP_TOKENS,
    *ENTITY_SUPPRESSED_TOKENS,
    *_ENTITY_KINDS,
    "benchmark",
    "gap",
    "tested",
    "validation",
})


def _phrase_tokens() -> set[str]:
    return {token for phrase, _hint in FACET_HINT_PHRASES for token in phrase}


def _matched_facets_for_gap(row: BenchmarkGapRow, current_matches: list[OpportunityRow]) -> list[str]:
    facets: set[str] = set()
    for match in current_matches:
        facets.update(_normalize_token(value) for value in match["modalities"])
        facets.update(_normalize_token(value) for value in match["signal_types"])
    for candidate in row["candidate_benchmarks"]:
        facets.update(candidate["matched_missing_facets"])
        facets.update(candidate["matched_hint_facets"])
    return _sorted_facets(facets)


def _candidate_mode(candidates: list[GapCandidateBenchmarkRow]) -> CandidateMode:
    if any(candidate["matched_missing_facets"] or candidate["matched_hint_facets"] for candidate in candidates):
        return "entity-specific"
    if candidates:
        return "fallback-only"
    return "none"


def _unmapped_high_value_terms(entity: ProjectBenchmarkEntity, matched_facets: list[str]) -> list[str]:
    excluded = set(_UNMAPPED_TERM_EXCLUSIONS)
    excluded.update(_phrase_tokens())
    excluded.update(FACET_HINT_TERMS)
    excluded.update(BENCHMARK_GAP_HINT_FACET_SET)
    excluded.update(matched_facets)
    excluded.update(token for token in entity.id_tokens if ":" not in token)
    return sorted(token for token in entity.tokens if token not in excluded and not re.fullmatch(r"\\d+.*", token))


def _why_no_specific_candidate(row: BenchmarkGapRow, mode: CandidateMode) -> list[str]:
    reasons: list[str] = []
    if row["gap_level"] == "weak":
        reasons.append("current-match-too-weak")
    if not row["suggested_search_facets"]:
        reasons.append("no-facet-hints")
    elif mode != "entity-specific":
        reasons.append("hints-have-no-candidate-facet-overlap")
    if mode == "fallback-only":
        reasons.append("only-fallback-candidates")
    if mode == "none":
        reasons.append("no-candidates")
    return reasons
```

- [ ] **Step 4: Add `evidence_report` to `BenchmarkGapReport` and `gaps_report()`**

Change the `BenchmarkGapReport` typed dict:

```python
class BenchmarkGapReport(TypedDict):
    benchmark_gaps: list[BenchmarkGapRow]
    summary: BenchmarkGapSummary
    calibration: GapCalibrationPayload
    evidence_report: EvidenceReport
    commons_notice: str | None
```

Add `evidence_report: bool = False` to `gaps_report()`. Store `current_matches_by_gap_entity` while building rows, then return:

```python
"evidence_report": _gap_evidence_report(
    rows,
    entities=analysis.entities,
    matched=matched,
    enabled=evidence_report,
),
```

Implement `_gap_evidence_report()` to return disabled payload when `enabled` is false, otherwise build the contract in the design.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -k evidence_report -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py docs/plans/2026-06-28-benchmark-gap-evidence-extraction-design.md docs/plans/2026-06-28-benchmark-gap-evidence-extraction-implementation-plan.md
rtk git commit -m "feat(benchmark): add gap evidence report"
```

## Task 2: CLI Exposure

- [ ] **Step 1: Add failing CLI JSON and table tests**

In `science/tests/test_benchmark_cli.py`, add tests asserting:

```python
result = _invoke_gaps(tmp_path, "--evidence-report", "--format", "json")
payload = json.loads(result.output)
assert payload["evidence_report"]["enabled"] is True
assert "entities" in payload["evidence_report"]
```

And for table mode:

```python
result = _invoke_gaps(tmp_path, "--evidence-report")
assert result.exit_code == 0
assert "Gap Evidence" in result.output
assert "fallback-only" in result.output
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py -k evidence_report -q
```

Expected: FAIL because `--evidence-report` does not exist.

- [ ] **Step 3: Add CLI option and rendering**

In `science/src/science_tool/cli.py`, add:

```python
@click.option("--evidence-report", is_flag=True, help="Include benchmark gap evidence extraction details.")
```

Thread `evidence_report=evidence_report` into `gaps_report()`. In table mode, when enabled, render a `Gap Evidence` table with columns:

- `entity`
- `mode`
- `hints`
- `matched facets`
- `unmapped terms`
- `why`

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py -k evidence_report -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat(cli): expose benchmark gap evidence report"
```

## Task 3: Lexicon Tuning From Real Project Terms

- [ ] **Step 1: Run evidence report over real projects**

Run:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark gaps --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --evidence-report --format json
```

Inspect `evidence_report.lexicon_candidates`.

- [ ] **Step 2: Add focused failing tests for two high-confidence real terms**

Choose only terms whose mapping is obvious from the report. For example, if `survival` and `therapy` are frequent:

```python
assert "clinical-outcome" in _entity_facet_hints(entity_with_survival_text)
assert "perturbation" in _entity_facet_hints(entity_with_therapy_text)
```

- [ ] **Step 3: Verify RED**

Run the focused tests and confirm the new terms are not mapped yet.

- [ ] **Step 4: Add the lexicon entries**

Add only high-confidence mappings to `FACET_HINT_TERMS`.

- [ ] **Step 5: Verify GREEN**

Run the focused tests and confirm they pass.

- [ ] **Step 6: Commit**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): tune gap evidence facet hints"
```

## Task 4: Full Verification

- [ ] Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark gaps --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --evidence-report --format json
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark gap-calibration --project pai=~/d/health/processes/post-acute-infection --project mm=~/d/cancer/cancer-types/multiple-myeloma --project natural=~/d/natural-systems --project cbioportal=~/d/cancer/data-sources/cbioportal --commons --format json
```

Expected:

- Ruff passes.
- Pytest passes.
- Evidence report JSON includes `enabled: true`, `summary`, `entities`, and `lexicon_candidates`.
- Gap calibration remains successful with no commons notices.
