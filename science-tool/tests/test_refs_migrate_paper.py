from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from science_tool.refs_migrate import (
    ID_REWRITE_RULES,
    PROSE_REWRITE_RULE,
    TYPE_REWRITE_RULES,
    rewrite_text,
    scan_project,
)


def test_id_rewrite_rules_cover_all_yaml_forms() -> None:
    patterns = {pat.pattern for pat, _ in ID_REWRITE_RULES}
    assert "id: article:" in patterns
    assert 'id: "article:' in patterns
    assert "- article:" in patterns
    assert any("[article:" in p for p in patterns)
    assert '"article:' in patterns
    assert "'article:" in patterns


def test_type_rewrite_rules_cover_all_quote_styles() -> None:
    patterns = {pat.pattern for pat, _ in TYPE_REWRITE_RULES}
    assert any("type: article" in p for p in patterns)
    assert any('type: "article"' in p for p in patterns)
    assert any("type: 'article'" in p for p in patterns)


def test_prose_rewrite_rule_uses_word_boundary() -> None:
    pat, _ = PROSE_REWRITE_RULE
    assert "\\b" in pat.pattern
    assert "article" in pat.pattern


def test_migrate_rewrites_id_field() -> None:
    before = '---\nid: article:Smith2024\ntype: "article"\n---\n\n# Body\n'
    after, count = rewrite_text(before)
    assert "id: paper:Smith2024" in after
    assert 'type: "paper"' in after
    assert count >= 2


def test_migrate_rewrites_related_list_inline() -> None:
    before = "related: [article:Smith2024, article:Jones2023]\n"
    after, count = rewrite_text(before)
    assert after == "related: [paper:Smith2024, paper:Jones2023]\n"
    assert count == 2


def test_migrate_rewrites_related_list_multiline() -> None:
    before = "related:\n  - article:Smith2024\n  - article:Jones2023\n"
    after, count = rewrite_text(before)
    assert "- paper:Smith2024" in after
    assert "- paper:Jones2023" in after
    assert count == 2


def test_migrate_rewrites_prose_mentions() -> None:
    before = "See article:Smith2024 for the full argument.\n"
    after, count = rewrite_text(before)
    assert after == "See paper:Smith2024 for the full argument.\n"
    assert count == 1


def test_migrate_preserves_particle_substrings() -> None:
    before = "The particle:muon and particle-physics community.\n"
    after, count = rewrite_text(before)
    assert after == before
    assert count == 0


def test_migrate_preserves_cite_prefix() -> None:
    before = "source_refs: [cite:Smith2024]\n"
    after, count = rewrite_text(before)
    assert after == before
    assert count == 0


def test_migrate_idempotent() -> None:
    before = "id: article:Smith2024\n"
    once, _ = rewrite_text(before)
    twice, count = rewrite_text(once)
    assert twice == once
    assert count == 0


FIXTURE = Path(__file__).parent / "fixtures" / "refs" / "legacy_project"


def test_scan_project_finds_all_rewrites() -> None:
    rewrites = scan_project(FIXTURE)
    assert len(rewrites) >= 4  # q01, Smith2024, t01, i01
    totals = {r.path.name: r.match_count for r in rewrites}
    assert totals["q01-example.md"] >= 3  # list items + prose
    assert totals["Smith2024.md"] >= 2  # id + type
    assert totals["t01-example.md"] >= 1  # inline-list
    assert totals["i01-example.md"] >= 1  # prose, NOT particle:muon


def test_scan_project_on_migrated_returns_empty() -> None:
    # Apply migration to an in-memory copy; re-scanning a migrated snapshot
    # would produce no rewrites. We verify by rewriting every file's text
    # and confirming the count is now 0.
    rewrites = scan_project(FIXTURE)
    for r in rewrites:
        _, n = __import__("science_tool.refs_migrate", fromlist=["rewrite_text"]).rewrite_text(r.new_text)
        assert n == 0, f"{r.path.name} not idempotent"


def test_scan_project_counts_are_accurate() -> None:
    rewrites = scan_project(FIXTURE)
    for r in rewrites:
        assert r.new_text != r.original_text
        assert r.match_count > 0


def test_scan_project_logs_warning_on_non_utf8_file(tmp_path: Path, caplog) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    bad = project / "doc" / "questions" / "bad.md"
    bad.write_bytes(b"\xff\xfe\x00not utf-8\n")

    with caplog.at_level("WARNING", logger="science_tool.refs_migrate"):
        scan_project(project)
    assert any("bad.md" in r.getMessage() for r in caplog.records)


def test_apply_rewrites_writes_files(tmp_path: Path) -> None:
    # Copy fixture into tmp_path so the test doesn't mutate the real fixture.
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "legacy_project")
    project = tmp_path / "legacy_project"

    from science_tool.refs_migrate import apply_rewrites
    rewrites = scan_project(project)
    apply_rewrites(rewrites)

    # Verify on-disk text is the new text.
    for r in rewrites:
        assert r.path.read_text(encoding="utf-8") == r.new_text

    # Re-scan: should produce 0 rewrites.
    assert scan_project(project) == []


def test_apply_rewrites_preserves_other_files(tmp_path: Path) -> None:
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "legacy_project")
    project = tmp_path / "legacy_project"
    science_yaml_before = (project / "science.yaml").read_text()

    from science_tool.refs_migrate import apply_rewrites
    apply_rewrites(scan_project(project))

    assert (project / "science.yaml").read_text() == science_yaml_before


def test_render_diff_emits_unified_diff() -> None:
    from science_tool.refs_migrate import FileRewrite, render_diff
    rewrite = FileRewrite(
        path=Path("doc/x.md"),
        original_text="id: article:X\n",
        new_text="id: paper:X\n",
        match_count=1,
    )
    diff = render_diff([rewrite])
    assert "--- doc/x.md" in diff
    assert "+++ doc/x.md" in diff
    assert "-id: article:X" in diff
    assert "+id: paper:X" in diff


def test_render_diff_respects_line_cap() -> None:
    from science_tool.refs_migrate import FileRewrite, render_diff
    many = [
        FileRewrite(
            path=Path(f"doc/x{i}.md"),
            original_text=f"article:X{i}\n" * 50,
            new_text=f"paper:X{i}\n" * 50,
            match_count=50,
        )
        for i in range(10)
    ]
    capped = render_diff(many, max_lines=200)
    assert "... " in capped and " more files with changes" in capped
    assert capped.count("\n") <= 220  # 200 diff lines + cap marker + slack


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "--allow-empty",
            "-m",
            "init",
            "-q",
        ],
        cwd=path,
        check=True,
    )


def test_check_git_clean_true_when_clean(tmp_path: Path) -> None:
    from science_tool.refs_migrate import check_git_clean

    _init_repo(tmp_path)
    assert check_git_clean(tmp_path) is True


def test_check_git_clean_false_when_dirty(tmp_path: Path) -> None:
    from science_tool.refs_migrate import check_git_clean

    _init_repo(tmp_path)
    (tmp_path / "new.txt").write_text("hi")
    assert check_git_clean(tmp_path) is False


def test_check_git_clean_true_for_non_git_dir(tmp_path: Path) -> None:
    from science_tool.refs_migrate import check_git_clean

    # Spec: if project isn't a git repo, don't block. User accepts the risk.
    assert check_git_clean(tmp_path) is True
