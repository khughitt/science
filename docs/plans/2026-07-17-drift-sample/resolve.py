"""Resolve drawn ids to frame rows and verify pinned bytes. Fails loudly."""

import hashlib
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from science_tool.drift_sample.frame import Pin, pinned_worktree

# Roots are machine paths and are deliberately absent from prereg.json
# (Task 7 writes `root: None`). They are re-supplied here, never committed
# into the record. The commits come from the pre-registration; only the
# location is local.
ROOTS = {
    "multiple-myeloma": Path.home() / "d/cancer/cancer-types/multiple-myeloma",
    "natural-systems": Path.home() / "d/natural-systems",
    "protein-landscape": Path.home() / "d/protein-landscape",
    "post-acute-infection": Path.home() / "d/health/processes/post-acute-infection",
}
# resolve.py sits beside prereg.json in the drift-sample dir, so anchor on this
# file's own directory rather than the cwd (this is run from science/).
PREREG = Path(__file__).resolve().parent / "prereg.json"


def resolve(rec: dict) -> tuple[list[dict], list[str]]:
    """Join drawn_ids to frame rows; exactly one row per id."""
    by_id: dict[str, list[dict]] = defaultdict(list)
    for row in rec["frame"]:
        by_id[row["plan_id"]].append(row)

    rows, errs = [], []
    for pid in rec["drawn_ids"]:
        hits = by_id.get(pid, [])
        if len(hits) != 1:
            errs.append(f"{pid}: resolved to {len(hits)} frame rows, expected exactly 1")
            continue
        rows.append(hits[0])
    return rows, errs


def main() -> int:
    rec = json.loads(PREREG.read_text())
    rows, errs = resolve(rec)

    by_project: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_project[row["project"]].append(row)

    with tempfile.TemporaryDirectory() as tmp:
        for project, prows in sorted(by_project.items()):
            pin = Pin(project=project, root=ROOTS[project], commit=rec["pins"][project])
            with pinned_worktree(pin, Path(tmp)) as wt:
                for row in prows:
                    path = wt / row["rel_path"]
                    if not path.exists():
                        errs.append(f"{row['plan_id']}: {row['rel_path']} missing at pin")
                        continue
                    got = hashlib.sha256(path.read_bytes()).hexdigest()
                    if got != row["source_sha256"]:
                        errs.append(
                            f"{row['plan_id']}: sha256 {got} != pinned {row['source_sha256']}"
                        )

    print("RESOLUTION ERRORS:", errs or "none")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
