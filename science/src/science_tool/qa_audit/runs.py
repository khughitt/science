from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from science_tool.markdown_utils import parse_frontmatter


@dataclass
class RunRecord:
    run_id: str
    workflow: str
    manifest_path: str
    supersedes: list[str] = field(default_factory=list)
    error: str | None = None


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def load_runs(runs_dir: Path) -> list[RunRecord]:
    """Load authored workflow-run entities from doc/workflow-runs/*.md frontmatter.

    A run missing the machine-readable fields the audit depends on
    (manifest_path, workflow) is returned with `error` set rather than skipped.
    """
    records: list[RunRecord] = []
    for path in sorted(runs_dir.glob("*.md")):
        fm, _ = parse_frontmatter(path)
        run_id = str(fm.get("id", path.stem))
        workflow = fm.get("workflow")
        manifest_path = fm.get("manifest_path")
        error = None
        if not workflow:
            error = "missing 'workflow'"
        elif not manifest_path:
            error = "missing 'manifest_path'"
        records.append(RunRecord(
            run_id=run_id,
            workflow=str(workflow or ""),
            manifest_path=str(manifest_path or ""),
            supersedes=_as_list(fm.get("supersedes")),
            error=error,
        ))
    return records


def chain_depth(runs: list[RunRecord], workflow: str) -> int:
    """Number of runs recorded for the workflow (its supersession chain); 1 == single run."""
    return sum(1 for r in runs if r.workflow == workflow)
