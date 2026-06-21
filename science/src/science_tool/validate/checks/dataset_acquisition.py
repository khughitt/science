"""Dataset acquisition check: an acquired dataset must carry a data pointer.

Acquisition lifecycle lives on `status` (candidate = not yet acquired); the data
pointer is `datapackage` OR `local_path` (the single-file escape hatch). Reads raw
frontmatter like dataset_taxonomy, re-enforcing the rule with a friendly message.
See docs/plans/2026-06-21-dataset-catalog-cli-design.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def evaluate_dataset_acquisition(datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    """Pure core: `datasets` are raw frontmatter dicts (each with `_path`)."""
    for fm in datasets:
        if (fm.get("kind") or fm.get("type")) != "dataset":
            continue
        if fm.get("status") == "candidate":
            continue  # not-yet-acquired: pointer optional
        if fm.get("datapackage") or fm.get("local_path"):
            continue  # acquired and pointed
        ident = fm.get("id", "?")
        path = fm.get("_path")
        yield Result(
            Severity.ERROR,
            Path(path) if path else None,
            None,
            f"{ident}: acquired dataset (status={fm.get('status')!r}) has no "
            f"datapackage or local_path; set status: candidate if not yet acquired, "
            f"or add a datapackage/local_path pointer",
            "dataset.acquired-without-pointer",
            None,
        )


@Check(section="dataset acquisition", order=32)
def check_dataset_acquisition(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_dataset_acquisition(dataset_frontmatters(ctx))
