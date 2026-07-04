from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from science_model.propositions import PropositionEntity
from science_model.reasoning import ClaimLayer, IdentificationStrength, Polarity, Predicate

from science_tool.dag.workbench import workbench_entity_body
from science_tool.dag.workbench_apply import (
    WorkbenchApplyError,
    apply_workbench,
    apply_workbench_plan,
    build_workbench_apply_plan,
)
from science_tool.entities import (
    parse_markdown_entity_file_preserving_body,
    render_entity_text,
    write_entity_file,
)


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: workbench-apply-test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    _, fm_text, _body = text.split("---\n", 2)
    loaded = yaml.safe_load(fm_text) or {}
    assert isinstance(loaded, dict)
    return loaded


def _proposition(entity_id: str = "proposition:a-affects-b") -> PropositionEntity:
    return PropositionEntity(
        id=entity_id,
        subject="a",
        predicate=Predicate.AFFECTS,
        object="b",
        polarity=Polarity.POSITIVE,
        claim_layer=ClaimLayer.CAUSAL_EFFECT,
        identification_strength=IdentificationStrength.OBSERVATIONAL,
    )


def test_render_entity_text_matches_write_entity_file_output(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    entity = _proposition()
    body = workbench_entity_body(entity)

    write_entity_file(entity, project_root=tmp_path, body=body, as_of=date(2026, 7, 4))

    path = tmp_path / "entities/propositions/a-affects-b.md"
    written = path.read_text(encoding="utf-8")
    rendered = render_entity_text(
        entity,
        body=body,
        created="2026-07-04",
        updated="2026-07-04",
    )
    assert written == rendered


def test_parse_markdown_entity_file_preserving_body_keeps_body_bytes(tmp_path: Path) -> None:
    path = tmp_path / "entity.md"
    path.write_text(
        "---\nid: proposition:x\ntype: proposition\n---\n\n# Title\n\nBody.\n",
        encoding="utf-8",
    )

    frontmatter, body = parse_markdown_entity_file_preserving_body(path)

    assert frontmatter["id"] == "proposition:x"
    assert body == "\n# Title\n\nBody.\n"


def test_parse_markdown_entity_file_preserving_body_keeps_crlf_body_bytes(tmp_path: Path) -> None:
    path = tmp_path / "entity.md"
    path.write_bytes(
        b"---\r\nid: proposition:x\r\ntype: proposition\r\n---\r\n\r\n# Title\r\n\r\nBody.\r\n"
    )

    frontmatter, body = parse_markdown_entity_file_preserving_body(path)

    assert frontmatter["id"] == "proposition:x"
    assert body == "\r\n# Title\r\n\r\nBody.\r\n"


def _write_workbench(
    path: Path,
    *,
    entity_id: str = "proposition:a-affects-b",
    claim_layer: str = "causal_effect",
    inline_evidence: bool = True,
) -> None:
    evidence = (
        """
    evidence:
      - stance: supports
        source: paper:Smith2026
        evidence_type: literature
"""
        if inline_evidence
        else """
    evidence:
      - evidence-line:a-affects-b-ev0
"""
    )
    path.write_text(
        f"""rows:
  - id: {entity_id}
    subject: a
    predicate: affects
    object: b
    patch: h1
    polarity: positive
    claim_layer: {claim_layer}
    identification_strength: observational
{evidence}""",
        encoding="utf-8",
    )


def test_build_workbench_apply_plan_is_read_only_and_plans_canonical_workbench(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)

    plan = build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    assert plan.status == "applied"
    assert plan.row_count == 1
    assert plan.proposition_count == 1
    assert plan.evidence_line_count == 1
    assert (tmp_path / "entities").exists() is False
    assert any(edit.path == workbench_path for edit in plan.edits)
    assert "evidence-line:a-affects-b-ev0" in plan.canonical_workbench_text


def test_apply_workbench_writes_entities_and_canonicalizes_workbench(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    assert result.status == "applied"
    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    ev_path = tmp_path / "entities/evidence-lines/a-affects-b-ev0.md"
    assert prop_path.is_file()
    assert ev_path.is_file()
    assert "evidence-line:a-affects-b-ev0" in workbench_path.read_text(encoding="utf-8")
    assert _frontmatter(prop_path)["updated"] == "2026-07-04"


def test_apply_workbench_result_changed_paths_are_project_relative(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    assert "entities/propositions/a-affects-b.md" in result.changed_paths
    assert "entities/evidence-lines/a-affects-b-ev0.md" in result.changed_paths
    assert "doc/figures/dags/h1.workbench.yaml" in result.changed_paths
    assert all(not Path(changed_path).is_absolute() for changed_path in result.changed_paths)


def test_apply_workbench_new_proposition_body_matches_workbench_body(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path, inline_evidence=False)

    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    _frontmatter, body = parse_markdown_entity_file_preserving_body(prop_path)
    assert body == workbench_entity_body(_proposition())


def test_apply_workbench_rerun_is_noop_without_timestamp_churn(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)

    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))
    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    first_frontmatter = _frontmatter(prop_path)

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 10))

    assert result.status == "no-op"
    assert _frontmatter(prop_path) == first_frontmatter


