import os
import subprocess
from pathlib import Path

from science_tool.validate.checks.code_files import check_code_files
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _ctx(root: Path, *, profile: str = "research", extra: str = "") -> ValidateContext:
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                f"profile: {profile}",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
                extra,
            ]
        ),
        encoding="utf-8",
    )
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _by_rule(results: list[Result]) -> dict[str, list[Result]]:
    out: dict[str, list[Result]] = {}
    for r in results:
        out.setdefault(r.rule or "", []).append(r)
    return out


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def _commit_all(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(repo, "commit", "-m", "init", env=env)


def test_no_code_dir_is_silent(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    assert list(check_code_files(ctx)) == []


def test_blockless_file_is_a_ghost(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text("print(1)\n", encoding="utf-8")
    ctx = _ctx(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.ghost"]) == 1
    ghost = by_rule["code.ghost"][0]
    assert ghost.severity is Severity.WARN
    assert ghost.path == Path("code/x.py")


def test_malformed_block_is_reported_with_error(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    # Unterminated block -> present but invalid.
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: library\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert "code.ghost" not in by_rule
    assert len(by_rule["code.malformed-block"]) == 1
    msg = by_rule["code.malformed-block"][0].message
    assert "unterminated" in msg


def test_valid_block_emits_no_ghost_or_malformed(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: library\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert "code.ghost" not in by_rule
    assert "code.malformed-block" not in by_rule


def test_excluded_file_is_not_walked(tmp_path: Path) -> None:
    (tmp_path / "code" / "vendor").mkdir(parents=True)
    (tmp_path / "code" / "vendor" / "lib.py").write_text("print(1)\n", encoding="utf-8")
    ctx = _ctx(tmp_path, extra="code_excludes:\n  - '**/vendor/**'")
    assert list(check_code_files(ctx)) == []


def test_findings_are_never_errors(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text("print(1)\n", encoding="utf-8")
    ctx = _ctx(tmp_path)
    assert all(r.severity is not Severity.ERROR for r in check_code_files(ctx))


def test_unreadable_file_is_reported_not_crashing(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text("print(1)\n", encoding="utf-8")
    ctx = _ctx(tmp_path)  # builds context (reads science.yaml) BEFORE we patch

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs):
        if self.name == "x.py":
            raise OSError("simulated unreadable file")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.unreadable"]) == 1
    assert by_rule["code.unreadable"][0].severity is Severity.WARN
    assert "code/x.py" in by_rule["code.unreadable"][0].message
    assert "code.ghost" not in by_rule  # the unreadable file did not also become a ghost


def test_missing_status_is_metadata_gap(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# task_ids: []\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.metadata-gap"]) == 1
    assert "missing required `status`" in by_rule["code.metadata-gap"][0].message


def test_invalid_status_is_metadata_gap(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: bogus\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.metadata-gap"]) == 1
    assert "'bogus'" in by_rule["code.metadata-gap"][0].message


def test_non_list_task_ids_is_metadata_gap(tmp_path: Path) -> None:
    # `task_ids: t999` parses to a scalar string, not a list — must not be
    # silently ignored.
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# task_ids: t999\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.metadata-gap"]) == 1
    assert "task_ids" in by_rule["code.metadata-gap"][0].message
    assert "code.unresolved-task" not in by_rule


def test_unknown_task_id_is_unresolved(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# task_ids: [t999]\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.unresolved-task"]) == 1
    assert "t999" in by_rule["code.unresolved-task"][0].message


def test_resolved_task_id_is_silent(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t491] Real task\n- created: 2026-01-01\n", encoding="utf-8"
    )
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# task_ids: [t491]\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.unresolved-task" not in _by_rule(list(check_code_files(ctx)))


def test_uncommitted_valid_block_is_flagged(tmp_path: Path) -> None:
    # No git repo at all -> last_content_change_date returns None.
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.uncommitted"]) == 1


def test_committed_valid_block_has_no_uncommitted_finding(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.uncommitted" not in _by_rule(list(check_code_files(ctx)))


def test_orphaned_executable_is_flagged(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# status: workflow-owned\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.orphaned-executable"]) == 1
    assert by_rule["code.orphaned-executable"][0].severity is Severity.WARN


def test_workflow_referenced_executable_is_not_orphan(tmp_path: Path) -> None:
    (tmp_path / "code" / "workflows").mkdir(parents=True)
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# status: workflow-owned\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    (tmp_path / "code" / "workflows" / "main.smk").write_text(
        'rule r:\n    script:\n        "../run.py"\n', encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.orphaned-executable" not in _by_rule(list(check_code_files(ctx)))


def test_exploratory_executable_is_exempt_from_orphan(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# status: exploratory\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.orphaned-executable" not in _by_rule(list(check_code_files(ctx)))


def test_declared_non_decision_bearing_executable_is_not_orphan(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# status: workflow-owned\n# decision_bearing: false\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.orphaned-executable" not in _by_rule(list(check_code_files(ctx)))


def test_library_valid_block_is_not_orphan(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "lib.py").write_text(
        '# science:code\n# status: library\n# science:end\ndef f():\n    return 1\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.orphaned-executable" not in _by_rule(list(check_code_files(ctx)))
