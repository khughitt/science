from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

GIT_BACKED_KINDS = frozenset({"skill-repo", "package-docs"})
REFERENCE_KINDS = frozenset({"book", "paper", "course"})
VALID_KINDS = GIT_BACKED_KINDS | REFERENCE_KINDS
FETCH_HOST_ALLOWLIST = frozenset({"github.com"})
SOURCE_KNOWN_KEYS = frozenset(
    {
        "title", "authors", "url", "kind", "license", "attribution_notice",
        "upstream_ref", "last_checked", "doi", "arxiv", "isbn", "notes",
    }
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
ARXIV_RE = re.compile(r"^(\d{4}\.\d{4,5}(v\d+)?|[a-z-]+(\.[A-Z]{2})?/\d{7}(v\d+)?)$")
ISBN_RE = re.compile(r"^(\d{13}|\d{9}[\dXx])$")


@dataclass(frozen=True)
class SourceRecord:
    id: str
    title: str
    authors: tuple[str, ...]
    url: str
    kind: str
    last_checked: str
    license: str | None = None
    attribution_notice: str | None = None
    upstream_ref: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    isbn: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class SourcesRegistry:
    records: dict[str, SourceRecord]
    errors: dict[str, list[str]]
    declared_ids: frozenset[str]


def iso_date(value: object) -> str | None:
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    return None


def _identifier_problem(ident: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return f"{ident} must be a non-empty string when present"
    if ident == "doi" and not DOI_RE.match(value):
        return "doi is malformed"
    if ident == "arxiv" and not ARXIV_RE.match(value):
        return "arxiv is malformed"
    if ident == "isbn" and not ISBN_RE.match(value.replace("-", "").replace(" ", "")):
        return "isbn is malformed"
    return None


def validate_record(source_id: object, raw: object) -> list[str]:
    if not isinstance(source_id, str) or not source_id:
        return ["source id must be a non-empty string"]
    if not isinstance(raw, dict):
        return ["record must be a mapping"]

    problems: list[str] = []
    unknown = set(raw) - SOURCE_KNOWN_KEYS
    if unknown:
        problems.append(f"unknown keys: {', '.join(sorted(unknown))}")

    if not isinstance(raw.get("title"), str) or not str(raw.get("title")).strip():
        problems.append("title must be a non-empty string")

    authors = raw.get("authors")
    if not isinstance(authors, list) or not authors or not all(
        isinstance(a, str) and a.strip() for a in authors
    ):
        problems.append("authors must be a non-empty list of strings")

    kind = raw.get("kind")
    if kind not in VALID_KINDS:
        problems.append(f"kind must be one of {sorted(VALID_KINDS)}")

    url = raw.get("url")
    parsed = None
    if not isinstance(url, str) or not url:
        problems.append("url is required")
    else:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            problems.append("url must use https")
        elif not parsed.hostname:
            problems.append("url must include a hostname")

    if iso_date(raw.get("last_checked")) is None:
        problems.append("last_checked must be an ISO date")

    for ident in ("doi", "arxiv", "isbn"):
        problem = _identifier_problem(ident, raw.get(ident))
        if problem:
            problems.append(problem)

    for opt in ("license", "attribution_notice", "notes"):
        value = raw.get(opt)
        if value is not None and not isinstance(value, str):
            problems.append(f"{opt} must be a string when present")

    if kind in GIT_BACKED_KINDS:
        ref = raw.get("upstream_ref")
        if not isinstance(ref, str) or not SHA_RE.match(ref):
            problems.append("git-backed source requires a full 40-hex upstream_ref")
        lic = raw.get("license")
        if not isinstance(lic, str) or not lic.strip():
            problems.append("git-backed source requires a license")
        if parsed is not None and parsed.hostname not in FETCH_HOST_ALLOWLIST:
            problems.append(f"git-backed url host must be in {sorted(FETCH_HOST_ALLOWLIST)}")
    elif kind in REFERENCE_KINDS and "upstream_ref" in raw:
        problems.append("reference-only source must not set upstream_ref")

    return problems


def _build_record(source_id: str, raw: dict[str, Any]) -> SourceRecord:
    return SourceRecord(
        id=source_id,
        title=raw["title"],
        authors=tuple(raw["authors"]),
        url=raw["url"],
        kind=raw["kind"],
        last_checked=iso_date(raw["last_checked"]) or "",
        license=raw.get("license"),
        attribution_notice=raw.get("attribution_notice"),
        upstream_ref=raw.get("upstream_ref"),
        doi=raw.get("doi"),
        arxiv=raw.get("arxiv"),
        isbn=raw.get("isbn"),
        notes=raw.get("notes"),
    )


def load_sources(path: Path) -> SourcesRegistry:
    empty = SourcesRegistry(records={}, errors={}, declared_ids=frozenset())
    if not path.is_file():
        return empty
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return SourcesRegistry(records={}, errors={"<file>": [f"invalid YAML: {exc}"]}, declared_ids=frozenset())
    if not isinstance(raw, dict):
        return SourcesRegistry(records={}, errors={"<file>": ["sources.yaml is not a mapping"]}, declared_ids=frozenset())

    records: dict[str, SourceRecord] = {}
    errors: dict[str, list[str]] = {}
    for source_id, record_raw in raw.items():
        sid = str(source_id)
        problems = validate_record(source_id, record_raw)
        if problems:
            errors[sid] = problems
        else:
            records[sid] = _build_record(sid, record_raw)
    return SourcesRegistry(records=records, errors=errors, declared_ids=frozenset(str(k) for k in raw))


def parse_frontmatter(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    try:
        parsed = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def leaf_source_refs(path: Path) -> tuple[list[str] | None, str | None]:
    frontmatter = parse_frontmatter(path)
    if frontmatter is None or "sources" not in frontmatter:
        return None, None
    raw = frontmatter["sources"]
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        return None, "sources must be a list of strings"
    return list(raw), None
