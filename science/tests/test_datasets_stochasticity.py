from __future__ import annotations

import pytest

from science_tool.datasets_stochasticity import (
    DatasetNotFoundError,
    report_dataset_stochasticity,
)


def test_reports_seeded_and_nondeterministic_steps(registrable_run_project):
    project_root, dataset_id = registrable_run_project
    report = report_dataset_stochasticity(project_root, dataset_id)

    assert report.run_id is not None
    by_kind = {s.stochasticity.value for s in report.stochastic_steps if s.stochasticity}
    assert "seedable" in by_kind
    assert "nondeterministic" in by_kind
    seeded = next(s for s in report.stochastic_steps if s.stochasticity and s.stochasticity.value == "seedable")
    assert seeded.realized_seeds == {"random_state": 42}
    assert report.deterministic_step_count >= 1


def test_unknown_dataset_raises(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "id: project:x\nname: X\nprofile: software\n", encoding="utf-8"
    )
    with pytest.raises(DatasetNotFoundError):
        report_dataset_stochasticity(tmp_path, "dataset:does-not-exist")
