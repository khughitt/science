import pandas as pd

from science_qa.config import QAConfig
from science_qa.checks import run_distribution_checks, per_variable_stats


def _ids(flags):
    return sorted(f.flag_id for f in flags)


def test_range_max_exceedance_flags_distribution():
    table = pd.DataFrame({"glucose": [50, 600]})
    cfg = QAConfig(ranges={"glucose": {"min": 30, "max": 500}})
    flags = run_distribution_checks(table, cfg)
    assert "generic/range/glucose/max" in _ids(flags)
    assert all(f.severity == "distribution" for f in flags)


def test_range_min_exceedance_flags_distribution():
    table = pd.DataFrame({"glucose": [10, 50]})
    cfg = QAConfig(ranges={"glucose": {"min": 30, "max": 500}})
    assert _ids(run_distribution_checks(table, cfg)) == ["generic/range/glucose/min"]


def test_range_within_bounds_no_flag():
    table = pd.DataFrame({"glucose": [50, 60]})
    cfg = QAConfig(ranges={"glucose": {"min": 30, "max": 500}})
    assert run_distribution_checks(table, cfg) == []


def test_per_variable_stats_shape():
    table = pd.DataFrame({"glucose": [50, 60, None]})
    stats = per_variable_stats(table)
    row = next(r for r in stats if r["variable"] == "glucose")
    assert row["n"] == 2
    assert row["pct_miss"] == "33.3"
