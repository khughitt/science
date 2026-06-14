---
title: Dataset adapters — Phase 2 (search quality layer)
date: 2026-06-14
status: design
---

# Dataset Adapters · Phase 2 Design

## 1. Intent

Phase 1 added breadth: nine adapters (`zenodo`, `dryad`, `geo`,
`semantic_scholar`, `cbioportal`, `figshare`, `arrayexpress`, `physionet`,
`sra`) and a canonical `access` tier. It deliberately left the *quality* of the
merged search untouched: `search_all` concatenates each source's hits in
fan-out order, with no ranking and no cross-source dedup, and the CLI `search`
table surfaces only `source / id / title / year / access / doi` even though
`DatasetResult` already carries `organism`, `modality`, and `sample_count`.

Phase 2 closes that gap with three changes — relevance ranking, DOI dedup, and
richer surfaced fields — so `science datasets search` is useful on its own, not
only as raw input the LLM skill re-ranks. The richer fields already exist on the
result type (Phase 1 §2.1); this phase only ranks, dedups, and surfaces them.

### Goals

- Rank merged results by lexical relevance to the query, in pure Python with no
  new dependency and no live network in tests.
- Collapse the same dataset surfacing from multiple repositories (e.g. one DOI
  appearing from Zenodo + Dryad + figshare) to a single result.
- Surface `modality` / `organism` / `sample_count` in `datasets search` output.

### Non-goals

- No semantic / embedding ranking (adds a model dependency and breaks the
  lightweight, offline-testable principle).
- No fuzzy-title dedup (risks merging distinct datasets); DOI-only.
- No `osf` adapter and no generalized `biostudies` toggle (later phase).
- No global result cap; `--max` stays per-source.

## 2. Architecture

One new private module plus two integration edits. Nothing about the adapter
protocol or the existing adapters changes — ranking and dedup operate on the
already-normalized `list[DatasetResult]` that `search_all` collects.

### 2.1 New module `datasets/_ranking.py`

Pure functions, no I/O, matching the `_base.py` private-module convention.

```python
def _normalize_doi(doi: str | None) -> str | None:
    """Canonical DOI key for dedup: lowercased, prefix-stripped, or None."""
```

Strips `https://doi.org/`, `http://dx.doi.org/`, and `doi:` prefixes;
lowercases (DOIs are case-insensitive); strips surrounding whitespace; returns
`None` for `None`/empty input.

```python
def dedupe_results(results: list[DatasetResult]) -> list[DatasetResult]:
    """Keep-first by normalized DOI; None-DOI results are never merged."""
```

Iterates in fan-out order, keeping the first result for each normalized DOI.
Results whose normalized DOI is `None` are all kept (no key collision).
Deterministic and order-preserving.

```python
def score_result(query: str, result: DatasetResult) -> float:
    """Field-weighted count of distinct query tokens matched."""
```

Tokenize both query and fields by lowercasing and splitting on `\W+` (drop
empty tokens). A query token contributes its field weight **once per field it
appears in**:

| Field | Weight |
|---|---|
| `title` | 3 |
| `keywords` (joined) | 2 |
| `organism`, `modality` | 1 each |
| `description` | 1 |

No stopword list, no normalization by query length — the raw weighted count is
the score. A result matching the query in the title outranks one matching only
in the description.

```python
def rank_results(query: str, results: list[DatasetResult]) -> list[DatasetResult]:
    """Stable sort by score descending."""
```

Uses a **stable** sort, so results with equal scores preserve their incoming
(post-dedup) order — meaning source fan-out order is the deterministic tiebreak.

### 2.2 `search_all` integration (`datasets/__init__.py`)

After the existing per-source collection loop, apply the quality pass:

```python
def search_all(
    query: str,
    *,
    sources: list[str] | None = None,
    max_per_source: int = 10,
    on_error: Callable[[str, Exception], None] | None = None,
    rank: bool = True,
) -> list[DatasetResult]:
    ...  # existing collection loop unchanged
    if rank:
        results = rank_results(query, dedupe_results(results))
    return results
```

`rank` defaults to `True` (the Phase 2 behavior). It is explicit rather than
unconditional so a caller that needs the raw concatenation (or to dedup/rank
itself) can opt out — per *explicit > defensive*. Dedup runs before ranking so a
collapsed duplicate cannot occupy two ranked slots.

`dedupe_results` and `rank_results` are added to `__all__` so callers and tests
can use them directly.

### 2.3 CLI richer fields (`cli.py::datasets_search`)

Extend the per-result row dict with the fields already on `DatasetResult`:

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

Because `output.py::emit_query_rows` serializes the full row dicts for JSON
output, all three new fields appear in `--format json` automatically. The table
adds two columns — `("modality", "Modality")` and `("organism", "Organism")` —
between `Access` and `DOI`; `sample_count` stays JSON-only to keep the terminal
table from overflowing. No change to `output.py`, `metadata`, `files`, or
`download`.

## 3. Testing

New `science/tests/test_datasets_ranking.py` (pure unit tests, no network):

- `test_normalize_doi` — `https://doi.org/10.X`, `doi:10.X`, bare `10.X`, mixed
  case, and `None`/empty all map as specified.
- `test_dedupe_keeps_first_by_doi` — two results with the same DOI from
  different sources collapse to the first; a third with a different DOI stays.
- `test_dedupe_keeps_all_none_doi` — multiple `None`-DOI results are all kept.
- `test_score_weights_title_over_description` — a title hit outscores a
  description-only hit for the same token.
- `test_rank_orders_by_score_stable` — higher score first; equal scores keep
  input order.

Extend `science/tests/test_datasets.py`:

- `test_search_all_dedupes_by_doi` — two mocked adapters returning the same DOI
  yield one result.
- `test_search_all_ranks_by_relevance` — the more query-relevant result sorts
  first.
- `test_search_all_rank_false_preserves_concatenation` — `rank=False` returns
  the raw fan-out order and count.

Extend `science/tests/test_datasets_cli.py`:

- `test_search_table_includes_modality_organism` — the `Modality` and
  `Organism` column headers appear in table output.
- `test_search_json_includes_richer_fields` — JSON rows carry `modality`,
  `organism`, and `sample_count`.

## 4. Documentation

- `commands/find-datasets.md` — note that `datasets search` now ranks results by
  lexical relevance and dedups by DOI across sources, and that the table shows
  modality/organism.
- Mirror the behavior note into `codex-skills/science-find-datasets/SKILL.md` if
  it duplicates the search-behavior description.

## 5. Validation

From `~/d/science`:

```bash
uv run pytest science/tests/test_datasets.py science/tests/test_datasets_ranking.py science/tests/test_datasets_cli.py
uv run ruff check science/src/science_tool/datasets science/src/science_tool/cli.py
```

## 6. Out of scope → later phase

- `osf` adapter and a generalized `biostudies` collection toggle.
- Fuzzy-title dedup for records lacking a DOI.
- Semantic / embedding-based ranking.
- A global (cross-source) result cap distinct from per-source `--max`.
