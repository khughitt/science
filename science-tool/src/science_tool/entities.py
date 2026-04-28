from __future__ import annotations

import re
import unicodedata
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml

from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import load_project_sources

EntityFilenamePolicy = Literal["local-part", "date-local-part"]


class EntityCommandError(ValueError):
    """Raised for user-correctable entity CLI errors."""


@dataclass(frozen=True)
class EntityPathPolicy:
    root: Path
    filename: EntityFilenamePolicy


_BUILTIN_MARKDOWN_POLICIES: dict[str, EntityPathPolicy] = {
    "question": EntityPathPolicy(root=Path("doc/questions"), filename="local-part"),
    "hypothesis": EntityPathPolicy(root=Path("specs/hypotheses"), filename="local-part"),
    "discussion": EntityPathPolicy(root=Path("doc/discussions"), filename="date-local-part"),
    "interpretation": EntityPathPolicy(root=Path("doc/interpretations"), filename="date-local-part"),
}
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_LOCAL_PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_ID_PREFIX_RE = re.compile(r"^(?P<prefix>[a-z]?)(?P<number>\d+)-", re.IGNORECASE)
_NOTES_HEADING_RE = re.compile(r"^##\s+Notes\s*$")
_DEFAULT_STATUS: dict[str, str] = {
    "question": "open",
    "hypothesis": "candidate",
    "discussion": "active",
    "interpretation": "active",
}
_STATUS_VALUES: dict[str, frozenset[str]] = {
    "question": frozenset({"open", "answered", "closed"}),
    "hypothesis": frozenset({"candidate", "active", "rejected", "supported"}),
    "discussion": frozenset({"active", "closed"}),
    "interpretation": frozenset({"active", "superseded"}),
}
_ALLOWED_EXPLICIT_ROOTS = (Path("doc"), Path("specs"), Path("research/packages"))


@dataclass(frozen=True)
class EntityWriteResult:
    entity_id: str
    path: Path
    warnings: list[str]


def resolve_path_policy(kind: str) -> EntityPathPolicy:
    try:
        return _BUILTIN_MARKDOWN_POLICIES[kind]
    except KeyError as exc:
        raise EntityCommandError(f"Unsupported source-authored entity kind: {kind}") from exc


