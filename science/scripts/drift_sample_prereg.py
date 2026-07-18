"""Capture pins, enumerate the frame, draw, and emit the pre-registration.

Run once. Its output is committed and hashed before any plan is adjudicated.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from science_tool.drift_sample.draw import draw
from science_tool.drift_sample.frame import enumerate_frame, pin_project, pinned_worktree
from science_tool.drift_sample.score import ALPHA, LADDER, THETA

SEED = 20260717
ROOTS = {
    "multiple-myeloma": Path.home() / "d/cancer/cancer-types/multiple-myeloma",
    "natural-systems": Path.home() / "d/natural-systems",
    "protein-landscape": Path.home() / "d/protein-landscape",
    "post-acute-infection": Path.home() / "d/health/processes/post-acute-infection",
}
# Anchor on the repo root, not the cwd: this script runs from science/, but the
# pre-registration lives beside the design and plan docs at the repo-root docs/.
_REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = _REPO_ROOT / "docs/plans/2026-07-17-drift-sample/prereg.json"


def main() -> int:
    pins = {name: pin_project(name, root) for name, root in ROOTS.items()}
    frame = []
    with tempfile.TemporaryDirectory() as tmp:
        for pin in pins.values():
            with pinned_worktree(pin, Path(tmp)) as wt:
                frame.extend(enumerate_frame(pin, wt))
    drawn = draw(frame, LADDER[0], seed=SEED)
    rubric = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    record = {
        "schema": 1,
        "seed": SEED,
        "theta": THETA,
        "alpha": ALPHA,
        "ladder": list(LADDER),
        "rubric_commit": rubric,
        "pins": {name: pin.commit for name, pin in pins.items()},
        "frame_size": len(frame),
        "frame": [asdict(r) | {"root": None} for r in frame],
        "drawn_ids": [r.plan_id for r in drawn],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"frame={len(frame)} drawn={len(drawn)}")
    print("pins:", json.dumps(record["pins"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
