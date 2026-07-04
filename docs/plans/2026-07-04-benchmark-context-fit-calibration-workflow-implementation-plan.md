# Benchmark Context-Fit Calibration Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the first durable context-fit calibration pass, generate a committed audit report from JSON outputs, and use it to choose the next benchmark slice.

**Architecture:** This is a read-only audit/report workflow, not a code feature. Existing `science benchmark ...` commands remain the source of truth; a one-off capture script writes raw JSON snapshots to a session scratch directory (`$CALIBRATION_SCRATCH`, not `/tmp`), validates count reconciliation, and writes a dated Markdown report under `docs/reports/`.

**Tech Stack:** Python stdlib (`json`, `subprocess`, `pathlib`, `collections`), existing `science` CLI commands, git.

---

## File Map

- Create: `docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md`
  - Durable report generated from JSON payloads.
- Use scratch only: `$CALIBRATION_SCRATCH` (a subdirectory of your session scratchpad, not `/tmp`)
  - Raw JSON snapshots and a temporary capture script.
- Do not modify source code unless a command fails because of a real bug.
- Do not commit raw JSON snapshots by default.

## Task 0: Confirm Worktree and Source Resolution

**Files:**
- Read only.

- [ ] **Step 1: Confirm branch and clean state**

Run from the worktree root:

```bash
rtk git status --short --branch
```

Expected output includes:

```text
* benchmark-context-fit-calibration
clean -- nothing to commit
```

If the branch differs, stop and report the actual branch. If the worktree is dirty, inspect the dirty files before continuing.

- [ ] **Step 2: Confirm Python imports resolve to this worktree**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python -c "import science_tool, pathlib; print(pathlib.Path(science_tool.__file__).resolve())"
```

Expected: printed path contains:

```text
.worktrees/benchmark-context-fit-calibration/science/src/science_tool
```

If it points at the main checkout, keep `PYTHONPATH=science/src:science/model/src` on every command in this plan.

- [ ] **Step 3: Confirm design/spec files are present**

Run:

```bash
rtk ls docs/plans/2026-07-04-benchmark-context-fit-calibration-workflow-design.md docs/reports/benchmark-context-fit-calibration-2026-07-04.md
```

Expected: both paths are printed. The existing `benchmark-context-fit-calibration-2026-07-04.md` is the seed report and must not be overwritten.

## Task 1: Capture Calibration JSON and Generate Report

**Files:**
- Create scratch: `$CALIBRATION_SCRATCH/capture_context_fit_calibration.py`
- Create: `docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md`

- [ ] **Step 1: Create the scratch directory**

Pick a scratch directory inside your session scratchpad (shown in your
environment) — do not use `/tmp`. Export `CALIBRATION_SCRATCH` to it and create
it. Shell state does not persist between the steps below, so re-export
`CALIBRATION_SCRATCH` (substituting the same absolute path) at the top of every
later command that references it.

```bash
export CALIBRATION_SCRATCH="<session-scratchpad>/benchmark-context-fit-calibration-pass-1"
mkdir -p "$CALIBRATION_SCRATCH"
```

Expected: exit 0.

- [ ] **Step 2: Write the capture script**

Create `$CALIBRATION_SCRATCH/capture_context_fit_calibration.py` with this exact content:

```python
import json
import os
import subprocess
from collections import Counter
from pathlib import Path


PASS_DATE = "2026-07-04"
PASS_LABEL = "pass-1"
TABLE_LIMIT = 20
REPORT = Path("docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md")

_scratch_env = os.environ.get("CALIBRATION_SCRATCH")
if not _scratch_env:
    raise SystemExit(
        "CALIBRATION_SCRATCH is unset; set it to a subdirectory of your session "
        "scratchpad (do not use /tmp) before running this script."
    )
SCRATCH = Path(_scratch_env).expanduser()
CONTEXT_FITS = (
    "direct-fit",
    "adjacent-fit",
    "method-fit",
    "blocked-fit",
    "generic-fallback",
    "out-of-context",
)
PROJECTS = {
    "multiple-myeloma": "~/d/cancer/cancer-types/multiple-myeloma",
    "post-acute-infection": "~/d/health/processes/post-acute-infection",
    "natural-systems": "~/d/natural-systems",
    "cbioportal": "~/d/cancer/data-sources/cbioportal",
}


