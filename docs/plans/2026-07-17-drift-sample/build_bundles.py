"""Build blinded adjudication bundles from the pre-registered draw.

One bundle per drawn plan: the blinded body plus the extracted deliverable and
task candidates -- and NO claimed_status. Built only from rows that resolved and
verified (Task 8 Step 1), so a bundle is never made from an unverified row.
"""

import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from science_tool.drift_sample.blind import blind_plan
from science_tool.drift_sample.extract import extract_deliverables, extract_task_refs
from science_tool.drift_sample.frame import Pin, pinned_worktree

_HERE = Path(__file__).resolve().parent
PREREG = _HERE / "prereg.json"
OUT = _HERE / "bundles.json"

# Re-supplied locally; deliberately absent from the committed record.
ROOTS = {
    "multiple-myeloma": Path.home() / "d/cancer/cancer-types/multiple-myeloma",
    "natural-systems": Path.home() / "d/natural-systems",
    "protein-landscape": Path.home() / "d/protein-landscape",
    "post-acute-infection": Path.home() / "d/health/processes/post-acute-infection",
}


def _resolve(rec: dict) -> tuple[list[dict], list[str]]:
    by_id: dict[str, list[dict]] = defaultdict(list)
    for row in rec["frame"]:
        by_id[row["plan_id"]].append(row)
    rows, errs = [], []
    for pid in rec["drawn_ids"]:
        hits = by_id.get(pid, [])
        if len(hits) != 1:
            errs.append(f"{pid}: resolved to {len(hits)} rows")
            continue
        rows.append(hits[0])
    return rows, errs


def main() -> int:
    rec = json.loads(PREREG.read_text())
    rows, errs = _resolve(rec)
    if errs:
        print("REFUSING: unresolved rows:", errs)
        return 1

    by_project: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_project[row["project"]].append(row)

    bundles = []
    with tempfile.TemporaryDirectory() as tmp:
        for project, prows in sorted(by_project.items()):
            pin = Pin(project=project, root=ROOTS[project], commit=rec["pins"][project])
            with pinned_worktree(pin, Path(tmp)) as wt:
                for row in prows:
                    raw = (wt / row["rel_path"]).read_text(errors="replace")
                    body = blind_plan(raw)
                    bundles.append(
                        {
                            "plan_id": row["plan_id"],
                            "project": project,
                            "rel_path": row["rel_path"],
                            "body": body,
                            "deliverables": extract_deliverables(body),
                            "tasks": extract_task_refs(body),
                        }
                    )

    bundles.sort(key=lambda b: b["plan_id"])
    OUT.write_text(json.dumps(bundles, indent=2, sort_keys=True) + "\n")
    print(f"bundles={len(bundles)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
