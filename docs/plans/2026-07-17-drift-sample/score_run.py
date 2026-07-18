"""Probe all 40 adjudicated plans, resolve reviewer pairs, and run the gate.

Input: verdicts_raw.json = {plan_id: [ {deliverables,tasks,superseded}, ... ]}
(2 or 3 reviewers per plan). Orchestrator probes each reviewer's set (blinding-safe),
runs adjudicate() -> per-reviewer status, resolves the plan's status by majority,
and reports the confusion matrix, Manski bounds, Cohen's kappa, and the gate.
"""

import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from science_tool.drift_sample.frame import Pin, pinned_worktree
from science_tool.correspondence.probe import probe_path, resolve_task
from science_tool.correspondence.adjudicate import Adjudicated, adjudicate
from science_tool.drift_sample.normalize import normalize_claim
from science_tool.drift_sample.score import verdict, manski, gate

_HERE = Path("../docs/plans/2026-07-17-drift-sample")
rec = json.loads((_HERE / "prereg.json").read_text())
frame = {f["plan_id"]: f for f in rec["frame"]}
raw = json.loads(Path(sys.argv[1]).read_text())

ROOTS = {
    "multiple-myeloma": Path.home() / "d/cancer/cancer-types/multiple-myeloma",
    "natural-systems": Path.home() / "d/natural-systems",
    "protein-landscape": Path.home() / "d/protein-landscape",
    "post-acute-infection": Path.home() / "d/health/processes/post-acute-infection",
}


def reviewer_status(wt, adj):
    delivs = [probe_path(wt, d).result for d in adj["deliverables"]]
    tasks = [resolve_task(wt, t) for t in adj["tasks"]]
    return adjudicate(delivs, tasks, superseded=adj.get("superseded", False))


by_project = defaultdict(list)
for pid in raw:
    by_project[frame[pid]["project"]].append(pid)

per_plan = {}          # pid -> resolved adjudicated status
disagreements = []     # pids where reviewers split with no majority
rater_a, rater_b = [], []  # first two reviewers' statuses, for kappa

with tempfile.TemporaryDirectory() as tmp:
    for project, pids in sorted(by_project.items()):
        pin = Pin(project=project, root=ROOTS[project], commit=rec["pins"][project])
        with pinned_worktree(pin, Path(tmp)) as wt:
            for pid in pids:
                statuses = [reviewer_status(wt, adj) for adj in raw[pid]]
                if len(statuses) >= 2:
                    rater_a.append(statuses[0].value)
                    rater_b.append(statuses[1].value)
                tally = Counter(s.value for s in statuses)
                top, n_top = tally.most_common(1)[0]
                if n_top * 2 > len(statuses):        # strict majority
                    per_plan[pid] = top
                else:
                    disagreements.append(pid)

print(f"resolved {len(per_plan)}/{len(raw)} plans; {len(disagreements)} need a 3rd reviewer")
if disagreements:
    print("DISAGREEMENTS:", disagreements)


def cohens_kappa(a: list[str], b: list[str]) -> float:
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


if rater_a:
    po = sum(1 for x, y in zip(rater_a, rater_b) if x == y) / len(rater_a)
    print(f"\ninter-rater: raw agreement {po:.0%}, Cohen's kappa {cohens_kappa(rater_a, rater_b):.2f} "
          f"(descriptive; does not gate)")

# Verdicts over resolved plans
verdicts = []
matrix = Counter()
for pid, status in per_plan.items():
    claimed = frame[pid]["claimed_status"]
    v = verdict(claimed, Adjudicated(status))
    verdicts.append(v)
    norm = normalize_claim(claimed) or "unmappable"
    matrix[(norm, status)] += 1

k_lo, k_hi = manski(verdicts)
n = len([v for v in verdicts])
print(f"\nn resolved = {n}")
print(f"mismatches k: lo={k_lo} hi={k_hi} (indeterminate span {k_hi-k_lo})")
print("confusion (normalized_claim -> adjudicated): count")
for (c, a), ct in sorted(matrix.items()):
    flag = " <-- MISMATCH" if c != a and a != "indeterminate" and c != "unmappable" else ""
    print(f"  {c:14} -> {a:14} : {ct}{flag}")

if n == 40:
    g_lo = gate(k_lo, 40)
    g_hi = gate(k_hi, 40)
    print(f"\nGATE at n=40: k_lo -> {g_lo.value} ; k_hi -> {g_hi.value}")
    if g_lo == g_hi:
        print(f"  RESOLVED: {g_lo.value}")
    else:
        print("  Manski bounds straddle theta -> inconclusive at this look; go to n=80")
else:
    print(f"\n(n={n} != 40; resolve disagreements before gating)")
