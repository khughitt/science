"""Planner and CLI for `science entity migrate-annotation-base-shape` (piece 3)."""

from __future__ import annotations

import json as _json
from pathlib import Path

import pytest
from click.testing import CliRunner
from science_model.frontmatter import split_frontmatter

from science_tool.entities_cli import entity_group
from science_tool.migrate_annotation_base_shape import (
    BaseShapeMigrationRefused,
    apply_plan,
    plan_repairs,
)

VALID_PROPOSITION = """\
---
id: proposition:a-affects-b
kind: proposition
title: An authored title
status: active
subject: concept:a
predicate: affects
object: concept:b
polarity: positive
created: '2026-06-01'
updated: '2026-06-01'
---
# body

## Summary
text
"""


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    for sub in ("propositions", "evidence-lines"):
        (tmp_path / "entities" / sub).mkdir(parents=True)
    return tmp_path


def _write(root: Path, sub: str, name: str, frontmatter: str, body: str = "# b\n\n## Summary\n") -> Path:
    path = root / "entities" / sub / name
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


EMPTY_TITLE_PROPOSITION = """\
id: proposition:a-affects-b
kind: proposition
title: ''
status: active
subject: concept:a
predicate: affects
object: concept:b
polarity: positive
created: '2026-06-01'
updated: '2026-06-01'
"""

EMPTY_TITLE_EVIDENCE_LINE = """\
id: evidence-line:a-affects-b-ev1
kind: evidence-line
title: ''
status: active
stance: supports
target: proposition:a-affects-b
source: paper:Walker2024
evidence_type: literature_evidence
created: '2026-06-01'
updated: '2026-06-01'
"""

UNQUOTED_DATES_PROPOSITION = """\
id: proposition:c-affects-d
kind: proposition
title: An authored title
status: active
subject: concept:c
predicate: affects
object: concept:d
polarity: positive
created: 2026-06-01
updated: 2026-06-01
"""


def test_plans_a_proposition_title_from_its_own_triple(tmp_path):
    root = _project(tmp_path)
    _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    plan = plan_repairs(root)
    assert plan.refusals == ()
    assert len(plan.repairs) == 1
    assert plan.repairs[0].title == "concept:a affects concept:b"


def test_plans_an_evidence_line_title_from_its_own_fields(tmp_path):
    root = _project(tmp_path)
    _write(root, "evidence-lines", "e.md", EMPTY_TITLE_EVIDENCE_LINE)
    plan = plan_repairs(root)
    assert plan.refusals == ()
    assert plan.repairs[0].title == "supports proposition:a-affects-b — paper:Walker2024"


def test_a_base_valid_record_is_skipped_byte_for_byte(tmp_path):
    root = _project(tmp_path)
    path = root / "entities/propositions/valid.md"
    path.write_text(VALID_PROPOSITION, encoding="utf-8")
    plan = plan_repairs(root)
    assert plan.repairs == ()
    assert plan.refusals == ()
    assert plan.skipped == 1
    assert path.read_text(encoding="utf-8") == VALID_PROPOSITION


def test_a_date_only_repair_changes_no_parsed_value(tmp_path):
    root = _project(tmp_path)
    path = _write(root, "propositions", "d.md", UNQUOTED_DATES_PROPOSITION)
    plan = plan_repairs(root)
    assert len(plan.repairs) == 1
    assert plan.repairs[0].title is None
    before, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    after, _ = split_frontmatter(plan.repairs[0].postimage)
    assert str(before["created"]) == after["created"]
    assert isinstance(after["created"], str)


@pytest.mark.parametrize("literal", ["null", "0"])
def test_a_title_that_is_not_the_empty_string_is_unsupported(tmp_path, literal):
    """The fixtures that discriminate `title == ""` from a naive falsiness check."""
    root = _project(tmp_path)
    frontmatter = EMPTY_TITLE_PROPOSITION.replace("title: ''", f"title: {literal}")
    _write(root, "propositions", "p.md", frontmatter)
    plan = plan_repairs(root)
    assert plan.repairs == ()
    assert len(plan.refusals) == 1


def test_an_unrepairable_record_is_not_reported_as_a_failed_repair(tmp_path):
    """No repair was attempted on a `title: null` record; the message must not claim one was.

    The validator's own text is passed through verbatim -- that is what the operator acts on.
    """
    root = _project(tmp_path)
    _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: null"))
    reason = plan_repairs(root).refusals[0].reason
    assert "after repair" not in reason
    assert reason.startswith("no repair available; base shape refuses it: ")
    assert "title" in reason


def test_a_missing_derivation_input_is_refused_not_repaired(tmp_path):
    """The 'title cannot be derived' branch: no `subject`, so the triple cannot be reconstructed."""
    root = _project(tmp_path)
    frontmatter = EMPTY_TITLE_PROPOSITION.replace("subject: concept:a\n", "")
    _write(root, "propositions", "p.md", frontmatter)
    plan = plan_repairs(root)
    assert plan.repairs == ()
    assert len(plan.refusals) == 1
    assert "title cannot be derived" in plan.refusals[0].reason
    assert "subject" in plan.refusals[0].reason


