from __future__ import annotations

import json
from pathlib import Path

import yaml

from science_tool.qa_audit.verdicts import FlagDisposition

VALID_DISPOSITIONS = {"open", "investigating", "addressed", "accepted-real", "wont-fix", "resolved"}


class QAManifestError(Exception):
    """Raised on an invalid disposition value (fail early; don't treat as open)."""


def _substrate_suffix(name: str, prefix: str) -> str | None:
    if name == prefix:
        return ""
    if name.startswith(prefix + ":"):
        return name[len(prefix) + 1 :]
    return None


def load_qa_artifacts(manifest_path: Path) -> tuple[bool, list[FlagDisposition]]:
    """Discover QA artifacts via a run's datapackage manifest.

    Selects resources named `qa_report` / `qa_report:<substrate>`, pairs each
    with its `qa_dispositions[:<substrate>]` counterpart, and returns
    (has_report, [FlagDisposition...]) aggregated across substrates. Manifests
    are YAML on disk (datapackage.yaml); JSON is also accepted.
    """
    text = manifest_path.read_text(encoding="utf-8")
    manifest = yaml.safe_load(text) or {}
    base = manifest_path.parent
    resources = manifest.get("resources", []) or []

    reports: dict[str, Path] = {}
    dispositions: dict[str, Path] = {}
    for res in resources:
        name = str(res.get("name", ""))
        sub = _substrate_suffix(name, "qa_report")
        if sub is not None:
            reports[sub] = base / res["path"]
            continue
        sub = _substrate_suffix(name, "qa_dispositions")
        if sub is not None:
            dispositions[sub] = base / res["path"]

    if not reports:
        return (False, [])

    flags: list[FlagDisposition] = []
    for substrate, report_path in sorted(reports.items()):
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        dist_ids = [f["flag_id"] for f in payload.get("flags", []) if f.get("severity") == "distribution"]

        disp_map: dict[str, dict] = {}
        disp_path = dispositions.get(substrate)
        if disp_path and disp_path.exists():
            loaded = yaml.safe_load(disp_path.read_text(encoding="utf-8")) or {}
            for entry in loaded.get("dispositions", []) or []:
                disp_map[entry["flag_id"]] = entry

        for flag_id in dist_ids:
            entry = disp_map.get(flag_id, {})
            disposition = str(entry.get("disposition", "open"))
            if disposition not in VALID_DISPOSITIONS:
                raise QAManifestError(f"invalid disposition {disposition!r} for {flag_id!r}")
            flags.append(FlagDisposition(disposition=disposition, change=str(entry.get("change", "") or "")))

    return (True, flags)


def load_qa_coverage(manifest_path: Path) -> dict | None:
    """Aggregate the coverage block(s) from a run's qa_report resources.

    Walks the same `qa_report`/`qa_report:<substrate>` resources as load_qa_artifacts and
    sums `ran` + `executable_denominator` across substrates. Returns None when there is no
    qa_report or no coverage block present (older reports predate the block).
    """
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    base = manifest_path.parent
    ran = denom = 0
    found = False
    for res in manifest.get("resources", []) or []:
        if _substrate_suffix(str(res.get("name", "")), "qa_report") is None:
            continue
        payload = json.loads((base / res["path"]).read_text(encoding="utf-8"))
        cov = payload.get("coverage")
        if isinstance(cov, dict):
            found = True
            ran += int(cov.get("ran", 0))
            denom += int(cov.get("executable_denominator", 0))
    return {"ran": ran, "executable_denominator": denom} if found else None
