"""Tests for the dataset acquisition check (acquired ⇒ datapackage|local_path)."""

from __future__ import annotations

from science_tool.validate.checks.dataset_acquisition import evaluate_dataset_acquisition
from science_tool.validate.result import Severity


def _fm(**kw):
    base = {"type": "dataset", "id": "dataset:x", "_path": "entities/datasets/x.md"}
    base.update(kw)
    return base


def test_candidate_without_pointer_is_ok():
    assert list(evaluate_dataset_acquisition([_fm(status="candidate")])) == []


def test_active_without_pointer_errors():
    results = list(evaluate_dataset_acquisition([_fm(status="active")]))
    assert len(results) == 1
    assert results[0].severity is Severity.ERROR
    assert results[0].rule == "dataset.acquired-without-pointer"


def test_active_with_datapackage_is_ok():
    assert list(evaluate_dataset_acquisition([_fm(status="active", datapackage="r/dp.yaml")])) == []


def test_active_with_local_path_is_ok():
    assert list(evaluate_dataset_acquisition([_fm(status="active", local_path="x.csv")])) == []


def test_non_dataset_is_skipped():
    assert list(evaluate_dataset_acquisition([{"type": "paper", "status": "active", "_path": "p"}])) == []


def test_template_default_status_is_candidate():
    from importlib.resources import files

    text = files("science_model").joinpath("templates/dataset.md").read_text(encoding="utf-8")
    assert 'status: "candidate"' in text
    assert 'status: "active"' not in text
