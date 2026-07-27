"""End-to-end acceptance on a sanitized MM30-shaped tree.

Shape derived from MM30 as of 2026-07-26: an external-dataset root whose
descriptors are tracked beside ignored bulk parquet and an ignored raw/ subtree,
a flat gitignored PDF store, and tracked source that an unanchored pattern had
been hiding. No MM30 content, only its layout.
"""

from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from science_tool.boundary.cli import boundary_group
from science_tool.validate.checks.boundary import check_boundary
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

DECL = {
    "roots": [
        {
            "path": "data/external",
            "class": "manifest",
            "tracked": ["datapackage.json", "*.qa_verdict.json"],
        },
        {"path": "data/raw", "class": "payload"},
        {"path": "pdfs", "class": "payload"},
    ]
}

_CONTROLLED_GIT_ENV = {
    "GIT_ATTR_NOSYSTEM": "1",
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_KEY_0": "core.attributesFile",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_VALUE_0": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}
_ENFORCEMENT_CONTRACT = {
    ("boundary.tracked-ignored", Severity.ERROR),
    ("boundary.generated-drift", Severity.ERROR),
    ("boundary.declaration-conflict", Severity.ERROR),
    ("boundary.unreachable-tracked", Severity.ERROR),
    ("boundary.ignored-undeclared", Severity.WARN),
    ("boundary.unanchored-pattern", Severity.WARN),
}


@dataclass(frozen=True)
class _GitState:
    status: bytes
    index: bytes
    worktree_diff: bytes
    staged_diff: bytes


@dataclass(frozen=True)
class _TreeEntry:
    path: str
    file_type: int
    mode: int
    content: bytes | None
    link_target: str | None


def _tree_snapshot(root: Path) -> tuple[_TreeEntry, ...]:
    entries: list[_TreeEntry] = []

    def visit(directory: Path, prefix: str) -> None:
        with os.scandir(directory) as scanned:
            children = sorted(scanned, key=lambda entry: os.fsencode(entry.name))
        for child in children:
            if not prefix and child.name == ".git":
                continue
            relative = child.name if not prefix else f"{prefix}/{child.name}"
            metadata = child.stat(follow_symlinks=False)
            file_type = stat.S_IFMT(metadata.st_mode)
            content = Path(child.path).read_bytes() if stat.S_ISREG(metadata.st_mode) else None
            link_target = os.readlink(child.path) if stat.S_ISLNK(metadata.st_mode) else None
            entries.append(
                _TreeEntry(
                    path=relative,
                    file_type=file_type,
                    mode=stat.S_IMODE(metadata.st_mode),
                    content=content,
                    link_target=link_target,
                )
            )
            if stat.S_ISDIR(metadata.st_mode):
                visit(Path(child.path), relative)

    visit(root, "")
    return tuple(entries)


def _git_process_env() -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(_CONTROLLED_GIT_ENV)
    return env


def _git_cli_env() -> dict[str, str | None]:
    env: dict[str, str | None] = {name: None for name in os.environ if name.startswith("GIT_")}
    env.update(_CONTROLLED_GIT_ENV)
    return env


@contextmanager
def _git_environment() -> Iterator[None]:
    with patch.dict(os.environ, _git_process_env(), clear=True):
        yield


def _git(
    root: Path,
    *args: str,
    check: bool = True,
    capture_output: bool = False,
    text: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        capture_output=capture_output,
        text=text,
        env=_git_process_env(),
    )


def _invoke(root: Path, *args: str):
    return CliRunner().invoke(
        boundary_group,
        [*args, "--project-root", str(root)],
        env=_git_cli_env(),
    )


def _git_state(root: Path) -> _GitState:
    def output(*args: str) -> bytes:
        return _git(root, *args, capture_output=True, text=False).stdout

    return _GitState(
        status=output("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        index=output("ls-files", "--stage", "-z"),
        worktree_diff=output("diff", "--binary", "--no-ext-diff"),
        staged_diff=output("diff", "--cached", "--binary", "--no-ext-diff"),
    )


def _mm30(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "init", "-q", "--template=", ".")
    _git(tmp_path, "config", "user.email", "t@e")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "MM", "id": "mm", "boundary": DECL}))

    def w(rel: str, body: str = "x") -> None:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    w("data/external/opentargets/25.03/datapackage.json", "{}")
    w("data/external/opentargets/25.03/opentargets.qa_verdict.json", "{}")
    w("data/external/opentargets/25.03/mm-associations.parquet")
    w("data/external/opentargets/25.03/raw/target/part-0.parquet")
    w("data/raw/GSE1234_series_matrix.txt", "x" * 200_000)
    w("pdfs/2024_Author_Title.pdf")
    w("tests/migration/archive/test_pilot.py", "def test_x(): pass\n")
    w("entities/hypotheses/h0001.md", "# h\n")
    w(".gitignore", ".venv/\narchive\n")
    return tmp_path


