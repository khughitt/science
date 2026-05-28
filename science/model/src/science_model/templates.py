from __future__ import annotations

import importlib.resources
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


MIGRATED_KINDS: frozenset[str] = frozenset(
    {"hypothesis", "question", "interpretation", "discussion", "theme", "proposition", "evidence-line"}
)
VALID_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "entity_id",
        "kind",
        "title",
        "status",
        "related",
        "source_refs",
        "created",
        "updated",
        "slug",
        "local_part",
        "nn",
        "phase",
    }
)


class EntityTemplateError(ValueError):
    """Raised when an entity template cannot be rendered."""


class FrontmatterFieldPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_: str | None = Field(default=None, alias="from")
    default: Any = None
    omit: bool = False

    @model_validator(mode="after")
    def valid_policy(self) -> "FrontmatterFieldPolicy":
        has_from = self.from_ is not None
        has_default = "default" in self.model_fields_set
        if self.omit and (has_from or has_default):
            raise ValueError("omit cannot be combined with from or default")
        if not (has_from or has_default or self.omit):
            raise ValueError("frontmatter field policy must set one of from, default, or omit")
        if has_default and self.default is None:
            raise ValueError("default cannot be null; use omit: true or a concrete default")
        if self.from_ is not None and self.from_ not in VALID_FIELD_NAMES:
            raise ValueError(f"unknown renderer field: {self.from_}")
        return self


class TemplateSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    required: bool


class TemplateMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frontmatter: dict[str, FrontmatterFieldPolicy]
    sections: list[TemplateSection]


@dataclass(frozen=True)
class SectionInfo:
    key: str
    name: str
    required: bool
    hint: str


@dataclass(frozen=True)
class _ParsedSection:
    name: str
    content: str


_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_PLACEHOLDER_RE = re.compile(r"\{\{([^{}]+)\}\}")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


class Renderer:
    def __init__(self, template_root: Path | None = None, today: date | None = None) -> None:
        self.template_root = template_root
        self.today = today or date.today()

    def render(
        self,
        kind: str,
        *,
        fields: dict[str, object],
        with_keys: list[str] | tuple[str, ...] = (),
        without_keys: list[str] | tuple[str, ...] = (),
        no_hints: bool = False,
    ) -> str:
        template_text = self._read_template(kind)
        frontmatter, body = _split_frontmatter(template_text, kind)
        metadata = _load_metadata(frontmatter, kind)
        h1, sections = _parse_body_sections(body, kind)
        _assert_declared_sections_exist(metadata, sections, kind)
        _assert_known_keys(metadata, sections, with_keys, without_keys, kind)

        context = _context_with_computed_fields(fields, self.today)
        rendered_frontmatter = _render_frontmatter(metadata, context)
        rendered_body = _render_body(
            h1=h1,
            sections=sections,
            metadata=metadata,
            context=context,
            with_keys=set(with_keys),
            without_keys=set(without_keys),
            no_hints=no_hints,
        )
        return "---\n" + yaml.safe_dump(rendered_frontmatter, sort_keys=False) + "---\n" + rendered_body

    def sections(self, kind: str) -> list[SectionInfo]:
        template_text = self._read_template(kind)
        frontmatter, body = _split_frontmatter(template_text, kind)
        metadata = _load_metadata(frontmatter, kind)
        _, parsed_sections = _parse_body_sections(body, kind)
        _assert_declared_sections_exist(metadata, parsed_sections, kind)
        metadata_by_name = {section.name: section for section in metadata.sections}
        rows: list[SectionInfo] = []
        for parsed_section in parsed_sections:
            section = metadata_by_name[parsed_section.name]
            rows.append(
                SectionInfo(
                    key=section.key,
                    name=section.name,
                    required=section.required,
                    hint=_first_hint(parsed_section.content),
                )
            )
        return rows

    def _read_template(self, kind: str) -> str:
        filename = f"{kind}.md"
        if self.template_root is not None:
            path = self.template_root / filename
            if not path.exists():
                raise EntityTemplateError(f"Template not found: {path}")
            return path.read_text(encoding="utf-8")
        resource = importlib.resources.files("science_model").joinpath("templates", filename)
        if not resource.is_file():
            raise EntityTemplateError(f"Packaged template not found: science_model/templates/{filename}")
        return resource.read_text(encoding="utf-8")


