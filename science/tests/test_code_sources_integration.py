import os
import subprocess
from datetime import date
from pathlib import Path

from science_tool.graph.sources import load_project_sources

_MANIFEST = (
    "name: demo\n"
    "created: 2026-01-01\n"
    "last_modified: 2026-01-02\n"
    "status: active\n"
    "summary: demo\n"
    "profile: research\n"
    "layout_version: 1\n"
    "knowledge_profiles:\n"
    "  local: knowledge/local\n"
)


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def test_load_project_sources_registers_code_file_entity(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (tmp_path / "knowledge" / "local").mkdir(parents=True)
    stages = tmp_path / "code" / "stages"
    stages.mkdir(parents=True)
    (stages / "run_fassoc.py").write_text(
        "# science:code\n# task_ids: [t491]\n# decision_bearing: true\n# status: workflow-owned\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )

    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(tmp_path, "commit", "-m", "init", env=env)

    sources = load_project_sources(tmp_path, include_commons=False)
    code_file = next(e for e in sources.entities if e.id == "code-file:stages/run_fassoc.py")
    assert code_file.kind == "code-file"
    assert code_file.decision_bearing is True
    assert code_file.status == "workflow-owned"
    assert code_file.task_ids == ["t491"]
    assert code_file.updated == date(2026, 4, 1)