def _findings(root: Path) -> list[Result]:
    with _git_environment():
        ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
        return list(check_boundary(ctx))


def test_acceptance_sync_then_clean(tmp_path: Path):
    repo = _mm30(tmp_path)

    result = _invoke(repo, "sync")
    assert result.exit_code == 0, result.output
    _git(repo, "add", "-A")
    staged = _git(repo, "ls-files", capture_output=True).stdout.split()

    # Descriptors tracked; payload not.
    assert "data/external/opentargets/25.03/datapackage.json" in staged
    assert "data/external/opentargets/25.03/opentargets.qa_verdict.json" in staged
    assert "data/external/opentargets/25.03/mm-associations.parquet" not in staged
    assert "data/external/opentargets/25.03/raw/target/part-0.parquet" not in staged
    assert "data/raw/GSE1234_series_matrix.txt" not in staged
    assert "pdfs/2024_Author_Title.pdf" not in staged

    # The unanchored bare `archive` rule STILL hides this file: `sync` manages
    # declared roots and deliberately does not rewrite unmanaged rules. Verified
    # against real git -- an earlier draft asserted the opposite.
    assert "tests/migration/archive/test_pilot.py" not in staged

    rules = [finding.rule for finding in _findings(repo)]
    assert "boundary.tracked-ignored" not in rules  # ignored AND untracked, so no contradiction
    assert "boundary.generated-drift" not in rules
    assert "boundary.unreachable-tracked" not in rules
    assert "boundary.unanchored-pattern" in rules  # the bare `archive` is reported


def test_acceptance_anchoring_the_warned_rule_is_the_remedy(tmp_path: Path):
    """Following the WARN's advice makes the hidden source reachable again.

    This is the check earning its keep: nothing else in the toolchain reports
    that a tracked-looking test file is invisible to git, ripgrep, and ruff.
    """
    repo = _mm30(tmp_path)
    result = _invoke(repo, "sync")
    assert result.exit_code == 0, result.output
    text = (repo / ".gitignore").read_text().replace("archive\n", "/archive/\n", 1)
    (repo / ".gitignore").write_text(text)
    _git(repo, "add", "-A")
    staged = _git(repo, "ls-files", capture_output=True).stdout.split()
    assert "tests/migration/archive/test_pilot.py" in staged
    assert "boundary.unanchored-pattern" not in {finding.rule for finding in _findings(repo)}


