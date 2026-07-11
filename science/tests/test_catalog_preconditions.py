"""Preconditions for the two catalog instruments (silent-instrument ruling).

Each of the four catalog helpers scans a directory that may simply not be there
(a wrong ``--project-root``, a project scaffolded without ``entities/``). Before
the migration all four answered that with ``[]`` — indistinguishable from a real
"nothing found", which the CLI then printed as a finding ("No matching benchmark
dataset entities.").

So each helper gets a pair here: the missing scan target must be ``unwired``
(with the machine-readable code, and no rows), and a positive control must still
be ``ok`` — a guard that refuses everything is not a guard, it is a break.

The commons notice is the other half. It is NOT unwired: the instrument ran, the
local rows are real, and only part of the input (commons) was dropped. It rides
as ``reason``/``code`` on an ``ok``/``empty`` result.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from science_tool.benchmark_catalog import benchmark_sources, list_benchmarks
from science_tool.benchmark_opportunities import (
    BenchmarkCatalogUnavailable,
    gaps_report,
    load_opportunity_datasets,
    opportunity_report,
)
from science_tool.cli import main as science_cli
from science_tool.datasets_catalog import list_datasets, reconcile_dataset_links
from science_tool.instruments import InstrumentResult

_BENCHMARK_DATASET = """---
id: dataset:local
kind: dataset
title: Local
benchmark:
  domains: [biology]
  benchmark_kinds: [static-association]
---

body
"""

_PLAIN_DATASET = """---
id: dataset:local
kind: dataset
title: Local
status: candidate
tier: track
origin: external
---

body
"""

_QUESTION = """---
id: question:q1
kind: question
title: Q1
datasets:
  - Local
---

body
"""


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- benchmark_sources -------------------------------------------------------


def test_benchmark_sources_empty_not_unwired_when_datasets_dir_missing(tmp_path: Path) -> None:
    """A missing entities/datasets/ is a TRUE zero, not a failure to run.

    The directory is DOCUMENTED optional (commands/catalog-benchmarks.md: "entities/datasets/,
    if present"), so its absence is a legitimate project state -- "this project catalogues no
    datasets" -- and reporting zero benchmarks is honest. Calling it `unwired` would hard-fail
    every benchmark report on a project that simply has not catalogued anything yet, and a
    spurious unwired is as dishonest as a spurious empty. The code rides along as a caveat.
    """
    result = benchmark_sources(tmp_path)

    assert result.status == "empty"
    assert result.code == "no_datasets_dir"
    assert result.rows == []


def test_benchmark_sources_ok_when_datasets_dir_present(tmp_path: Path) -> None:
    _write(tmp_path, "entities/datasets/local.md", _BENCHMARK_DATASET)

    result = benchmark_sources(tmp_path)

    assert result.status == "ok"
    assert [source["fallback_id"] for source in result.rows] == ["dataset:local"]
    assert result.reason is None


def test_benchmark_sources_empty_when_datasets_dir_present_but_no_benchmarks(tmp_path: Path) -> None:
    """A TRUE zero: the directory exists, it just holds no benchmark datasets."""
    _write(tmp_path, "entities/datasets/local.md", _PLAIN_DATASET)

    result = benchmark_sources(tmp_path)

    assert result.status == "empty"
    assert result.rows == []
    assert result.code is None


# --- list_benchmarks ---------------------------------------------------------


def test_list_benchmarks_empty_not_unwired_when_datasets_dir_missing(tmp_path: Path) -> None:
    """Propagates the true-zero from benchmark_sources -- see the note there."""
    result = list_benchmarks(tmp_path)

    assert result.status == "empty"
    assert result.code == "no_datasets_dir"
    assert result.rows == []


def test_list_benchmarks_ok_when_datasets_dir_present(tmp_path: Path) -> None:
    _write(tmp_path, "entities/datasets/local.md", _BENCHMARK_DATASET)

    result = list_benchmarks(tmp_path)

    assert result.status == "ok"
    assert [row["id"] for row in result.rows] == ["dataset:local"]


def test_list_benchmarks_empty_when_filter_excludes_every_row(tmp_path: Path) -> None:
    """Filter miss on a wired project is a TRUE zero, not unwired."""
    _write(tmp_path, "entities/datasets/local.md", _BENCHMARK_DATASET)

    result = list_benchmarks(tmp_path, domain="no-such-domain")

    assert result.status == "empty"
    assert result.rows == []


# --- list_datasets -----------------------------------------------------------


def test_list_datasets_empty_not_unwired_when_datasets_dir_missing(tmp_path: Path) -> None:
    """Same ruling: the optional catalogue directory's absence is a true zero."""
    result = list_datasets(tmp_path)

    assert result.status == "empty"
    assert result.code == "no_datasets_dir"
    assert result.rows == []


def test_list_datasets_ok_when_datasets_dir_present(tmp_path: Path) -> None:
    _write(tmp_path, "entities/datasets/local.md", _PLAIN_DATASET)

    result = list_datasets(tmp_path)

    assert result.status == "ok"
    assert [row["id"] for row in result.rows] == ["dataset:local"]
    assert result.reason is None


# --- reconcile_dataset_links -------------------------------------------------


def test_reconcile_dataset_links_unwired_when_entities_dir_missing(tmp_path: Path) -> None:
    result = reconcile_dataset_links(tmp_path)

    assert result.status == "unwired"
    assert result.code == "entities_dir_missing"
    assert result.rows == []


def test_reconcile_dataset_links_ok_when_entities_dir_present(tmp_path: Path) -> None:
    _write(tmp_path, "entities/datasets/local.md", _PLAIN_DATASET)
    _write(tmp_path, "entities/questions/q1.md", _QUESTION)

    result = reconcile_dataset_links(tmp_path)

    assert result.status == "ok"
    assert [row["resolved_dataset"] for row in result.rows] == ["dataset:local"]


def test_reconcile_dataset_links_empty_when_nothing_to_reconcile(tmp_path: Path) -> None:
    """entities/ exists and was scanned; no free-text dataset entry resolves."""
    _write(tmp_path, "entities/datasets/local.md", _PLAIN_DATASET)

    result = reconcile_dataset_links(tmp_path)

    assert result.status == "empty"
    assert result.rows == []
    assert result.code is None


# --- the commons notice is a CAVEAT, not an unwired result --------------------


def test_benchmark_sources_commons_notice_rides_on_a_successful_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write(tmp_path, "entities/datasets/local.md", _BENCHMARK_DATASET)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "no-such-commons"))

    result = benchmark_sources(tmp_path, include_commons=True)

    assert result.status == "ok"  # the instrument RAN; local rows are real
    assert [source["fallback_id"] for source in result.rows] == ["dataset:local"]
    assert result.code == "commons_unavailable"
    assert result.reason