def test_apply_workbench_preserves_authored_proposition_body_on_semantic_update(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)
    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    prop_path.write_text(
        prop_path.read_text(encoding="utf-8").replace("## Summary\n\n", "## Summary\n\nReviewed prose.\n"),
        encoding="utf-8",
    )
    _write_workbench(workbench_path, claim_layer="structural_claim", inline_evidence=False)

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 10))

    assert result.status == "applied"
    assert "Reviewed prose." in prop_path.read_text(encoding="utf-8")
    fm = _frontmatter(prop_path)
    assert fm["claim_layer"] == "structural_claim"
    assert fm["created"] == "2026-07-04"
    assert fm["updated"] == "2026-07-10"


def test_apply_workbench_preserves_curated_proposition_frontmatter_on_semantic_update(
    tmp_path: Path,
) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)
    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    frontmatter, body = parse_markdown_entity_file_preserving_body(prop_path)
    frontmatter["status"] = "ack"
    frontmatter["source_refs"] = ["paper:Smith2026"]
    frontmatter["origins"] = [{"type": "user", "ref": "manual:test", "date": "2026-07-04"}]
    frontmatter["review_state"] = {"last_reviewed": "2026-07-04", "last_review_note": "manual review"}
    frontmatter["related"] = ["question:manual-test"]
    frontmatter["ontology_terms"] = ["obo:TEST_0001"]
    prop_path.write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body,
        encoding="utf-8",
    )
    _write_workbench(workbench_path, claim_layer="structural_claim", inline_evidence=False)

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 10))

    assert result.status == "applied"
    fm = _frontmatter(prop_path)
    assert fm["claim_layer"] == "structural_claim"
    assert fm["status"] == "ack"
    assert fm["source_refs"] == ["paper:Smith2026"]
    assert fm["origins"] == [{"type": "user", "ref": "manual:test", "date": "2026-07-04"}]
    assert fm["review_state"] == {"last_reviewed": "2026-07-04", "last_review_note": "manual review"}
    assert fm["related"] == ["question:manual-test"]
    assert fm["ontology_terms"] == ["obo:TEST_0001"]
    assert fm["created"] == "2026-07-04"
    assert fm["updated"] == "2026-07-10"


def test_apply_workbench_preserves_authored_evidence_line_body_on_semantic_update(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)
    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    ev_path = tmp_path / "entities/evidence-lines/a-affects-b-ev0.md"
    ev_path.write_text(
        ev_path.read_text(encoding="utf-8").replace("## Notes\n", "## Notes\n\nCurated evidence note.\n"),
        encoding="utf-8",
    )
    _write_workbench(workbench_path)
    text = workbench_path.read_text(encoding="utf-8").replace("paper:Smith2026", "paper:Jones2026")
    workbench_path.write_text(text, encoding="utf-8")

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 11))

    assert result.status == "applied"
    assert "Curated evidence note." in ev_path.read_text(encoding="utf-8")
    fm = _frontmatter(ev_path)
    assert fm["source"] == "paper:Jones2026"
    assert fm["created"] == "2026-07-04"
    assert fm["updated"] == "2026-07-11"


def test_apply_workbench_rejects_malformed_existing_target_before_write(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)
    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    prop_path.parent.mkdir(parents=True)
    prop_path.write_text("---\n: : bad yaml\n---\nBody\n", encoding="utf-8")

    try:
        apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))
    except WorkbenchApplyError as exc:
        assert "malformed existing entity target" in str(exc)
    else:
        raise AssertionError("expected WorkbenchApplyError")
    assert "evidence-line:a-affects-b-ev0" not in workbench_path.read_text(encoding="utf-8")