@pytest.mark.parametrize(
    ("field", "literal", "expected_type"),
    [
        ("subject", "", "NoneType"),  # `subject:` with no value parses as null
        ("subject", "[x, y]", "list"),
        ("predicate", "3", "int"),
        ("object", "{a: b}", "dict"),
    ],
)
def test_a_non_string_proposition_derivation_input_is_refused(tmp_path, field, literal, expected_type):
    """A non-string input mints a garbage title that base shape then HAPPILY accepts.

    `subject:` (null) derives `None affects concept:b`; a list derives
    `['x', 'y'] affects concept:b`. Base shape only asks that `title` be a non-empty string and
    never inspects `subject`, so without this guard the garbage is written and the post-condition
    scan reports success.
    """
    root = _project(tmp_path)
    original = {"subject": "subject: concept:a", "predicate": "predicate: affects", "object": "object: concept:b"}
    frontmatter = EMPTY_TITLE_PROPOSITION.replace(original[field], f"{field}: {literal}")
    _write(root, "propositions", "p.md", frontmatter)

    plan = plan_repairs(root)

    assert plan.repairs == ()
    assert len(plan.refusals) == 1
    assert plan.refusals[0].reason == f"title cannot be derived: field '{field}' is {expected_type}, not a string"


@pytest.mark.parametrize(
    ("field", "literal", "expected_type"),
    [("stance", "[a, b]", "list"), ("source", "3", "int"), ("evidence_type", "3", "int")],
)
def test_a_non_string_evidence_line_derivation_input_is_refused(tmp_path, field, literal, expected_type):
    """`evidence_type: 3` raises AttributeError inside the derivation -- a crash, not a refusal."""
    root = _project(tmp_path)
    original = {
        "stance": "stance: supports",
        "source": "source: paper:Walker2024",
        "evidence_type": "evidence_type: literature_evidence",
    }
    frontmatter = EMPTY_TITLE_EVIDENCE_LINE.replace(original[field], f"{field}: {literal}")
    if field == "evidence_type":
        # The tail prefers `source`, so `evidence_type` only reaches the derivation without one.
        frontmatter = frontmatter.replace("source: paper:Walker2024\n", "")
    _write(root, "evidence-lines", "e.md", frontmatter)

    plan = plan_repairs(root)

    assert plan.repairs == ()
    assert len(plan.refusals) == 1
    assert (
        plan.refusals[0].reason
        == f"title cannot be derived: field '{field}' is {expected_type}, not a string or null"
    )


@pytest.mark.parametrize("field", ["stance", "source", "evidence_type"])
def test_a_null_optional_evidence_line_input_still_repairs(tmp_path, field):
    """`stance`/`source`/`evidence_type` are `str | None` in the derivation's own signature."""
    root = _project(tmp_path)
    frontmatter = "".join(
        line for line in EMPTY_TITLE_EVIDENCE_LINE.splitlines(keepends=True) if not line.startswith(f"{field}:")
    )
    _write(root, "evidence-lines", "e.md", frontmatter)
    plan = plan_repairs(root)
    assert plan.refusals == ()
    assert len(plan.repairs) == 1


def test_a_stray_non_entity_file_is_skipped_not_refused(tmp_path):
    """Refusal is batch-wide, so refusing a README would make the command unrunnable here."""
    root = _project(tmp_path)
    (root / "entities/propositions/README.md").write_text("# Propositions\n\nNotes.\n", encoding="utf-8")
    good = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)

    plan = plan_repairs(root)

    assert plan.refusals == ()
    assert plan.skipped == 1
    assert [r.path for r in plan.repairs] == [good]


def test_a_foreign_kind_in_the_directory_is_skipped_not_mis_derived(tmp_path):
    """Kind comes from the record. Deriving from the directory applies the wrong formula."""
    root = _project(tmp_path)
    frontmatter = EMPTY_TITLE_EVIDENCE_LINE.replace("kind: evidence-line", "kind: interpretation")
    _write(root, "evidence-lines", "stowaway.md", frontmatter)

    plan = plan_repairs(root)

    assert plan.repairs == ()
    assert plan.refusals == ()
    assert plan.skipped == 1


def test_apply_refuses_the_whole_batch_and_names_every_refusal(tmp_path):
    root = _project(tmp_path)
    good = _write(root, "propositions", "good.md", EMPTY_TITLE_PROPOSITION)
    _write(root, "propositions", "bad1.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: null"))
    _write(root, "propositions", "bad2.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: 0"))
    before = good.read_text(encoding="utf-8")

    plan = plan_repairs(root)
    with pytest.raises(BaseShapeMigrationRefused) as excinfo:
        apply_plan(plan)

    assert "bad1.md" in str(excinfo.value)
    assert "bad2.md" in str(excinfo.value)
    assert good.read_text(encoding="utf-8") == before


