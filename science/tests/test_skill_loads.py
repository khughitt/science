from __future__ import annotations

from science_tool.graph.skill_loads import SkillLoadRecord, skill_load_node_uri


def test_identity_excludes_reason() -> None:
    a = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="one")
    b = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="two")
    assert skill_load_node_uri(a) == skill_load_node_uri(b)
    assert a.source == "authored"
    assert "reason" not in a.identity_payload()
    assert a.payload()["reason"] == "one"


def test_identity_distinguishes_plan_and_skill() -> None:
    base = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="r")
    other_skill = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="mutational-signatures-qa", reason="r")
    other_plan = SkillLoadRecord(plan_id="plan:0002-y", canonical_skill_id="driver-selection", reason="r")
    assert skill_load_node_uri(base) != skill_load_node_uri(other_skill)
    assert skill_load_node_uri(base) != skill_load_node_uri(other_plan)


def test_node_uri_is_under_project_skill_load_namespace() -> None:
    rec = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="r")
    assert "skill-load/" in str(skill_load_node_uri(rec))
