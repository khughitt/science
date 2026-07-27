from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from science_tool.boundary.config import BoundaryConfig
from science_tool.boundary.generate import (
    MANAGED_BEGIN,
    MANAGED_END,
    render_managed_block,
    splice_managed_block,
)
from science_tool.validate.checks.boundary import check_boundary
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _repo(tmp_path: Path, boundary: dict | None = None) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    payload: dict = {"name": "Demo", "id": "demo"}
    if boundary is not None:
        payload["boundary"] = boundary
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
    return tmp_path


def _results(root: Path) -> list:
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_boundary(ctx))


def _rules(root: Path) -> list[str]:
    return [r.rule for r in _results(root)]


def _hash_blob(repo: Path, body: bytes) -> str:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
            input=body,
            check=True,
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )


def _install_invalid_root_index_entry(repo: Path, kind: str, correct: str) -> None:
    if kind == "intent-to-add":
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
        return

    if kind == "symlink":
        oid = _hash_blob(repo, b"ignore-target")
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
        return

    if kind == "gitlink":
        subprocess.run(
            ["git", "-C", str(repo), "add", "science.yaml"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-qm", "fixture head"],
            check=True,
        )
        commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "update-index",
                "--add",
                "--cacheinfo",
                "160000",
                commit,
                ".gitignore",
            ],
            check=True,
        )
        return

    if kind == "unmerged":
        base = _hash_blob(repo, correct.encode())
        ours = _hash_blob(repo, b"ours\n")
        theirs = _hash_blob(repo, b"theirs\n")
        records = f"100644 {base} 1\t.gitignore\n100644 {ours} 2\t.gitignore\n100644 {theirs} 3\t.gitignore\n"
        subprocess.run(
            ["git", "-C", str(repo), "update-index", "--index-info"],
            input=records,
            check=True,
            text=True,
        )
        return

    if kind == "stale-blob":
        (repo / ".gitignore").write_text("stale indexed bytes\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", ".gitignore"],
            check=True,
        )
        (repo / ".gitignore").write_text(correct, encoding="utf-8")
        return

    raise AssertionError(f"unknown invalid root index kind {kind!r}")