def test_planning_writes_nothing(tmp_path):
    root = _project(tmp_path)
    path = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    before = path.read_text(encoding="utf-8")
    plan_repairs(root)
    assert path.read_text(encoding="utf-8") == before


def test_apply_is_idempotent(tmp_path):
    root = _project(tmp_path)
    path = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    apply_plan(plan_repairs(root))
    once = path.read_text(encoding="utf-8")
    second = plan_repairs(root)
    assert second.repairs == ()
    assert second.skipped == 1
    assert path.read_text(encoding="utf-8") == once


def test_the_repair_does_not_stamp_updated(tmp_path):
    """The repair restores what the writer should have persisted; it asserts no new change."""
    root = _project(tmp_path)
    path = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    apply_plan(plan_repairs(root))
    frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    assert frontmatter["created"] == "2026-06-01"
    assert frontmatter["updated"] == "2026-06-01"


def test_apply_preserves_crlf_body_bytes(tmp_path):
    """Pins the preserving-body reader: Path.read_text would silently rewrite line endings."""
    root = _project(tmp_path)
    path = root / "entities/propositions/crlf.md"
    body = "# b\r\n\r\n## Summary\r\ntext\r\n"
    text = f"---\n{EMPTY_TITLE_PROPOSITION}---\n".replace("\n", "\r\n") + body
    path.write_bytes(text.encode("utf-8"))

    apply_plan(plan_repairs(root))

    # The exact original body bytes, not merely "some CRLF survived" -- a partial
    # rewrite would leave CRLF elsewhere in the file and pass a weaker assertion.
    assert path.read_bytes().endswith(body.encode("utf-8"))


def test_dates_are_force_quoted_by_the_canonical_renderer(tmp_path):
    """Pins the renderer choice: the workbench emitter does NOT force-quote."""
    root = _project(tmp_path)
    path = _write(root, "propositions", "d.md", UNQUOTED_DATES_PROPOSITION)
    apply_plan(plan_repairs(root))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert 'created: "2026-06-01"' in lines
    assert 'updated: "2026-06-01"' in lines


def test_a_datetime_valued_date_is_unsupported(tmp_path):
    """The measured defect is a bare date; a datetime's time component would be discarded."""
    root = _project(tmp_path)
    frontmatter = UNQUOTED_DATES_PROPOSITION.replace("created: 2026-06-01", "created: 2026-06-01 10:30:00")
    _write(root, "propositions", "dt.md", frontmatter)
    plan = plan_repairs(root)
    assert plan.repairs == ()
    assert len(plan.refusals) == 1


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    root = _project(tmp_path)
    path = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    before = path.read_text(encoding="utf-8")
    monkeypatch.chdir(root)

    result = CliRunner().invoke(entity_group, ["migrate-annotation-base-shape", "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = _json.loads(result.output)
    assert payload["written"] == 0
    assert len(payload["repairs"]) == 1
    assert path.read_text(encoding="utf-8") == before


def test_apply_repairs_the_invalid_and_leaves_the_valid_byte_identical(tmp_path, monkeypatch):
    """Pins the base-valid skip: a command that re-renders everything passes every other test."""
    root = _project(tmp_path)
    valid = root / "entities/propositions/valid.md"
    valid.write_text(VALID_PROPOSITION, encoding="utf-8")
    invalid = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    monkeypatch.chdir(root)

    result = CliRunner().invoke(
        entity_group, ["migrate-annotation-base-shape", "--apply", "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    assert _json.loads(result.output)["written"] == 1
    assert valid.read_text(encoding="utf-8") == VALID_PROPOSITION
    repaired, _ = split_frontmatter(invalid.read_text(encoding="utf-8"))
    assert repaired["title"] == "concept:a affects concept:b"


def test_dry_run_names_refusals_and_exits_nonzero(tmp_path, monkeypatch):
    """Report-first: a dry run must not print 'would repair' while hiding its blockers."""
    root = _project(tmp_path)
    good = _write(root, "propositions", "good.md", EMPTY_TITLE_PROPOSITION)
    _write(root, "propositions", "bad.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: null"))
    before = good.read_text(encoding="utf-8")
    monkeypatch.chdir(root)

    result = CliRunner().invoke(entity_group, ["migrate-annotation-base-shape"])

    assert result.exit_code != 0
    assert "bad.md" in result.output
    assert "would repair" not in result.output
    assert good.read_text(encoding="utf-8") == before


def test_apply_with_unsupported_records_exits_nonzero_and_writes_nothing(tmp_path, monkeypatch):
    root = _project(tmp_path)
    good = _write(root, "propositions", "good.md", EMPTY_TITLE_PROPOSITION)
    _write(root, "propositions", "bad1.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: null"))
    _write(root, "propositions", "bad2.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: 0"))
    before = good.read_text(encoding="utf-8")
    monkeypatch.chdir(root)

    result = CliRunner().invoke(entity_group, ["migrate-annotation-base-shape", "--apply"])

    assert result.exit_code != 0
    assert "bad1.md" in result.output
    assert "bad2.md" in result.output
    assert good.read_text(encoding="utf-8") == before
