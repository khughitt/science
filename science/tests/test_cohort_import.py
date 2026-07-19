from __future__ import annotations

import json

import pytest

from science_tool.entity_import import (
    AttributedWarning,
    CohortImportPlan,
    EntityImportError,
    ImportMember,
    RefDependentCohortError,
    parse_cohort_import_plan,
)


def _member(n: int) -> ImportMember:
    return ImportMember(
        source_rel=f"doc/plans/x{n}.md",
        source_sha256="0" * 64,
        entity_id=f"plan:{n:04d}-x{n}",
        number=n,
        dest_rel=f"entities/plans/{n:04d}-x{n}.md",
        title=f"X{n}",
        status="proposed",
        frontmatter={"id": f"plan:{n:04d}-x{n}", "kind": "plan"},
        rendered_text="body",
    )


def test_cohort_plan_defaults_and_discriminator():
    plan = CohortImportPlan(
        project_root="/r", kind="plan", members=[_member(1), _member(2)]
    )
    assert plan.plan_type == "cohort-import"
    assert plan.schema_version == 1


def test_cohort_plan_forbids_extra_fields():
    with pytest.raises(Exception):
        CohortImportPlan(
            project_root="/r",
            kind="plan",
            members=[_member(1), _member(2)],
            bogus=1,
        )


def test_member_forbids_extra_fields():
    with pytest.raises(Exception):
        ImportMember(
            source_rel="s",
            source_sha256="0" * 64,
            entity_id="plan:0001-x",
            number=1,
            dest_rel="d",
            title="t",
            status="proposed",
            frontmatter={},
            rendered_text="b",
            kind="plan",
        )


def test_parse_cohort_round_trips():
    plan = CohortImportPlan(
        project_root="/r",
        kind="plan",
        members=[_member(1), _member(2)],
        warnings=[
            AttributedWarning(source_rel="doc/plans/x1.md", message="w")
        ],
    )
    raw = plan.model_dump_json().encode("utf-8")
    assert parse_cohort_import_plan(raw) == plan


def test_parse_cohort_rejects_garbage():
    with pytest.raises(EntityImportError):
        parse_cohort_import_plan(b'{"not": "a plan"}')


def test_parse_cohort_rejects_non_integer_schema_version():
    """StrictInt: a boolean or string schema_version must NOT coerce to 1."""
    base = CohortImportPlan(
        project_root="/r", kind="plan", members=[_member(1), _member(2)]
    )
    payload = base.model_dump(mode="json")
    for bad in (True, "1"):
        raw = json.dumps({**payload, "schema_version": bad}).encode("utf-8")
        with pytest.raises(EntityImportError):
            parse_cohort_import_plan(raw)


def test_ref_dependent_error_is_import_error():
    assert issubclass(RefDependentCohortError, EntityImportError)