def test_list_datasets_commons_notice_rides_on_a_successful_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write(tmp_path, "entities/datasets/local.md", _PLAIN_DATASET)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "no-such-commons"))

    result = list_datasets(tmp_path, include_commons=True)

    assert result.status == "ok"
    assert result.code == "commons_unavailable"
    assert result.reason


def test_list_benchmarks_commons_notice_rides_on_an_empty_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Zero rows + a dropped commons input: ``empty`` WITH a caveat, still not unwired."""
    _write(tmp_path, "entities/datasets/local.md", _PLAIN_DATASET)  # no benchmark block
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "no-such-commons"))

    result = list_benchmarks(tmp_path, include_commons=True)

    assert result.status == "empty"
    assert result.rows == []
    assert result.code == "commons_unavailable"
    assert result.reason


# --- the opportunity layer inherits the precondition --------------------------


def test_load_opportunity_datasets_carries_the_status_it_does_not_launder_it(tmp_path: Path) -> None:
    """The same instrument one layer up: it carries the status verbatim.

    It re-exports benchmark_sources' result rather than re-wrapping it. Re-wrapping via
    `from_rows(inner.rows)` would downgrade an unwired to empty -- and would pass every
    row-count test, because the rows are identical. That trap is the reason this test
    checks `code`, not just row count.
    """
    result = load_opportunity_datasets(tmp_path, include_commons=False)

    assert result.status == "empty"
    assert result.code == "no_datasets_dir"
    assert result.rows == []


@pytest.mark.parametrize("report", [opportunity_report, gaps_report])
def test_benchmark_reports_render_a_true_zero_catalog(tmp_path: Path, report) -> None:
    """An uncatalogued project is a legitimate state -- the reports must still run.

    An earlier draft made a missing entities/datasets/ `unwired`, which hard-failed all four
    benchmark reports on any project that had never catalogued a dataset. That is a spurious
    unwired, and the docs call the directory optional. The reports render the real zero.
    """
    _write(tmp_path, "entities/questions/q1.md", _QUESTION)  # entities/ exists, datasets/ does not

    payload = report(tmp_path)

    assert payload["commons_notice"] is None


def test_benchmark_reports_refuse_a_catalog_that_did_not_load(tmp_path: Path) -> None:
    """The refusal itself is still correct, and still wired.

    If the catalog scan is ever `unwired`, every project entity looks uncovered -- so "no
    opportunities" / "every entity is a gap" would be a finding manufactured from an
    instrument that never ran. The reports refuse rather than report that.
    """
    _write(tmp_path, "entities/questions/q1.md", _QUESTION)
    (tmp_path / "entities" / "datasets").mkdir()

    def _unwired(*_args, **_kwargs):
        return InstrumentResult[object].unwired(code="catalog_unreadable", reason="simulated")

    with mock.patch("science_tool.benchmark_opportunities.load_opportunity_datasets", _unwired):
        with pytest.raises(BenchmarkCatalogUnavailable, match="catalog_unreadable"):
            gaps_report(tmp_path)


# --- the CLI refuses too, rather than printing a zero -------------------------


def _invoke(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        list(args),
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("dataset", "reconcile-links"), "dataset reconcile-links did not run (entities_dir_missing)"),
    ],
)
def test_cli_refuses_to_render_an_instrument_that_did_not_run(
    tmp_path: Path,
    args: tuple[str, ...],
    message: str,
) -> None:
    """reconcile-links scans entities/ itself -- a CORE directory, not an optional one.

    Its absence means the reconciliation never ran, so "no resolvable free-text dataset
    links" would be a clean bill from a scan that never happened.
    """
    result = _invoke(tmp_path, *args)

    assert result.exit_code == 1
    assert message in result.output
    assert "no resolvable free-text dataset links" not in result.output
