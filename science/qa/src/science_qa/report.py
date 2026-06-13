# science/qa/src/science_qa/report.py
from __future__ import annotations

import json
from pathlib import Path

from science_qa.coverage import Coverage
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag


def _sorted(flags: list[Flag]) -> list[Flag]:
    return sorted(flags, key=lambda f: f.flag_id)


def write_reports(flags: list[Flag], *, report_dir: Path, rows_checked: int, coverage: Coverage) -> None:
    """Write qa_report.json (immutable flag ledger + coverage) and qa_report.md.

    Deterministic: output depends only on the sorted flag set, rows_checked, and the
    coverage block — never on wall-clock — so re-run-and-diff stays clean.
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    ordered = _sorted(flags)
    structural = [f for f in ordered if f.severity == SEVERITY_STRUCTURAL]
    distribution = [f for f in ordered if f.severity == SEVERITY_DISTRIBUTION]
    cov = coverage.to_dict()

    payload = {
        "rows_checked": rows_checked,
        "structural_count": len(structural),
        "distribution_count": len(distribution),
        "flags": [f.to_dict() for f in ordered],
        "coverage": cov,
    }
    (report_dir / "qa_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# QA / sanity-check report",
        "",
        f"- Rows checked: {rows_checked}",
        f"- Structural flags: **{len(structural)}** · Distribution flags: **{len(distribution)}**",
        "",
        "## Flagged issues",
        "### 🔴 Structural (ingest/derive bugs — build-fatal)",
    ]
    lines += [f"- `{f.flag_id}` — {f.message}" for f in structural] or ["- none"]
    lines += ["", "### 🟡 Distribution (domain review — not fatal)"]
    lines += [f"- `{f.flag_id}` — {f.message}" for f in distribution] or ["- none"]
    lines += [
        "",
        "## Coverage",
        f"- Executable denominator: {cov['executable_denominator']} "
        f"(ran {cov['ran']} · empty {cov['empty']} · blocked {cov['blocked']} · n/a {cov['not-applicable']})",
        f"- Declared-but-unconfigured families: {', '.join(cov['unconfigured_families']) or 'none'}",
        f"- Narrow-checking signal: {', '.join(cov['narrow_signal']) or 'none'}",
        "",
    ]
    (report_dir / "qa_report.md").write_text("\n".join(lines), encoding="utf-8")
