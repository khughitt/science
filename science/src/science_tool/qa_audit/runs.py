from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.markdown_utils import frontmatter_span


@dataclass
class RunRecord:
    run_id: str
    workflow: str
    manifest_path: str
    error: str | None = None


def load_runs(runs_dir: Path) -> list[RunRecord]:
    """Load authored workflow-run entities from entities/workflow-runs/*.md frontmatter.

    A run missing the machine-readable fields the audit depends on
    (manifest_path, workflow) is returned with `error` set rather than skipped.
    """
    records: list[RunRecord] = []
    for path in sorted(runs_dir.glob("*.md")):
        fm, _ = frontmatter_span(path)
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
            error=error,
        ))
    return records


def chain_depth(runs: list[RunRecord], workflow: str) -> int:
    """Number of runs recorded for the workflow; 1 == single run.

    Counts runs — it does NOT follow a supersession chain. The top-level `supersedes:` field it
    once loaded was retired in S2: nothing consumed it.
    """
    return sum(1 for r in runs if r.workflow == workflow)
