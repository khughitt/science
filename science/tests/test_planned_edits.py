import dataclasses
from pathlib import Path

import pytest

from science_tool.annotation.planned_edits import (
    PlannedFileEdit,
    PlannedEditDriftError,
    changed_and_noop_paths,
    current_text,
    plan_create,
    plan_create_or_update,
    plan_numeric_create,
    plan_update,
    publish_edit,
    publish_order,
    sha256_text,
)
from science_tool.dag.entity_frontmatter import EntityWriteError


def test_current_text_preserves_crlf(tmp_path: Path):
    """`Path.read_text()` applies universal-newline translation, which would rewrite bytes
    the edit never intended -- and the round-trip guard would then certify the rewrite as
    correct. The preserving reader at entities.py:1920-1923 is the precedent."""
    target = tmp_path / "record.md"
    target.write_bytes(b"---\r\nid: proposition:x\r\n---\r\nbody\r\n")

    assert current_text(target) == "---\r\nid: proposition:x\r\n---\r\nbody\r\n"


def test_plan_update_reports_unchanged_when_text_matches(tmp_path: Path):
    target = tmp_path / "record.md"
    target.write_text("same\n", encoding="utf-8")

    edit = plan_update(target, "same\n", "noop")

    assert edit.changed is False
    assert edit.before_sha256 == edit.after_sha256 == sha256_text("same\n")


def test_changed_and_noop_paths_partitions(tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("one\n", encoding="utf-8")
    b.write_text("two\n", encoding="utf-8")

    changed, noop = changed_and_noop_paths(
        [plan_update(a, "ONE\n", "r"), plan_update(b, "two\n", "r")]
    )

    assert changed == (a.as_posix(),)
    assert noop == (b.as_posix(),)


def test_planned_file_edit_is_frozen(tmp_path: Path):
    """A planner that could mutate an edit after constructing it could desynchronize
    final_text from after_sha256, and the drift check added in Task 6 reads both."""
    target = tmp_path / "a.md"
    target.write_text("x\n", encoding="utf-8")
    edit = plan_update(target, "y\n", "r")

    assert isinstance(edit, PlannedFileEdit)
    with pytest.raises(dataclasses.FrozenInstanceError):
        edit.final_text = "z\n"  # type: ignore[misc]


def test_update_refuses_when_the_target_drifted(tmp_path: Path):
    """os.replace overwrites unconditionally, so an update planned against bytes that have
    since changed would silently discard the other writer's work -- and preflight is what
    makes that race worth caring about, since the window is now the whole planning phase."""
    target = tmp_path / "record.md"
    target.write_text("planned against this\n", encoding="utf-8")
    edit = plan_update(target, "my new content\n", "r")

    target.write_text("someone else got here first\n", encoding="utf-8")

    with pytest.raises(PlannedEditDriftError) as excinfo:
        publish_edit(edit, project_root=tmp_path)

    assert target.name in str(excinfo.value)
    # The assertion that matters: the other writer's bytes survive.
    assert target.read_text(encoding="utf-8") == "someone else got here first\n"


def test_update_publishes_when_the_target_is_unchanged(tmp_path: Path):
    target = tmp_path / "record.md"
    target.write_text("before\n", encoding="utf-8")
    edit = plan_update(target, "after\n", "r")

    publish_edit(edit, project_root=tmp_path)

    assert target.read_text(encoding="utf-8") == "after\n"


def test_create_refuses_an_intervening_file_without_clobbering_it(tmp_path: Path):
    """Asserting only that an error was raised is not enough -- an atomic_write_text publish
    would overwrite the file and could still raise later in the batch. The assertion that
    fails under os.replace is the untouched pre-existing content."""
    dest = tmp_path / "new.md"
    edit = plan_create(dest, "my planned content\n", "r")

    dest.write_text("another writer created this\n", encoding="utf-8")

    with pytest.raises(EntityWriteError):
        publish_edit(edit, project_root=tmp_path)

    assert dest.read_text(encoding="utf-8") == "another writer created this\n"


def test_plan_create_needs_no_pre_image(tmp_path: Path):
    """Fails if plan_create calls current_text on a path that does not exist."""
    edit = plan_create(tmp_path / "absent.md", "content\n", "r")

    assert edit.before_sha256 is None
    assert edit.changed is True
    assert edit.operation == "create"


def test_plan_create_or_update_dispatches_on_existence(tmp_path: Path):
    absent = tmp_path / "absent.md"
    present = tmp_path / "present.md"
    present.write_text("before\n", encoding="utf-8")

    assert plan_create_or_update(absent, "x\n", "r").operation == "create"
    assert plan_create_or_update(present, "x\n", "r").operation == "update"


@pytest.mark.parametrize(
    ("kind", "local_part", "number", "relative_path"),
    (
        pytest.param(
            "question",
            "0002-wrong-prefix",
            1,
            "entities/questions/0002-wrong-prefix.md",
            id="wrong-number-prefix",
        ),
        pytest.param(
            "question",
            "0001-right-prefix",
            1,
            "entities/questions/different.md",
            id="wrong-path",
        ),
        pytest.param(
            "hypothesis",
            "0001-right-prefix",
            1,
            "entities/questions/0001-right-prefix.md",
            id="wrong-kind-directory",
        ),
    ),
)
def test_numeric_create_rejects_inconsistent_metadata_without_consuming_a_number(
    tmp_path: Path,
    kind: str,
    local_part: str,
    number: int,
    relative_path: str,
) -> None:
    from science_tool.entities import EntityCommandError
    from science_tool.entity_reservation import propose_number

    before_numbers = {
        candidate_kind: propose_number(tmp_path, candidate_kind)
        for candidate_kind in ("question", "hypothesis")
    }
    edit = plan_numeric_create(
        tmp_path / relative_path,
        "planned entity\n",
        "numeric metadata test",
        kind=kind,
        local_part=local_part,
        number=number,
    )

    with pytest.raises(EntityCommandError, match="numeric create metadata"):
        publish_edit(edit, project_root=tmp_path)

    assert not list((tmp_path / "entities").rglob("*.md"))
    assert {
        candidate_kind: propose_number(tmp_path, candidate_kind)
        for candidate_kind in before_numbers
    } == before_numbers


def test_publish_order_puts_entity_edits_before_side_stores(tmp_path: Path):
    """The paths are chosen so a plain path sort yields the OPPOSITE order: `a/index.json`
    precedes `z/record.md` alphabetically. Prose recovery depends on the entity landing
    first, so this ordering is a contract, not presentation."""
    index = plan_create(tmp_path / "a" / "index.json", "{}\n", "prose_decomposition_index")
    entity = plan_create(tmp_path / "z" / "record.md", "body\n", "prose_promotion_mint")

    assert [e.path for e in publish_order([index, entity])] == [entity.path, index.path]


def test_publish_order_is_path_sorted_within_each_group(tmp_path: Path):
    second = plan_create(tmp_path / "b.md", "x\n", "prose_promotion_mint")
    first = plan_create(tmp_path / "a.md", "x\n", "prose_promotion_accrual")

    assert [e.path for e in publish_order([second, first])] == [first.path, second.path]
