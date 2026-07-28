r"""
# ─── 16. Frontmatter cross-reference validation ──────────────────
echo ""
echo "Checking frontmatter cross-references..."

xref_result=$(XREF_SPECS="$SPECS_DIR" XREF_DOC="$DOC_DIR" XREF_TASKS="$TASKS_DIR" XREF_SCIENCE_YAML="science.yaml" python3 << 'PYEOF'
import os, re

try:
    import yaml
except Exception:  # pragma: no cover - shell fallback
    yaml = None

QUOTE = "[\"']?"
NOT_QUOTE = "[^\"'\n]+"
LOCAL_KINDS = {
    "assumption", "book", "concept", "data-package", "dataset", "discussion", "experiment",
    "finding", "hypothesis", "inquiry", "interpretation", "mechanism", "method",
    "model", "observation", "paper", "pre-registration", "proposition", "question",
    "report", "source", "story", "task", "theme", "topic", "validation-report",
    "workflow", "workflow-run", "meta",
}

def extract_frontmatter(path):
    try:
        with open(path) as f:
            content = f.read()
    except Exception:
        return None, []
    m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return None, []
    fm = m.group(1)
    id_match = re.search(r'^id:\s*' + QUOTE + '(' + NOT_QUOTE + ')' + QUOTE, fm, re.MULTILINE)
    doc_id = id_match.group(1).strip() if id_match else None
    related = []
    rel_match = re.search(r'^related:\s*\[(.*?)\]', fm, re.MULTILINE)
    if rel_match:
        items = rel_match.group(1)
        related = [s.strip().strip('"').strip("'") for s in items.split(',') if s.strip()]
    else:
        in_related = False
        for line in fm.split('\n'):
            if line.startswith('related:'):
                in_related = True
                continue
            if in_related:
                if line.startswith('  - '):
                    val = line[4:].strip().strip('"').strip("'")
                    if '{{' not in val and val:
                        related.append(val)
                elif not line.startswith(' '):
                    in_related = False
    return doc_id, related


def load_task_ids(tasks_dir):
    task_ids = set()
    if not os.path.isdir(tasks_dir):
        return task_ids

    task_paths = [os.path.join(tasks_dir, "active.md")]
    done_dir = os.path.join(tasks_dir, "done")
    if os.path.isdir(done_dir):
        for name in os.listdir(done_dir):
            if name.endswith(".md"):
                task_paths.append(os.path.join(done_dir, name))

    header_re = re.compile(r"^##\s+\[(\w+)\]")
    for path in task_paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    match = header_re.match(line)
                    if match:
                        task_ids.add(f"task:{match.group(1).lower()}")
        except Exception:
            continue
    return task_ids


def load_project_ids(path):
    if yaml is None or not os.path.isfile(path):
        return set()
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return set()
    ids = set()
    project_id = data.get("id")
    if isinstance(project_id, str) and project_id:
        ids.add(project_id)
    peers = data.get("peers")
    if isinstance(peers, list):
        for peer in peers:
            if isinstance(peer, dict) and isinstance(peer.get("id"), str):
                ids.add(peer["id"])
    return ids


def classify_ref(ref, project_ids):
    parts = ref.split(":")
    if re.fullmatch(r"t[0-9]{3,}", ref):
        return "local"
    if len(parts) == 2:
        first, _slug = parts
        if first in LOCAL_KINDS:
            return "local"
        if first in project_ids:
            return "legacy"
        return "local"
    if len(parts) == 3:
        project_id, _kind, _slug = parts
        if project_id in project_ids:
            return "cross"
        return "unknown-namespace"
    return "local"


search_dirs = [os.environ['XREF_SPECS'], os.environ['XREF_DOC']]
all_ids = set()
refs_by_file = {}
for search_dir in search_dirs:
    if not os.path.isdir(search_dir):
        continue
    for root, dirs, files in os.walk(search_dir):
        for fname in files:
            if not fname.endswith('.md'):
                continue
            path = os.path.join(root, fname)
            doc_id, related = extract_frontmatter(path)
            if doc_id:
                all_ids.add(doc_id)
            if related:
                refs_by_file[path] = related

all_ids.update(load_task_ids(os.environ["XREF_TASKS"]))
project_ids = load_project_ids(os.environ["XREF_SCIENCE_YAML"])


def emit(*parts):
    print("\t".join(str(part) for part in parts))


broken = 0
for path, refs in refs_by_file.items():
    for ref in refs:
        shape = classify_ref(ref, project_ids)
        if shape == "cross":
            continue
        if shape == "unknown-namespace":
            project_id = ref.split(":", 1)[0]
            emit("UNKNOWN_NAMESPACE", os.path.basename(path), project_id, "-", ref)
            broken += 1
            continue
        if shape == "legacy":
            project_id, slug = ref.split(":", 1)
            emit("LEGACY_PROJECT_REF", os.path.basename(path), project_id, slug, ref)
            continue
        if ref not in all_ids:
            emit("BROKEN", os.path.basename(path), ref, "-", ref)
            broken += 1
if broken == 0:
    print('OK')
PYEOF
2>/dev/null || echo "SKIP")

if [ "$xref_result" = "SKIP" ]; then
    info "Frontmatter cross-reference check skipped (python3 error)"
elif [ "$xref_result" = "OK" ]; then
    info "All frontmatter cross-references valid"
else
    while IFS=$'\t' read -r status filename project_id slug raw; do
        if [ "$status" = "BROKEN" ]; then
            ref="$project_id"
            warn "Broken reference in $filename: related ID '$ref' not found"
        elif [ "$status" = "UNKNOWN_NAMESPACE" ]; then
            error "Unknown project namespace '${project_id}' in ref '${raw}'. Add it to science.yaml peers: or use a local ref."
        elif [ "$status" = "LEGACY_PROJECT_REF" ]; then
            warn "Legacy cross-project ref '${raw}' is missing an entity kind. Use '${project_id}:question:${slug}' or another explicit <project-id>:<kind>:<slug> ref."
        fi
    done < <(echo "$xref_result")
fi
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entity_scan import iter_entity_markdown
from science_tool.tasks import known_task_ids
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

QUOTE = "[\"']?"
NOT_QUOTE = "[^\"'\n]+"
FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

LOCAL_KINDS = {
    "assumption",
    "book",
    "concept",
    "data-package",
    "dataset",
    "discussion",
    "evidence-line",
    "experiment",
    "finding",
    "hypothesis",
    "inquiry",
    "interpretation",
    "mechanism",
    "method",
    "model",
    "observation",
    "paper",
    "pre-registration",
    "proposition",
    "question",
    "report",
    "source",
    "story",
    "synthesis",
    "task",
    "theme",
    "topic",
    "validation-report",
    "workflow",
    "workflow-run",
    "meta",
}

RefShape = Literal["local", "legacy", "cross", "unknown-namespace"]


SECTION, RULES = declare_validation_rules(
    section_id="cross-references",
    section_title="cross references",
    section_order=126,
    rule_ids=("cross-references.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(
    severity: Severity,
    message: str,
    *,
    key: list[str],
) -> CheckObservation:
    return validation_observation(
        severity=severity,
        path=None,
        line=None,
        message=message,
        rule=RULES["cross-references.check"],
        task=None,
        qualifiers={"key": key},
    )


def _extract_frontmatter(ctx: ValidateContext, path: Path) -> tuple[str | None, list[str]]:
    content = ctx.read_text_cached(path)
    match = FRONTMATTER.match(content)
    if not match:
        return None, []

    frontmatter = match.group(1)
    id_match = re.search(r"^id:\s*" + QUOTE + "(" + NOT_QUOTE + ")" + QUOTE, frontmatter, re.MULTILINE)
    doc_id = id_match.group(1).strip() if id_match else None
    related: list[str] = []

    related_match = re.search(r"^related:\s*\[(.*?)\]", frontmatter, re.MULTILINE)
    if related_match:
        items = related_match.group(1)
        related = [item.strip().strip('"').strip("'") for item in items.split(",") if item.strip()]
    else:
        in_related = False
        for line in frontmatter.split("\n"):
            if line.startswith("related:"):
                in_related = True
                continue
            if in_related:
                if line.startswith("  - "):
                    value = line[4:].strip().strip('"').strip("'")
                    if "{{" not in value and value:
                        related.append(value)
                elif not line.startswith(" "):
                    in_related = False

    return doc_id, related


def _load_task_ids(ctx: ValidateContext) -> set[str]:
    tasks_dir = ctx.project_root / "tasks"
    if not tasks_dir.is_dir():
        return set()
    return {f"task:{task_id}" for task_id in known_task_ids(tasks_dir)}


def _load_project_ids(ctx: ValidateContext) -> set[str]:
    ids: set[str] = set()
    project_id = ctx.manifest.get("id")
    if isinstance(project_id, str) and project_id:
        ids.add(project_id)
    peers = ctx.manifest.get("peers")
    if isinstance(peers, list):
        for peer in peers:
            if isinstance(peer, dict) and isinstance(peer.get("id"), str):
                ids.add(peer["id"])
    return ids


def _archive_problem_key(problem: str) -> list[str]:
    """Recover the stable archive predicate components from its diagnostic."""
    patterns = (
        ("active-row-file-missing", r"^active archive row (.+?): file missing at "),
        ("file-without-active-row", r"^archived file (.+?) has no active index row$"),
        ("token-multiple-owners", r"^archive token (.+?) claimed by multiple active entries:"),
        ("token-live-collision", r"^archive id/alias (.+?) collides with the live alias space$"),
    )
    for code, pattern in patterns:
        match = re.search(pattern, problem)
        if match is not None:
            return [code, match.group(1)]
    raise ValueError(f"unrecognized archive verification problem: {problem}")


def _classify_ref(ref: str, project_ids: set[str]) -> RefShape:
    parts = ref.split(":")
    if re.fullmatch(r"t[0-9]{3,}", ref):
        return "local"
    if len(parts) == 2:
        first, _slug = parts
        if first in LOCAL_KINDS:
            return "local"
        if first in project_ids:
            return "legacy"
        return "local"
    if len(parts) == 3:
        project_id, _kind, _slug = parts
        if project_id in project_ids:
            return "cross"
        return "unknown-namespace"
    return "local"


@Check(section=SECTION, order=20, producer_id="validate.cross-references.cross-references", rules=tuple(RULES.values()))
def check_cross_references(ctx: ValidateContext) -> Iterator[CheckObservation]:
    all_ids: set[str] = set()
    refs_by_file: dict[Path, list[str]] = {}

    entities_dir = ctx.project_root / "entities"
    if entities_dir.is_dir():
        for path in iter_entity_markdown(entities_dir):
            doc_id, related = _extract_frontmatter(ctx, path)
            if doc_id:
                all_ids.add(doc_id)
            if related:
                refs_by_file[path] = related

    all_ids.update(_load_task_ids(ctx))
    from science_tool.archive import load_archive_index

    all_ids.update(load_archive_index(ctx.project_root).resolvable_ids())
    project_ids = _load_project_ids(ctx)

    emitted = False
    reported: set[tuple[str, RefShape, str]] = set()
    for path, refs in refs_by_file.items():
        for ref in refs:
            shape = _classify_ref(ref, project_ids)
            if shape == "cross":
                continue
            identity = (
                path.relative_to(ctx.project_root).as_posix(),
                shape,
                ref,
            )
            if identity in reported:
                continue
            reported.add(identity)
            if shape == "unknown-namespace":
                project_id = ref.split(":", 1)[0]
                emitted = True
                yield _result(
                    Severity.ERROR,
                    f"Unknown project namespace '{project_id}' in ref '{ref}'. "
                    "Add it to science.yaml peers: or use a local ref.",
                    key=[
                        "unknown-project-namespace",
                        identity[0],
                        project_id,
                        ref,
                    ],
                )
                continue
            if shape == "legacy":
                project_id, slug = ref.split(":", 1)
                emitted = True
                yield _result(
                    Severity.WARN,
                    f"Legacy cross-project ref '{ref}' is missing an entity kind. "
                    f"Use '{project_id}:question:{slug}' or another explicit <project-id>:<kind>:<slug> ref.",
                    key=["legacy-cross-project", identity[0], ref],
                )
                continue
            if ref not in all_ids:
                emitted = True
                yield _result(
                    Severity.WARN,
                    f"Broken reference in {path.name}: related ID '{ref}' not found",
                    key=[
                        "broken-related",
                        identity[0],
                        ref,
                    ],
                )

    if not emitted:
        yield _result(
            Severity.INFO,
            "All frontmatter cross-references valid",
            key=["valid"],
        )


@Check(section=SECTION, order=21, producer_id="validate.cross-references.archive-index", rules=())
def check_archive_index(ctx: ValidateContext) -> Iterator[CheckObservation]:
    from science_tool.archive import verify_archive

    live_space: set[str] = set()
    load_error: str | None = None
    try:
        sources = ctx.project_sources()
        for e in sources.entities:
            live_space.add(e.canonical_id)
            live_space.update(e.aliases or [])
            live_space.update(getattr(e, "same_as", None) or [])
    except Exception as exc:  # degraded, but NOT silently passed
        load_error = str(exc)

    problems = verify_archive(ctx.project_root, live_alias_space=live_space)
    if load_error is not None:
        yield _result(
            Severity.ERROR,
            f"Archive index: could not load live entities for collision check ({load_error})",
            key=["archive-live-entity-load"],
        )
    for problem in problems:
        yield _result(
            Severity.ERROR,
            f"Archive index: {problem}",
            key=_archive_problem_key(problem),
        )
    if not problems and load_error is None:
        yield _result(
            Severity.INFO,
            "Archive index consistent",
            key=["archive-consistent"],
        )