def derive_slug(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    slug = slug[:72].rstrip("-")
    if len(slug) < 2:
        raise EntityCommandError("Title cannot derive a stable slug; requires --slug")
    return validate_slug(slug)


def validate_slug(slug: str) -> str:
    if len(slug) < 2 or not _SLUG_RE.fullmatch(slug):
        raise EntityCommandError(f"Invalid slug: {slug}")
    return slug


def validate_entity_id(kind: str, entity_id: str) -> str:
    prefix = f"{kind}:"
    if not entity_id.startswith(prefix):
        raise EntityCommandError(f"Entity id must use prefix {prefix}")
    local_part = entity_id[len(prefix) :]
    if not _LOCAL_PART_RE.fullmatch(local_part):
        raise EntityCommandError(f"Invalid local entity id: {entity_id}")
    return entity_id


def generate_entity_id(
    project_root: Path,
    kind: str,
    title: str,
    entity_id: str | None,
    slug: str | None,
) -> str:
    if entity_id is not None:
        return validate_entity_id(kind, entity_id)

    slug_value = validate_slug(slug) if slug is not None else derive_slug(title)
    siblings = _existing_local_parts(project_root, kind)
    if not siblings:
        raise EntityCommandError(f"No existing {kind} siblings; provide --id for the first source-authored entity")

    conventions: dict[str, tuple[str, int, int]] = {}
    for local_part in siblings:
        match = _ID_PREFIX_RE.match(local_part)
        if match is None:
            continue
        prefix = match.group("prefix").lower()
        number = int(match.group("number"))
        conventions[prefix] = (prefix, max(number, conventions.get(prefix, (prefix, 0, 0))[1]), len(match.group("number")))

    if len(conventions) != 1:
        raise EntityCommandError(f"Mixed ID conventions for {kind}; provide --id explicitly")
    prefix, max_number, width = next(iter(conventions.values()))
    return f"{kind}:{prefix}{max_number + 1:0{width}d}-{slug_value}"


def path_for_entity(kind: str, entity_id: str, today: date) -> Path:
    del today
    validate_entity_id(kind, entity_id)
    local_part = entity_id.split(":", 1)[1]
    return resolve_path_policy(kind).root / f"{local_part}.md"


def resolve_entity_ref(project_root: Path, ref: str) -> str:
    entities = _load_markdown_entities(project_root)
    if ":" in ref:
        for entity in entities:
            if entity["id"] == ref:
                return ref
        raise EntityCommandError(f"Entity not found: {ref}")

    matches = [
        entity["id"]
        for entity in entities
        if entity["id"].split(":", 1)[1] == ref or entity["id"].split(":", 1)[1].startswith(f"{ref}-")
    ]
    if not matches:
        raise EntityCommandError(f"Entity not found: {ref}")
    if len(matches) > 1:
        raise EntityCommandError(f"Ambiguous entity reference {ref}: {', '.join(sorted(matches))}")
    return matches[0]


def build_entity_markdown(
    *,
    kind: str,
    entity_id: str,
    title: str,
    status: str,
    related: list[str],
    source_refs: list[str],
    today: date,
) -> str:
    frontmatter: dict[str, object] = {
        "id": validate_entity_id(kind, entity_id),
        "type": kind,
        "title": title,
        "status": status,
        "related": related,
        "source_refs": source_refs,
        "created": today.isoformat(),
        "updated": today.isoformat(),
    }
    body = f"# {title}\n\n## Summary\n\n\n## Notes\n"
    return "---\n" + _dump_frontmatter(frontmatter) + "---\n" + body


def create_entity(
    project_root: Path,
    kind: str,
    title: str,
    *,
    entity_id: str | None = None,
    slug: str | None = None,
    explicit_path: Path | None = None,
    status: str | None = None,
    related: list[str] | None = None,
    source_refs: list[str] | None = None,
    today: date | None = None,
) -> EntityWriteResult:
    project_root = project_root.resolve()
    today_value = today or date.today()
    if kind == "concept":
        raise EntityCommandError("Source-authored concepts are not supported; use graph add concept instead")
    resolve_path_policy(kind)
    if slug is not None and entity_id is not None:
        raise EntityCommandError("Use either --slug or --id, not both")

    entity_id_value = generate_entity_id(project_root, kind, title, entity_id, slug)
    status_value = status or _DEFAULT_STATUS[kind]
    _validate_status(kind, status_value)
    rel_path = _resolve_destination_rel_path(project_root, kind, entity_id_value, explicit_path, today_value)
    destination = project_root / rel_path
    if destination.exists():
        raise EntityCommandError(f"Destination already exists: {rel_path}")

    text = build_entity_markdown(
        kind=kind,
        entity_id=entity_id_value,
        title=title,
        status=status_value,
        related=list(related or []),
        source_refs=list(source_refs or []),
        today=today_value,
    )
    warnings = _validate_prospective_write(
        project_root=project_root,
        rel_path=rel_path,
        text=text,
        target_entity_id=entity_id_value,
    )

    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, destination)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    return EntityWriteResult(entity_id=entity_id_value, path=destination, warnings=warnings)


def append_note_to_body(body: str, note_line: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if not _NOTES_HEADING_RE.fullmatch(line):
            continue
        insert_at = len(lines)
        for next_index in range(index + 1, len(lines)):
            if lines[next_index].startswith("## ") and not _NOTES_HEADING_RE.fullmatch(lines[next_index]):
                insert_at = next_index
                break
        before = lines[:insert_at]
        after = lines[insert_at:]
        while before and before[-1] == "":
            before.pop()
        updated_lines = [*before, "", note_line]
        if after:
            updated_lines.extend(["", *after])
        return "\n".join(updated_lines)

    return body.rstrip("\n") + "\n\n## Notes\n\n" + note_line


def _dump_frontmatter(frontmatter: dict[str, object]) -> str:
    return yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False)


def _validate_status(kind: str, status: str) -> None:
    if status not in _STATUS_VALUES[kind]:
        raise EntityCommandError(f"Invalid status for {kind}: {status}")


