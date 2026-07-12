"""An entity's status must be in its kind's DECLARED vocabulary.

Status was validated on CLI writes only. Hand-authored frontmatter was never re-checked and
`science validate` never looked at status at all -- so `status: retired` (a TASK status)
sat in a committed natural-systems hypothesis and nothing said a word (fb-2026-07-11-005).

The vocabulary comes from the Kind Descriptors, never from a table in the check.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.status_vocabulary import check_status_vocabulary
from science_tool.validate.context import ValidateContext


def _entity(root: Path, rel: str, *, entity_id: str, kind: str, status: str) -> None:
    path = root / "entities" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nid: "{entity_id}"\nkind: {kind}\ntitle: "T"\nstatus: "{status}"\n---\n\nBody.\n',
        encoding="utf-8",
    )


def _run(root: Path) -> list[str]:
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return [r.message for r in check_status_vocabulary(ctx)]


def test_task_status_on_a_hypothesis_is_flagged(tmp_path: Path) -> None:
    """`retired` is not in the hypothesis vocabulary. It is a TASK status.

    This is the exact defect: the author needed a WORKFLOW word, `status` was the only
    field available, and the workflow word overwrote the epistemic verdict.
    """
    _entity(tmp_path, "hypotheses/0009-x.md", entity_id="hypothesis:0009-x", kind="hypothesis", status="retired")

    messages = _run(tmp_path)

    assert any("retired" in m and "hypothesis" in m for m in messages), messages


def test_declared_status_passes(tmp_path: Path) -> None:
    """`weakened` IS in the vocabulary -- and is what hypothesis:0009 should have carried,
    since a non-significant confirmatory null (z = -0.889) failed to confirm rather than
    refuting anything."""
    _entity(tmp_path, "hypotheses/0009-x.md", entity_id="hypothesis:0009-x", kind="hypothesis", status="weakened")

    assert not _run(tmp_path)


def test_unknown_kind_does_not_crash_the_check(tmp_path: Path) -> None:
    """`valid_statuses` raises KeyError for an unregistered kind. That defect is already
    owned by `unknown_entity_kind` in the source loader, so this check must skip rather
    than crash or double-report."""
    _entity(tmp_path, "aliens/0001-x.md", entity_id="alien:0001-x", kind="alien", status="green")

    assert not _run(tmp_path)  # and no exception


def test_missing_status_is_not_this_checks_business(tmp_path: Path) -> None:
    path = tmp_path / "entities" / "hypotheses" / "0009-x.md"
    path.parent.mkdir(parents=True)
    path.write_text('---\nid: "hypothesis:0009-x"\nkind: hypothesis\ntitle: "T"\n---\n\nBody.\n', encoding="utf-8")

    assert not _run(tmp_path)
