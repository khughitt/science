# Dataset Adapters · Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a search quality layer to `science_tool.datasets` — lexical relevance ranking, DOI-based cross-source dedup keeping the best representative, and richer fields surfaced in `datasets search` output.

**Architecture:** One new pure-function module `datasets/_ranking.py` (normalize / score / richness / dedup / rank) operating on the already-normalized `list[DatasetResult]` that `search_all` collects. `search_all` gains a `rank: bool = True` quality pass (dedup → rank). The CLI `datasets search` command surfaces `modality`/`organism` in its table and `sample_count` in JSON. No adapter or protocol changes.

**Tech Stack:** Python 3.13, `re` (stdlib tokenizer), `pytest`, `unittest.mock`, `click.testing.CliRunner`, `uv run`.

**Design spec:** `~/d/science/docs/plans/2026-06-14-dataset-adapters-phase2-design.md`

**Working directory for ALL commands:** `~/d/science/science` (the inner dir is the Python project root — `pyproject.toml` lives there, and `uv run` / pytest fail from the outer repo root). Source paths are relative to `src/`, test paths relative to `tests/`.

---

## File Structure

- **Create** `src/science_tool/datasets/_ranking.py` — all Phase 2 pure functions: `_normalize_doi`, `_tokens`, `score_result`, `_richness`, `dedupe_results`, `rank_results`. One responsibility: ranking/dedup of result lists. Private-module convention matches `_base.py`.
- **Modify** `src/science_tool/datasets/__init__.py` — import `dedupe_results` / `rank_results`, add them to `__all__`, add `rank: bool = True` to `search_all` and apply the quality pass.
- **Modify** `src/science_tool/cli.py` — extend `datasets_search` row dicts and table columns.
- **Create** `tests/test_datasets_ranking.py` — unit tests for the pure functions.
- **Modify** `tests/test_datasets.py` — `search_all` dedup/rank/opt-out tests.
- **Modify** `tests/test_datasets_cli.py` — richer-field table/JSON tests.
- **Modify** `commands/find-datasets.md` and `codex-skills/science-find-datasets/SKILL.md` — document the new search behavior.

---

## Task 1: DOI normalization

**Files:**
- Create: `src/science_tool/datasets/_ranking.py`
- Test: `tests/test_datasets_ranking.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_datasets_ranking.py`:

```python
"""Tests for dataset result ranking and dedup (datasets/_ranking.py)."""

from __future__ import annotations

from science_tool.datasets._base import DatasetResult
from science_tool.datasets._ranking import _normalize_doi


class TestNormalizeDoi:
    def test_strips_https_prefix(self) -> None:
        assert _normalize_doi("https://doi.org/10.5281/ZENODO.123") == "10.5281/zenodo.123"

    def test_strips_dx_and_doi_scheme(self) -> None:
        assert _normalize_doi("http://dx.doi.org/10.1/x") == "10.1/x"
        assert _normalize_doi("doi:10.1/x") == "10.1/x"

    def test_bare_doi_lowercased_and_trimmed(self) -> None:
        assert _normalize_doi("  10.1/ABC  ") == "10.1/abc"

    def test_none_and_empty_return_none(self) -> None:
        assert _normalize_doi(None) is None
        assert _normalize_doi("") is None
        assert _normalize_doi("   ") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datasets_ranking.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.datasets._ranking'`

- [ ] **Step 3: Write minimal implementation**

Create `src/science_tool/datasets/_ranking.py`:

```python
"""Relevance ranking and cross-source dedup for merged dataset search results.

Pure functions over already-normalized DatasetResult lists — no I/O, no network.
Applied by search_all after the per-source fan-out (datasets/__init__.py).
"""

from __future__ import annotations

import re

from science_tool.datasets._base import DatasetResult

_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def _normalize_doi(doi: str | None) -> str | None:
    """Canonical DOI key for dedup: lowercased, prefix-stripped, or None."""
    if doi is None:
        return None
    value = doi.strip().lower()
    for prefix in _DOI_PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    value = value.strip()
    return value or None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datasets_ranking.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/datasets/_ranking.py tests/test_datasets_ranking.py
git commit -m "feat(datasets): add _normalize_doi for cross-source dedup (phase2)"
```

