from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from science_tool.consolidation import build_decision_material
from science_tool.plan_common import AllSupersessionMembers, fingerprint
from science_tool.supersede_plan import (
    InvalidRelation, SupersededChainReport, SupersedePlan, SupersedePreviewReport,
    derive_supersede_plan, plan_supersede,
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

    # Verify that extra top-level keys are rejected (tampered plan protection).
    tampered = json.loads(plan.model_dump_json())
    tampered["bogus_key"] = 1
    with pytest.raises(ValidationError):
        SupersedePlan.model_validate_json(json.dumps(tampered))


def _chain(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n---\nbody\n",
        encoding="utf-8")


def test_plan_supersede_freezes_writes_and_digest(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    assert plan.to_mark == ["interpretation:0002-b"]
    assert len(plan.writes) == 1
    w = plan.writes[0]
    assert w.role == "entity-rewrite"
    assert w.rel_path == "entities/interpretations/0002-b.md"
    # pre-state fingerprint matches the live file at preview time
    assert w.pre == fingerprint(tmp_path / w.rel_path)
    assert "status: superseded" in w.postimage
    assert plan.decision_inputs_sha256  # non-empty
    assert plan.preview_report.to_mark == ["interpretation:0002-b"]


def test_plan_supersede_post_mode_matches_the_live_file(tmp_path: Path) -> None:
    _chain(tmp_path)
    live = tmp_path / "entities" / "interpretations" / "0002-b.md"
    os.chmod(live, 0o640)  # a non-default mode a rewrite must preserve
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    w = plan.writes[0]
    assert w.post.mode == 0o640  # NOT a nominal 0o644
    assert w.pre.mode == 0o640


def test_derive_supersede_plan_matches_plan_supersede_given_the_same_material(
    tmp_path: Path,
) -> None:
    # `derive_supersede_plan`, handed the material `plan_supersede` would have built itself,
    # must produce the SAME plan -- proving the delegation in `plan_supersede` is faithful and
    # that deriving from an already-built material never re-loads or re-derives anything.
    _chain(tmp_path)
    material = build_decision_material(tmp_path)
    derived = derive_supersede_plan(
        tmp_path, material, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18"
    )
    direct = plan_supersede(
        tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18"
    )
    assert derived == direct