def env() -> dict[str, str]:
    result = dict(os.environ)
    root = Path.cwd().resolve()
    prefix = f"{root / 'science/src'}:{root / 'science/model/src'}"
    existing = result.get("PYTHONPATH")
    result["PYTHONPATH"] = f"{prefix}:{existing}" if existing else prefix
    return result


def science_json(args: list[str], *, output: Path) -> dict:
    command = [
        "rtk",
        "uv",
        "run",
        "--frozen",
        "--project",
        "science",
        "science",
        *args,
        "--format",
        "json",
    ]
    completed = subprocess.run(
        command,
        cwd=Path.cwd(),
        env=env(),
        text=True,
        capture_output=True,
        check=True,
    )
    output.write_text(completed.stdout, encoding="utf-8")
    if completed.stderr.strip():
        output.with_suffix(".stderr.txt").write_text(completed.stderr, encoding="utf-8")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"failed to parse JSON from {' '.join(command)}: {exc}") from exc


def project_path(value: str) -> str:
    return str(Path(value).expanduser())


def project_specs() -> list[str]:
    specs: list[str] = []
    for label, root in PROJECTS.items():
        specs.extend(["--project", f"{label}={project_path(root)}"])
    return specs


def count_total(counts: dict[str, int]) -> int:
    missing = [fit for fit in CONTEXT_FITS if fit not in counts]
    if missing:
        raise SystemExit(f"context_fit_counts missing classes: {missing}")
    return sum(int(counts[fit]) for fit in CONTEXT_FITS)


def validate_tests_payload(label: str, payload: dict) -> None:
    total = int(payload["summary"]["test_plan_rows"])
    counted = count_total(payload["summary"]["context_fit_counts"])
    if total != counted:
        raise SystemExit(f"{label} tests count mismatch: rows={total} context_fit_total={counted}")


def validate_triage_payload(label: str, payload: dict) -> None:
    total = int(payload["summary"]["test_plan_rows"])
    counted = count_total(payload["summary"]["context_fit_counts"])
    if total != counted:
        raise SystemExit(f"{label} triage count mismatch: rows={total} context_fit_total={counted}")


def validate_gaps_payload(label: str, payload: dict) -> None:
    candidates = sum(len(row["candidate_benchmarks"]) for row in payload["benchmark_gaps"])
    counted = count_total(payload["summary"]["candidate_context_fit_counts"])
    if candidates != counted:
        raise SystemExit(f"{label} gaps count mismatch: candidates={candidates} context_fit_total={counted}")


def format_counts(counts: dict[str, int]) -> str:
    return " | ".join(str(counts[fit]) for fit in CONTEXT_FITS)


