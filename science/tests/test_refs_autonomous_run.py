from __future__ import annotations

from pathlib import Path

import pytest

from science_model.autonomous_runs import RunRecordError
from science_tool.refs import check_refs

RUN_ID = "run:2026-07-24-curation-sweep-a3f1"

_RECORD = f"""---
id: {RUN_ID}
agent: curation-sweep
model: claude-opus-5
tier: belief-neutral
branch: auto/2026-07-24-curation-sweep-a3f1
base_commit: {"a" * 40}
head_commit: {"b" * 40}
toolkit_revision: {"c" * 40}
policy_identity:
  id: core-default
  version: "1"
basis_digest: {"d" * 64}
started: 2026-07-24T09:00:00+00:00
ended: 2026-07-24T09:30:00+00:00
budget:
  tokens: 12000
  wall_clock_seconds: 1800.5
disposition: clean
---

Body.
"""


def _write(root: Path, *, run_ref: str | None, with_record: bool = True) -> None:
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    topics = root / "entities" / "topics"
    topics.mkdir(parents=True, exist_ok=True)
    extra = f"autonomous_run: {run_ref}\n" if run_ref else ""
    (topics / "demo.md").write_text(
        f"---\nid: topic:demo\nkind: topic\ntitle: Demo\nstatus: active\n{extra}---\n\nBody.\n",
        encoding="utf-8",
    )
    if with_record:
        runs = root / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "2026-07-24-curation-sweep-a3f1.md").write_text(_RECORD, encoding="utf-8")


def _run_issues(root: Path):
    return [issue for issue in check_refs(root) if issue.ref_type == "autonomous-run"]


def test_resolvable_reference_reports_nothing(tmp_path: Path) -> None:
    _write(tmp_path, run_ref=RUN_ID)
    assert _run_issues(tmp_path) == []


def test_dangling_reference_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, run_ref="run:2026-07-24-curation-sweep-ffff")
    issues = _run_issues(tmp_path)
    assert len(issues) == 1
    assert issues[0].ref_value == "run:2026-07-24-curation-sweep-ffff"
    assert "no run record" in issues[0].message
    assert issues[0].file == "entities/topics/demo.md"


def test_reference_with_no_runs_directory_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, run_ref=RUN_ID, with_record=False)
    assert len(_run_issues(tmp_path)) == 1


def test_entity_without_the_field_reports_nothing(tmp_path: Path) -> None:
    _write(tmp_path, run_ref=None)
    assert _run_issues(tmp_path) == []


def test_added_by_is_never_treated_as_a_run_reference(tmp_path: Path) -> None:
    # Design testing item 10, second half: `user` and `explore-ideas:...` stay valid.
    (tmp_path / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    topics = tmp_path / "entities" / "topics"
    topics.mkdir(parents=True, exist_ok=True)
    (topics / "demo.md").write_text(
        "---\nid: topic:demo\nkind: topic\ntitle: Demo\nstatus: active\n"
        "added_by: user\n---\n\nBody.\n",
        encoding="utf-8",
    )
    assert _run_issues(tmp_path) == []


def test_malformed_run_record_propagates(tmp_path: Path) -> None:
    _write(tmp_path, run_ref=RUN_ID)
    record = tmp_path / "runs" / "2026-07-24-curation-sweep-a3f1.md"
    record.write_text(
        record.read_text(encoding="utf-8").replace("disposition: clean", "disposition: passed"),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError):
        check_refs(tmp_path)
