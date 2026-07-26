from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from science_model.autonomous_runs import RunTier

import science_tool.autonomy.extract as extract
from science_tool.autonomy.changes import BODY_FIELD, ChangeType, UNACCOUNTED_CHANGE_FIELD
from science_tool.autonomy.extract import ExtractError, extract_change_set
from science_tool.autonomy.path_gate import evaluate

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


def test_a_mode_only_change_reports_an_unaccounted_component(repo: Path):
    """A chmod must be explicit so it cannot piggyback on an allowed field edit."""
    base = _git(repo, "rev-parse", "HEAD")
    (repo / PAPER).chmod(0o755)
    head = _commit(repo, "chmod")

    changes = extract_change_set(repo, base, head).changes
    assert len(changes) == 1
    assert changes[0].change_type is ChangeType.MODIFIED
    assert changes[0].fields == (UNACCOUNTED_CHANGE_FIELD,)


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


def test_invalid_timestamp_constructor_is_an_extract_error(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(
        repo,
        PAPER,
        _paper_text().replace("venue: Nature\n", "venue: Nature\nupdated: 2026-99-99\n"),
    )
    head = _commit(repo, "invalid timestamp")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, head)


def test_invalid_timestamp_constructor_in_yaml_key_is_an_extract_error():
    node = yaml.compose("2026-99-99\n")
    assert isinstance(node, yaml.ScalarNode)

    with pytest.raises(ExtractError):
        extract._yaml_key(node)


def test_invalid_timestamp_constructor_in_template_key_is_an_extract_error():
    with pytest.raises(ExtractError):
        extract._frontmatter_template("2026-99-99: value\n")


def test_value_error_from_yaml_composition_is_an_extract_error(
    monkeypatch: pytest.MonkeyPatch,
):
    def invalid_composition(_block: str):
        raise ValueError("invalid YAML composition")

    monkeypatch.setattr(extract.yaml, "compose", invalid_composition)

    with pytest.raises(ExtractError):
        extract._field_map({}, "field: value\n")


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


def test_a_boolean_to_integer_edit_is_accounted_as_a_denied_field(repo: Path):
    _write(repo, PAPER, _paper_text().replace("venue: Nature\n", "venue: Nature\nconfidence: true\n"))
    _commit(repo, "add boolean confidence")
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science").replace("venue: Science\n", "venue: Science\nconfidence: 1\n"))
    head = _commit(repo, "change venue and confidence")

    change = extract_change_set(repo, base, head).changes[0]
    assert change.fields == ("confidence", "venue")
    assert evaluate(
        extract_change_set(repo, base, head), tier=RunTier.BELIEF_NEUTRAL
    ).allowed is False


def test_frontmatter_keys_that_collide_when_stringified_are_uncomputable(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(
        repo,
        PAPER,
        _paper_text(venue="Science").replace("venue: Science\n", "1: a\n'1': b\nvenue: Science\n"),
    )
    head = _commit(repo, "introduce colliding keys")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, head)


def test_an_allowed_field_plus_a_mode_change_is_denied(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science"))
    (repo / PAPER).chmod(0o755)
    head = _commit(repo, "edit venue and chmod")

    change_set = extract_change_set(repo, base, head)
    assert "venue" in change_set.changes[0].fields
    assert UNACCOUNTED_CHANGE_FIELD in change_set.changes[0].fields
    assert evaluate(change_set, tier=RunTier.BELIEF_NEUTRAL).allowed is False


def test_an_allowed_field_plus_a_frontmatter_comment_change_is_denied(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(
        repo,
        PAPER,
        _paper_text(venue="Science").replace("venue: Science\n", "# source verified\nvenue: Science\n"),
    )
    head = _commit(repo, "edit venue and comment")

    change_set = extract_change_set(repo, base, head)
    assert "venue" in change_set.changes[0].fields
    assert UNACCOUNTED_CHANGE_FIELD in change_set.changes[0].fields
    assert evaluate(change_set, tier=RunTier.BELIEF_NEUTRAL).allowed is False


def test_a_nul_containing_revision_is_an_extract_error(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, "HEAD\0malicious")


def test_option_like_revisions_are_delimited_before_rev_parse(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    calls: list[tuple[str, ...]] = []

    def fake_git(_repo_root: Path, *args: str) -> bytes:
        calls.append(args)
        return b"a" * 40 + b"\n"

    monkeypatch.setattr(extract, "_git", fake_git)

    extract._require_commit(repo, "--show-toplevel")

    assert calls == [
        ("rev-parse", "--verify", "--end-of-options", "--show-toplevel^{commit}")
    ]


def test_an_option_like_revision_is_an_extract_error(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, "--show-toplevel")


def test_quoted_key_syntax_cannot_piggyback_on_an_allowed_value_edit(repo: Path):
    _write(repo, PAPER, _paper_text().replace("venue: Nature", "'venue': Nature"))
    _commit(repo, "quote venue key")
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science"))
    head = _commit(repo, "unquote venue key and edit value")

    change_set = extract_change_set(repo, base, head)
    assert change_set.changes[0].fields == (UNACCOUNTED_CHANGE_FIELD, "venue")
    assert evaluate(change_set, tier=RunTier.BELIEF_NEUTRAL).allowed is False


def test_crlf_to_lf_cannot_piggyback_on_an_allowed_value_edit(repo: Path):
    _write(
        repo,
        PAPER,
        "---\r\nid: paper:smith2020\r\nkind: paper\r\ntitle: T\r\nvenue: Nature\r\n---\r\nAbstract.\n",
    )
    _commit(repo, "use crlf")
    base = _git(repo, "rev-parse", "HEAD")
    _write(
        repo,
        PAPER,
        "---\nid: paper:smith2020\nkind: paper\ntitle: T\nvenue: Science\n---\nAbstract.\n",
    )
    head = _commit(repo, "use lf and edit venue")

    change_set = extract_change_set(repo, base, head)
    assert change_set.changes[0].fields == (UNACCOUNTED_CHANGE_FIELD, "venue")
    assert evaluate(change_set, tier=RunTier.BELIEF_NEUTRAL).allowed is False


def test_a_cyclic_alias_with_an_allowed_edit_is_an_extract_error(repo: Path):
    _write(repo, PAPER, _paper_text().replace("venue: Nature\n", "loop: &loop [*loop]\nvenue: Nature\n"))
    _commit(repo, "add cyclic alias")
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science").replace("venue: Science\n", "loop: &loop [*loop]\nvenue: Science\n"))
    head = _commit(repo, "edit venue")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, head)


def test_a_nested_mapping_collision_beneath_a_sequence_is_an_extract_error(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(
        repo,
        PAPER,
        _paper_text(venue="Science").replace(
            "venue: Science\n", "items:\n  - 1: a\n    true: b\nvenue: Science\n"
        ),
    )
    head = _commit(repo, "add ambiguous nested mapping")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, head)
