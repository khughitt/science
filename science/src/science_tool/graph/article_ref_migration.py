"""One-shot migration for external-literature reference prefixes."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


ARTICLE_REF_FIELDS: frozenset[str] = frozenset(
    {
        "consumed_by",
        "datapackage",
        "datasets",
        "evidence",
        "inputs",
        "object",
        "outputs",
        "produces",
        "ref",
        "references",
        "related",
        "source",
        "source_refs",
        "sources",
        "subject",
        "supports",
        "target",
    }
)

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".snakemake",
        ".venv",
        ".worktrees",
        "__pycache__",
        "data",
        "logs",
        "models",
        "node_modules",
        "results",
        "worktrees",
    }
)

ARTICLE_ALIAS_RE = re.compile(r"(?<![A-Za-z0-9_-])article:([A-Za-z0-9][A-Za-z0-9_.-]*)")
YAML_KEY_RE = re.compile(r"^(?P<indent>\s*)(?P<dash>-\s*)?(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*:(?P<rest>.*)$")


@dataclass(frozen=True)
class ArticleRefMigrationReport:
    project_root: str
    apply: bool
    changed_files: tuple[str, ...]
    rewrite_count: int

    @property
    def changed_file_count(self) -> int:
        return len(self.changed_files)

    def to_json(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "mode": "apply" if self.apply else "dry-run",
            "changed_file_count": self.changed_file_count,
            "changed_files": list(self.changed_files),
            "rewrite_count": self.rewrite_count,
        }


def plan_article_ref_migration(project_root: Path, *, apply: bool = False) -> ArticleRefMigrationReport:
    project_root = project_root.resolve()
    changed_files: list[str] = []
    rewrite_count = 0
    for path in _iter_candidate_paths(project_root):
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        migrated, count = _migrate_text(path, original)
        if count == 0 or migrated == original:
            continue
        rewrite_count += count
        changed_files.append(path.relative_to(project_root).as_posix())
        if apply:
            path.write_text(migrated, encoding="utf-8")
    return ArticleRefMigrationReport(
        project_root=project_root.as_posix(),
        apply=apply,
        changed_files=tuple(sorted(changed_files)),
        rewrite_count=rewrite_count,
    )


def _iter_candidate_paths(project_root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(project_root).parts):
            continue
        if path.suffix.lower() in {".json", ".md", ".markdown", ".yaml", ".yml"}:
            paths.append(path)
    return sorted(paths)


def _migrate_text(path: Path, text: str) -> tuple[str, int]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _migrate_json_text(text)
    if suffix in {".md", ".markdown"}:
        return _migrate_markdown_frontmatter(text)
    if suffix in {".yaml", ".yml"}:
        return _migrate_yaml_text(text)
    return text, 0


def _migrate_markdown_frontmatter(text: str) -> tuple[str, int]:
    split = _split_frontmatter(text)
    if split is None:
        return text, 0
    before, yaml_block, after = split
    migrated_block, count = _migrate_yaml_lines(yaml_block)
    if count == 0:
        return text, 0
    return before + migrated_block + after, count


def _split_frontmatter(text: str) -> tuple[str, str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return text[:4], text[4:end], text[end:]


def _migrate_yaml_text(text: str) -> tuple[str, int]:
    return _migrate_yaml_lines(text)


def _migrate_yaml_lines(text: str) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    stack: list[tuple[int, bool]] = []
    migrated_lines: list[str] = []
    rewrite_count = 0
    for line in lines:
        if line.lstrip().startswith("#"):
            migrated_lines.append(line)
            continue
        content = line[:-1] if line.endswith("\n") else line
        newline = "\n" if line.endswith("\n") else ""
        parent_ref = stack[-1][1] if stack else False
        match = YAML_KEY_RE.match(content)
        dash_key = match.group("key") if match is not None and match.group("dash") else None
        if parent_ref and content.lstrip().startswith("- ") and (dash_key is None or dash_key == "article"):
            rewritten, count = _rewrite_article_aliases(content)
            rewrite_count += count
            migrated_lines.append(rewritten + newline)
            continue
        if match is not None:
            indent = len(match.group("indent"))
            while stack and indent <= stack[-1][0]:
                stack.pop()
            parent_ref = stack[-1][1] if stack else False
            key = match.group("key")
            in_ref_context = parent_ref or key in ARTICLE_REF_FIELDS
            if parent_ref or key in ARTICLE_REF_FIELDS:
                rewritten, count = _rewrite_article_aliases(content)
                rewrite_count += count
                content = rewritten
            stack.append((indent, in_ref_context))
            migrated_lines.append(content + newline)
            continue
        parent_ref = stack[-1][1] if stack else False
        if parent_ref:
            rewritten, count = _rewrite_article_aliases(content)
            rewrite_count += count
            content = rewritten
        migrated_lines.append(content + newline)
    return "".join(migrated_lines), rewrite_count


def _migrate_json_text(text: str) -> tuple[str, int]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text, 0
    migrated, count = _migrate_json_value(data, in_ref_context=False)
    if count == 0:
        return text, 0
    return json.dumps(migrated, indent=2, ensure_ascii=False) + "\n", count


def _migrate_json_value(value: Any, *, in_ref_context: bool) -> tuple[Any, int]:
    if isinstance(value, str):
        if not in_ref_context:
            return value, 0
        return _rewrite_article_aliases(value)
    if isinstance(value, list):
        total = 0
        migrated_items: list[Any] = []
        for item in value:
            migrated, count = _migrate_json_value(item, in_ref_context=in_ref_context)
            migrated_items.append(migrated)
            total += count
        return migrated_items, total
    if isinstance(value, dict):
        total = 0
        migrated_dict: dict[str, Any] = {}
        for key, item in value.items():
            child_ref_context = in_ref_context or key in ARTICLE_REF_FIELDS
            migrated, count = _migrate_json_value(item, in_ref_context=child_ref_context)
            migrated_dict[key] = migrated
            total += count
        return migrated_dict, total
    return value, 0


def _rewrite_article_aliases(text: str) -> tuple[str, int]:
    return ARTICLE_ALIAS_RE.subn(r"paper:\1", text)
