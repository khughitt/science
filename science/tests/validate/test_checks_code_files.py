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