def table_header(label: str) -> list[str]:
    return [
        "",
        f"## {label}",
        "",
        "| Project | rows | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]


def candidate_rows(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for gap in payload["benchmark_gaps"]:
        for candidate in gap["candidate_benchmarks"]:
            rows.append(
                {
                    "entity_id": gap["entity_id"],
                    "benchmark_id": candidate["benchmark_id"],
                    "candidate_score": candidate["candidate_score"],
                    "candidate_mode": gap["candidate_mode"],
                    "context_fit": candidate["context_fit"],
                    "context_fit_warnings": list(candidate["context_fit_warnings"]),
                    "context_fit_reasons": list(candidate["context_fit_reasons"]),
                    "reason_notes": list(candidate["reason_notes"]),
                }
            )
    return rows


def warning_rows(gaps_by_project: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for project, payload in gaps_by_project.items():
        for row in candidate_rows(payload):
            if row["context_fit"] in {"direct-fit", "adjacent-fit"} and row["context_fit_warnings"]:
                rows.append({"project": project, **row})
    rows.sort(key=lambda row: (row["project"], row["context_fit"], row["benchmark_id"], row["entity_id"]))
    return rows


def _fit_benchmark_counts(gaps_by_project: dict[str, dict], fit: str) -> list[tuple[str, str, int]]:
    counter: Counter[tuple[str, str]] = Counter()
    for project, payload in gaps_by_project.items():
        for row in candidate_rows(payload):
            if row["context_fit"] == fit:
                counter[(project, row["benchmark_id"])] += 1
    return [(project, benchmark_id, count) for (project, benchmark_id), count in counter.most_common()]


def blocked_counts(gaps_by_project: dict[str, dict]) -> list[tuple[str, str, int]]:
    return _fit_benchmark_counts(gaps_by_project, "blocked-fit")


def fallback_counts(gaps_by_project: dict[str, dict]) -> list[tuple[str, str, int]]:
    return _fit_benchmark_counts(gaps_by_project, "generic-fallback")


def _benchmark_concentration(rows: list[tuple[str, str, int]]) -> tuple[float, int]:
    """Return (top-benchmark share, total candidates) over the full row set.

    Rows are (project, benchmark_id, count). Shares are computed per benchmark id
    across projects, so a single benchmark that recurs everywhere reads as
    concentrated. Runs over the untruncated candidate set, not a top-N slice.
    """
    total = sum(count for _, _, count in rows)
    if not total:
        return 0.0, 0
    by_benchmark: Counter[str] = Counter()
    for _project, benchmark_id, count in rows:
        by_benchmark[benchmark_id] += count
    return by_benchmark.most_common(1)[0][1] / total, total


def _class_total(payloads: dict[str, dict], key: str, fit: str) -> int:
    return sum(payload["summary"][key][fit] for payload in payloads.values())


def context_decision(
    tests_by_project: dict[str, dict],
    triage_by_project: dict[str, dict],
    gaps_by_project: dict[str, dict],
) -> list[str]:
    lines: list[str] = ["", "## Recommendation", ""]

    natural_direct = tests_by_project["natural-systems"]["summary"]["context_fit_counts"]["direct-fit"]
    direct_warnings = len(warning_rows(gaps_by_project))

    triage_total = sum(payload["summary"]["test_plan_rows"] for payload in triage_by_project.values())
    fallback = _class_total(triage_by_project, "context_fit_counts", "generic-fallback")
    fallback_ratio = fallback / triage_total if triage_total else 0.0

    concrete_total = sum(payload["summary"]["test_plan_rows"] for payload in tests_by_project.values())
    method_concrete = _class_total(tests_by_project, "context_fit_counts", "method-fit")
    method_ratio = method_concrete / concrete_total if concrete_total else 0.0

    fallback_conc, fallback_candidates = _benchmark_concentration(fallback_counts(gaps_by_project))
    blocked_conc, blocked_candidates = _benchmark_concentration(blocked_counts(gaps_by_project))

    # Precedence follows the design's Decision Rules: classifier regressions
    # first, then fallback dominance, then concentrated blockers, then the
    # expected method-fit steady state. "Dominant" is a >0.5 share. blocked-fit
    # drives a recommendation only when a few benchmark ids concentrate it (>=0.5
    # of blocked candidates), not merely because some blocked rows exist.
    if natural_direct:
        recommendation = "classifier tuning"
        reason = (
            f"`natural-systems` has {natural_direct} direct-fit concrete row(s); "
            "the seed baseline is zero, so this is a regression signal."
        )
    elif direct_warnings:
        recommendation = "classifier tuning"
        reason = f"{direct_warnings} direct/adjacent gap candidate(s) carry cross-context warnings."
    elif triage_total and fallback_ratio > 0.5 and fallback_conc >= 0.5:
        recommendation = "metadata/staging cleanup"
        reason = (
            f"generic-fallback dominates triage ({fallback}/{triage_total} = {fallback_ratio:.2f}) "
            f"and fallback candidates concentrate on a few benchmark ids "
            f"(top id = {fallback_conc:.2f} of {fallback_candidates}); prefer task-support/dataset "
            "metadata for those records over matcher changes."
        )
    elif triage_total and fallback_ratio > 0.5:
        recommendation = "presentation/report tuning"
        reason = (
            f"generic-fallback dominates triage ({fallback}/{triage_total} = {fallback_ratio:.2f}) "
            "but is spread across many benchmarks while concrete direct/method rows are already "
            "separated; prefer report presentation tuning over matcher changes."
        )
    elif blocked_candidates and blocked_conc >= 0.5:
        recommendation = "metadata/staging cleanup"
        reason = (
            f"blocked-fit gap candidates are concentrated (top id = {blocked_conc:.2f} of "
            f"{blocked_candidates}); resolve via task-support/access metadata before scorer changes."
        )
    elif method_ratio > 0.5:
        recommendation = "workflow promotion"
        reason = (
            f"method-fit dominates concrete non-fallback rows ({method_concrete}/{concrete_total} = "
            f"{method_ratio:.2f}); this is the expected actionable steady state, so no matcher change "
            "is indicated."
        )
    else:
        recommendation = "workflow promotion"
        reason = (
            "no classifier regression, fallback dominance, or concentrated blocker was detected; "
            "the report surfaces stable fields."
        )

    lines.extend(
        [
            f"Primary next slice: **{recommendation}**.",
            "",
            f"Reason: {reason}",
            "",
            "Signals:",
            f"- natural-systems direct-fit concrete rows: {natural_direct}",
            f"- direct/adjacent gap candidates with cross-context warnings: {direct_warnings}",
            f"- generic-fallback triage share: {fallback}/{triage_total} ({fallback_ratio:.2f})",
            f"- fallback candidate concentration: {fallback_conc:.2f} of {fallback_candidates}",
            f"- method-fit concrete share: {method_concrete}/{concrete_total} ({method_ratio:.2f})",
            f"- blocked-fit candidate concentration: {blocked_conc:.2f} of {blocked_candidates}",
        ]
    )
    return lines


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    gap_calibration = science_json(
        ["benchmark", "gap-calibration", "--commons", *project_specs()],
        output=SCRATCH / "gap-calibration.json",
    )

    tests_by_project: dict[str, dict] = {}
    triage_by_project: dict[str, dict] = {}
    gaps_by_project: dict[str, dict] = {}
    direct_gaps_by_project: dict[str, dict] = {}

    for label, root in PROJECTS.items():
        project_root = project_path(root)
        tests = science_json(
            [
                "benchmark",
                "tests",
                "--commons",
                "--exclude-fallback",
                "--state",
                "concrete",
                "--project-root",
                project_root,
            ],
            output=SCRATCH / f"{label}-tests-concrete.json",
        )
        triage = science_json(
            ["benchmark", "test-triage", "--commons", "--project-root", project_root],
            output=SCRATCH / f"{label}-test-triage.json",
        )
        gaps = science_json(
            ["benchmark", "gaps", "--commons", "--project-root", project_root],
            output=SCRATCH / f"{label}-gaps.json",
        )
        direct_gaps = science_json(
            [
                "benchmark",
                "gaps",
                "--commons",
                "--context-fit",
                "direct-fit",
                "--project-root",
                project_root,
            ],
            output=SCRATCH / f"{label}-gaps-direct-fit.json",
        )

        validate_tests_payload(label, tests)
        validate_triage_payload(label, triage)
        validate_gaps_payload(label, gaps)
        validate_gaps_payload(f"{label} direct-fit", direct_gaps)

        tests_by_project[label] = tests
        triage_by_project[label] = triage
        gaps_by_project[label] = gaps
        direct_gaps_by_project[label] = direct_gaps

    lines: list[str] = [
        f"# Benchmark Context-Fit Calibration {PASS_LABEL} - {PASS_DATE}",
        "",
        "## Commands",
        "",
        "- `science benchmark gap-calibration --commons --format json`",
        "- `science benchmark gaps --commons --format json`",
        "- `science benchmark gaps --commons --context-fit direct-fit --format json`",
        "- `science benchmark tests --commons --exclude-fallback --state concrete --format json`",
        "- `science benchmark test-triage --commons --format json`",
        "",
        "## Projects",
        "",
    ]
    for label, root in PROJECTS.items():
        lines.append(f"- `{label}`: `{root}`")

    aggregate = gap_calibration["aggregate"]
    lines.extend(
        [
            "",
            "## Aggregate Gap Calibration",
            "",
            f"- gap rows: `{aggregate['gap_rows']}`",
            f"- candidate rows: `{aggregate['candidate_rows']}`",
            f"- entity-specific candidate rows: `{aggregate['entity_specific_candidate_rows']}`",
            f"- fallback candidate rows: `{aggregate['fallback_candidate_rows']}`",
            f"- fallback candidate ratio: `{aggregate['fallback_candidate_ratio']}`",
            f"- fallback concentration warning: `{aggregate['fallback_concentration_warning']}`",
            "",
            "Top fallback benchmarks:",
        ]
    )
    for row in aggregate["top_fallback_benchmark_shares"]:
        lines.append(f"- `{row['benchmark_id']}`: {row['count']} ({row['share']})")

    lines.extend(table_header("Concrete Non-Fallback Test Rows"))
    for label, payload in tests_by_project.items():
        counts = payload["summary"]["context_fit_counts"]
        lines.append(f"| {label} | {payload['summary']['test_plan_rows']} | {format_counts(counts)} |")

    lines.extend(table_header("Full Triage Rows"))
    for label, payload in triage_by_project.items():
        counts = payload["summary"]["context_fit_counts"]
        lines.append(f"| {label} | {payload['summary']['test_plan_rows']} | {format_counts(counts)} |")

    lines.extend(table_header("Unfiltered Gap Candidates"))
    for label, payload in gaps_by_project.items():
        counts = payload["summary"]["candidate_context_fit_counts"]
        candidate_total = sum(len(row["candidate_benchmarks"]) for row in payload["benchmark_gaps"])
        lines.append(f"| {label} | {candidate_total} | {format_counts(counts)} |")

    lines.extend(
        [
            "",
            "## Direct-Fit Gap Filter Check",
            "",
            "| Project | gap rows | candidate rows | direct-fit candidates |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for label, payload in direct_gaps_by_project.items():
        candidate_total = sum(len(row["candidate_benchmarks"]) for row in payload["benchmark_gaps"])
        direct_total = payload["summary"]["candidate_context_fit_counts"]["direct-fit"]
        lines.append(f"| {label} | {len(payload['benchmark_gaps'])} | {candidate_total} | {direct_total} |")

    lines.extend(["", "## Suspicious Direct Or Adjacent Rows", ""])
    warnings = warning_rows(gaps_by_project)
    if warnings:
        lines.extend(
            [
                "| Project | context_fit | benchmark | entity | warnings |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in warnings[:TABLE_LIMIT]:
            warnings_text = ", ".join(row["context_fit_warnings"])
            lines.append(
                f"| {row['project']} | {row['context_fit']} | `{row['benchmark_id']}` | `{row['entity_id']}` | {warnings_text} |"
            )
        if len(warnings) > TABLE_LIMIT:
            lines.extend(["", f"_Showing top {TABLE_LIMIT} of {len(warnings)} warned rows._"])
    else:
        lines.append("No direct-fit or adjacent-fit candidates carried context-fit warnings.")

    lines.extend(["", "## Blocked-Fit Concentration", ""])
    blocked = blocked_counts(gaps_by_project)
    if blocked:
        lines.extend(["| Project | benchmark | blocked-fit candidates |", "| --- | --- | ---: |"])
        for project, benchmark_id, count in blocked[:TABLE_LIMIT]:
            lines.append(f"| {project} | `{benchmark_id}` | {count} |")
        if len(blocked) > TABLE_LIMIT:
            lines.extend(
                ["", f"_Showing top {TABLE_LIMIT} of {len(blocked)} (project, benchmark) blocked-fit pairs._"]
            )
    else:
        lines.append("No blocked-fit gap candidates were present.")

    lines.extend(["", "## Generic Fallback Concentration", ""])
    fallback = fallback_counts(gaps_by_project)
    if fallback:
        lines.extend(["| Project | benchmark | generic-fallback candidates |", "| --- | --- | ---: |"])
        for project, benchmark_id, count in fallback[:TABLE_LIMIT]:
            lines.append(f"| {project} | `{benchmark_id}` | {count} |")
        if len(fallback) > TABLE_LIMIT:
            lines.extend(
                ["", f"_Showing top {TABLE_LIMIT} of {len(fallback)} (project, benchmark) generic-fallback pairs._"]
            )
    else:
        lines.append("No generic-fallback gap candidates were present.")

    notices = gap_calibration["commons_notices"]
    lines.extend(["", "## Commons Notices", ""])
    if notices:
        for notice in notices:
            lines.append(f"- `{notice['label']}`: {notice['notice']}")
    else:
        lines.append("No commons notices were reported.")

    lines.extend(context_decision(tests_by_project, triage_by_project, gaps_by_project))
    lines.extend(
        [
            "",
            "## Raw Snapshots",
            "",
            "Raw JSON snapshots were written to the session scratch directory and are intentionally not committed.",
            "",
        ]
    )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the capture script**

Run:

```bash
export CALIBRATION_SCRATCH="<session-scratchpad>/benchmark-context-fit-calibration-pass-1"
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python "$CALIBRATION_SCRATCH/capture_context_fit_calibration.py"
```

Expected output:

```text
docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md
```

Expected side effects:

- `$CALIBRATION_SCRATCH/gap-calibration.json`
- one `*-tests-concrete.json`, `*-test-triage.json`, `*-gaps.json`, and `*-gaps-direct-fit.json` file per project;
- `docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md`.

If the command fails with a JSON count mismatch, do not edit the report by hand. Inspect the failing payload and decide whether the bug is in the command output or the validation script.

## Task 2: Review and Validate the Generated Report

**Files:**
- Read: `docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md`
- Read: `$CALIBRATION_SCRATCH/*.json`
- Modify only if the report generator has a bug: `$CALIBRATION_SCRATCH/capture_context_fit_calibration.py`

- [ ] **Step 1: Inspect the generated report**

Run:

```bash
rtk sed -n '1,260p' docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md
```

Expected:

- report has command, project, aggregate gap calibration, concrete tests, full triage, unfiltered gap candidates, direct-fit filter check, suspicious rows, concentration, commons notices, recommendation, and raw snapshot sections;
- all context-fit count tables have seven numeric columns after `Project`: `rows` plus the six context-fit classes;
- there are no hand-filled incomplete cells.

- [ ] **Step 2: Verify report path and completion hygiene**

Run:

```bash
rtk uv run --frozen --project science python - <<'PY'
from pathlib import Path

path = Path("docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md")
text = path.read_text(encoding="utf-8")
bad = ["TB" + "D", "TO" + "DO", "FIX" + "ME", "/mnt/" + "ssd", "/home/" + "keith"]
hits = [token for token in bad if token in text]
if hits:
    raise SystemExit(f"unexpected report hygiene hits: {hits}")
print("report hygiene check passed")
PY
```

Expected output:

```text
report hygiene check passed
```

- [ ] **Step 3: Run an independent count reconciliation check**

Run:

```bash
export CALIBRATION_SCRATCH="<session-scratchpad>/benchmark-context-fit-calibration-pass-1"
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python - <<'PY'
import json
import os
from pathlib import Path

scratch = Path(os.environ["CALIBRATION_SCRATCH"]).expanduser()
fits = ("direct-fit", "adjacent-fit", "method-fit", "blocked-fit", "generic-fallback", "out-of-context")

for path in sorted(scratch.glob("*-tests-concrete.json")):
    payload = json.loads(path.read_text())
    assert sum(payload["summary"]["context_fit_counts"][fit] for fit in fits) == payload["summary"]["test_plan_rows"], path

for path in sorted(scratch.glob("*-test-triage.json")):
    payload = json.loads(path.read_text())
    assert sum(payload["summary"]["context_fit_counts"][fit] for fit in fits) == payload["summary"]["test_plan_rows"], path

for path in sorted(scratch.glob("*-gaps.json")) + sorted(scratch.glob("*-gaps-direct-fit.json")):
    payload = json.loads(path.read_text())
    candidate_total = sum(len(row["candidate_benchmarks"]) for row in payload["benchmark_gaps"])
    assert sum(payload["summary"]["candidate_context_fit_counts"][fit] for fit in fits) == candidate_total, path

print("context-fit count reconciliation passed")
PY
```

Expected output:

```text
context-fit count reconciliation passed
```

- [ ] **Step 4: Confirm git sees only the report**

Run:

```bash
rtk git status --short
```

Expected: only the generated report is untracked or modified:

```text
?? docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md
```

If source files changed, stop and inspect them before committing.

## Task 3: Commit the Calibration Report

**Files:**
- Add: `docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md`

- [ ] **Step 1: Stage only the report**

Run:

```bash
rtk git add docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md
```

Expected: one report file staged.

- [ ] **Step 2: Review the staged diff**

Run:

```bash
rtk git diff --cached -- docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md
```

Expected:

- only the pass-1 report is staged;
- no raw JSON snapshots are staged;
- report includes a concrete recommendation.

- [ ] **Step 3: Commit the report**

Run:

```bash
rtk git commit -m "docs: record benchmark context-fit calibration pass"
```

Expected: commit succeeds.

- [ ] **Step 4: Final status**

Run:

```bash
rtk git status --short --branch
```

Expected:

```text
* benchmark-context-fit-calibration
clean -- nothing to commit
```

## Task 4: Handoff Decision

**Files:**
- Read: `docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md`

- [ ] **Step 1: Extract the report recommendation**

Run:

```bash
rtk rg -n "Primary next slice|Reason:|Aggregate generic-fallback share" docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md
```

Expected: three lines identifying the recommended next slice and its reason.

- [ ] **Step 2: Present the next-slice choice**

In the final handoff, report:

- report path;
- commit id;
- primary next slice from the report;
- whether any command or JSON validation failed;
- whether source code was unchanged.

Do not merge to `main` until the report has been reviewed.