def _resolve_destination_rel_path(
    project_root: Path,
    kind: str,
    entity_id: str,
    explicit_path: Path | None,
    today: date,
) -> Path:
    if explicit_path is None:
        return path_for_entity(kind, entity_id, today)
    if explicit_path.is_absolute():
        raise EntityCommandError("--path must be relative to the project root")
    if ".." in explicit_path.parts:
        raise EntityCommandError("--path must not contain '..'")
    if explicit_path.suffix != ".md":
        raise EntityCommandError("--path must point to a .md file")
    resolved = (project_root / explicit_path).resolve()
    if not resolved.is_relative_to(project_root):
        raise EntityCommandError("--path must stay within the project root")
    if not any(explicit_path == root or explicit_path.is_relative_to(root) for root in _ALLOWED_EXPLICIT_ROOTS):
        raise EntityCommandError("--path must be under doc, specs, or research/packages")
    return explicit_path


def _validate_prospective_write(
    *,
    project_root: Path,
    rel_path: Path,
    text: str,
    target_entity_id: str,
) -> list[str]:
    rel_path_text = rel_path.as_posix()
    baseline_rows, _ = audit_project_sources(load_project_sources(project_root))
    prospective_rows, _ = audit_project_sources(load_project_sources(project_root, markdown_overrides={rel_path_text: text}))

    baseline_keys = {_audit_row_key(row) for row in baseline_rows}
    new_rows = [row for row in prospective_rows if _audit_row_key(row) not in baseline_keys]
    warnings = [_format_preexisting_warning(row) for row in baseline_rows if row.get("status") == "fail"]
    blocking_rows: list[dict[str, Any]] = []
    for row in new_rows:
        if _is_allowed_unresolved_target_warning(row, target_entity_id):
            warnings.append(_format_new_warning(row))
            continue
        if row.get("status") == "fail":
            blocking_rows.append(row)
    if blocking_rows:
        raise EntityCommandError("; ".join(_format_blocking_row(row) for row in blocking_rows))
    return warnings


def _audit_row_key(row: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("check", "")),
        str(row.get("status", "")),
        str(row.get("source", "")),
        str(row.get("field", "")),
        str(row.get("target", "")),
        str(row.get("details", "")),
    )


def _is_allowed_unresolved_target_warning(row: dict[str, Any], target_entity_id: str) -> bool:
    return (
        row.get("check") == "unresolved_reference"
        and row.get("status") == "fail"
        and row.get("source") == target_entity_id
        and row.get("field") in {"related", "source_refs"}
    )


def _format_preexisting_warning(row: dict[str, Any]) -> str:
    return f"pre-existing audit failure: {row.get('check')} on {row.get('source')}: {row.get('details')}"


def _format_new_warning(row: dict[str, Any]) -> str:
    return f"{row.get('check')} on {row.get('source')}: {row.get('details')}"


def _format_blocking_row(row: dict[str, Any]) -> str:
    return f"{row.get('check')} on {row.get('source')}: {row.get('details')}"


def _existing_local_parts(project_root: Path, kind: str) -> list[str]:
    local_parts: list[str] = []
    for entity in _load_markdown_entities(project_root, kind=kind):
        local_parts.append(entity["id"].split(":", 1)[1])
    return local_parts


def _load_markdown_entities(project_root: Path, kind: str | None = None) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for policy_kind, policy in _BUILTIN_MARKDOWN_POLICIES.items():
        if kind is not None and policy_kind != kind:
            continue
        root = project_root / policy.root
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            frontmatter, _ = _parse_markdown_file(path)
            entity_id = frontmatter.get("id")
            entity_kind = frontmatter.get("type") or frontmatter.get("kind")
            if isinstance(entity_id, str) and isinstance(entity_kind, str):
                entities.append({"id": entity_id, "kind": entity_kind, "path": path, "frontmatter": frontmatter})
    return entities


def _parse_markdown_file(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ({}, text)
    try:
        _, frontmatter_text, body = text.split("---\n", 2)
    except ValueError:
        return ({}, text)
    frontmatter = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(frontmatter, dict):
        return ({}, body)
    return (frontmatter, body.lstrip("\n"))
