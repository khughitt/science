"""Warn when a project's committed science.yaml id diverges from the registry.

`ensure_registered` records each project's id in the global registry from the
working-tree value at graph-build time, so the registry can silently drift from
the committed science.yaml id (e.g. registry says `cancer-meta` while the
committed manifest says `meta`). The divergence otherwise surfaces only much
later as a cross-project peer check crash. Surfacing it as a validate finding
catches it at validate/health/pre-commit time. See fb-2026-05-29-005.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.data_root import PROJECT_CONFIG_FILENAME
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, message: str) -> Result:
    return Result(severity, Path(PROJECT_CONFIG_FILENAME), None, message, "registration", None)


@Check(section="registration consistency...", order=2)
def check_registration_consistency(ctx: ValidateContext) -> Iterator[Result]:
    committed_id = ctx.manifest.get("id")
    if not committed_id:
        return  # no committed id to compare against the registry

    from science_tool.registry.config import get_default_config_path, load_global_config

    cfg = load_global_config()
    for project in cfg.projects:
        try:
            registered_path = Path(project.path).expanduser().resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if registered_path != ctx.project_root:
            continue
        if project.id is not None and project.id != committed_id:
            yield _result(
                Severity.WARN,
                f"science.yaml declares id {committed_id!r} but the global registry "
                f"({get_default_config_path()}) records id {project.id!r} for this project; "
                "peers and rebuilds may use the stale registry id. Reconcile the registry "
                "(edit it, or re-run a graph build) so it matches the committed id.",
            )
        else:
            yield _result(Severity.INFO, f"registry id matches science.yaml id ({committed_id})")
        return
