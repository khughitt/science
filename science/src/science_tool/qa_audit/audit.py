from __future__ import annotations

from pathlib import Path

from science_tool.qa_audit.manifest import load_qa_artifacts
from science_tool.qa_audit.runs import chain_depth, load_runs
from science_tool.qa_audit.verdicts import RESOLVED_ENGAGED, engagement_verdict, iteration_verdict


def audit_workflows(*, runs_dir: Path, repo_root: Path) -> list[dict]:
    runs = load_runs(runs_dir)
    workflows = sorted({r.workflow for r in runs if r.workflow})
    rows: list[dict] = []

    for workflow in workflows:
        wf_runs = [r for r in runs if r.workflow == workflow]
        depth = chain_depth(runs, workflow)
        # Use the last authored run for QA artifact discovery (single run in the MVP case).
        latest = wf_runs[-1]

        try:
            if latest.error:
                raise FileNotFoundError(latest.error)
            raw = Path(latest.manifest_path)
            manifest_path = raw if raw.is_absolute() else repo_root / raw
            if not manifest_path.exists():
                raise FileNotFoundError(f"manifest not found: {manifest_path}")
            has_report, flags = load_qa_artifacts(manifest_path)
        except Exception as exc:  # noqa: BLE001 — per-row ERROR, audit must not crash
            rows.append({
                "workflow": workflow, "runs": len(wf_runs), "chain_depth": depth,
                "open_flags": 0, "dispositioned_flags": 0,
                "iteration": "ERROR", "engagement": "ERROR", "detail": str(exc),
            })
            continue

        open_flags = sum(1 for f in flags if f.disposition == "open")
        dispositioned = sum(1 for f in flags if f.disposition in RESOLVED_ENGAGED)
        rows.append({
            "workflow": workflow, "runs": len(wf_runs), "chain_depth": depth,
            "open_flags": open_flags, "dispositioned_flags": dispositioned,
            "iteration": iteration_verdict(chain_depth=depth, flags=flags),
            "engagement": engagement_verdict(has_report=has_report, flags=flags),
        })
    return rows


def render_markdown(rows: list[dict]) -> str:
    header = (
        "| Workflow | Runs | Chain | Open | Dispositioned | Iteration | Engagement |\n"
        "| --- | --- | --- | --- | --- | --- | --- |"
    )
    body = [
        f"| {r['workflow']} | {r['runs']} | {r['chain_depth']} | {r['open_flags']} | "
        f"{r['dispositioned_flags']} | {r['iteration']} | {r['engagement']} |"
        for r in rows
    ]
    return "\n".join([header, *body]) + "\n"
