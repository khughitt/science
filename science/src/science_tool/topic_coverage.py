from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from science_tool.markdown_utils import rendered_prose

# Placeholder sentences emitted by the promotion / substrate-retirement path.
# NOTE: duplicates a string that path owns; centralizing this constant with the
# emitter is deferred (design §Follow-ups).
STUB_SENTINEL = re.compile(r"(has|have) not yet been (curated|added|separately curated)", re.IGNORECASE)
_HEADING = re.compile(r"^#+\s")
_LIST_MARKER = re.compile(r"^([-*+]|\d+\.)\s+")


class MalformedTopicError(ValueError):
    """A topic file has a frontmatter block that does not parse to a mapping."""


@dataclass(frozen=True)
class TopicRow:
    id: str
    title: str
    path: str  # project-root-relative, POSIX
    substantive: bool

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "path": self.path, "substantive": self.substantive}


@dataclass(frozen=True)
class TopicCoverage:
    n_topics: int
    n_substantive: int
    stub_ratio: float | None
    stub_dominated: bool
    note: str | None
    topics: tuple[TopicRow, ...]

    def to_dict(self) -> dict:
        out: dict = {
            "n_topics": self.n_topics,
            "n_substantive": self.n_substantive,
            "stub_ratio": self.stub_ratio,
            "stub_dominated": self.stub_dominated,
            "topics": [r.to_dict() for r in self.topics],
        }
        if self.note is not None:
            out["note"] = self.note
        return out


def _read_frontmatter_strict(path: Path) -> tuple[dict, int]:
    """Return ``(frontmatter, body_start_line)``.

    An absent or validly-empty block returns ``({}, ...)``; a present block that
    fails to parse or is not a mapping raises ``MalformedTopicError``. Unlike
    ``markdown_utils.parse_frontmatter``, YAML errors are NOT swallowed.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 1  # genuinely no frontmatter block
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            try:
                data = yaml.safe_load("\n".join(lines[1 : i - 1]))
            except yaml.YAMLError as exc:
                raise MalformedTopicError(f"{path}: unparseable frontmatter: {exc}") from exc
            if data is None:
                return {}, i + 1  # validly empty block -> stem fallback upstream
            if not isinstance(data, dict):
                raise MalformedTopicError(f"{path}: frontmatter is not a mapping")
            return data, i + 1
    raise MalformedTopicError(f"{path}: unterminated frontmatter block")


def _residual_content_lines(body: str) -> list[str]:
    lines: list[str] = []
    for raw in rendered_prose(body).splitlines():
        line = raw.strip()
        if not line or _HEADING.match(line):
            continue
        line = _LIST_MARKER.sub("", line).strip()
        if line:
            lines.append(line)
    return lines


def _is_stub(body: str) -> bool:
    residual = _residual_content_lines(body)
    if not residual:
        return True
    # search (not fullmatch): catches lines that combine boilerplate with a sentinel,
    # e.g. "This topic exists as a promoted project term. ... has not yet been curated."
    return all(STUB_SENTINEL.search(line) for line in residual)


def _load_row(path: Path, project_root: Path) -> TopicRow | None:
    data, body_start = _read_frontmatter_strict(path)
    kind = data.get("kind")
    if kind is not None and kind != "topic":
        return None
    stem = path.stem
    body = "\n".join(path.read_text(encoding="utf-8").splitlines()[body_start - 1 :])
    return TopicRow(
        id=data.get("id") or f"topic:{stem}",
        title=data.get("title") or stem,
        path=path.relative_to(project_root).as_posix(),
        substantive=not _is_stub(body),
    )


def compute_topic_coverage(project_root: Path) -> TopicCoverage:
    project_root = project_root.resolve()
    topics_dir = project_root / "entities" / "topics"
    rows: list[TopicRow] = []
    if topics_dir.is_dir():
        for path in sorted(topics_dir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            row = _load_row(path, project_root)
            if row is not None:
                rows.append(row)
    rows.sort(key=lambda r: r.id)

    n_topics = len(rows)
    n_substantive = sum(1 for r in rows if r.substantive)
    if n_topics == 0:
        return TopicCoverage(0, 0, None, False, "no topics", ())
    stub_ratio = 1 - n_substantive / n_topics
    return TopicCoverage(n_topics, n_substantive, stub_ratio, stub_ratio > 0.5, None, tuple(rows))
