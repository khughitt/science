from __future__ import annotations

import pytest

from science_tool.plan_common import AllSupersessionMembers
from science_tool.supersede_plan import (
    InvalidRelation, SupersededChainReport, SupersedePlan, SupersedePreviewReport,
)


def _empty_report() -> SupersedePreviewReport:
    return SupersedePreviewReport(
        chains=[], non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
        invalid_relations=[], archived_targets=[], unmanaged_targets=[], unbacked_inverses=[])


def test_preview_report_forbids_execution_keys() -> None:
    rpt = _empty_report()
    assert rpt.to_mark == []
    with pytest.raises(ValueError):
        SupersedePreviewReport(chains=[], non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
                               invalid_relations=[], archived_targets=[], unmanaged_targets=[],
                               unbacked_inverses=[], applied=[])  # type: ignore[call-arg]


def test_nested_report_models_forbid_extra_keys() -> None:
    # A tampered plan cannot smuggle an unknown key past a nested model.
    with pytest.raises(ValueError):
        SupersededChainReport(survivor="a", members=["b"], linear=True, bogus=1)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        InvalidRelation(code="c", path="p", subject="s", predicate="pr", object="o",
                        message="m", extra="x")  # type: ignore[call-arg]


def test_preview_report_coerces_dicts_into_nested_models() -> None:
    rpt = SupersedePreviewReport(
        chains=[{"survivor": "a", "members": ["b"], "linear": True}],
        non_linear=[], to_mark=["b"], skipped_kinds=[], to_repair=[],
        invalid_relations=[], archived_targets=[], unmanaged_targets=[], unbacked_inverses=[])
    assert rpt.chains[0].survivor == "a"  # a typed model, not a bare dict
    with pytest.raises(ValueError):
        SupersedePreviewReport(chains=[{"survivor": "a", "members": ["b"], "linear": True, "x": 1}],
                               non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
                               invalid_relations=[], archived_targets=[], unmanaged_targets=[],
                               unbacked_inverses=[])


def test_supersede_plan_roundtrips_and_forbids_extra() -> None:
    plan = SupersedePlan(
        schema_version=1, project_root="/p", material_version=1, preview_date="2026-07-18",
        selection=AllSupersessionMembers(kind="all"), decision_inputs_sha256="a" * 64,
        to_mark=[], to_repair=[], writes=[], preview_report=_empty_report(),
    )
    again = SupersedePlan.model_validate_json(plan.model_dump_json())
    assert again == plan