---

## Task 2: Lexical scoring

**Files:**
- Modify: `src/science_tool/datasets/_ranking.py`
- Test: `tests/test_datasets_ranking.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datasets_ranking.py`:

```python
from science_tool.datasets._ranking import score_result


def _r(**kw) -> DatasetResult:
    base = dict(source="s", id="i", title="")
    base.update(kw)
    return DatasetResult(**base)


class TestScoreResult:
    def test_title_hit_outscores_description_hit(self) -> None:
        in_title = _r(title="circadian rhythm", description="unrelated")
        in_desc = _r(title="unrelated", description="circadian rhythm")
        assert score_result("circadian", in_title) > score_result("circadian", in_desc)

    def test_token_counts_once_per_field(self) -> None:
        # "rhythm" appears twice in the title but the query token scores once.
        r = _r(title="rhythm rhythm")
        assert score_result("rhythm", r) == 3.0  # title weight

    def test_multiple_fields_accumulate(self) -> None:
        r = _r(title="sleep", keywords=["sleep"], description="sleep")
        # title 3 + keywords 2 + description 1
        assert score_result("sleep", r) == 6.0

    def test_organism_and_modality_each_weight_one(self) -> None:
        r = _r(title="x", organism="mouse", modality="mouse")
        assert score_result("mouse", r) == 2.0

    def test_empty_query_scores_zero(self) -> None:
        assert score_result("", _r(title="anything")) == 0.0

    def test_no_match_scores_zero(self) -> None:
        assert score_result("zzz", _r(title="abc")) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datasets_ranking.py::TestScoreResult -v`
Expected: FAIL with `ImportError: cannot import name 'score_result'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/science_tool/datasets/_ranking.py` (after the imports add the token regex and weights; add the functions at the end):

```python
_TOKEN_RE = re.compile(r"\w+")

# Field weights for lexical scoring (design §2.1).
_TITLE_WEIGHT = 3
_KEYWORDS_WEIGHT = 2
_ENTITY_WEIGHT = 1  # organism, modality (each)
_DESCRIPTION_WEIGHT = 1


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def score_result(query: str, result: DatasetResult) -> float:
    """Field-weighted count of distinct query tokens matched in a result."""
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    fields: list[tuple[str, int]] = [
        (result.title, _TITLE_WEIGHT),
        (" ".join(result.keywords), _KEYWORDS_WEIGHT),
        (result.organism or "", _ENTITY_WEIGHT),
        (result.modality or "", _ENTITY_WEIGHT),
        (result.description, _DESCRIPTION_WEIGHT),
    ]
    score = 0.0
    for text, weight in fields:
        if not text:
            continue
        score += weight * len(query_tokens & _tokens(text))
    return score
```

Place `_TOKEN_RE` and the weight constants directly below `_DOI_PREFIXES`, and the two functions at the bottom of the file.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datasets_ranking.py -v`
Expected: PASS (10 tests total)

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/datasets/_ranking.py tests/test_datasets_ranking.py
git commit -m "feat(datasets): add field-weighted score_result (phase2)"
```

---

## Task 3: Metadata richness

**Files:**
- Modify: `src/science_tool/datasets/_ranking.py`
- Test: `tests/test_datasets_ranking.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datasets_ranking.py`:

```python
from science_tool.datasets._ranking import _richness


class TestRichness:
    def test_counts_populated_optional_fields(self) -> None:
        bare = _r(title="t")
        rich = _r(title="t", organism="mouse", modality="rna-seq", keywords=["a"], year=2024)
        assert _richness(rich) > _richness(bare)

    def test_bare_result_is_zero(self) -> None:
        assert _richness(_r(title="t")) == 0

    def test_empty_keywords_not_counted(self) -> None:
        # default keywords=[] is falsy and must not count toward richness
        assert _richness(_r(title="t", keywords=[])) == 0

    def test_doi_not_counted(self) -> None:
        # doi is the group key in dedup, constant within a group, so excluded
        assert _richness(_r(title="t", doi="10.1/x")) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datasets_ranking.py::TestRichness -v`