def test_acceptance_verify_current_tree_is_transactional(tmp_path: Path):
    repo = _mm30(tmp_path)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    ignore_before_bytes = (repo / ".gitignore").read_bytes()
    ignore_before_text = (repo / ".gitignore").read_text()
    state_before = _git_state(repo)
    assert state_before.status == b""
    assert state_before.worktree_diff == b""
    assert state_before.staged_diff == b""
    tree_before = _tree_snapshot(repo)
    assert {
        "data/external/opentargets/25.03/datapackage.json",
        "data/external/opentargets/25.03/mm-associations.parquet",
        "data/raw/GSE1234_series_matrix.txt",
        "entities/hypotheses/h0001.md",
        "pdfs/2024_Author_Title.pdf",
        "tests/migration/archive/test_pilot.py",
    } <= {entry.path for entry in tree_before}
    hidden_source = repo / "tests/migration/archive/test_pilot.py"
    hidden_source_before = hidden_source.read_bytes()
    hidden_source.write_bytes(hidden_source_before + b"# snapshot seam\n")
    assert _tree_snapshot(repo) != tree_before
    hidden_source.write_bytes(hidden_source_before)
    assert _tree_snapshot(repo) == tree_before
    link_target = "tests/migration/archive/test_pilot.py"
    snapshot_link = repo / "snapshot-link"
    snapshot_link.symlink_to(link_target)
    tree_with_link = _tree_snapshot(repo)
    assert tree_with_link != tree_before
    link_entry = next(entry for entry in tree_with_link if entry.path == "snapshot-link")
    assert link_entry.file_type == stat.S_IFLNK
    assert link_entry.mode == stat.S_IMODE(snapshot_link.lstat().st_mode)
    assert link_entry.content is None
    assert link_entry.link_target == link_target
    snapshot_link.unlink()
    assert _tree_snapshot(repo) == tree_before

    result = _invoke(repo, "sync", "--verify-current-tree")
    assert result.exit_code == 1, result.output
    expected_flips = [
        "data/external/.hidden",
        "data/external/opentargets/25.03/mm-associations.parquet",
        "data/external/opentargets/25.03/raw/target/part-0.parquet",
        "data/external/p1/p2/p3/probe.bin",
        "data/external/probe.bin",
        "data/external/probe.parquet",
        "data/raw/.hidden",
        "data/raw/GSE1234_series_matrix.txt",
        "data/raw/p1/p2/p3/probe.bin",
        "data/raw/probe.bin",
        "data/raw/probe.parquet",
        "pdfs/.hidden",
        "pdfs/2024_Author_Title.pdf",
        "pdfs/p1/p2/p3/probe.bin",
        "pdfs/probe.bin",
        "pdfs/probe.parquet",
    ]
    assert result.output.splitlines() == [
        f"boundary: {len(expected_flips)} ignore decision(s) would change:",
        *(f"  {path}: ignored=False -> True" for path in expected_flips),
    ]
    assert (repo / ".gitignore").read_bytes() == ignore_before_bytes
    assert (repo / ".gitignore").read_text() == ignore_before_text
    assert _git_state(repo) == state_before
    assert _tree_snapshot(repo) == tree_before


def test_acceptance_init_proposes_the_same_shape(tmp_path: Path):
    repo = _mm30(tmp_path)
    (repo / "science.yaml").write_text(yaml.safe_dump({"name": "MM", "id": "mm"}))
    config_before_bytes = (repo / "science.yaml").read_bytes()
    config_before_text = (repo / "science.yaml").read_text()
    ignore_before_bytes = (repo / ".gitignore").read_bytes()
    ignore_before_text = (repo / ".gitignore").read_text()
    state_before = _git_state(repo)
    tree_before = _tree_snapshot(repo)

    result = _invoke(repo, "init")
    assert result.exit_code == 0, result.output
    assert yaml.safe_load(result.output) == {
        "boundary": {
            "roots": [
                {
                    "path": "data/external",
                    "class": "manifest",
                    "tracked": ["datapackage.json"],
                },
                {"path": "data/raw", "class": "payload"},
                {"path": "pdfs", "class": "payload"},
            ]
        }
    }
    assert (repo / "science.yaml").read_bytes() == config_before_bytes
    assert (repo / "science.yaml").read_text() == config_before_text
    assert (repo / ".gitignore").read_bytes() == ignore_before_bytes
    assert (repo / ".gitignore").read_text() == ignore_before_text
    assert _git_state(repo) == state_before
    assert _tree_snapshot(repo) == tree_before