def test_tracked_ignored_fires_without_any_declaration(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data/big.csv").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "data/big.csv"], check=True)
    (repo / ".gitignore").write_text("/data/\n")
    assert "boundary.tracked-ignored" in _rules(repo)


def test_clean_undeclared_project_is_silent(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("/papers/pdfs/\n")
    # Implicit-versioned semantics begin at enrollment: no declaration, no
    # ignored-undeclared finding.
    assert _rules(repo) == []


def test_nested_science_project_in_enclosing_worktree_is_checked(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    nested = tmp_path / "projects/demo"
    (nested / "data").mkdir(parents=True)
    (nested / "science.yaml").write_text("name: Demo\nid: demo\n", encoding="utf-8")
    (nested / "data/big.csv").write_text("x", encoding="utf-8")
    (nested / ".gitignore").write_text("/data/\n", encoding="utf-8")
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "add",
            "-f",
            "projects/demo/science.yaml",
            "projects/demo/.gitignore",
            "projects/demo/data/big.csv",
        ],
        check=True,
    )

    assert "boundary.tracked-ignored" in _rules(nested)


def test_dangling_git_marker_fails_closed(tmp_path: Path):
    from science_tool.boundary.gitio import BoundaryGitError

    (tmp_path / "science.yaml").write_text("name: Demo\nid: demo\n", encoding="utf-8")
    (tmp_path / ".git").symlink_to(tmp_path / "missing-gitdir", target_is_directory=True)

    with pytest.raises(BoundaryGitError, match="repository discovery"):
        _results(tmp_path)


def test_corrupt_gitfile_marker_fails_closed(tmp_path: Path):
    from science_tool.boundary.gitio import BoundaryGitError

    (tmp_path / "science.yaml").write_text("name: Demo\nid: demo\n", encoding="utf-8")
    (tmp_path / ".git").write_text("not a gitdir pointer\n", encoding="utf-8")

    with pytest.raises(BoundaryGitError, match="repository discovery"):
        _results(tmp_path)


def test_genuine_nonrepository_is_skipped(tmp_path: Path):
    (tmp_path / "science.yaml").write_text("name: Demo\nid: demo\n", encoding="utf-8")

    assert _results(tmp_path) == []


def test_unanchored_pattern_warns(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("archive\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unanchored-pattern" in _rules(repo)


def test_freshly_scaffolded_project_is_quiet(tmp_path: Path):
    """THE adoption contract. Six of the scaffold's own rules are bare directory
    names (`.venv/`, `__pycache__/`, `.mypy_cache/`, `.ipynb_checkpoints/`,
    `*.egg-info/`, `.worktrees/`), so a fresh project warned six times and then
    printed 'clean'. Anchoring them would be WRONG -- a nested
    `inc/shiny/.venv/` must still be ignored -- so the allowlist is what
    silences them."""
    from science_tool.boundary.config import DEFAULT_UNMANAGED_ALLOW

    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("\n".join(DEFAULT_UNMANAGED_ALLOW) + "\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert _rules(repo) == []


def test_allowlist_silences_an_unanchored_pattern(tmp_path: Path):
    repo = _repo(tmp_path, {"unmanaged_allow": ["vendor/"]})
    (repo / ".gitignore").write_text("vendor/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unanchored-pattern" not in _rules(repo)


def test_mm30_bare_archive_still_fires_despite_the_allowlist(tmp_path: Path):
    """The motivating case must survive the exemption: `archive` is not in the
    default allowlist."""
    from science_tool.boundary.config import DEFAULT_UNMANAGED_ALLOW

    assert "archive" not in DEFAULT_UNMANAGED_ALLOW
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("\n".join(DEFAULT_UNMANAGED_ALLOW) + "\narchive\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    findings = [r for r in _results(repo) if r.rule == "boundary.unanchored-pattern"]
    assert [f.line for f in findings] == [len(DEFAULT_UNMANAGED_ALLOW) + 1]


def test_negation_does_not_warn_as_unanchored(tmp_path: Path):
    """`!archive` was reported with a message about swallowing tracked source --
    the opposite of what a negation does, and unsilenceable because
    unmanaged_allow rejects `!` patterns."""
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("!archive\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unanchored-pattern" not in _rules(repo)


def test_negation_outside_a_declared_root_is_not_ignored_undeclared(tmp_path: Path):
    """A negation ignores nothing, so the predicate is false of it -- and it
    could never be silenced, since unmanaged_allow rejects `!` patterns."""
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("!/papers/keep.pdf\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.ignored-undeclared" not in _rules(repo)


def test_generated_drift_fires_when_block_is_stale(tmp_path: Path):
    repo = _repo(tmp_path, {"roots": [{"path": "data/raw", "class": "payload"}]})
    (repo / ".gitignore").write_text(splice_managed_block("", "/wrong/\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.generated-drift" in _rules(repo)


def test_no_drift_when_block_matches(tmp_path: Path):
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.generated-drift" not in _rules(repo)


def test_correct_root_gitignore_must_be_a_tracked_governed_source(tmp_path: Path):
    decl = {
        "roots": [{"path": "data/raw", "class": "payload"}],
        "unmanaged_allow": [],
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(
        splice_managed_block("", render_managed_block(cfg)),
        encoding="utf-8",
    )
    excludes = repo / ".git/root-excludes"
    excludes.write_text("/.gitignore\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.excludesFile", str(excludes)],
        check=True,
    )
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/secret.bin").write_text("secret", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    indexed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    assert b".gitignore" not in indexed
    assert b"data/raw/secret.bin" not in indexed

    findings = [result for result in _results(repo) if result.rule == "boundary.generated-drift"]

    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert "tracked, present, regular" in findings[0].message


@pytest.mark.parametrize(
    "index_kind",
    ("intent-to-add", "symlink", "gitlink", "unmerged", "stale-blob"),
)
def test_generated_drift_requires_durable_root_index_blob(
    tmp_path: Path,
    index_kind: str,
):
    decl = {
        "roots": [{"path": "data/raw", "class": "payload"}],
        "unmanaged_allow": [],
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    correct = splice_managed_block("", render_managed_block(cfg))
    (repo / ".gitignore").write_text(correct, encoding="utf-8")
    _install_invalid_root_index_entry(repo, index_kind, correct)

    findings = [result for result in _results(repo) if result.rule == "boundary.generated-drift"]

    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert "stage-0 regular blob" in findings[0].message
    assert (repo / ".gitignore").is_file()
    assert not (repo / ".gitignore").is_symlink()
    assert (repo / ".gitignore").read_text(encoding="utf-8") == correct


def test_generated_drift_rejects_symlinked_root_gitignore_without_following(tmp_path: Path):
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path / "repo", decl)
    expected = splice_managed_block("", render_managed_block(BoundaryConfig.model_validate(decl)))
    outside = tmp_path / "outside-ignore"
    outside.write_text(expected, encoding="utf-8")
    (repo / ".gitignore").symlink_to(outside)
    subprocess.run(["git", "-C", str(repo), "add", "-f", ".gitignore"], check=True)

    findings = [result for result in _results(repo) if result.rule == "boundary.generated-drift"]

    assert len(findings) == 1
    assert "symlink" in findings[0].message
    assert outside.read_text(encoding="utf-8") == expected


def test_generated_drift_rejects_nonregular_root_gitignore(tmp_path: Path):
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    (repo / ".gitignore").mkdir()

    findings = [result for result in _results(repo) if result.rule == "boundary.generated-drift"]

    assert len(findings) == 1
    assert "not a regular file" in findings[0].message


def test_payload_index_invariant_catches_untracked_nested_negations(tmp_path: Path):
    decl = {
        "roots": [{"path": "data/raw", "class": "payload"}],
        "unmanaged_allow": [],
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(
        splice_managed_block("", render_managed_block(cfg)),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    (repo / ".git/info/exclude").write_text("/data/.gitignore\n", encoding="utf-8")
    (repo / "data").mkdir()
    (repo / "data/.gitignore").write_text("!raw/\n!raw/**\n", encoding="utf-8")
    (repo / "data/raw").mkdir()
    (repo / "data/raw/secret.bin").write_text("secret", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    indexed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    assert b"data/raw/secret.bin" in indexed
    assert b"data/.gitignore" not in indexed

    findings = [result for result in _results(repo) if result.rule == "boundary.index-violation"]

    assert [(finding.path.as_posix(), finding.severity) for finding in findings] == [
        ("data/raw/secret.bin", Severity.ERROR)
    ]


def test_payload_index_invariant_catches_indexed_root_symlink(tmp_path: Path):
    decl = {
        "roots": [{"path": "data/raw", "class": "payload"}],
        "unmanaged_allow": [],
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(
        splice_managed_block("", render_managed_block(cfg)),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (repo / "data").mkdir()
    (repo / "data/raw").symlink_to(outside, target_is_directory=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    indexed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    assert b"data/raw" in indexed

    findings = [result for result in _results(repo) if result.rule == "boundary.index-violation"]

    assert [(finding.path.as_posix(), finding.severity) for finding in findings] == [("data/raw", Severity.ERROR)]


def test_manifest_index_invariant_catches_only_nonmatching_staged_path(tmp_path: Path):
    decl = {
        "roots": [
            {
                "path": "data/external",
                "class": "manifest",
                "tracked": ["datapackage.json"],
            }
        ],
        "unmanaged_allow": [],
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(
        splice_managed_block("", render_managed_block(cfg)),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    (repo / ".git/info/exclude").write_text("/data/.gitignore\n", encoding="utf-8")
    (repo / "data").mkdir()
    (repo / "data/.gitignore").write_text(
        "!external/\n!external/**\n",
        encoding="utf-8",
    )
    dataset = repo / "data/external/ds"
    dataset.mkdir(parents=True)
    (dataset / "datapackage.json").write_text("{}\n", encoding="utf-8")
    (dataset / "part.parquet").write_text("payload", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    indexed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    assert b"data/external/ds/datapackage.json" in indexed
    assert b"data/external/ds/part.parquet" in indexed
    assert b"data/.gitignore" not in indexed

    findings = [result for result in _results(repo) if result.rule == "boundary.index-violation"]

    assert [(finding.path.as_posix(), finding.severity) for finding in findings] == [
        ("data/external/ds/part.parquet", Severity.ERROR)
    ]


def test_index_invariant_uses_effective_git_casefolding(tmp_path: Path):
    decl = {
        "roots": [
            {"path": "Data/Raw", "class": "payload"},
            {
                "path": "Data/External",
                "class": "manifest",
                "tracked": ["DataPackage.json"],
            },
        ],
        "unmanaged_allow": [],
    }
    repo = _repo(tmp_path, decl)
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.ignoreCase", "true"],
        check=True,
    )
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(
        splice_managed_block("", render_managed_block(cfg)),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    (repo / ".git/info/exclude").write_text("/data/.gitignore\n", encoding="utf-8")
    (repo / "data").mkdir()
    (repo / "data/.gitignore").write_text(
        "!raw/\n!raw/**\n!external/\n!external/**\n",
        encoding="utf-8",
    )
    (repo / "data/raw").mkdir()
    (repo / "data/raw/secret.bin").write_text("secret", encoding="utf-8")
    dataset = repo / "data/external/ds"
    dataset.mkdir(parents=True)
    (dataset / "datapackage.json").write_text("{}\n", encoding="utf-8")
    (dataset / "part.parquet").write_text("payload", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    indexed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    assert b"data/raw/secret.bin" in indexed
    assert b"data/external/ds/datapackage.json" in indexed
    assert b"data/external/ds/part.parquet" in indexed

    findings = [result for result in _results(repo) if result.rule == "boundary.index-violation"]

    assert [(finding.path.as_posix(), finding.severity) for finding in findings] == [
        ("data/external/ds/part.parquet", Severity.ERROR),
        ("data/raw/secret.bin", Severity.ERROR),
    ]


def test_index_invariant_does_not_expand_unicode_in_tracked_globs(tmp_path: Path):
    decl = {
        "roots": [
            {
                "path": "Data/External",
                "class": "manifest",
                "tracked": ["Straße.json"],
            }
        ],
        "unmanaged_allow": [],
    }
    repo = _repo(tmp_path, decl)
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.ignoreCase", "true"],
        check=True,
    )
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(
        splice_managed_block("", render_managed_block(cfg)),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    dataset = repo / "data/external/ds"
    dataset.mkdir(parents=True)
    target = dataset / "STRASSE.JSON"
    target.write_text("{}\n", encoding="utf-8")
    ignored = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "check-ignore",
            "--no-index",
            "-q",
            "data/external/ds/STRASSE.JSON",
        ],
        check=False,
    )
    assert ignored.returncode == 0, "Git must not equate Straße.json with STRASSE.JSON"

    (repo / ".git/info/exclude").write_text("/data/.gitignore\n", encoding="utf-8")
    (repo / "data/.gitignore").write_text(
        "!external/\n!external/**\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    indexed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    assert b"data/external/ds/STRASSE.JSON" in indexed
    assert b"data/.gitignore" not in indexed

    findings = [result for result in _results(repo) if result.rule == "boundary.index-violation"]

    assert [(finding.path.as_posix(), finding.severity) for finding in findings] == [
        ("data/external/ds/STRASSE.JSON", Severity.ERROR)
    ]


def test_index_invariant_does_not_expand_unicode_in_root_prefixes(tmp_path: Path):
    decl = {
        "roots": [{"path": "Data/Straße", "class": "payload"}],
        "unmanaged_allow": [],
    }
    repo = _repo(tmp_path, decl)
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.ignoreCase", "true"],
        check=True,
    )
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(
        splice_managed_block("", render_managed_block(cfg)),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    outside = repo / "data/STRASSE/outside.bin"
    outside.parent.mkdir(parents=True)
    outside.write_text("outside", encoding="utf-8")
    ignored = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "check-ignore",
            "--no-index",
            "-q",
            "data/STRASSE/outside.bin",
        ],
        check=False,
    )
    assert ignored.returncode == 1, "Git must not equate Straße with STRASSE"
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)

    findings = [result for result in _results(repo) if result.rule == "boundary.index-violation"]

    assert findings == []


def test_declaration_conflict_catches_a_bare_wildcard(tmp_path: Path):
    """`*.parquet` names no root but governs paths inside one. Text prefix
    comparison misses this entirely; asking git does not."""
    decl = {
        "roots": [
            {
                "path": "data/external",
                "class": "manifest",
                "tracked": ["datapackage.json"],
            }
        ]
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("*.parquet\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_nested_marker_region_is_hand_owned_and_conflicts_with_declaration(tmp_path: Path):
    """Only the root marker block is managed; nested files are wholly hand-owned."""
    decl = {
        "roots": [
            {
                "path": "inc/data",
                "class": "manifest",
                "tracked": ["datapackage.json"],
            }
        ]
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    (repo / "inc/data/ds").mkdir(parents=True)
    (repo / "inc/data/ds/part.parquet").write_text("x", encoding="utf-8")
    (repo / "inc/.gitignore").write_text(
        f"{MANAGED_BEGIN}\n*.parquet\n{MANAGED_END}\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(repo), "add", "-f", ".gitignore", "inc/.gitignore"],
        check=True,
    )

    findings = [result for result in _results(repo) if result.rule == "boundary.declaration-conflict"]

    assert [(finding.path.as_posix(), finding.line) for finding in findings] == [("inc/.gitignore", 2)]


def test_exact_name_rule_conflicts_with_directory_symlink_leaf(tmp_path: Path):
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/link").symlink_to(outside, target_is_directory=True)
    (repo / ".gitignore").write_text(
        splice_managed_block("/data/raw/link\n", render_managed_block(cfg)),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "-f", ".gitignore"], check=True)

    findings = [result for result in _results(repo) if result.rule == "boundary.declaration-conflict"]

    assert [(finding.path.as_posix(), finding.line) for finding in findings] == [(".gitignore", 1)]


def test_declaration_conflict_catches_a_subdirectory_scoped_rule(tmp_path: Path):
    """No generic probe visits `foo/`; the real-tree sample is what finds it."""
    decl = {
        "roots": [
            {
                "path": "data/external",
                "class": "manifest",
                "tracked": ["datapackage.json"],
            }
        ]
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / "data/external/foo").mkdir(parents=True)
    (repo / "data/external/foo/part.parquet").write_text("x")
    (repo / ".gitignore").write_text(splice_managed_block("data/external/foo/*.parquet\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_nested_gitignore_scope_is_not_a_false_conflict(tmp_path: Path):
    """`data/raw` inside inc/.gitignore scopes to inc/, NOT the declared root."""
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    (repo / "inc").mkdir()
    (repo / "inc/.gitignore").write_text("data/raw\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "inc/.gitignore"], check=True)
    assert "boundary.declaration-conflict" not in _rules(repo)


def test_allowlist_cannot_excuse_a_conflict(tmp_path: Path):
    """The allowlist excuses undeclared noise; it may NEVER excuse a rule that
    targets a declared root, or it reopens the adjudication this check closes."""
    decl = {
        "roots": [
            {
                "path": "data/external",
                "class": "manifest",
                "tracked": ["datapackage.json"],
            }
        ],
        "unmanaged_allow": ["*.parquet"],
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("*.parquet\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_declaration_conflict_catches_a_hand_written_pin(tmp_path: Path):
    """A `!` rule pinning one file out of a declared payload root IS the per-case
    exception the declaration replaces. It ignores nothing, so no ignore-rule
    search finds it -- only reporting matches rather than winners does."""
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/keep.csv").write_text("x")
    (repo / ".gitignore").write_text(splice_managed_block("!/data/raw/keep.csv\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_declaration_conflict_sees_a_rule_shadowed_by_a_hand_written_negation(
    tmp_path: Path,
):
    """Among unmanaged rules the LAST match still wins, and git reports the
    negation here. Peeling is what surfaces the ignore rule underneath."""
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/x.csv").write_text("x")
    (repo / ".gitignore").write_text(splice_managed_block("/data/raw/**\n!/data/raw/**\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    findings = [r for r in _results(repo) if r.rule == "boundary.declaration-conflict"]
    assert sorted(f.line for f in findings) == [
        1,
        2,
    ], "both rules must be reported, not just the winner"


def test_duplicate_of_a_generated_line_is_a_conflict(tmp_path: Path):
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("/data/raw/\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_invalid_declaration_is_an_error_not_silence(tmp_path: Path):
    repo = _repo(
        tmp_path,
        {
            "roots": [
                {"path": "data", "class": "payload"},
                {
                    "path": "data/external",
                    "class": "manifest",
                    "tracked": ["datapackage.json"],
                },
            ]
        },
    )
    rules = _rules(repo)
    assert "boundary.invalid-declaration" in rules


def test_declaration_is_loaded_once_per_validation(tmp_path: Path, monkeypatch):
    """Allowlist and roots must come from one snapshot. Loading twice can mix
    two declarations or let an unguarded second parse escape."""
    import science_tool.validate.checks.boundary as boundary_mod

    repo = _repo(tmp_path, {"roots": [{"path": "data/raw", "class": "payload"}]})
    real_load = boundary_mod.load_project_config
    calls = 0

    def counted_load(root):
        nonlocal calls
        calls += 1
        return real_load(root)

    monkeypatch.setattr(boundary_mod, "load_project_config", counted_load)
    _results(repo)
    assert calls == 1


def test_universal_checks_survive_an_invalid_declaration(tmp_path: Path):
    """Both universal checks run even when declaration loading fails.
    `unanchored-pattern` uses the default allowlist in that case; a broken
    declaration must not turn either universal check off."""
    repo = _repo(
        tmp_path,
        {
            "roots": [
                {"path": "data", "class": "payload"},
                {
                    "path": "data/external",
                    "class": "manifest",
                    "tracked": ["datapackage.json"],
                },
            ]
        },
    )
    (repo / ".gitignore").write_text("archive\n")
    (repo / "data").mkdir()
    (repo / "data/big.csv").write_text("x")
    subprocess.run(
        ["git", "-C", str(repo), "add", "-f", ".gitignore", "data/big.csv"],
        check=True,
    )
    (repo / ".gitignore").write_text("archive\n/data/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    rules = _rules(repo)
    assert "boundary.invalid-declaration" in rules
    assert "boundary.unanchored-pattern" in rules
    assert "boundary.tracked-ignored" in rules


def test_explicit_null_boundary_is_invalid_while_universal_checks_run(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "science.yaml").write_text(
        "name: Demo\nid: demo\nboundary:\n",
        encoding="utf-8",
    )
    (repo / ".gitignore").write_text("archive\n", encoding="utf-8")
    (repo / "data").mkdir()
    (repo / "data/big.csv").write_text("x", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", "-f", ".gitignore", "data/big.csv"],
        check=True,
    )
    (repo / ".gitignore").write_text("archive\n/data/\n", encoding="utf-8")

    rules = _rules(repo)

    assert "boundary.invalid-declaration" in rules
    assert "boundary.unanchored-pattern" in rules
    assert "boundary.tracked-ignored" in rules


def test_ignored_undeclared_warns_and_allowlist_silences_it(tmp_path: Path):
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("/papers/pdfs/\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.ignored-undeclared" in _rules(repo)

    decl_allowed = dict(decl, unmanaged_allow=["/papers/pdfs/"])
    repo2 = _repo(tmp_path / "two", decl_allowed)
    (repo2 / ".gitignore").write_text(splice_managed_block("/papers/pdfs/\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo2), "add", ".gitignore"], check=True)
    assert "boundary.ignored-undeclared" not in _rules(repo2)


def test_allowlist_is_source_scoped(tmp_path: Path):
    """Same text in root and nested file are DIFFERENT rules."""
    decl = {
        "roots": [{"path": "data/raw", "class": "payload"}],
        "unmanaged_allow": ["build/"],
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("build/\n", render_managed_block(cfg)))
    (repo / "inc").mkdir()
    (repo / "inc/.gitignore").write_text("build/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "inc/.gitignore"], check=True)
    ctx = ValidateContext.from_project_root(repo, strict=False, verbose=False)
    findings = [r for r in check_boundary(ctx) if r.rule == "boundary.ignored-undeclared"]
    assert len(findings) == 1
    assert "inc/.gitignore" in str(findings[0].path)


def test_allowlist_rejects_previously_committed_intent_to_add_source(tmp_path: Path):
    decl = {
        "roots": [{"path": "data/raw", "class": "payload"}],
        "unmanaged_allow": [
            {
                "source": "inc/.gitignore",
                "pattern": "vendor/",
            }
        ],
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(
        splice_managed_block("", render_managed_block(cfg)),
        encoding="utf-8",
    )
    (repo / "inc").mkdir()
    (repo / "inc/.gitignore").write_text("vendor/\n", encoding="utf-8")
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "add",
            ".gitignore",
            "inc/.gitignore",
            "science.yaml",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "fixture"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "rm", "--cached", "inc/.gitignore"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "add", "-N", "inc/.gitignore"],
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
    assert b"inc/.gitignore" not in names

    findings = [result for result in _results(repo) if result.rule == "boundary.invalid-declaration"]

    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert "inc/.gitignore" in findings[0].message


def test_unreachable_tracked_fires_on_shadowed_descriptor(tmp_path: Path):
    decl = {
        "roots": [
            {
                "path": "data/external",
                "class": "manifest",
                "tracked": ["datapackage.json"],
            }
        ]
    }
    repo = _repo(tmp_path, decl)
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.json").write_text("{}")
    # Bare exclude instead of the descend-preserving form: descriptor unreachable.
    (repo / ".gitignore").write_text(splice_managed_block("", "/data/external/\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unreachable-tracked" in _rules(repo)


def test_unreachable_tracked_quiet_on_correct_generation(tmp_path: Path):
    decl = {
        "roots": [
            {
                "path": "data/external",
                "class": "manifest",
                "tracked": ["datapackage.json"],
            }
        ]
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.json").write_text("{}")
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unreachable-tracked" not in _rules(repo)


def test_unreachable_tracked_checks_directory_symlink_leaf(tmp_path: Path):
    decl = {
        "roots": [
            {
                "path": "data/external",
                "class": "manifest",
                "tracked": ["datapackage.json"],
            }
        ]
    }
    repo = _repo(tmp_path, decl)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "data/external").mkdir(parents=True)
    (repo / "data/external/datapackage.json").symlink_to(
        outside,
        target_is_directory=True,
    )
    (repo / ".gitignore").write_text(
        splice_managed_block("", "/data/external/\n"),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)

    assert "boundary.unreachable-tracked" in _rules(repo)


def test_unreachable_tracked_catches_glob_negation_case(tmp_path: Path):
    """`!build/**/README.md` under `/build/` -- no parent-directory analysis
    could evaluate this; the oracle can."""
    decl = {"roots": [{"path": "build", "class": "manifest", "tracked": ["README.md"]}]}
    repo = _repo(tmp_path, decl)
    (repo / "build/sub").mkdir(parents=True)
    (repo / "build/sub/README.md").write_text("x")
    (repo / ".gitignore").write_text(splice_managed_block("", "/build/\n!build/**/README.md\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unreachable-tracked" in _rules(repo)
