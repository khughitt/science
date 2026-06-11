from __future__ import annotations

import json
from pathlib import Path

from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag


def _sorted(flags: list[Flag]) -> list[Flag]:
    return sorted(flags, key=lambda f: f.flag_id)


def write_reports(flags: list[Flag], *, report_dir: Path, rows_checked: int) -> None:
    """Write qa_report.json (immutable flag ledger) and qa_report.md.

    Deterministic: output depends only on the flag set (sorted by id) and
    rows_checked — never on wall-clock — so re-run-and-diff stays clean.
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    ordered = _sorted(flags)
    structural = [f for f in ordered if f.severity == SEVERITY_STRUCTURAL]
    distribution = [f for f in ordered if f.severity == SEVERITY_DISTRIBUTION]

    payload = {
        "rows_checked": rows_checked,
        "structural_count": len(structural),
        "distribution_count": len(distribution),
        "flags": [f.to_dict() for f in ordered],
    }
    (report_dir / "qa_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

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
    lines.append("")
    (report_dir / "qa_report.md").write_text("\n".join(lines), encoding="utf-8")
