from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from science_tool.boundary.gitio import (
    governed_ignore_files,
    tracked_ignored,
    unmanaged_rules,
    visible_paths,
    matching_unmanaged_rules,
)


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    return tmp_path


def _write(repo: Path, rel: str, body: str = "x\n") -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


def test_visible_paths_excludes_ignored(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "keep.txt")
    _write(repo, "skip.log")
    _write(repo, ".gitignore", "*.log\n")
    vis = visible_paths(repo)
    assert "keep.txt" in vis
    assert "skip.log" not in vis


def test_visible_paths_includes_tracked_even_if_later_ignored(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "a.log")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "a.log"], check=True)
    _write(repo, ".gitignore", "*.log\n")
    assert "a.log" in visible_paths(repo)


def test_visible_paths_matches_git_add_for_file_level_negation(tmp_path: Path):
    """The oracle must agree with staging, where check-ignore does not."""
    repo = _repo(tmp_path)
    _write(repo, "s/m/archive/a.py")
    _write(repo, "gi", "archive\n")
    subprocess.run(["git", "-C", str(repo), "config", "core.excludesFile", str(repo / "gi")], check=True)
    _write(repo, ".gitignore", "!/s/m/archive/a.py\n")
    assert "s/m/archive/a.py" not in visible_paths(repo)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    staged = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True).stdout.split()
    assert "s/m/archive/a.py" not in staged


def test_visible_paths_directory_level_negation_works(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "s/m/archive/a.py")
    _write(repo, "gi", "archive\n")
    subprocess.run(["git", "-C", str(repo), "config", "core.excludesFile", str(repo / "gi")], check=True)
    _write(repo, ".gitignore", "!/s/m/archive/\n")
    assert "s/m/archive/a.py" in visible_paths(repo)


def test_visible_paths_handles_newline_in_filename(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "we\nird.txt")
    assert "we\nird.txt" in visible_paths(repo)


def test_tracked_ignored_reports_source_and_line(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "data/raw/big.csv")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "data/raw/big.csv"], check=True)
    _write(repo, ".gitignore", "# c\n/data/raw/\n")
    hits = tracked_ignored(repo)
    assert [h.path for h in hits] == ["data/raw/big.csv"]
    assert hits[0].source.endswith(".gitignore")
    assert hits[0].line == 2
    assert hits[0].pattern == "/data/raw/"


def test_tracked_ignored_filters_negation_matches(tmp_path: Path):
    """`check-ignore -v` reports `!`-prefixed matches; those files are NOT ignored."""
    repo = _repo(tmp_path)
    _write(repo, "data/keep.tsv")
    _write(repo, ".gitignore", "data/*\n!data/keep.tsv\n")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "data/keep.tsv"], check=True)
    assert tracked_ignored(repo) == []


def test_tracked_ignored_sees_global_excludes(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "archive/a.py")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "archive/a.py"], check=True)
    _write(repo, "gi", "archive\n")
    subprocess.run(["git", "-C", str(repo), "config", "core.excludesFile", str(repo / "gi")], check=True)
    hits = tracked_ignored(repo)
    assert [h.path for h in hits] == ["archive/a.py"]
    assert hits[0].source.endswith("gi")