Expected: FAIL with `ImportError: cannot import name '_richness'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/science_tool/datasets/_ranking.py`:

```python
def _richness(result: DatasetResult) -> int:
    """Count of populated optional metadata fields (dedup representative tiebreak).

    `doi` is excluded: it is the dedup group key, identical within a group.
    """
    optional = (
        result.description,
        result.url,
        result.year,
        result.license,
        result.keywords,
        result.organism,
        result.modality,
        result.access,
        result.sample_count,
        result.file_count,
        result.total_size_bytes,
    )
    return sum(1 for value in optional if value)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datasets_ranking.py -v`
Expected: PASS (14 tests total)

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/datasets/_ranking.py tests/test_datasets_ranking.py
git commit -m "feat(datasets): add _richness for dedup representative selection (phase2)"
```

---

## Task 4: Best-representative dedup

**Files:**
- Modify: `src/science_tool/datasets/_ranking.py`
- Test: `tests/test_datasets_ranking.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datasets_ranking.py`:

```python
from science_tool.datasets._ranking import dedupe_results


class TestDedupeResults:
    def test_keeps_richest_representative(self) -> None:
        # Same DOI, equal score (identical titles) -> richer record wins.
        bare = _r(source="zenodo", title="circadian gene atlas", doi="10.1/x")
        rich = _r(
            source="figshare", title="circadian gene atlas", doi="10.1/x",
            organism="mouse", keywords=["circadian"], modality="rna-seq",
        )
        out = dedupe_results("circadian", [bare, rich])
        assert len(out) == 1
        assert out[0].source == "figshare"

    def test_prefers_higher_score(self) -> None:
        # Same DOI, different titles -> the more query-relevant title wins,
        # even though it appears second in fan-out order.
        low = _r(source="dryad", title="generic dataset", doi="10.1/y")
        high = _r(source="zenodo", title="circadian rhythm dataset", doi="10.1/y")
        out = dedupe_results("circadian", [low, high])
        assert len(out) == 1
        assert out[0].source == "zenodo"

    def test_distinct_doi_kept(self) -> None:
        a = _r(title="a", doi="10.1/a")
        b = _r(title="b", doi="10.1/b")
        out = dedupe_results("q", [a, b])
        assert {r.doi for r in out} == {"10.1/a", "10.1/b"}

    def test_none_doi_all_kept(self) -> None:
        a = _r(source="s1", title="a")
        b = _r(source="s2", title="b")
        out = dedupe_results("q", [a, b])
        assert len(out) == 2

    def test_group_position_is_first_appearance(self) -> None:
        # The dup group's slot is fixed by first appearance, even when a later,
        # richer member becomes the representative.
        first = _r(source="zenodo", title="alpha", doi="10.1/dup")
        middle = _r(title="beta", doi="10.1/other")
        rich_dup = _r(source="figshare", title="alpha", doi="10.1/dup", organism="mouse")
        out = dedupe_results("q", [first, middle, rich_dup])
        assert [r.doi for r in out] == ["10.1/dup", "10.1/other"]
        assert out[0].source == "figshare"  # representative is the richer one
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datasets_ranking.py::TestDedupeResults -v`
Expected: FAIL with `ImportError: cannot import name 'dedupe_results'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/science_tool/datasets/_ranking.py`:

```python
def dedupe_results(query: str, results: list[DatasetResult]) -> list[DatasetResult]:
    """Collapse same-DOI records, keeping the best representative.

    Groups by normalized DOI. Within a group the representative maximizes
    ``(score_result(query, r), _richness(r))`` — relevance first, metadata
    completeness as tiebreak. None-DOI records are never grouped. A group's
    output position is fixed by its first appearance in fan-out order.
    """
    groups: dict[str, list[DatasetResult]] = {}
    slots: list[DatasetResult | str] = []
    for r in results:
        key = _normalize_doi(r.doi)
        if key is None:
            slots.append(r)
        elif key in groups:
            groups[key].append(r)
        else:
            groups[key] = [r]
            slots.append(key)

    out: list[DatasetResult] = []
    for slot in slots:
        if isinstance(slot, str):
            group = groups[slot]
            out.append(max(group, key=lambda r: (score_result(query, r), _richness(r))))
        else:
            out.append(slot)
    return out
