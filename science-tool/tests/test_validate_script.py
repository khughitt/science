from __future__ import annotations

import subprocess
from pathlib import Path


def _validate_script_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "validate.sh"


def _write_common_files(root: Path, profile: str) -> None:
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                'created: "2026-03-18"',
                'last_modified: "2026-03-18"',
                'summary: "demo"',
                'status: "active"',
                f"profile: {profile}",
                "layout_version: 2",
                "tags: []",
                "data_sources: []",
                "knowledge_profiles:",
                "  curated: []",
                "  local: project_specific",
                "aspects: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text("# Operational Guide\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / "active.md").write_text("<!-- tasks -->\n", encoding="utf-8")
    (root / "specs").mkdir(parents=True)
    (root / "doc" / "background" / "topics").mkdir(parents=True)
    (root / "doc" / "background" / "papers").mkdir(parents=True)
    (root / "doc" / "questions").mkdir(parents=True)
    (root / "doc" / "methods").mkdir(parents=True)
    (root / "doc" / "datasets").mkdir(parents=True)
    (root / "doc" / "searches").mkdir(parents=True)
    (root / "doc" / "discussions").mkdir(parents=True)
    (root / "doc" / "interpretations").mkdir(parents=True)
    (root / "doc" / "reports").mkdir(parents=True)
    (root / "doc" / "meta").mkdir(parents=True)
    (root / "doc" / "plans").mkdir(parents=True)
    (root / "knowledge" / "sources" / "project_specific").mkdir(parents=True)


def test_validate_accepts_research_profile_with_root_src_and_code(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "research")
    (tmp_path / "RESEARCH_PLAN.md").write_text("# Research Plan\n\n## Research Direction\n", encoding="utf-8")
    (tmp_path / "specs" / "research-question.md").write_text("# Question\n", encoding="utf-8")
    (tmp_path / "specs" / "scope-boundaries.md").write_text("# Scope\n", encoding="utf-8")
    (tmp_path / "specs" / "hypotheses").mkdir(parents=True)
    (tmp_path / "papers" / "pdfs").mkdir(parents=True)
    (tmp_path / "papers" / "references.bib").write_text("% bib\n", encoding="utf-8")
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "models").mkdir(parents=True)
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "code" / "scripts").mkdir(parents=True)
    (tmp_path / "code" / "notebooks").mkdir(parents=True)
    (tmp_path / "code" / "workflows").mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_validate_accepts_software_profile_without_research_code_roots(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
