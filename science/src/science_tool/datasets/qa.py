# science/src/science_tool/datasets/qa.py
"""Thin `science datasets qa` wrapper: resolve a package path, run the science_qa engine
in-process, and apply the build-fatal exit-code policy. No QA logic lives here."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from science_tool.datasets.validate import DESCRIPTOR_NAMES

if TYPE_CHECKING:
    from science_qa.runner import PackageRunResult


def _resolve_descriptor(path: Path) -> Path:
    """A package directory or a descriptor file → the descriptor file. Fail early."""
    path = Path(path)
    if path.is_file() and path.name in DESCRIPTOR_NAMES:
        return path
    if path.is_dir():
        for name in DESCRIPTOR_NAMES:
            candidate = path / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"no datapackage descriptor at {path}")


def run_package_qa(path: Path, *, resource: str | None = None,
                   report_dir: Path | None = None, runknobs: Path | None = None,
                   no_strict: bool = False) -> tuple["PackageRunResult", int]:
    """Resolve, run, and compute the exit code. Raises (CompileError / RunnerError /
    ValueError / FileNotFoundError) on bad input — the CLI maps those to exit 2."""
    from science_qa.runner import run_qa_package

    descriptor = _resolve_descriptor(Path(path))
    resources = [resource] if resource else None
    result = run_qa_package(descriptor, report_dir=report_dir, resources=resources,
                            runknobs_path=runknobs)
    code = 1 if (result.package_structural_failed and not no_strict) else 0
    return result, code


def render_resource_line(outcome) -> str:
    n_struct = (sum(1 for f in outcome.result.flags if f.severity == "structural")
                if outcome.result else 0)
    n_dist = (sum(1 for f in outcome.result.flags if f.severity == "distribution")
              if outcome.result else 0)
    label = "FAIL" if outcome.status == "fail" else outcome.status
    detail = outcome.reason if outcome.reason else f"{n_struct} structural, {n_dist} distribution"
    return f"{outcome.name:<28} {label:<8} {detail}"


def render_package_summary(result: PackageRunResult) -> str:
    n_fail = sum(1 for o in result.outcomes if o.status == "fail")
    n_blocked = sum(1 for o in result.outcomes if o.status == "blocked")
    n_skipped = sum(1 for o in result.outcomes if o.status == "skipped")
    verdict = "FAIL" if result.package_structural_failed else "ok"
    return (f"--\npackage: {verdict}  "
            f"({n_fail} structural; {n_blocked} blocked, {n_skipped} skipped)")
