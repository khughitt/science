from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import science_tool.autonomy.extract as extract
from science_tool.autonomy.changes import BODY_FIELD, ChangeType
from science_tool.autonomy.extract import ExtractError, extract_change_set

PAPER = "entities/papers/smith2020.md"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message, "--allow-empty")
    return _git(root, "rev-parse", "HEAD")


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _paper_text(*, venue: str = "Nature", body: str = "Abstract.\n") -> str:
    return f"---\nid: paper:smith2020\nkind: paper\ntitle: T\nvenue: {venue}\n---\n\n{body}"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    _write(tmp_path, PAPER, _paper_text())
    _commit(tmp_path, "base")
    return tmp_path


def test_a_frontmatter_edit_reports_that_field(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science"))
    head = _commit(repo, "edit venue")

    change_set = extract_change_set(repo, base, head)
    assert len(change_set.changes) == 1
    change = change_set.changes[0]
    assert change.path == PAPER
    assert change.entity_kind == "paper"
    assert change.change_type is ChangeType.MODIFIED
    assert change.fields == ("venue",)


def test_a_body_edit_reports_the_content_pseudo_field(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(body="Rewritten abstract.\n"))
    head = _commit(repo, "edit body")

    assert extract_change_set(repo, base, head).changes[0].fields == (BODY_FIELD,)


def test_an_added_field_is_reported(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text().replace("venue: Nature\n", "venue: Nature\nconfidence: 0.9\n"))
    head = _commit(repo, "add confidence")

    assert extract_change_set(repo, base, head).changes[0].fields == ("confidence",)


def test_a_removed_field_is_reported(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text().replace("venue: Nature\n", ""))
    head = _commit(repo, "drop venue")

    assert extract_change_set(repo, base, head).changes[0].fields == ("venue",)


def test_a_new_entity_file_is_an_addition(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "entities/papers/jones2021.md", _paper_text())
    head = _commit(repo, "new paper")

    change = extract_change_set(repo, base, head).changes[0]
    assert change.change_type is ChangeType.ADDED
    assert change.entity_kind == "paper"


def test_a_deleted_entity_file_is_a_deletion(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / PAPER).unlink()
    head = _commit(repo, "delete paper")

    change = extract_change_set(repo, base, head).changes[0]
    assert change.change_type is ChangeType.DELETED
    assert change.entity_kind == "paper"


def test_a_rename_is_a_deletion_plus_an_addition(repo: Path):
    """--no-renames: a rename that git would summarise as R100 must surface as both
    halves, because both halves are independently denied."""
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", PAPER, "entities/papers/renamed.md")
    head = _commit(repo, "rename")

    kinds = {(c.path, c.change_type) for c in extract_change_set(repo, base, head).changes}
    assert (PAPER, ChangeType.DELETED) in kinds
    assert ("entities/papers/renamed.md", ChangeType.ADDED) in kinds


def test_a_non_entity_path_carries_no_fields(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "core/decisions.md", "flag: on\n")
    head = _commit(repo, "touch decisions")

    change = next(
        c for c in extract_change_set(repo, base, head).changes if c.path == "core/decisions.md"
    )
    assert change.entity_kind is None
    assert change.fields == ()


def test_the_range_is_two_dot_not_merge_base(repo: Path):
    """Design §6: a merge-base baseline moves under rebase and integration-branch
    advancement. `base..head` must diff the recorded trees, not their merge-base.

    History: A -- C   (main, C edits venue to 'Cell')
              \\
               B      (branch from A, B edits the body)

    base=C, head=B. Two-dot C..B shows BOTH the body edit and venue reverting to
    'Nature'. Three-dot C...B diffs from merge-base A and shows only the body edit.
    """
    a = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side", a)
    _write(repo, PAPER, _paper_text(body="Side body.\n"))
    b = _commit(repo, "side edit")
    _git(repo, "checkout", "-q", "-")
    _write(repo, PAPER, _paper_text(venue="Cell"))
    c = _commit(repo, "main edit")

    fields = extract_change_set(repo, c, b).changes[0].fields
    assert set(fields) == {"venue", BODY_FIELD}, "three-dot semantics would report only the body"


def test_an_unresolvable_commit_is_an_error_not_an_empty_change_set(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(ExtractError):
        extract_change_set(repo, base, "0" * 40)


def test_a_replacement_ref_cannot_hide_a_change(repo: Path):
    """`git replace` grafts one commit's content onto another's identity, and ordinary
    git honours it -- a diff over a tampered repository reports NOTHING. Every git
    invocation must pass --no-replace-objects."""
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "science.yaml", "name: t\nschema_version: 2\n")
    head = _commit(repo, "edit config")
    _git(repo, "replace", head, base)

    changes = extract_change_set(repo, base, head).changes
    assert [c.path for c in changes] == ["science.yaml"], (
        "replacement ref hid the change; git ran without --no-replace-objects"
    )


def test_a_mode_only_change_is_reported_as_a_modification(repo: Path):
    """A chmod produces `M` with identical blobs and therefore no changed fields. The
    extractor must still report the modification so the gate can deny it."""
    base = _git(repo, "rev-parse", "HEAD")
    (repo / PAPER).chmod(0o755)
    head = _commit(repo, "chmod")

    changes = extract_change_set(repo, base, head).changes
    assert len(changes) == 1
    assert changes[0].change_type is ChangeType.MODIFIED
    assert changes[0].fields == ()


def test_an_unreadable_entity_blob_is_an_error_not_an_empty_field_list(repo: Path):
    """Fail-open regression: a blob that cannot be decoded must NOT diff to zero
    changed fields, which the evaluator would allow."""
    base = _git(repo, "rev-parse", "HEAD")
    (repo / PAPER).write_bytes(b"---\nid: paper:smith2020\nkind: paper\ntitle: \xff\xfe\n---\n")
    head = _commit(repo, "invalid utf-8")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, head)


def test_malformed_frontmatter_is_an_error_not_a_body_only_change(repo: Path):
    """A delimited but unparseable block raises out of `split_frontmatter`; it must
    surface as ExtractError so the CLI can report 'could not evaluate' (exit 2)."""
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, "---\nid: paper:smith2020\nvenue: [unclosed\n---\n\nAbstract.\n")
    head = _commit(repo, "malformed frontmatter")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, head)


def test_changes_are_ordered_by_path(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "zzz.txt", "z\n")
    _write(repo, "aaa.txt", "a\n")
    head = _commit(repo, "two files")

    paths = [c.path for c in extract_change_set(repo, base, head).changes]
    assert paths == sorted(paths)


@pytest.mark.parametrize(
    "diff_output", [b"M100\0untrusted.md\0", b"M\0untrusted.md", b"M\0\0"]
)
def test_malformed_diff_records_are_errors(
    repo: Path, monkeypatch: pytest.MonkeyPatch, diff_output: bytes
):
    def fake_git(_repo_root: Path, *args: str) -> bytes:
        if args[:2] == ("rev-parse", "--verify"):
            return b"a" * 40 + b"\n"
        assert args[0] == "diff"
        return diff_output

    monkeypatch.setattr(extract, "_git", fake_git)

    with pytest.raises(ExtractError):
        extract_change_set(repo, "base", "head")
