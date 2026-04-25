from __future__ import annotations

import os
import subprocess
import sys
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
                "  local: local",
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
    (root / "knowledge" / "sources" / "local").mkdir(parents=True)


def _validate_env(*, extra_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    path_parts: list[str] = []
    if extra_path is not None:
        path_parts.append(str(extra_path))
    path_parts.extend(["/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    env["PATH"] = ":".join(path_parts)
    return env


def _write_python3_stub(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "python3"
    stub.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f'exec "{sys.executable}" "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)


def _write_science_tool_stub(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "science-tool"
    stub.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -eu",
                'if [ "${1:-}" = "graph" ] && [ "${2:-}" = "audit" ]; then',
                "    printf '{\"rows\": []}\\n'",
                "    exit 0",
                "fi",
                "printf '{\"rows\": []}\\n'",
                "exit 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)


def _write_minimal_research_project(root: Path) -> None:
    """Set up a research-profile project with all paths the validator expects."""
    _write_common_files(root, "research")
    _write_python3_stub(root / "bin")
    _write_science_tool_stub(root / "bin")
    (root / "RESEARCH_PLAN.md").write_text("# Research Plan\n\n## Research Direction\n", encoding="utf-8")
    (root / "specs" / "research-question.md").write_text("# Question\n", encoding="utf-8")
    (root / "specs" / "scope-boundaries.md").write_text("# Scope\n", encoding="utf-8")
    (root / "specs" / "hypotheses").mkdir(parents=True)
    (root / "papers" / "pdfs").mkdir(parents=True)
    (root / "papers" / "references.bib").write_text("% bib\n", encoding="utf-8")
    (root / "data" / "raw").mkdir(parents=True)
    (root / "data" / "processed").mkdir(parents=True)
    (root / "models").mkdir(parents=True)
    (root / "results").mkdir(parents=True)
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "code" / "scripts").mkdir(parents=True)
    (root / "code" / "notebooks").mkdir(parents=True)
    (root / "code" / "workflows").mkdir(parents=True)


def _hypothesis_body(phase_line: str) -> str:
    """Compose a hypothesis file body with a configurable phase frontmatter line."""
    fm_lines = [
        "---",
        'id: "hypothesis:h01-test"',
        'type: "hypothesis"',
        'title: "Test"',
        'status: "proposed"',
    ]
    if phase_line:
        fm_lines.append(phase_line)
    fm_lines.extend([
        "source_refs: []",
        "related: []",
        'created: "2026-04-25"',
        'updated: "2026-04-25"',
        "---",
        "",
        "# Hypothesis: Test",
        "",
        "## Falsifiability",
        "",
        "Some falsifiability prose.",
        "",
    ])
    return "\n".join(fm_lines)


def test_validate_accepts_research_profile_with_root_src_and_code(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "research")
    _write_python3_stub(tmp_path / "bin")
    _write_science_tool_stub(tmp_path / "bin")
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
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_validate_accepts_software_profile_without_research_code_roots(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    _write_science_tool_stub(tmp_path / "bin")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_validate_fails_when_science_tool_is_missing(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert (
        "science-tool is required for task management, feedback, and graph workflows" in result.stdout + result.stderr
    )


def test_validate_reports_missing_science_tool_once_when_graph_exists(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "knowledge" / "graph.trig").write_text("", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    message = "science-tool is required for task management, feedback, and graph workflows"
    assert result.returncode != 0
    assert result.stdout.count(message) + result.stderr.count(message) == 1


def test_validate_accepts_science_tool_on_path(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    _write_science_tool_stub(tmp_path / "bin")

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_validate_accepts_hypothesis_with_phase_active(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "specs" / "hypotheses" / "h01-test.md").write_text(
        _hypothesis_body('phase: "active"'),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "invalid phase" not in combined.lower(), combined


def test_validate_accepts_hypothesis_with_phase_candidate(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "specs" / "hypotheses" / "h01-test.md").write_text(
        _hypothesis_body('phase: "candidate"'),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "invalid phase" not in combined.lower(), combined


def test_validate_accepts_hypothesis_without_phase(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "specs" / "hypotheses" / "h01-test.md").write_text(
        _hypothesis_body(""),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "invalid phase" not in combined.lower(), combined


def test_validate_warns_on_invalid_phase_value(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "specs" / "hypotheses" / "h01-test.md").write_text(
        _hypothesis_body('phase: "tentative"'),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "invalid phase" in combined.lower() and "tentative" in combined, combined