def test_build_workbench_apply_plan_rejects_escaping_entity_target_before_write(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    escaped_path = tmp_path.parent / "escaped.md"
    escaped_path.unlink(missing_ok=True)
    escape_local_part = Path("..") / ".." / ".." / "escaped"
    _write_workbench(workbench_path, entity_id=f"proposition:{escape_local_part}", inline_evidence=False)

    try:
        build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))
    except WorkbenchApplyError as exc:
        message = str(exc)
        assert "target" in message
        assert "escape" in message
    else:
        raise AssertionError("expected WorkbenchApplyError")
    assert not escaped_path.exists()
    assert not (tmp_path / "entities").exists()


@pytest.mark.parametrize(
    "entity_id",
    [
        "proposition:../../doc/owned",
        "proposition:../evidence-lines/foo",
    ],
)
def test_build_workbench_apply_plan_rejects_malformed_proposition_target_ids(
    tmp_path: Path,
    entity_id: str,
) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path, entity_id=entity_id, inline_evidence=False)

    with pytest.raises(WorkbenchApplyError, match="local part"):
        build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    assert not (tmp_path / "entities").exists()


def test_build_workbench_apply_plan_rejects_wrong_prefix_proposition_row_id(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path, entity_id="evidence-line:not-a-proposition", inline_evidence=False)

    with pytest.raises(WorkbenchApplyError, match="prefix proposition:"):
        build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    assert not (tmp_path / "entities").exists()


def test_apply_workbench_rejects_input_hash_drift(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)

    plan = build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))
    workbench_path.write_text(workbench_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    try:
        apply_workbench_plan(plan)
    except WorkbenchApplyError as exc:
        assert "changed since it was parsed" in str(exc)
    else:
        raise AssertionError("expected WorkbenchApplyError")


def test_apply_workbench_plan_rejects_entity_target_hash_drift(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)
    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    _write_workbench(workbench_path, claim_layer="structural_claim", inline_evidence=False)
    plan = build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 10))
    drifted_text = prop_path.read_text(encoding="utf-8").replace("## Summary\n\n", "## Summary\n\nIntervening edit.\n")
    prop_path.write_text(drifted_text, encoding="utf-8")

    with pytest.raises(WorkbenchApplyError, match="entity target changed since it was planned"):
        apply_workbench_plan(plan)

    text = prop_path.read_text(encoding="utf-8")
    assert "Intervening edit." in text
    assert "structural_claim" not in text


def test_build_workbench_apply_plan_rejects_duplicate_target_with_different_final_text(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    workbench_path.write_text(
        """rows:
  - id: proposition:shared
    subject: a
    predicate: affects
    object: b
    patch: h1
    claim_layer: causal_effect
  - id: proposition:shared
    subject: a
    predicate: affects
    object: c
    patch: h1
    claim_layer: structural_claim
""",
        encoding="utf-8",
    )

    try:
        build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))
    except WorkbenchApplyError as exc:
        assert "conflicting planned writes" in str(exc)
    else:
        raise AssertionError("expected WorkbenchApplyError")


def test_build_workbench_apply_plan_rejects_duplicate_identical_explicit_rows(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    workbench_path.write_text(
        """rows:
  - id: proposition:shared
    subject: a
    predicate: affects
    object: b
    patch: h1
    polarity: positive
    claim_layer: causal_effect
  - id: proposition:shared
    subject: a
    predicate: affects
    object: b
    patch: h1
    polarity: positive
    claim_layer: causal_effect
""",
        encoding="utf-8",
    )

    with pytest.raises(WorkbenchApplyError, match="duplicate proposition row id"):
        build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))


def test_build_workbench_apply_plan_rejects_duplicate_idless_proposition_targets(
    tmp_path: Path,
) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    workbench_path.write_text(
        """rows:
  - subject: a
    predicate: affects
    object: b
    patch: h1
    polarity: positive
    claim_layer: causal_effect
  - subject: a
    predicate: affects
    object: b
    patch: h1
    polarity: positive
    claim_layer: causal_effect
""",
        encoding="utf-8",
    )

    with pytest.raises(WorkbenchApplyError, match="duplicate proposition target proposition:a-affects-b"):
        build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    assert not (tmp_path / "entities").exists()
    assert "id: proposition:a-affects-b" not in workbench_path.read_text(encoding="utf-8")
