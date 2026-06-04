"""Port of validate.sh "Checking paper summaries..." block.

Checks paper entities under both ``entities/papers/`` (new layout) and the
legacy ``$DOC_DIR/background/papers/`` root for template section conformance
and dataset-ref validity.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.entities import resolve_path_policy
from science_tool.validate._helpers import entity_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "papers", None)


@Check(section="paper summaries...", order=7)
def check_papers(ctx: ValidateContext) -> Iterator[Result]:
    papers_root = resolve_path_policy("paper").root
    yield _result(
        Severity.INFO,
        papers_root.as_posix(),
        f"Paper summary structure is checked in {papers_root.as_posix()}/",
    )
    yield from _check_paper_dataset_refs(ctx)


def _check_paper_dataset_refs(ctx: ValidateContext) -> Iterator[Result]:
    """Warn on free-text paper `datasets:` entries.

    The canonical commons paper schema requires `datasets` items to be
    `dataset:`-prefixed refs, but a free-text value is tolerated project-locally
    and only rejected at `commons promote --apply` — after the summary is
    written and committed. Flagging it during validate/pre-commit lets the
    author fix it before promotion (fb-2026-05-29-006).
    """
    for fm in entity_frontmatters(ctx):
        if (fm.get("kind") or fm.get("type")) != "paper":
            continue
        datasets = fm.get("datasets")
        if not isinstance(datasets, list):
            continue
        paper_id = fm.get("id") or fm.get("_path")
        for entry in datasets:
            if isinstance(entry, str) and not entry.startswith("dataset:"):
                yield _result(
                    Severity.WARN,
                    fm.get("_path"),
                    f"paper {paper_id} datasets entry {entry!r} is free-text; commons "
                    "promotion requires 'dataset:'-prefixed refs (the canonical paper "
                    "schema rejects free-text). Convert it before promoting.",
                )