def test_acceptance_hostile_global_git_config_cannot_alter_fixture(tmp_path: Path, monkeypatch):
    hostile_home = tmp_path / "hostile-home"
    excludes = hostile_home / "global-excludes"
    hooks = hostile_home / "hooks"
    attributes = hostile_home / "xdg/git/attributes"
    template_hooks = hostile_home / "template/hooks"
    hooks.mkdir(parents=True)
    attributes.parent.mkdir(parents=True)
    template_hooks.mkdir(parents=True)
    excludes.write_text("science.yaml\n*.json\n")
    attributes.write_text("science.yaml export-ignore\n")
    pre_commit = hooks / "pre-commit"
    pre_commit.write_text("#!/bin/sh\nexit 97\n")
    pre_commit.chmod(0o755)
    template_pre_commit = template_hooks / "pre-commit"
    template_pre_commit.write_text("#!/bin/sh\nexit 96\n")
    template_pre_commit.chmod(0o755)
    (hostile_home / ".gitconfig").write_text(f"[core]\n\texcludesFile = {excludes}\n\thooksPath = {hooks}\n")
    monkeypatch.setenv("HOME", str(hostile_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(hostile_home / "xdg"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("GIT_CONFIG_GLOBAL", raising=False)

    # Precondition: ordinary Git sees the hostile user settings and template.
    hostile_env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    hostile_env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TEMPLATE_DIR": str(hostile_home / "template"),
            "HOME": str(hostile_home),
            "XDG_CONFIG_HOME": str(hostile_home / "xdg"),
        }
    )
    hostile_repo = tmp_path / "hostile-repo"
    hostile_repo.mkdir()
    subprocess.run(
        ["git", "-C", str(hostile_repo), "init", "-q", "."],
        check=True,
        env=hostile_env,
    )
    (hostile_repo / "science.yaml").write_text("name: hostile\n")
    assert (hostile_repo / ".git/hooks/pre-commit").is_file()
    assert (
        subprocess.run(
            [
                "git",
                "-C",
                str(hostile_repo),
                "check-ignore",
                "--no-index",
                "science.yaml",
            ],
            env=hostile_env,
        ).returncode
        == 0
    )
    hostile_attribute = subprocess.run(
        [
            "git",
            "-C",
            str(hostile_repo),
            "check-attr",
            "export-ignore",
            "--",
            "science.yaml",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=hostile_env,
    )
    assert hostile_attribute.stdout.strip() == "science.yaml: export-ignore: set"
    configured_hooks = subprocess.run(
        [
            "git",
            "-C",
            str(hostile_repo),
            "config",
            "--global",
            "--get",
            "core.hooksPath",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=hostile_env,
    )
    assert configured_hooks.stdout.strip() == str(hooks)

    monkeypatch.setenv("GIT_TEMPLATE_DIR", str(hostile_home / "template"))
    for name in (
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_WORK_TREE",
    ):
        monkeypatch.setenv(name, str(hostile_home / f"bogus-{name.lower()}"))

    repo = _mm30(tmp_path / "repo")
    assert not (repo / ".git/hooks").exists()
    hermetic_attribute = _git(
        repo,
        "check-attr",
        "export-ignore",
        "--",
        "science.yaml",
        capture_output=True,
    )
    assert hermetic_attribute.stdout.strip() == "science.yaml: export-ignore: unspecified"

    result = _invoke(repo, "sync")
    assert result.exit_code == 0, result.output
    _git(repo, "add", "-A")
    staged = _git(repo, "ls-files", capture_output=True).stdout.split()
    assert "science.yaml" in staged
    assert "data/external/opentargets/25.03/datapackage.json" in staged
    _git(repo, "commit", "-qm", "hermetic")


def test_acceptance_pins_the_six_check_severity_contract(tmp_path: Path):
    observed: set[tuple[str, Severity]] = set()

    drift = _mm30(tmp_path / "drift")
    _git(drift, "add", ".gitignore", "science.yaml")
    observed.update((finding.rule, finding.severity) for finding in _findings(drift))

    tracked = _mm30(tmp_path / "tracked")
    assert _invoke(tracked, "sync").exit_code == 0
    _git(tracked, "add", "-A")
    _git(tracked, "add", "-f", "data/raw/GSE1234_series_matrix.txt")
    observed.update((finding.rule, finding.severity) for finding in _findings(tracked))

    conflict = _mm30(tmp_path / "conflict")
    assert _invoke(conflict, "sync").exit_code == 0
    conflict_ignore = conflict / ".gitignore"
    conflict_ignore.write_text(f"*.parquet\n{conflict_ignore.read_text()}")
    _git(conflict, "add", ".gitignore")
    observed.update((finding.rule, finding.severity) for finding in _findings(conflict))

    unreachable = _mm30(tmp_path / "unreachable")
    assert _invoke(unreachable, "sync").exit_code == 0
    unreachable_ignore = unreachable / ".gitignore"
    generated = unreachable_ignore.read_text()
    assert "/data/external/**\n" in generated
    unreachable_ignore.write_text(generated.replace("/data/external/**\n", "/data/external/\n", 1))
    _git(unreachable, "add", ".gitignore")
    observed.update((finding.rule, finding.severity) for finding in _findings(unreachable))

    assert observed == _ENFORCEMENT_CONTRACT
