from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from science_tool.bibliography import bibliography_key_from_reference, load_bib_keys
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter

_SAFE_PAPER_SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")

if TYPE_CHECKING:
    from science_tool.validate.context import ValidateContext


def parse_frontmatter_document(ctx: ValidateContext, path: Path) -> tuple[dict[str, Any], str]:
    text = ctx.read_text_cached(path)
    if not text.startswith("---\n"):
        return ({}, text)

    try:
        _prefix, raw_frontmatter, body = text.split("---\n", 2)
    except ValueError:
        return ({}, text)
    data = yaml.safe_load(raw_frontmatter) or {}
    if not isinstance(data, dict):
        return ({}, body)
    return (data, body)


def resolve_reference(ctx: ValidateContext, ref: str) -> Path | None:
    bibliography_path = _resolve_bibliography_reference(ctx, ref)
    if bibliography_path is not None:
        return bibliography_path

    task_path = _resolve_task_reference(ctx, ref)
    if task_path is not None:
        return task_path

    if ref.count(":") >= 2:
        return None

    frontmatter_path = _resolve_frontmatter_reference(ctx, ref)
    if frontmatter_path is not None:
        return frontmatter_path

    paper_slug = _paper_slug(ref)
    if paper_slug is None:
        return None
    paper_path = ctx.papers_dir / f"{paper_slug}.md"
    if paper_path.is_file():
        return paper_path
    return None


def section_banner(section: str) -> str:
    return f"Checking {section}"


def _resolve_bibliography_reference(ctx: ValidateContext, ref: str) -> Path | None:
    key = bibliography_key_from_reference(ref)
    if key is None:
        return None
    if key not in load_bib_keys(ctx.project_root):
        return None
    return ctx.project_root / "papers" / "references.bib"


def _resolve_task_reference(ctx: ValidateContext, ref: str) -> Path | None:
    task_id = _task_id(ref)
    if task_id is None:
        return None

    heading_re = re.compile(rf"^##\s+\[{re.escape(task_id)}\](?:\s|$)", re.MULTILINE)
    for path in _task_files(ctx.project_root):
        if heading_re.search(ctx.read_text_cached(path)):
            return path
    return None


def _resolve_frontmatter_reference(ctx: ValidateContext, ref: str) -> Path | None:
    for path in _markdown_files(ctx.doc_dir) + _markdown_files(ctx.specs_dir):
        frontmatter, _body = parse_frontmatter_document(ctx, path)
        if frontmatter.get("id") == ref:
            return path
    return None


def _task_id(ref: str) -> str | None:
    if ref.startswith("task:"):
        candidate = ref[len("task:") :]
    else:
        candidate = ref
    if re.fullmatch(r"t\d{3,}", candidate) is None:
        return None
    return candidate


def _task_files(project_root: Path) -> list[Path]:
    paths: list[Path] = []
    active = project_root / "tasks" / "active.md"
    if active.is_file():
        paths.append(active)

    done_dir = project_root / "tasks" / "done"
    if done_dir.is_dir():
        paths.extend(sorted(done_dir.glob("*.md")))
    return paths


def _markdown_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def _paper_slug(ref: str) -> str | None:
    if not ref.startswith("paper:"):
        return None
    slug = ref[len("paper:") :]
    if _SAFE_PAPER_SLUG_RE.fullmatch(slug) is None:
        return None
    return slug or None


def raw_frontmatter(path: Path) -> dict[str, Any]:
    """Raw frontmatter for either an entity.md (fenced YAML) or a datapackage.yaml.

    Reads directly (uncached) and tolerates malformed input by returning {} —
    callers re-enforce schema-critical fields themselves, because raw frontmatter
    bypasses the closed graph Entity.
    """
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(text) or {}
        elif text.startswith("---"):
            end = text.find("\n---", 3)
            data = yaml.safe_load(text[3:end]) if end != -1 else {}
        else:
            data = {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def dataset_frontmatters(ctx: ValidateContext) -> list[dict[str, Any]]:
    """Raw frontmatter for every project dataset entity, BOTH backends, by tolerant
    file discovery that does NOT strict-validate through the graph loader (which
    RAISES on a malformed core-kind entity and would crash the run):

    - datapackage-backed datasets (`DatapackageAdapter`: data/, results/)
    - markdown datasets (`MarkdownAdapter` scoped to doc/datasets/)

    `kind` is the canonical field; `type` is the authored alias — accept either.
    Each dict carries `_path` (project-relative). De-duped by entity id (first wins).
    """
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    adapters = (DatapackageAdapter(), MarkdownAdapter(scan_roots=["doc/datasets"]))
    for adapter in adapters:
        for ref in adapter.discover(ctx.project_root):
            abs_path = ctx.project_root / ref.path
            if not abs_path.is_file():
                continue
            fm = raw_frontmatter(abs_path)
            if (fm.get("kind") or fm.get("type")) != "dataset":
                continue
            ident = fm.get("id")
            if isinstance(ident, str) and ident:
                if ident in seen_ids:
                    continue
                seen_ids.add(ident)
            fm["_path"] = ref.path
            out.append(fm)
    return out