def test_governed_files_exclude_untracked_and_info_exclude(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "/data/**\n!/data/**/\n")
    _write(repo, "src/.gitignore", "build/\n")
    _write(repo, "data/nested/.gitignore", "x\n")
    (repo / ".git/info").mkdir(parents=True, exist_ok=True)
    (repo / ".git/info/exclude").write_text("secret/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "src/.gitignore"], check=True)
    files = governed_ignore_files(repo)
    assert ".gitignore" in files
    assert "src/.gitignore" in files
    assert "data/nested/.gitignore" not in files  # untracked -> not shareable
    assert not any("info/exclude" in f for f in files)


def test_unmanaged_rules_skip_the_managed_block_and_comments(tmp_path: Path):
    from science_tool.boundary.generate import splice_managed_block

    repo = _repo(tmp_path)
    text = splice_managed_block("# note\n.venv/\n\n", "/data/raw/\n")
    _write(repo, ".gitignore", text)
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    rules = unmanaged_rules(repo)
    patterns = [r.pattern for r in rules]
    assert patterns == [".venv/"]
    assert rules[0].source == ".gitignore"


def test_unmanaged_rules_report_a_duplicate_of_a_generated_line(tmp_path: Path):
    """Text equality must NOT suppress: a hand-written duplicate outside the
    block is exactly what declaration-conflict exists to reject."""
    from science_tool.boundary.generate import splice_managed_block

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", splice_managed_block("/data/raw/\n", "/data/raw/\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert [r.pattern for r in unmanaged_rules(repo)] == ["/data/raw/"]


@pytest.mark.parametrize("operation", ["unmanaged_rules", "matching_unmanaged_rules"])
def test_rule_introspection_rejects_malformed_managed_blocks(
    tmp_path: Path,
    operation: str,
):
    from science_tool.boundary.generate import MANAGED_BEGIN, ManagedBlockError

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", f"{MANAGED_BEGIN}\n/data/raw/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)

    with pytest.raises(ManagedBlockError, match="unmatched BEGIN"):
        if operation == "unmanaged_rules":
            unmanaged_rules(repo)
        else:
            matching_unmanaged_rules(repo, ["data/raw/x.csv"])


def test_git_failure_raises_rather_than_reporting_clean(tmp_path: Path):
    from science_tool.boundary.gitio import BoundaryGitError

    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    with pytest.raises(BoundaryGitError):
        visible_paths(not_a_repo)


def test_matching_rules_use_git_semantics_for_wildcards(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "*.parquet\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/external/ds/part.parquet"])
    assert [r.pattern for r in hits["data/external/ds/part.parquet"]] == ["*.parquet"]


def test_matching_rules_respect_nested_gitignore_scope(tmp_path: Path):
    """`data/raw` inside inc/.gitignore scopes to inc/, not the repo root."""
    repo = _repo(tmp_path)
    _write(repo, "inc/.gitignore", "data/raw\n")
    subprocess.run(["git", "-C", str(repo), "add", "inc/.gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/raw/x.csv", "inc/data/raw/y.csv"])
    assert "data/raw/x.csv" not in hits
    assert hits["inc/data/raw/y.csv"][0].source == "inc/.gitignore"


