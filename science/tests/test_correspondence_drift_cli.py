from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCIENCE_YAML = """\
name: fixture
profile: research
created: 2026-07-18
last_modified: 2026-07-18
status: active
summary: Fixture project for the correspondence-drift CLI exit-code test.
layout_version: 3
knowledge_profiles:
  local: entities
  curated: []
"""

_PYPROJECT = """\
[project]
name = "fixture"
version = "0.0.0"
requires-python = ">=3.11"

[dependency-groups]
dev = ["science"]

[tool.uv.sources]
science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }
"""

_AGENTS = """\
# Fixture

<!-- BEGIN: load-bearing-constraints (managed by /science:curate; edit core/decisions.md instead) -->
<!-- END: load-bearing-constraints -->
"""


def _clean_project(root: Path) -> None:
    for d in ("doc", "knowledge", "tasks", "code", "papers", "data", "models", "results", "src", "entities/plans"):
        (root / d).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "science.yaml").write_text(_SCIENCE_YAML, encoding="utf-8")
    (root / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (root / "AGENTS.md").write_text(_AGENTS, encoding="utf-8")
    (root / "tasks" / "active").mkdir()
    (root / "entities" / "research-question.md").write_text(
        '---\nid: "research-question:main"\nkind: research-question\ntitle: "RQ"\n'
        'status: "open"\ncreated: 2026-07-18\nupdated: 2026-07-18\n---\n\nWhat?\n',
        encoding="utf-8",
    )
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")


def _add_stale_plan(root: Path) -> None:
    (root / "entities" / "plans" / "0001-x.md").write_text(
        '---\nid: "plan:0001-x"\nkind: plan\ntitle: "T"\nstatus: "draft"\n'
        'created: 2026-07-18\nupdated: 2026-07-18\n---\n\n## Deliverables\n\nBuilds `src/a.py`.\n',
        encoding="utf-8",
    )


def _validate(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "science_tool", "validate", "--fail-on", "hygiene", "--format", "json"],
        cwd=root, capture_output=True, text=True,
    )


def test_fixture_is_validation_clean_before_the_stale_plan(tmp_path: Path):
    # The precondition the exit-code assertion depends on: with no stale plan, the tree is clean.
    _clean_project(tmp_path)
    proc = _validate(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["summary"] == {"errors": 0, "warnings": 0, "infos": 0}


def test_drift_warn_exits_zero_even_at_top_fail_on_tier(tmp_path: Path):
    _clean_project(tmp_path)
    _add_stale_plan(tmp_path)
    proc = _validate(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    rules = [r["rule"] for r in payload["results"]]
    assert rules == ["plan.correspondence-drift"]  # the ONE finding, and it did not gate
