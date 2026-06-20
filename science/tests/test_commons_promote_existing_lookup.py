"""Tests for _semver_key and _existing_canonical_for_slug in promote.py."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.commons.errors import PromoteInputError

# --------------------------------------------------------------------------- #
# Shared fixtures / helpers                                                    #
# --------------------------------------------------------------------------- #


def _init_commons(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@x"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)
    (root / "papers").mkdir()
    (root / ".gitignore").write_text("registry.sqlite\n.registry-*.sqlite\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)


def _add_tag(root: Path, tag: str) -> None:
    """Create a lightweight git tag on the current HEAD."""
    subprocess.run(["git", "-C", str(root), "tag", tag], check=True)


# --------------------------------------------------------------------------- #
# _semver_key tests                                                            #
# --------------------------------------------------------------------------- #


def test_semver_key_basic_ordering() -> None:
    from science_tool.commons.promote import _semver_key

    assert _semver_key("1.0.0") == (1, 0, 0)
    assert _semver_key("2.3.4") == (2, 3, 4)


def test_semver_key_minor_ordering() -> None:
    """1.10.0 must sort higher than 1.9.0 (numeric, not lexicographic)."""
    from science_tool.commons.promote import _semver_key

    assert _semver_key("1.10.0") > _semver_key("1.9.0")


def test_semver_key_patch_ordering() -> None:
    from science_tool.commons.promote import _semver_key

    assert _semver_key("1.0.10") > _semver_key("1.0.9")


def test_semver_key_major_ordering() -> None:
    from science_tool.commons.promote import _semver_key

    assert _semver_key("2.0.0") > _semver_key("1.99.99")


def test_semver_key_raises_on_malformed() -> None:
    from science_tool.commons.promote import _semver_key

    with pytest.raises(PromoteInputError):
        _semver_key("not-a-version")


def test_semver_key_raises_on_two_parts() -> None:
    from science_tool.commons.promote import _semver_key

    with pytest.raises(PromoteInputError):
        _semver_key("1.0")


# --------------------------------------------------------------------------- #
# _existing_canonical_for_slug tests                                           #
# --------------------------------------------------------------------------- #


def test_existing_canonical_returns_none_when_no_tags(tmp_path) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _existing_canonical_for_slug

    _init_commons(tmp_path)
    result = _existing_canonical_for_slug(tmp_path, PROMOTE_KIND_PAPER, "dubois2022")
    assert result is None


def test_existing_canonical_returns_none_when_no_matching_tag(tmp_path) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _existing_canonical_for_slug

    _init_commons(tmp_path)
    _add_tag(tmp_path, "paper/Adams2025/1.0.0")
    result = _existing_canonical_for_slug(tmp_path, PROMOTE_KIND_PAPER, "dubois2022")
    assert result is None


def test_existing_canonical_case_insensitive_match(tmp_path) -> None:
    """Tag paper/Dubois2022/1.0.0 matched by normalized query 'dubois2022'."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _existing_canonical_for_slug

    _init_commons(tmp_path)
    _add_tag(tmp_path, "paper/Dubois2022/1.0.0")
    result = _existing_canonical_for_slug(tmp_path, PROMOTE_KIND_PAPER, "dubois2022")
    assert result == ("Dubois2022", "1.0.0")


def test_existing_canonical_max_semver_selection(tmp_path) -> None:
    """With tags 1.0.0 and 1.2.0, returns the highest version."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _existing_canonical_for_slug

    _init_commons(tmp_path)
    _add_tag(tmp_path, "paper/Foo2020/1.0.0")
    # Make another commit to allow a second tag on a different commit point,
    # but lightweight tags on same commit are fine too.
    _add_tag(tmp_path, "paper/Foo2020/1.2.0")
    result = _existing_canonical_for_slug(tmp_path, PROMOTE_KIND_PAPER, "foo2020")
    assert result == ("Foo2020", "1.2.0")


def test_existing_canonical_max_semver_numeric_not_lexicographic(tmp_path) -> None:
    """1.10.0 must beat 1.9.0 (numeric comparison, not lexicographic)."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _existing_canonical_for_slug

    _init_commons(tmp_path)
    _add_tag(tmp_path, "paper/Bar2021/1.9.0")
    _add_tag(tmp_path, "paper/Bar2021/1.10.0")
    result = _existing_canonical_for_slug(tmp_path, PROMOTE_KIND_PAPER, "bar2021")
    assert result == ("Bar2021", "1.10.0")


def test_existing_canonical_integrity_guard_raises_on_multiple_cases(tmp_path) -> None:
    """Tags paper/Dubois2022/1.0.0 AND paper/dubois2022/1.0.0 → PromoteInputError."""
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _existing_canonical_for_slug

    _init_commons(tmp_path)
    _add_tag(tmp_path, "paper/Dubois2022/1.0.0")
    _add_tag(tmp_path, "paper/dubois2022/1.0.0")
    with pytest.raises(PromoteInputError, match="multiple cases"):
        _existing_canonical_for_slug(tmp_path, PROMOTE_KIND_PAPER, "dubois2022")


def test_existing_canonical_returns_committed_case_not_query_case(tmp_path) -> None:
    """The first tuple element is the tag's case, not the normalized query."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _existing_canonical_for_slug

    _init_commons(tmp_path)
    _add_tag(tmp_path, "paper/SmithJones2019/1.0.0")
    result = _existing_canonical_for_slug(tmp_path, PROMOTE_KIND_PAPER, "smithjones2019")
    assert result is not None
    committed_case, version = result
    assert committed_case == "SmithJones2019"
    assert version == "1.0.0"


def test_existing_canonical_skips_malformed_tags(tmp_path) -> None:
    """Malformed tags (missing slug or version segment) are silently skipped.

    A two-segment tag like ``paper/Foo2020`` has no version component; after
    ``rest.rpartition("/")`` the slug is empty. Previously this caused
    ``_normalize_slug_for_match`` to raise ``PromoteCandidateError``, violating
    the function's contract. The fix guards with ``if not case_slug or not version``.

    Case 1: only a malformed tag present → returns None (no valid match).
    Case 2: malformed tag + a well-formed tag → valid match is returned.
    """
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _existing_canonical_for_slug

    # Case 1: only the malformed two-segment tag — must return None, not raise.
    _init_commons(tmp_path)
    _add_tag(tmp_path, "paper/Foo2020")  # missing version segment
    result = _existing_canonical_for_slug(tmp_path, PROMOTE_KIND_PAPER, "foo2020")
    assert result is None

    # Case 2: malformed tag coexists with a valid tag — valid match returned.
    _add_tag(tmp_path, "paper/Bar2021/1.0.0")
    result2 = _existing_canonical_for_slug(tmp_path, PROMOTE_KIND_PAPER, "bar2021")
    assert result2 == ("Bar2021", "1.0.0")