def _split_frontmatter(text: str, kind: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise EntityTemplateError(f"Template {kind}.md is missing YAML frontmatter")
    rest = text[len("---\n") :]
    end = rest.find("\n---\n")
    if end == -1:
        raise EntityTemplateError(f"Template {kind}.md is missing YAML frontmatter")
    frontmatter = rest[:end]
    body = rest[end + len("\n---\n") :]
    return frontmatter, body


def _load_metadata(frontmatter_text: str, kind: str) -> TemplateMetadata:
    try:
        loaded = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        raise EntityTemplateError(f"Template {kind}.md has invalid YAML frontmatter: {exc}") from exc
    if not isinstance(loaded, dict) or "_template" not in loaded:
        raise EntityTemplateError(f"Template {kind}.md is missing the _template metadata block")
    try:
        return TemplateMetadata.model_validate(loaded["_template"])
    except Exception as exc:
        raise EntityTemplateError(f"Template {kind}.md _template metadata invalid: {exc}") from exc


def _parse_body_sections(body: str, kind: str) -> tuple[str, list[_ParsedSection]]:
    del kind
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        h1 = body.strip()
        return h1, []
    h1 = body[: matches[0].start()].strip()
    sections: list[_ParsedSection] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        chunk = body[match.start() : end]
        sections.append(_ParsedSection(name=match.group(1), content=chunk))
    return h1, sections


def _assert_declared_sections_exist(
    metadata: TemplateMetadata, parsed_sections: list[_ParsedSection], kind: str
) -> None:
    parsed_names = {section.name for section in parsed_sections}
    for section in metadata.sections:
        if section.name not in parsed_names:
            raise EntityTemplateError(
                f"Template {kind}.md declares section '{section.name}' but no matching heading exists in the body"
            )


def _assert_known_keys(
    metadata: TemplateMetadata,
    parsed_sections: list[_ParsedSection],
    with_keys: list[str] | tuple[str, ...],
    without_keys: list[str] | tuple[str, ...],
    kind: str,
) -> None:
    del kind
    metadata_by_name = {section.name: section for section in metadata.sections}
    valid_keys = [metadata_by_name[parsed.name].key for parsed in parsed_sections if parsed.name in metadata_by_name]
    valid_set = set(valid_keys)
    for key in list(with_keys) + list(without_keys):
        if key not in valid_set:
            raise EntityTemplateError(f"Unknown section key '{key}'. Valid keys: " + ", ".join(valid_keys))


def _context_with_computed_fields(fields: dict[str, object], today: date) -> dict[str, object]:
    context = dict(fields)
    iso_today = today.isoformat()
    slug_value = str(context.get("slug", "")) or ""
    context.setdefault("YYYY-MM-DD", iso_today)
    context.setdefault("YYYY-MM-DD-slug", f"{iso_today}-{slug_value}" if slug_value else iso_today)
    return context


def _render_frontmatter(metadata: TemplateMetadata, context: dict[str, object]) -> dict[str, object]:
    output: dict[str, object] = {}
    for name, policy in metadata.frontmatter.items():
        if policy.omit:
            continue
        if policy.from_ is not None:
            value = context.get(policy.from_)
            if value is None and "default" in policy.model_fields_set:
                value = policy.default
            output[name] = value
            continue
        value = policy.default
        if isinstance(value, str):
            value = _substitute(value, context)
        output[name] = value
    return output


def _render_body(
    *,
    h1: str,
    sections: list[_ParsedSection],
    metadata: TemplateMetadata,
    context: dict[str, object],
    with_keys: set[str],
    without_keys: set[str],
    no_hints: bool,
) -> str:
    metadata_by_name = {section.name: section for section in metadata.sections}
    pieces: list[str] = []
    rendered_h1 = _substitute(h1, context)
    if no_hints:
        rendered_h1 = _strip_hints(rendered_h1).strip()
    if rendered_h1:
        pieces.append(rendered_h1 + "\n")

    for parsed in sections:
        section = metadata_by_name[parsed.name]
        include = section.key in with_keys if not section.required else section.key not in without_keys
        if not include:
            continue
        chunk = _substitute(parsed.content, context)
        if no_hints:
            chunk = _strip_hints(chunk)
        chunk = chunk.rstrip() + "\n"
        pieces.append("\n" + chunk)
    return "".join(pieces)


def _substitute(text: str, context: dict[str, object]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key in context:
            value = context[key]
            return "" if value is None else str(value)
        return match.group(0)

    return _PLACEHOLDER_RE.sub(repl, text)


def _strip_hints(text: str) -> str:
    return _HTML_COMMENT_RE.sub("", text)


def _first_hint(content: str) -> str:
    match = _HTML_COMMENT_RE.search(content)
    if not match:
        return ""
    inner = match.group(0)[len("<!--") : -len("-->")]
    return re.sub(r"\s+", " ", inner).strip()
