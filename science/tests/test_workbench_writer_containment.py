"""Writer containment: what the workbench persists must satisfy the durable base contract.

The boundary rule (design §5.1): empty fields may be acceptable while constructing an in-memory
entity; they are NOT acceptable once persisted as authored source. `workbench.py` used to cite the
entity-model tests' minimal-construction pattern as precedent for a production write.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from science_model.reasoning import EvidenceType
from science_tool.dag.workbench import (
    EvidenceStub,
    WorkbenchRow,
    _evidence_line_for_stub,
    _proposition_for_row,
)


def _row(**over) -> WorkbenchRow:
    # `polarity` is REQUIRED here: `affects` is sign-meaningful, and `PropositionEntity` rejects it
    # without positive/negative/unsigned. Omitting it makes every test below fail during fixture
    # construction, before any title assertion is reached.
    base = {
        "subject": "concept:a",
        "predicate": "affects",
        "object": "concept:b",
        "patch": "p",
        "polarity": "unsigned",
    }
    return WorkbenchRow(**{**base, **over})


def test_proposition_title_is_the_triple() -> None:
    # THE RULING (design §5.2). Deterministic generation, not a required input field: `WorkbenchRow`
    # is extra="forbid" and carries no `title`, so requiring one would widen the authored-input
    # contract. Changing this string is a behaviour change and must fail here.
    prop = _proposition_for_row(_row())
    assert prop.title == "concept:a affects concept:b"


def test_evidence_line_title_uses_source_when_present() -> None:
    stub = EvidenceStub(stance="supports", source="paper:Smith2025")
    line = _evidence_line_for_stub(stub, target_id="proposition:0001-x", index=0)
    assert line.title == "supports proposition:0001-x — paper:Smith2025"


def test_evidence_line_title_falls_back_to_evidence_type() -> None:
    stub = EvidenceStub(stance="disputes", evidence_type=EvidenceType.LITERATURE)
    line = _evidence_line_for_stub(stub, target_id="proposition:0001-x", index=0)
    assert line.title == "disputes proposition:0001-x — literature"


def test_evidence_line_title_without_qualifiers_is_still_non_empty() -> None:
    # `target_id` is computed and always present, so the head alone satisfies minLength: 1 even
    # when the stub carries no stance, source or evidence_type.
    line = _evidence_line_for_stub(EvidenceStub(), target_id="proposition:0001-x", index=0)
    assert line.title == "supports proposition:0001-x"


def test_generated_titles_are_whitespace_collapsed() -> None:
    prop = _proposition_for_row(_row(subject="concept:a  b", object="concept:c\td"))
    assert prop.title == "concept:a b affects concept:c d"


@pytest.mark.parametrize("field", ["subject", "object"])
def test_empty_triple_terms_fail_at_PARSE_time(field: str) -> None:
    # Not at title construction, and not at base validation. `predicate` is already protected by
    # the `Predicate("")` conversion; subject and object were not protected by anything.
    with pytest.raises(ValidationError):
        _row(**{field: ""})


_SKELETON_KEYS = frozenset({
    "datapackage", "accessions", "parent_dataset", "license", "local_path", "xrefs", "siblings",
    "consumed_by", "produced_by", "scope", "provisional", "pre_registered", "deprecated_ids",
    "profile", "project",
})


def _created_frontmatter(tmp_path, entity) -> dict:
    """Frontmatter of the file the CREATE path would write for `entity`."""
    import yaml

    from science_tool.dag.workbench_apply import _entity_edit

    edit = _entity_edit(tmp_path, entity, as_of=date(2026, 7, 27))
    return yaml.safe_load(edit.final_text.split("---\n", 2)[1])


def test_created_proposition_carries_only_owned_keys(tmp_path) -> None:
    from science_tool.dag.entity_frontmatter import CREATE_ONLY_KEYS, PROPOSITION_OWNED_KEYS

    fm = _created_frontmatter(tmp_path, _proposition_for_row(_row()))
    allowed = PROPOSITION_OWNED_KEYS | CREATE_ONLY_KEYS
    assert set(fm) <= allowed, f"unowned keys persisted: {sorted(set(fm) - allowed)}"


def test_created_evidence_line_carries_no_skeleton_fields(tmp_path) -> None:
    # The 391-document uniform set from mm30. Each of these was written as an empty default.
    line = _evidence_line_for_stub(
        EvidenceStub(stance="supports", source="paper:S"), target_id="proposition:0001-x", index=0
    )
    fm = _created_frontmatter(tmp_path, line)
    assert not (set(fm) & _SKELETON_KEYS), f"skeleton fields persisted: {sorted(set(fm) & _SKELETON_KEYS)}"


def test_created_entity_has_a_non_empty_title(tmp_path) -> None:
    fm = _created_frontmatter(tmp_path, _proposition_for_row(_row()))
    assert fm["title"].strip()


def test_created_evidence_line_keeps_a_deliberate_false(tmp_path) -> None:
    # `belief_eligible=False` is a staging DECISION -- an empirical stub with no dataset_usage is
    # staged ineligible. It must survive the allowlist projection, because a stamped-ineligible
    # line that serializes as eligible is a belief-affecting silent change.
    from science_model.reasoning import EvidenceType

    stub = EvidenceStub(stance="supports", evidence_type=EvidenceType.EMPIRICAL_DATA)
    line = _evidence_line_for_stub(stub, target_id="proposition:0001-x", index=0)
    assert line.belief_eligible is False
    fm = _created_frontmatter(tmp_path, line)
    assert fm["belief_eligible"] is False


def test_title_is_CREATE_ONLY() -> None:
    # Adding `title` to a per-kind update set would overwrite an author's replacement on the next
    # apply and contradict design §5.2. The delta between create and update is exactly this.
    from science_tool.dag.entity_frontmatter import (
        CREATE_ONLY_KEYS,
        EVIDENCE_LINE_OWNED_KEYS,
        PROPOSITION_OWNED_KEYS,
    )

    assert CREATE_ONLY_KEYS == frozenset({"title", "status"})
    for owned in (PROPOSITION_OWNED_KEYS, EVIDENCE_LINE_OWNED_KEYS):
        assert "title" not in owned
        assert "status" not in owned


def test_update_preserves_an_authors_replacement_title(tmp_path) -> None:
    # The reason title is create-only, proved behaviourally rather than by set arithmetic.
    from science_tool.dag.workbench_apply import _entity_edit

    import yaml

    entity = _proposition_for_row(_row())
    first = _entity_edit(tmp_path, entity, as_of=date(2026, 7, 27))
    first.path.parent.mkdir(parents=True, exist_ok=True)
    # Replace the title in the FRONTMATTER ONLY. `str.replace` over the whole file also rewrites
    # the body heading, and then a substring assertion passes even when the frontmatter title was
    # overwritten -- an inert proof of exactly the thing this test exists to catch.
    frontmatter, body = first.final_text.split("---\n", 2)[1:]
    edited = yaml.safe_load(frontmatter) | {"title": "An author's real title"}
    first.path.write_text(
        "---\n" + yaml.safe_dump(edited, sort_keys=False, allow_unicode=True) + "---\n" + body,
        encoding="utf-8",
    )

    second = _entity_edit(tmp_path, entity, as_of=date(2026, 7, 28))

    reloaded = yaml.safe_load(second.final_text.split("---\n", 2)[1])
    assert reloaded["title"] == "An author's real title"


def test_recompiling_preserves_an_authors_title_and_body(tmp_path) -> None:
    # `compile_workbench` is re-run routinely. If its writer rendered every call as a create, the
    # second run would silently overwrite the title an author wrote and the prose under it -- on
    # the path that writes most entities.
    import yaml

    from science_tool.dag import workbench as wb

    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    workbench = wb.WorkbenchFile.model_validate(
        {"patch": "p", "rows": [{"subject": "concept:a", "predicate": "affects",
                                 "object": "concept:b", "patch": "p", "polarity": "unsigned"}]}
    )
    wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 27))

    written = next((tmp_path / "entities").rglob("*.md"))
    frontmatter, body = written.read_text(encoding="utf-8").split("---\n", 2)[1:]
    edited = yaml.safe_load(frontmatter) | {"title": "An author's real title"}
    written.write_text(
        "---\n" + yaml.safe_dump(edited, sort_keys=False, allow_unicode=True) + "---\n"
        + body + "\nAuthored prose.\n",
        encoding="utf-8",
    )

    wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 28))

    after = written.read_text(encoding="utf-8")
    assert yaml.safe_load(after.split("---\n", 2)[1])["title"] == "An author's real title"
    assert "Authored prose." in after


@pytest.mark.parametrize(
    "corruption",
    [
        pytest.param({"id": "question:wrong"}, id="wrong-id"),
        pytest.param({"kind": "question"}, id="wrong-kind"),
        pytest.param({"created": None}, id="missing-created"),
    ],
)
def test_compile_refuses_a_PARSEABLE_but_inadmissible_destination(tmp_path, corruption) -> None:
    # THE defect this admission rule exists for, and the one the two tests above CANNOT reach:
    # a destination that parses fine but is not this entity's file, or has no dates.
    # `render_update` overwrites id, kind, created and updated, so without `read_existing_target`
    # running FIRST the file is repaired into validity and `certify_persisted` passes on a record
    # that was never admissible. Malformed YAML does not prove this -- it raises during parsing
    # even when the admission checks are skipped entirely.
    import yaml

    from science_tool.dag import workbench as wb
    from science_tool.dag.entity_frontmatter import MalformedTargetError

    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    workbench = wb.WorkbenchFile.model_validate(
        {"patch": "p", "rows": [{"subject": "concept:a", "predicate": "affects",
                                 "object": "concept:b", "patch": "p", "polarity": "unsigned"}]}
    )
    wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 27))

    written = next((tmp_path / "entities").rglob("*.md"))
    frontmatter, body = written.read_text(encoding="utf-8").split("---\n", 2)[1:]
    corrupted = yaml.safe_load(frontmatter) | corruption
    corrupted = {k: v for k, v in corrupted.items() if v is not None}  # None means "remove the key"
    written.write_text(
        "---\n" + yaml.safe_dump(corrupted, sort_keys=False, allow_unicode=True) + "---\n" + body,
        encoding="utf-8",
    )
    before = written.read_bytes()

    with pytest.raises(MalformedTargetError):
        wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 28))

    assert written.read_bytes() == before, "a refused destination was modified anyway"


def test_update_of_an_empty_title_record_is_REJECTED(tmp_path) -> None:
    # THE §5.4 ruling. Three implementations were plausible -- reject, skip validation, backfill --
    # and only rejection is fail-early without silently migrating a record nobody asked to touch.
    from science_tool.dag.entity_frontmatter import PersistedShapeError
    from science_tool.dag.workbench_apply import _entity_edit

    entity = _proposition_for_row(_row())
    edit = _entity_edit(tmp_path, entity, as_of=date(2026, 7, 27))
    edit.path.parent.mkdir(parents=True, exist_ok=True)
    edit.path.write_text(
        edit.final_text.replace(f"title: {entity.title}", "title: ''"), encoding="utf-8"
    )

    with pytest.raises(PersistedShapeError) as exc:
        _entity_edit(tmp_path, entity, as_of=date(2026, 7, 28))

    message = str(exc.value)
    assert entity.id in message            # names the record
    assert "title" in message              # names the field
    assert edit.path.read_text(encoding="utf-8").count("title: ''") == 1  # and wrote nothing


def test_the_apply_create_path_is_validated_too(tmp_path, monkeypatch) -> None:
    # Both create paths, not just the risky-looking one. Neutralize the title derivation and the
    # create path must refuse to plan a write rather than emit an empty-title file.
    from science_tool.dag.entity_frontmatter import PersistedShapeError
    from science_tool.dag.workbench_apply import _entity_edit

    entity = _proposition_for_row(_row())
    monkeypatch.setattr(entity, "title", "", raising=False)
    with pytest.raises(PersistedShapeError, match="title"):
        _entity_edit(tmp_path, entity, as_of=date(2026, 7, 27))


def test_the_COMPILE_path_is_validated_and_writes_nothing(tmp_path, monkeypatch) -> None:
    # The second create path, exercised through its real entry point. Task 3 routes it through the
    # shared renderer; without certification INSIDE render_create, a compile-path regression could
    # still persist an invalid base shape while `_entity_edit` stayed green.
    from science_tool.dag import workbench as wb
    from science_tool.dag.entity_frontmatter import PersistedShapeError

    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    monkeypatch.setattr(wb, "_proposition_title", lambda row: "")
    workbench = wb.WorkbenchFile.model_validate(
        {"patch": "p", "rows": [{"subject": "concept:a", "predicate": "affects",
                                 "object": "concept:b", "patch": "p", "polarity": "unsigned"}]}
    )

    with pytest.raises(PersistedShapeError, match="title"):
        wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 27))

    assert not list((tmp_path / "entities").rglob("*.md")), "a refused compile still wrote a file"
