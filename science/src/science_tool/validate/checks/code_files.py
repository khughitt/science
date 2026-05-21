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

from science_tool.code.classification import classify_code_file
from science_tool.code.git import last_content_change_date
from science_tool.code.hardcoded_paths import find_hardcoded_paths
from science_tool.code.lifecycle import CODE_FILE_STATUSES, ORPHAN_GATING_EXEMPT_STATUSES
from science_tool.code.metadata import parse_code_metadata
from science_tool.code.workflow_refs import find_workflow_references
from science_tool.graph.storage_adapters.code import CodeAdapter
from science_tool.paths import resolve_paths
from science_tool.tasks import known_task_ids
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, rel_path: str, message: str, rule: str, *, line: int | None = None) -> Result:
    return Result(severity, Path(rel_path), line, message, rule, None)


def _is_workflow_file(rel_path: str) -> bool:
    name = Path(rel_path).name
    return name == "Snakefile" or name.endswith(".smk")


@Check(section="code files...", order=6)
def check_code_files(ctx: ValidateContext) -> Iterator[Result]:
    paths = resolve_paths(ctx.project_root)
    adapter = CodeAdapter(
        code_roots=paths.code_roots,
        repo_root=ctx.project_root,
        excludes=paths.code_excludes,
    )
    refs = adapter.discover(ctx.project_root)
    if not refs:
        return
    task_ids = known_task_ids(paths.tasks_dir)
    code_root_names = tuple(
        root.relative_to(ctx.project_root).as_posix() for root in paths.code_roots
    )
    workflow_files = [
        ctx.project_root / ref.path for ref in refs if _is_workflow_file(ref.path)
    ]
    workflow_refs = find_workflow_references(
        workflow_files, project_root=ctx.project_root, code_root_names=code_root_names
    )
    hardcoded_prefixes = paths.hardcoded_path_patterns
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
        for finding in find_hardcoded_paths(text, extra_prefixes=hardcoded_prefixes):
            yield _result(
                Severity.WARN,
                ref.path,
                f"Hardcoded path {finding.pattern!r} at line {finding.line_number}: {finding.line}",
                "code.hardcoded-path",
                line=finding.line_number,
            )
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
        yield from _check_valid_block(ctx, ref.path, metadata.fields, task_ids, text, workflow_refs)


def _check_valid_block(
    ctx: ValidateContext,
    rel_path: str,
    fields: dict[str, object],
    task_ids: set[str],
    text: str,
    workflow_refs: dict[str, list[str]],
) -> Iterator[Result]:
    status = str(fields.get("status") or "")
    if status not in CODE_FILE_STATUSES:
        expected = ", ".join(sorted(CODE_FILE_STATUSES))
        message = (
            f"Code-file block has invalid status {status!r}; expected one of {expected}"
            if status
            else f"Code-file block missing required `status` field (expected one of {expected})"
        )
        yield _result(Severity.WARN, rel_path, message, "code.metadata-gap")

    raw_task_ids = fields.get("task_ids")
    if isinstance(raw_task_ids, list):
        for entry in raw_task_ids:
            task_id = str(entry)
            if task_id not in task_ids:
                yield _result(
                    Severity.WARN,
                    rel_path,
                    f"Code-file references unknown task id {task_id!r} (no such task in tasks/)",
                    "code.unresolved-task",
                )
    elif raw_task_ids is not None:
        # Present but not a list (e.g. `task_ids: t999` -> a scalar string):
        # a malformed field, not "no tasks". Flag it rather than silently drop it.
        yield _result(
            Severity.WARN,
            rel_path,
            f"Code-file `task_ids` must be a list, got {type(raw_task_ids).__name__}",
            "code.metadata-gap",
        )

    if last_content_change_date(rel_path, repo_root=ctx.project_root) is None:
        yield _result(
            Severity.WARN,
            rel_path,
            (
                f"Code-file has a valid block but no committed content date "
                f"(untracked or never committed); freshness will not see it: {rel_path}"
            ),
            "code.uncommitted",
        )

    raw_decision_bearing = fields.get("decision_bearing")
    declared_decision_bearing = (
        raw_decision_bearing if isinstance(raw_decision_bearing, bool) else None
    )
    classification = classify_code_file(
        rel_path,
        text,
        declared_decision_bearing=declared_decision_bearing,
        workflow_referenced=rel_path in workflow_refs,
    )
    if (
        classification.classification == "orphaned-executable"
        and classification.effective_decision_bearing
        and status not in ORPHAN_GATING_EXEMPT_STATUSES
    ):
        yield _result(
            Severity.WARN,
            rel_path,
            f"Decision-bearing executable not referenced by any workflow (orphaned): {rel_path}",
            "code.orphaned-executable",
        )
