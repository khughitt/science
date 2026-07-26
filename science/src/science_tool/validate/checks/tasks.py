r"""Port of validate.sh task queue validation block.

echo "Checking task queue..."

if [ ! -f "$TASKS_DIR/active.md" ]; then
    warn "$TASKS_DIR/active.md not found (use /science:tasks to create)"
else
    info "$TASKS_DIR/active.md exists"
    task_check_result=$(XREF_TASKS="$TASKS_DIR" python3 <<'PYEOF' 2>/dev/null
import os
import re
from pathlib import Path

tasks_dir = Path(os.environ["XREF_TASKS"])
header_any = re.compile(r"^##\s+\[([^\]]+)\]\s+(.+)$")
header_valid = re.compile(r"^##\s+\[(t[0-9]{3,})\]\s+(.+)$")
task_ref = re.compile(r"\bt\d+[A-Za-z.]*\b")
local_parent = re.compile(r"^task:t[0-9]{3,}$")
required = ("aspects", "priority", "status", "created")
ref_fields = {"related", "blocked-by", "blocked_by", "parent"}


def display_path(path):
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def split_list_value(raw):
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return [item.strip() for item in value[1:-1].split(",") if item.strip()]
    return [value] if value else []


paths = [tasks_dir / "active.md"]
done_dir = tasks_dir / "done"
if done_dir.is_dir():
    paths.extend(sorted(done_dir.glob("*.md")))

declared = set()
blocks = []
for path in paths:
    if not path.is_file():
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    current = None
    for line_no, line in enumerate(lines, start=1):
        any_match = header_any.match(line)
        if any_match:
            task_id = any_match.group(1)
            valid_match = header_valid.match(line)
            if valid_match is None:
                print(
                    f"ERROR:Invalid task id '{task_id}' in {display_path(path)}: task ids must match tNNN. "
                    "Use parent: task:t001 for fragments or subtasks."
                )
                current = None
                continue
            current = {"path": display_path(path), "line": line_no, "id": task_id, "lines": []}
            blocks.append(current)
            declared.add(task_id)
            continue
        if current is not None:
            current["lines"].append(line)

seen = {}
for task_id in sorted(declared):
    count = sum(1 for block in blocks if block["id"] == task_id)
    if count > 1:
        seen[task_id] = count
for task_id in sorted(seen):
    print(f"ERROR:duplicate task IDs in active.md: {task_id}")

for block in blocks:
    fields = {}
    for line in block["lines"]:
        match = re.match(r"^-\s+([\w-]+):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    for field in required:
        if field not in fields:
            print(f"ERROR:task {block['id']} missing required field: {field}")
    parent = fields.get("parent", "")
    if parent and not local_parent.match(parent):
        print(f"ERROR:task {block['id']} parent must be local task ref like task:t001")
    refs_to_check = []
    for field_name in ref_fields:
        for value in split_list_value(fields.get(field_name, "")):
            refs_to_check.append(value)
    for raw_ref in refs_to_check:
        if ":" in raw_ref:
            if not raw_ref.startswith("task:"):
                continue
            raw_ref = raw_ref.split(":", 1)[1]
        for match in task_ref.finditer(raw_ref):
            raw = match.group(0)
            if raw in declared:
                continue
            if re.fullmatch(r"t[0-9]{3,}", raw):
                print(f"ERROR:stale task ref '{raw}' in {block['path']}")
            elif raw.startswith("t"):
                print(f"ERROR:stale or invalid task ref '{raw}' in {block['path']}")

if blocks:
    print(f"OK:{len(blocks)}")
else:
    print("EMPTY:0")
PYEOF
) || task_check_result="SKIP"

    if [ "$task_check_result" = "SKIP" ]; then
        warn "Task queue check skipped (python3 error)"
    else
        task_count=0
        while IFS=: read -r status detail; do
            case "$status" in
                ERROR)
                    error "$detail"
                    ;;
                OK)
                    task_count="$detail"
                    ;;
                EMPTY)
                    task_count=0
                    ;;
            esac
        done <<< "$task_check_result"
        if [ "$task_count" = "0" ]; then
            info "  no tasks in active.md"
        else
            info "  ${task_count} task(s) validated"
        fi
    fi
fi
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

HEADER_ANY = re.compile(r"^##\s+\[([^\]]+)\]\s+(.+)$")
HEADER_VALID = re.compile(r"^##\s+\[(t[0-9]{3,})\]\s+(.+)$")
TASK_REF = re.compile(r"\bt\d+[A-Za-z.]*\b")
LOCAL_PARENT = re.compile(r"^task:t[0-9]{3,}$")
REQUIRED_FIELDS = ("aspects", "priority", "status", "created")
REF_FIELDS = ("related", "blocked-by", "blocked_by", "parent")


@dataclass
class _TaskBlock:
    path: str
    line: int
    task_id: str
    fields: dict[str, object] = field(default_factory=dict)


def _result(severity: Severity, message: str) -> Result:
    return Result(severity, None, None, message, "tasks", None)


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _split_list_value(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if raw is None:
        return []
    value = str(raw).strip()
    if value.startswith("[") and value.endswith("]"):
        return [item.strip() for item in value[1:-1].split(",") if item.strip()]
    return [value] if value else []


@Check(section="task queue...", order=18)
def check_tasks(ctx: ValidateContext) -> Iterator[Result]:
    from science_tool.tasks import _load_task_frontmatter, _task_search_paths

    tasks_dir = ctx.project_root / "tasks"
    active_dir = tasks_dir / "active"
    if not active_dir.is_dir():
        yield _result(Severity.WARN, "tasks/active/ not found (use /science:tasks to create)")
        return

    yield _result(Severity.INFO, "tasks/active/ exists")

    declared: set[str] = set()
    blocks: list[_TaskBlock] = []

    for path in _task_search_paths(tasks_dir):
        if path.parent.name == "active":
            try:
                fields, _body = _load_task_frontmatter(ctx.read_text_cached(path), path=path)
            except ValueError as exc:
                yield _result(Severity.ERROR, str(exc))
                continue
            task_id = fields.get("id")
            if not isinstance(task_id, str) or HEADER_VALID.fullmatch(f"## [{task_id}] task") is None:
                yield _result(
                    Severity.ERROR,
                    f"Invalid task id '{task_id}' in {_display_path(ctx.project_root, path)}: "
                    "task ids must match tNNN. Use parent: task:t001 for fragments or subtasks.",
                )
                continue
            blocks.append(
                _TaskBlock(
                    path=_display_path(ctx.project_root, path),
                    line=1,
                    task_id=task_id,
                    fields=fields,
                )
            )
            declared.add(task_id)
            continue

        current: _TaskBlock | None = None
        lines = ctx.read_text_cached(path).splitlines()
        for line_no, line in enumerate(lines, start=1):
            any_match = HEADER_ANY.match(line)
            if any_match:
                task_id = any_match.group(1)
                valid_match = HEADER_VALID.match(line)
                if valid_match is None:
                    yield _result(
                        Severity.ERROR,
                        f"Invalid task id '{task_id}' in {_display_path(ctx.project_root, path)}: "
                        "task ids must match tNNN. Use parent: task:t001 for fragments or subtasks.",
                    )
                    current = None
                    continue
                current = _TaskBlock(
                    path=_display_path(ctx.project_root, path),
                    line=line_no,
                    task_id=task_id,
                )
                blocks.append(current)
                declared.add(task_id)
                continue
            if current is not None:
                field_match = re.match(r"^-\s+([\w-]+):\s*(.*)$", line)
                if field_match:
                    current.fields[field_match.group(1)] = field_match.group(2).strip()

    for task_id in sorted(declared):
        count = sum(1 for block in blocks if block.task_id == task_id)
        if count > 1:
            yield _result(Severity.ERROR, f"duplicate task IDs in active/: {task_id}")

    for block in blocks:
        yield from _validate_block(block, declared)

    if blocks:
        yield _result(Severity.INFO, f"  {len(blocks)} task(s) validated")
    else:
        yield _result(Severity.INFO, "  no tasks in active/")


def _validate_block(block: _TaskBlock, declared: set[str]) -> Iterator[Result]:
    for field_name in REQUIRED_FIELDS:
        if field_name not in block.fields:
            yield _result(Severity.ERROR, f"task {block.task_id} missing required field: {field_name}")

    parent = block.fields.get("parent", "")
    if parent and (not isinstance(parent, str) or not LOCAL_PARENT.match(parent)):
        yield _result(Severity.ERROR, f"task {block.task_id} parent must be local task ref like task:t001")

    refs_to_check: list[str] = []
    for field_name in REF_FIELDS:
        refs_to_check.extend(_split_list_value(block.fields.get(field_name, "")))

    for raw_ref in refs_to_check:
        if ":" in raw_ref:
            if not raw_ref.startswith("task:"):
                continue
            raw_ref = raw_ref.split(":", 1)[1]
        for match in TASK_REF.finditer(raw_ref):
            raw = match.group(0)
            if raw in declared:
                continue
            if re.fullmatch(r"t[0-9]{3,}", raw):
                yield _result(Severity.ERROR, f"stale task ref '{raw}' in {block.path}")
            elif raw.startswith("t"):
                yield _result(Severity.ERROR, f"stale or invalid task ref '{raw}' in {block.path}")
