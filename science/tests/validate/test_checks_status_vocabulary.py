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


def test_a_VERDICT_word_in_status_is_flagged(tmp_path: Path) -> None:
    """☠️ THIS TEST ASSERTED THE EXACT OPPOSITE, AND THE INVERSION IS THE WHOLE ARC.

    It read: "`retired` is not in the hypothesis vocabulary. It is a TASK status." That was true, and
    it was the DEFECT -- not the rule. The author of natural-systems' `hypothesis:0009` needed a
    lifecycle word, `status` held the epistemic verdict, and so writing "stop working on this"
    destroyed "the evidence failed to confirm it" (fb-2026-07-11-005).

    `status` is the LIFECYCLE now, so `retired` is not merely allowed -- it is the correct word, and
    the test below asserts it passes. What is flagged is the mirror image: a VERDICT word sitting in
    the lifecycle field, which is every unmigrated hypothesis in the corpus and precisely what the
    migration exists to move.
    """
    _entity(tmp_path, "hypotheses/0009-x.md", entity_id="hypothesis:0009-x", kind="hypothesis", status="weakened")

    messages = _run(tmp_path)

    assert any("weakened" in m and "hypothesis" in m for m in messages), messages


def test_a_LIFECYCLE_word_passes(tmp_path: Path) -> None:
    """`retired` IS the vocabulary now -- the word `hypothesis:0009` needed and could not have."""
    _entity(tmp_path, "hypotheses/0009-x.md", entity_id="hypothesis:0009-x", kind="hypothesis", status="retired")

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
