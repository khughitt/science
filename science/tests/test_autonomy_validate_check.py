from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.validate.checks.autonomous_runs import check_autonomous_runs
from science_tool.validate.result import Severity

RUN_ID = "run:2026-07-25-curation-sweep-a3f1"
SLUG = "2026-07-25-curation-sweep-a3f1"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _ctx(project_root: Path):
    """Minimal ValidateContext -- this check reads only `project_root`."""
    from science_tool.validate.context import ValidateContext

    return ValidateContext(
        project_root=project_root,
        doc_dir=project_root / "doc",
        specs_dir=project_root / "entities" / "specs",
        manifest={},
        strict=False,
        verbose=False,
    )


def _record_text(*, base: str, head: str, branch: str = f"auto/{SLUG}", extra: str = "") -> str:
    return (
        "---\n"
        f"id: {RUN_ID}\n"
        "agent: curation-sweep\n"
        "model: test-model\n"
        "tier: belief-neutral\n"
        f"branch: {branch}\n"
        f"base_commit: {base}\n"
        f"head_commit: {head}\n"
        f"toolkit_revision: {'c' * 40}\n"
        "policy_identity:\n  id: core-default\n  version: '1'\n"
        f"basis_digest: {'d' * 64}\n"
        "started: '2026-07-25T09:00:00+00:00'\n"
        "ended: '2026-07-25T09:30:00+00:00'\n"
        "budget:\n  tokens: 100\n  wall_clock_seconds: 1800.0\n"
        "disposition: clean\n"
        f"{extra}"
        "---\n"
    )


def _write_record(root: Path, text: str, *, stem: str = SLUG) -> None:
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{stem}.md").write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "f.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _commit_with_trailer(root: Path, run_id: str) -> str:
    (root / "f.txt").write_text(f"{run_id}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"docs: work\n\nScience-Run: {run_id}")
    return _git(root, "rev-parse", "HEAD")


def test_a_project_with_no_runs_directory_yields_nothing(repo: Path):
    assert list(check_autonomous_runs(_ctx(repo))) == []


def test_a_non_git_project_yields_nothing(tmp_path: Path):
    (tmp_path / "runs").mkdir()
    assert list(check_autonomous_runs(_ctx(tmp_path))) == []


def test_a_consistent_record_yields_nothing(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base=base, head=head))

    assert list(check_autonomous_runs(_ctx(repo))) == []


def test_an_unattested_autonomous_commit_is_an_error(repo: Path):
    """A commit claiming a run that has no record: exactly the coverage gap §6 names."""
    _commit_with_trailer(repo, "run:2026-01-01-ghost-0000")

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "run:2026-01-01-ghost-0000" in results[0].message
    assert "no run record" in results[0].message


def test_an_unreachable_base_commit_is_an_error(repo: Path):
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base="0" * 40, head=head))

    results = list(check_autonomous_runs(_ctx(repo)))
    assert any(r.severity is Severity.ERROR and "base_commit" in r.message for r in results)


def test_an_unreachable_head_commit_is_an_error(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base=base, head="0" * 40))

    results = list(check_autonomous_runs(_ctx(repo)))
    assert any(r.severity is Severity.ERROR and "head_commit" in r.message for r in results)


def test_an_internally_inconsistent_record_is_an_error(repo: Path):
    """unwired + a digest fails model validation inside load_run_records, so this row is
    reached by converting RunRecordError -- there is no separate branch to write."""
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(
        repo, _record_text(base=base, head=head).replace("disposition: clean", "disposition: unwired")
    )

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "basis_digest" in results[0].message


def test_a_malformed_record_does_not_crash_validate(repo: Path):
    _write_record(repo, "not frontmatter at all\n")

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]


def test_a_nonconforming_branch_is_rejected_by_the_loader_not_by_a_branch_check(repo: Path):
    """`AutonomousRunRecord._validate_identity` rebuilds `auto/<slug>` from the id and
    refuses anything else, so a nonconforming branch never survives `load_run_records`.
    It surfaces as the loader ERROR, and a `record.branch` comparison in this check would
    be code no input can reach."""
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base=base, head=head, branch="feature/hand-made"))

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "branch must be" in results[0].message


def test_an_unreadable_history_is_an_error_not_silence(repo: Path, monkeypatch: pytest.MonkeyPatch):
    """The scan gates the early return. Swallowing a git failure into `[]` makes the
    whole check report nothing on a repository it could not read."""
    from science_tool.validate.checks import autonomous_runs as module

    def _fail(root, *args):
        return subprocess.CompletedProcess(args=args, returncode=128, stdout="", stderr="boom")

    monkeypatch.setattr(module, "_git", _fail)

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "could not scan" in results[0].message


def test_an_unattested_commit_on_a_retained_branch_is_found(repo: Path):
    """A quarantined run KEEPS its branch (design §6), unmerged. Scanning only HEAD makes
    exactly the commits this check exists to find invisible."""
    _git(repo, "checkout", "-q", "-b", "auto/2026-01-01-ghost-0000")
    _commit_with_trailer(repo, "run:2026-01-01-ghost-0000")
    _git(repo, "checkout", "-q", "-")

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "run:2026-01-01-ghost-0000" in results[0].message


def test_the_check_module_is_registered():
    """Writing the module does not enable it: `validate` runs only what
    CANONICAL_CHECK_MODULES names."""
    from science_tool.validate.checks import CANONICAL_CHECK_MODULES

    assert "autonomous_runs" in CANONICAL_CHECK_MODULES


def test_a_record_committed_after_its_own_range_yields_nothing(repo: Path):
    """The legitimate shape. `finish` writes the record only once `head_commit` is known,
    so the operator's commit of it necessarily lands after the range ends."""
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base=base, head=head))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: attest the run")

    assert list(check_autonomous_runs(_ctx(repo))) == []


def test_a_record_added_inside_its_own_range_is_an_error(repo: Path):
    """The forgery `finish` cannot report on.

    The actor knows its own run id -- it must, to write the trailers -- so it can commit
    `runs/<slug>.md` claiming `clean`. `finish` then hits the writer's never-overwrite
    rule, returns `unwired`, and leaves no durable record of its own; the forgery is the
    only attestation that survives. Nothing else in this check looks at it.

    The range is filled in afterwards, which is how an actor gets a plausible late
    `head_commit` without knowing a future sha -- and it is exactly what puts the commit
    that ADDED the record inside the range the record itself names.
    """
    base = _git(repo, "rev-parse", "HEAD")
    _write_record(repo, _record_text(base=base, head=base))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"chore: attest\n\nScience-Run: {RUN_ID}")
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base=base, head=head))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"chore: amend attestation\n\nScience-Run: {RUN_ID}")

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "attests" in results[0].message
    assert str(Path(f"runs/{SLUG}.md")) == str(results[0].path)


def test_an_uninvokable_git_is_an_error_not_a_validate_crash(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    """`validate` runs on any machine, including one with no git on PATH. An OSError out
    of the runner must become a row, not a traceback out of the whole report."""
    from science_tool.autonomy import git as git_module

    _write_record(repo, _record_text(base="0" * 40, head="0" * 40))

    class _NoGit:
        @staticmethod
        def run(*args, **kwargs):
            raise OSError(2, "No such file or directory: 'git'")

    monkeypatch.setattr(git_module, "subprocess", _NoGit)

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "could not execute git" in results[0].message