def test_matching_rules_see_past_a_later_managed_rule(tmp_path: Path):
    """The managed block is spliced AFTER the hand-written region, so it always
    WINS. Isolation is what makes the shadowed unmanaged rule visible."""
    from science_tool.boundary.generate import splice_managed_block

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", splice_managed_block("*.parquet\n", "/data/external/**\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    target = "data/external/ds/part.parquet"
    # Real resolution: the managed rule wins.
    assert tracked_ignored(repo) == []  # nothing tracked yet
    hits = matching_unmanaged_rules(repo, [target])
    assert [r.pattern for r in hits[target]] == ["*.parquet"]
    assert hits[target][0].line == 1, "managed lines are blanked, so line numbers still match"


def test_matching_rules_report_a_duplicate_shadowed_by_the_managed_block(tmp_path: Path):
    from science_tool.boundary.generate import splice_managed_block

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", splice_managed_block("/data/raw/\n", "/data/raw/\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/raw/x.csv"])
    assert hits["data/raw/x.csv"][0].line == 1


def test_matching_rules_see_past_an_unmanaged_negation(tmp_path: Path):
    """Isolation alone is not enough: among unmanaged rules the last match still
    wins, and git reports the NEGATION here. Peeling is what surfaces the ignore
    rule underneath it. Both lines are reported -- the negation is itself an
    unauthorised per-case exception."""
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "/data/raw/**\n!/data/raw/**\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/raw/x.csv"])
    assert [(r.line, r.pattern) for r in hits["data/raw/x.csv"]] == [
        (1, "/data/raw/**"),
        (2, "!/data/raw/**"),
    ]


def test_matching_rules_report_a_standalone_negation(tmp_path: Path):
    """A lone `!` rule ignores nothing, so no ignore-rule search would find it --
    but pinning one file out of a declared payload root by hand is exactly the
    per-case exception the declaration replaces."""
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "!/data/raw/keep.csv\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/raw/keep.csv", "data/raw/other.csv"])
    assert [r.pattern for r in hits["data/raw/keep.csv"]] == ["!/data/raw/keep.csv"]
    assert "data/raw/other.csv" not in hits


def test_matching_rules_attribute_one_rule_to_every_path_it_matches(tmp_path: Path):
    """Peeling blanks a rule only AFTER the whole round is recorded; blanking
    mid-round would drop every path after the first."""
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "*.parquet\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    paths = ["data/external/a.parquet", "data/external/b.parquet", "data/external/c.parquet"]
    hits = matching_unmanaged_rules(repo, paths)
    assert sorted(hits) == sorted(paths)


def test_matching_rules_peel_independently_for_each_path(tmp_path: Path):
    """A path-specific winner must not globally peel an earlier shared rule."""
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "*.parquet\nspecial.parquet\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)

    hits = matching_unmanaged_rules(repo, ["a.parquet", "special.parquet"])

    assert [(r.line, r.pattern) for r in hits["a.parquet"]] == [(1, "*.parquet")]
    assert [(r.line, r.pattern) for r in hits["special.parquet"]] == [
        (1, "*.parquet"),
        (2, "special.parquet"),
    ]


def test_matching_rules_terminate_when_nothing_matches(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "/unrelated/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert matching_unmanaged_rules(repo, ["data/external/a.parquet"]) == {}


def test_governed_ignore_files_skip_a_tracked_but_deleted_file(tmp_path: Path):
    """`ls-files` still lists it; it governs nothing."""
    repo = _repo(tmp_path)
    _write(repo, "inc/.gitignore", "build/\n")
    subprocess.run(["git", "-C", str(repo), "add", "inc/.gitignore"], check=True)
    (repo / "inc" / ".gitignore").unlink()
    assert governed_ignore_files(repo) == []


def test_governed_ignore_files_skip_a_symlink(tmp_path: Path):
    """git opens .gitignore with O_NOFOLLOW and applies NO rules from a symlink
    -- it warns 'unable to access' even when the target resolves. is_file() and
    read_text() both follow, so without this filter the scratch repo invents
    active rules git ignores, from content OUTSIDE the repository."""
    repo = _repo(tmp_path)
    outside = tmp_path.parent / "outside-rules.txt"
    outside.write_text("*.parquet\n")
    (repo / ".gitignore").symlink_to(outside)
    subprocess.run(["git", "-C", str(repo), "add", "-f", ".gitignore"], check=True)

    # Precondition: git itself applies nothing from it.
    rc = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "--no-index", "-q", "d/x.parquet"],
        capture_output=True,
    ).returncode
    assert rc != 0, "fixture precondition: git applies no rules from a symlinked .gitignore"

    assert governed_ignore_files(repo) == []
    assert unmanaged_rules(repo) == []


def test_governed_ignore_files_reject_a_nonregular_index_entry(tmp_path: Path):
    """A regular worktree file cannot make an indexed symlink shareable."""
    repo = _repo(tmp_path)
    source = _write(repo, ".gitignore", "*.parquet\n")
    oid = (
        subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
            input=b"ignore-target",
            check=True,
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "update-index",
            "--add",
            "--cacheinfo",
            "120000",
            oid,
            ".gitignore",
        ],
        check=True,
    )
    assert source.is_file()
    assert not source.is_symlink()

    assert governed_ignore_files(repo) == []


def test_governed_ignore_files_skip_intent_to_add(tmp_path: Path):
    """Intent-to-add is omitted by write-tree, so its rules are not shareable."""
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "*.parquet\n")
    subprocess.run(
        ["git", "-C", str(repo), "add", "-N", ".gitignore"],
        check=True,
    )
    tree = subprocess.run(
        ["git", "-C", str(repo), "write-tree"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    names = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "-z", tree],
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    assert b".gitignore" not in names

    assert governed_ignore_files(repo) == []
    assert unmanaged_rules(repo) == []


def test_governed_ignore_files_skip_a_symlinked_parent(tmp_path: Path):
    """No parent component may redirect governed reads outside the repository."""
    repo = _repo(tmp_path)
    source = _write(repo, "dir/.gitignore", "*.inside\n")
    subprocess.run(["git", "-C", str(repo), "add", "dir/.gitignore"], check=True)
    source.unlink()
    (repo / "dir").rmdir()

    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    _write(outside, ".gitignore", "*.outside\n")
    (repo / "dir").symlink_to(outside, target_is_directory=True)

    assert governed_ignore_files(repo) == []
    assert unmanaged_rules(repo) == []


def test_governed_ignore_files_fail_closed_on_parent_access_error(tmp_path: Path):
    from science_tool.boundary.gitio import BoundaryGitError

    repo = _repo(tmp_path)
    _write(repo, "dir/.gitignore", "*.parquet\n")
    subprocess.run(["git", "-C", str(repo), "add", "dir/.gitignore"], check=True)
    (repo / "dir").chmod(0o000)
    try:
        if os.access(repo / "dir", os.R_OK | os.X_OK):
            pytest.skip("running as root; permissions are not enforced")
        with pytest.raises(BoundaryGitError, match="cannot inspect governed ignore file"):
            governed_ignore_files(repo)
    finally:
        (repo / "dir").chmod(0o755)


def test_unreadable_source_raises_rather_than_reporting_no_rules(tmp_path: Path):
    """An unreadable rule source is not an empty one: swallowing it would leave
    the file governed on paper and ungoverned in fact."""
    from science_tool.boundary.gitio import BoundaryGitError

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "/data/raw/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    (repo / ".gitignore").chmod(0o000)
    try:
        if os.access(repo / ".gitignore", os.R_OK):
            pytest.skip("running as root; permissions are not enforced")
        with pytest.raises(BoundaryGitError, match="cannot read governed ignore file"):
            unmanaged_rules(repo)
    finally:
        (repo / ".gitignore").chmod(0o644)


def test_non_utf8_gitignore_is_read_and_evaluated(tmp_path: Path):
    """git evaluates byte-valued patterns; strict UTF-8 decoding raised
    UnicodeDecodeError on a file git handles fine."""
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_bytes(b"caf\xe9/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert [r.pattern for r in unmanaged_rules(repo)] == ["caf\udce9/"]
    target = "caf\udce9/x"
    assert target in matching_unmanaged_rules(repo, [target])


def test_rule_parser_matches_git_line_and_whitespace_semantics(tmp_path: Path):
    """`splitlines()` and `rstrip()` both invent a different rule stream.

    Git splits on LF (with CRLF handling), treats U+2028 as pattern text, strips
    only an unescaped trailing ASCII space, and preserves escaped ASCII space
    and U+00A0. The scratch repository must make the same decisions.
    """
    repo = _repo(tmp_path)
    body = "archive \narchive\\ \narchive\u00a0/\nfoo\u2028bar/\r\nmid\rname/\nterminal\r"
    (repo / ".gitignore").write_bytes(body.encode("utf-8"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)

    assert [(r.line, r.pattern) for r in unmanaged_rules(repo)] == [
        (1, "archive"),
        (2, "archive\\ "),
        (3, "archive\u00a0/"),
        (4, "foo\u2028bar/"),
        (5, "mid\rname/"),
        (6, "terminal"),
    ]
    subjects = [
        "archive/x",
        "archive /x",
        "archive\u00a0/x",
        "foo\u2028bar/x",
        "mid\rname/x",
        "terminal/x",
    ]
    for subject in subjects:
        rc = subprocess.run(["git", "-C", str(repo), "check-ignore", "--no-index", "-q", subject]).returncode
        assert rc == 0, f"real-repository precondition: git must match {subject!r}"
    assert set(matching_unmanaged_rules(repo, subjects)) == set(subjects)


def test_matching_rules_inherit_core_ignorecase(tmp_path: Path):
    """On a case-insensitive checkout git sets core.ignoreCase=true and
    `*.PARQUET` then matches `x.parquet`. A fresh scratch repo does not inherit
    it, so that conflict was silently missed."""
    repo = _repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "config", "core.ignoreCase", "true"], check=True)
    _write(repo, ".gitignore", "*.PARQUET\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "d/x.parquet" in matching_unmanaged_rules(repo, ["d/x.parquet"])


def test_matching_rules_are_case_sensitive_without_it(tmp_path: Path):
    """The other half: the scratch repo must not invent case-insensitivity."""
    repo = _repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "config", "core.ignoreCase", "false"], check=True)
    _write(repo, ".gitignore", "*.PARQUET\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert matching_unmanaged_rules(repo, ["d/x.parquet"]) == {}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", "true"),
        ("false", "false"),
        ("", "false"),
    ],
)
def test_ignore_case_accepts_git_boolean_values(
    tmp_path: Path,
    value: str,
    expected: str,
):
    from science_tool.boundary.gitio import _ignore_case

    repo = _repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.ignoreCase", value],
        check=True,
    )
    assert _ignore_case(repo) == expected


def test_ignore_case_accepts_bare_true_and_unset(tmp_path: Path):
    from science_tool.boundary.gitio import _ignore_case

    repo = _repo(tmp_path)
    assert _ignore_case(repo) is None

    config = repo / ".git" / "config"
    config.write_text(config.read_text() + "[core]\n\tignoreCase\n")
    assert _ignore_case(repo) == "true"


def test_matching_rules_ignore_git_init_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo = _repo(tmp_path)
    _write(repo, "inc/.gitignore", "*.parquet\n")
    subprocess.run(["git", "-C", str(repo), "add", "inc/.gitignore"], check=True)

    template = tmp_path / "template"
    _write(template, "info/exclude", "inc/\n")
    monkeypatch.setenv("GIT_TEMPLATE_DIR", str(template))

    hits = matching_unmanaged_rules(repo, ["inc/x.parquet"])
    assert [(r.source, r.pattern) for r in hits["inc/x.parquet"]] == [("inc/.gitignore", "*.parquet")]


def test_matching_rules_reject_unexpected_scratch_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.boundary import gitio
    from science_tool.boundary.gitio import BoundaryGitError

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "*.parquet\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    real_git = gitio._git

    def fake_git(
        project_root: Path,
        *args: str,
        stdin: bytes | None = None,
        ok: tuple[int, ...] = (0,),
    ) -> bytes:
        if project_root != repo and args[:2] == ("check-ignore", "--no-index"):
            return b".git/info/exclude\0" + b"1\0" + b"*.parquet\0" + b"x.parquet\0"
        return real_git(project_root, *args, stdin=stdin, ok=ok)

    monkeypatch.setattr(gitio, "_git", fake_git)
    with pytest.raises(BoundaryGitError, match="unexpected ignore source"):
        matching_unmanaged_rules(repo, ["x.parquet"])


@pytest.mark.parametrize(
    "payload",
    [
        b"path-without-terminator",
        b"first\0\0second\0",
    ],
)
def test_split_z_rejects_malformed_framing(payload: bytes):
    from science_tool.boundary.gitio import BoundaryGitError, _split_z

    with pytest.raises(BoundaryGitError, match="malformed NUL-delimited"):
        _split_z(payload)


def test_tracked_ignored_rejects_incomplete_verbose_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.boundary import gitio
    from science_tool.boundary.gitio import BoundaryGitError

    calls = 0

    def fake_git(
        project_root: Path,
        *args: str,
        stdin: bytes | None = None,
        ok: tuple[int, ...] = (0,),
    ) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            return b"a.parquet\0"
        return b".gitignore\0" + b"1\0" + b"*.parquet\0"

    monkeypatch.setattr(gitio, "_git", fake_git)
    with pytest.raises(BoundaryGitError, match="expected four fields"):
        gitio.tracked_ignored(tmp_path)


@pytest.mark.parametrize(
    "payload",
    [
        b"a.parquet",
        b"a.parquet\0\0",
    ],
)
def test_tracked_ignored_rejects_malformed_ls_files_stream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
):
    from science_tool.boundary import gitio
    from science_tool.boundary.gitio import BoundaryGitError

    calls = 0

    def fake_git(
        project_root: Path,
        *args: str,
        stdin: bytes | None = None,
        ok: tuple[int, ...] = (0,),
    ) -> bytes:
        nonlocal calls
        calls += 1
        if calls > 1:
            pytest.fail("malformed ls-files output was forwarded to check-ignore")
        return payload

    monkeypatch.setattr(gitio, "_git", fake_git)
    with pytest.raises(BoundaryGitError, match="malformed NUL-delimited"):
        gitio.tracked_ignored(tmp_path)


def test_tracked_ignored_rejects_invalid_verbose_line_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.boundary import gitio
    from science_tool.boundary.gitio import BoundaryGitError

    calls = 0

    def fake_git(
        project_root: Path,
        *args: str,
        stdin: bytes | None = None,
        ok: tuple[int, ...] = (0,),
    ) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            return b"a.parquet\0"
        return b".gitignore\0" + b"not-a-line\0" + b"*.parquet\0" + b"a.parquet\0"

    monkeypatch.setattr(gitio, "_git", fake_git)
    with pytest.raises(BoundaryGitError, match="invalid line number"):
        gitio.tracked_ignored(tmp_path)


def test_matching_rules_reject_incomplete_verbose_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.boundary import gitio
    from science_tool.boundary.gitio import BoundaryGitError

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "*.parquet\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    real_git = gitio._git

    def fake_git(
        project_root: Path,
        *args: str,
        stdin: bytes | None = None,
        ok: tuple[int, ...] = (0,),
    ) -> bytes:
        if project_root != repo and args[:2] == ("check-ignore", "--no-index"):
            return b".gitignore\0" + b"1\0" + b"*.parquet\0"
        return real_git(project_root, *args, stdin=stdin, ok=ok)

    monkeypatch.setattr(gitio, "_git", fake_git)
    with pytest.raises(BoundaryGitError, match="expected four fields"):
        matching_unmanaged_rules(repo, ["x.parquet"])


def test_ignore_case_query_uses_nul_framing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.boundary import gitio

    seen: tuple[str, ...] = ()

    def fake_git(
        project_root: Path,
        *args: str,
        stdin: bytes | None = None,
        ok: tuple[int, ...] = (0,),
    ) -> bytes:
        nonlocal seen
        seen = args
        return b"true\0"

    monkeypatch.setattr(gitio, "_git", fake_git)
    assert gitio._ignore_case(tmp_path) == "true"
    assert seen == ("config", "-z", "--type=bool", "--get", "core.ignoreCase")


@pytest.mark.parametrize(
    "payload",
    [
        b"true",
        b"true\0false\0",
        b"\0",
        b"maybe\0",
    ],
)
def test_ignore_case_rejects_malformed_scalar_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
):
    from science_tool.boundary import gitio
    from science_tool.boundary.gitio import BoundaryGitError

    def fake_git(
        project_root: Path,
        *args: str,
        stdin: bytes | None = None,
        ok: tuple[int, ...] = (0,),
    ) -> bytes:
        return payload

    monkeypatch.setattr(gitio, "_git", fake_git)
    with pytest.raises(BoundaryGitError):
        gitio._ignore_case(tmp_path)


def test_leading_whitespace_in_a_rule_is_preserved(tmp_path: Path):
    """git treats leading whitespace as significant -- ` .venv/` does NOT ignore
    `.venv/`. Normalising it made the rule compare equal to the default allow
    entry `.venv/`, widening an exact-text allowance to different behaviour."""
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", " .venv/\ntrail/ \n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    patterns = [r.pattern for r in unmanaged_rules(repo)]
    assert patterns == [" .venv/", "trail/"], "leading kept, trailing stripped -- as git does"


def test_unmanaged_rules_from_nested_file_carry_their_source(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "build/\n")
    _write(repo, "inc/shiny/.gitignore", "build/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "inc/shiny/.gitignore"], check=True)
    rules = unmanaged_rules(repo)
    sources = sorted((r.source, r.pattern) for r in rules)
    assert sources == [(".gitignore", "build/"), ("inc/shiny/.gitignore", "build/")]