```

Note: `max` returns the first maximal element on a tie, so equal `(score, richness)` keeps the earliest fan-out member — deterministic.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datasets_ranking.py -v`
Expected: PASS (19 tests total)

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/datasets/_ranking.py tests/test_datasets_ranking.py
git commit -m "feat(datasets): add best-representative DOI dedup (phase2)"
```

---

## Task 5: Stable relevance ranking

**Files:**
- Modify: `src/science_tool/datasets/_ranking.py`
- Test: `tests/test_datasets_ranking.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datasets_ranking.py`:

```python
from science_tool.datasets._ranking import rank_results


class TestRankResults:
    def test_orders_by_score_descending(self) -> None:
        low = _r(source="a", title="generic data")
        high = _r(source="b", title="circadian rhythm data")
        out = rank_results("circadian rhythm", [low, high])
        assert [r.source for r in out] == ["b", "a"]

    def test_equal_scores_keep_input_order(self) -> None:
        # Neither matches the query -> equal (zero) score -> stable order preserved.
        first = _r(source="first", title="alpha")
        second = _r(source="second", title="beta")
        out = rank_results("zzz", [first, second])
        assert [r.source for r in out] == ["first", "second"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datasets_ranking.py::TestRankResults -v`
Expected: FAIL with `ImportError: cannot import name 'rank_results'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/science_tool/datasets/_ranking.py`:

```python
def rank_results(query: str, results: list[DatasetResult]) -> list[DatasetResult]:
    """Stable sort by descending lexical score (equal scores keep input order)."""
    return sorted(results, key=lambda r: score_result(query, r), reverse=True)
```

`sorted` is stable and `reverse=True` preserves the relative order of equal-scoring elements.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datasets_ranking.py -v`
Expected: PASS (21 tests total)

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/datasets/_ranking.py tests/test_datasets_ranking.py
git commit -m "feat(datasets): add stable rank_results (phase2)"
```

---

## Task 6: Wire the quality pass into search_all

**Files:**
- Modify: `src/science_tool/datasets/__init__.py`
- Test: `tests/test_datasets.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datasets.py`, inside the `TestRegistry` class (after `test_search_all_degrades_when_one_adapter_fails`):

```python
    def test_search_all_dedupes_by_doi(self) -> None:
        """The same DOI from two sources collapses to one ranked result."""
        from science_tool.datasets import register, search_all

        class ZenodoLike:
            name = "zlike"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [DatasetResult(source="zlike", id="1", title="shared", doi="10.1/dup")]

            def metadata(self, dataset_id: str) -> DatasetResult:  # pragma: no cover
                return DatasetResult(source="zlike", id=dataset_id, title="x")

            def files(self, dataset_id: str) -> list[FileInfo]:  # pragma: no cover
                return []

            def download(self, file_info: FileInfo, dest_dir: Path) -> Path:  # pragma: no cover
                return dest_dir

        class FigshareLike(ZenodoLike):
            name = "flike"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [DatasetResult(source="flike", id="2", title="shared", doi="10.1/dup", organism="mouse")]

        register("zlike", ZenodoLike)
        register("flike", FigshareLike)
        results = search_all("shared", sources=["zlike", "flike"])
        assert len(results) == 1
        # richer (organism-bearing) figshare record is the representative
        assert results[0].source == "flike"

    def test_search_all_ranks_by_relevance(self) -> None:
        """More query-relevant results sort first."""
        from science_tool.datasets import register, search_all

        class TwoHits:
            name = "twohits"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [
                    DatasetResult(source="twohits", id="1", title="unrelated record"),
                    DatasetResult(source="twohits", id="2", title="circadian rhythm record"),
                ]

            def metadata(self, dataset_id: str) -> DatasetResult:  # pragma: no cover
                return DatasetResult(source="twohits", id=dataset_id, title="x")

            def files(self, dataset_id: str) -> list[FileInfo]:  # pragma: no cover
                return []

            def download(self, file_info: FileInfo, dest_dir: Path) -> Path:  # pragma: no cover
                return dest_dir

        register("twohits", TwoHits)
        results = search_all("circadian rhythm", sources=["twohits"])
        assert [r.id for r in results] == ["2", "1"]

    def test_search_all_rank_false_preserves_concatenation(self) -> None:
        """rank=False returns the raw fan-out order and count (no dedup/rank)."""
        from science_tool.datasets import register, search_all

        class DupSource:
            name = "dupsource"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [
                    DatasetResult(source="dupsource", id="1", title="unrelated", doi="10.1/dup"),
                    DatasetResult(source="dupsource", id="2", title="circadian", doi="10.1/dup"),
                ]

            def metadata(self, dataset_id: str) -> DatasetResult:  # pragma: no cover
                return DatasetResult(source="dupsource", id=dataset_id, title="x")

            def files(self, dataset_id: str) -> list[FileInfo]:  # pragma: no cover
                return []

            def download(self, file_info: FileInfo, dest_dir: Path) -> Path:  # pragma: no cover
                return dest_dir

        register("dupsource", DupSource)
        results = search_all("circadian", sources=["dupsource"], rank=False)
        assert [r.id for r in results] == ["1", "2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datasets.py::TestRegistry -v`
Expected: FAIL — `test_search_all_dedupes_by_doi` and `test_search_all_ranks_by_relevance` fail on order/count; `test_search_all_rank_false_preserves_concatenation` fails with `TypeError: search_all() got an unexpected keyword argument 'rank'`

- [ ] **Step 3: Write minimal implementation**

In `src/science_tool/datasets/__init__.py`:

(a) Add the import after the `_base` import near the top:

```python
from science_tool.datasets._base import DatasetAdapter, DatasetResult, FileInfo
from science_tool.datasets._ranking import dedupe_results, rank_results
```

(b) Add the two helpers to `__all__` (keep it sorted):

```python
__all__ = [
    "DatasetAdapter",
    "DatasetResult",
    "FileInfo",
    "available_adapters",
    "dedupe_results",
    "get_adapter",
    "rank_results",
    "register",
    "search_all",
]
```

(c) Add the `rank` parameter and apply the quality pass. Replace the `search_all` signature and its final `return results`:

```python
def search_all(
    query: str,
    *,
    sources: list[str] | None = None,
    max_per_source: int = 10,
    on_error: Callable[[str, Exception], None] | None = None,
    rank: bool = True,
) -> list[DatasetResult]:
```

and, at the end of the function body (replacing `return results`):

```python
    if rank:
        results = rank_results(query, dedupe_results(query, results))
    return results
```

Also extend the docstring with one line before the closing `"""`:

```python
    When ``rank`` is true (the default), results are deduped by DOI (keeping the
    best-scoring / richest representative) and ranked by lexical relevance to
    ``query``. Pass ``rank=False`` for the raw concatenation.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datasets.py -v`
Expected: PASS (all, including the pre-existing `test_search_all*` — the single-source degrade test is unaffected because one source returns one result)

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/datasets/__init__.py tests/test_datasets.py
git commit -m "feat(datasets): apply dedup+rank quality pass in search_all (phase2)"
```

---

## Task 7: Surface richer fields in the CLI

**Files:**
- Modify: `src/science_tool/cli.py` (`datasets_search`, ~lines 2974-2998)
- Test: `tests/test_datasets_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datasets_cli.py`, inside `class TestDatasetsCLI`:

```python
    def test_search_table_includes_modality_organism(self, runner: CliRunner) -> None:
        mock_results = [
            DatasetResult(
                source="geo", id="GSE1", title="Circadian liver",
                modality="rna-seq", organism="mouse", sample_count=24,
            ),
        ]
        with patch("science_tool.cli.search_all", return_value=mock_results):
            result = runner.invoke(main, ["datasets", "search", "circadian"])
        assert result.exit_code == 0
        assert "Modality" in result.output
        assert "Organism" in result.output

    def test_search_json_includes_richer_fields(self, runner: CliRunner) -> None:
        mock_results = [
            DatasetResult(
                source="geo", id="GSE1", title="Circadian liver",
                modality="rna-seq", organism="mouse", sample_count=24,
            ),
        ]
        with patch("science_tool.cli.search_all", return_value=mock_results):
            result = runner.invoke(main, ["datasets", "search", "circadian", "--format", "json"])
        assert result.exit_code == 0
        import json

        row = json.loads(result.output)["rows"][0]
        assert row["modality"] == "rna-seq"
        assert row["organism"] == "mouse"
        assert row["sample_count"] == 24
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_datasets_cli.py::TestDatasetsCLI::test_search_json_includes_richer_fields tests/test_datasets_cli.py::TestDatasetsCLI::test_search_table_includes_modality_organism -v`
Expected: FAIL — JSON row has no `modality` key (`KeyError`); table output lacks `Modality`/`Organism` headers

- [ ] **Step 3: Write minimal implementation**

In `src/science_tool/cli.py`, in `datasets_search`, replace the `rows` comprehension and the `columns` list.

Replace the rows block:

```python
    rows = [
        {
            "source": r.source,
            "id": r.id,
            "title": r.title[:80],
            "year": r.year or "",
            "access": r.access or "",
            "modality": r.modality or "",
            "organism": r.organism or "",
            "sample_count": r.sample_count or "",
            "doi": r.doi or "",
        }
        for r in results
    ]
```

Replace the `columns` argument to `emit_query_rows`:

```python
        columns=[
            ("source", "Source"),
            ("id", "ID"),
            ("title", "Title"),
            ("year", "Year"),
            ("access", "Access"),
            ("modality", "Modality"),
            ("organism", "Organism"),
            ("doi", "DOI"),
        ],
```

(`sample_count` is intentionally in the row dict but not in `columns`, so it appears in JSON output but not the table — design §2.3.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_datasets_cli.py -v`
Expected: PASS (all, including pre-existing `test_search_json_includes_access`)

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/cli.py tests/test_datasets_cli.py
git commit -m "feat(datasets): surface modality/organism/sample_count in datasets search (phase2)"
```

---

## Task 8: Documentation

**Files:**
- Modify: `commands/find-datasets.md`
- Modify: `codex-skills/science-find-datasets/SKILL.md`

- [ ] **Step 1: Locate the search-behavior description**

Run: `grep -n "search_all\|concatenat\|ranks\|Adapters cover\|datasets search" commands/find-datasets.md codex-skills/science-find-datasets/SKILL.md`
Expected: lines describing how `datasets search` returns results (the Phase 1 adapter-coverage note region).

- [ ] **Step 2: Add the Phase 2 behavior note**

In `commands/find-datasets.md`, near the adapter-coverage / search-behavior guidance, add a sentence (adapt the surrounding markdown style):

```markdown
`science datasets search` ranks merged results by lexical relevance to the query
(title weighted over keywords over description) and dedups records sharing a DOI
across sources, keeping the most relevant / metadata-complete copy. The result
table shows modality and organism; `--format json` additionally carries
`sample_count`. Pass distinct query terms — ranking is lexical token overlap,
not semantic.
```

- [ ] **Step 3: Mirror into the codex skill if it duplicates the description**

If `codex-skills/science-find-datasets/SKILL.md` contains a parallel search-behavior or adapter-coverage paragraph (from Step 1), add the same note there in its style. If it does not duplicate that content, skip this step (do not invent a new section).

- [ ] **Step 4: Commit**

```bash
git add commands/find-datasets.md codex-skills/science-find-datasets/SKILL.md
git commit -m "doc(datasets): note search ranking + DOI dedup + richer fields (phase2)"
```

---

## Final Validation

Run from `~/d/science/science`:

```bash
uv run pytest tests/test_datasets_ranking.py tests/test_datasets.py tests/test_datasets_cli.py -v
uv run ruff check src/science_tool/datasets src/science_tool/cli.py
```

Expected: all tests pass, ruff clean.
