"""Walk declared code roots and flag unregistered / malformed code files.

Every finding here is WARN or INFO — never ERROR — so Tier 0 (report-only, the
default) never blocks `science validate`. The `--fail-on` gate ladder
(validate/gates.py) promotes selected rules to a nonzero exit when a project
opts in. Findings travel as validation Results, never as `graph materialize`
preconditions (umbrella design §6 fragility firewall).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.code.metadata import parse_code_metadata
from science_tool.graph.storage_adapters.code import CodeAdapter
from science_tool.paths import resolve_paths
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, rel_path: str, message: str, rule: str) -> Result:
    return Result(severity, Path(rel_path), None, message, rule, None)


@Check(section="code files...", order=6)
def check_code_files(ctx: ValidateContext) -> Iterator[Result]:
    paths = resolve_paths(ctx.project_root)
    adapter = CodeAdapter(
        code_roots=paths.code_roots,
        repo_root=ctx.project_root,
        excludes=paths.code_excludes,
    )
    refs = adapter.discover(ctx.project_root)
    for ref in refs:
        abs_path = ctx.project_root / ref.path
        try:
            text = abs_path.read_text(errors="replace")
        except OSError as exc:
            # Discovered but now unreadable (deleted/renamed between discovery
            # and read, or a permission/IO error). `validate` runs every check
            # in one pass with no per-check exception guard, so a raw OSError
            # here would abort the whole run. Surface it as a finding rather
            # than crashing or silently dropping the file (ungated: not in any
            # gate tier).
            yield _result(
                Severity.WARN,
                ref.path,
                f"Could not read code file {ref.path}: {exc}",
                "code.unreadable",
            )
            continue
        metadata = parse_code_metadata(text)
        if not metadata.present:
            yield _result(
                Severity.WARN,
                ref.path,
                f"Code artifact has no science:code block: {ref.path}",
                "code.ghost",
            )
            continue
        if metadata.fields is None:
            yield _result(
                Severity.WARN,
                ref.path,
                f"Malformed science:code block in {ref.path}: {metadata.error}",
                "code.malformed-block",
            )
            continue
        # Valid block: per-field completeness checks are added in Task 5.
