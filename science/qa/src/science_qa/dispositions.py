from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DISPOSITIONS_FILENAME = "qa_dispositions.yaml"
VALID_DISPOSITIONS = {"open", "investigating", "addressed", "accepted-real", "wont-fix", "resolved"}


@dataclass
class MergeStats:
    added: int = 0
    resolved: int = 0
    unchanged: int = 0


def reconcile_dispositions(report_dir: Path, distribution_flag_ids: list[str]) -> MergeStats:
    """Create-if-absent / merge-by-flag_id. Never overwrites a filled entry.

    This file is analyst-owned and is NEVER a declared Snakemake rule output —
    callers write it outside any strict-gate rule's output set so a failed build
    cannot delete hand-entered dispositions.
    """
    path = report_dir / DISPOSITIONS_FILENAME
    existing: dict[str, dict] = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for entry in loaded.get("dispositions", []) or []:
            existing[entry["flag_id"]] = entry

    current = set(distribution_flag_ids)
    stats = MergeStats()
    merged: dict[str, dict] = {}

    for flag_id in current:
        existing_entry = existing.get(flag_id)
        if existing_entry is not None and existing_entry.get("disposition") != "resolved":
            merged[flag_id] = existing_entry
            stats.unchanged += 1
        else:
            merged[flag_id] = {"flag_id": flag_id, "disposition": "open", "note": "", "change": ""}
            stats.added += 1

    for flag_id, entry in existing.items():
        if flag_id not in current:
            merged[flag_id] = {**entry, "disposition": "resolved"}
            stats.resolved += 1

    report_dir.mkdir(parents=True, exist_ok=True)
    ordered = [merged[k] for k in sorted(merged)]
    path.write_text(yaml.safe_dump({"dispositions": ordered}, sort_keys=True), encoding="utf-8")
    return stats
