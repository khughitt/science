from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Literal

import yaml

IssueKind = Literal[
    "missing-frontmatter",
    "invalid-yaml",
    "missing-field",
    "invalid-field",
    "missing-section",
    "broken-relative-link",
    "missing-index-entry",
]


@dataclass(frozen=True)
class SkillIssue:
    path: Path
    kind: IssueKind
    field: str | None = None
    detail: str = ""

    def to_json(self) -> dict[str, str | None]:
        return {
            "path": self.path.as_posix(),
            "kind": self.kind,
            "field": self.field,
            "detail": self.detail,
        }


REQUIRED_FIELDS = ("name", "description")
MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+)\)")
HALT_ON_REQUIRED = {
    "data/embeddings-manifold-qa.md",
    "data/functional-genomics-qa.md",
    "data/protein-sequence-structure-qa.md",
    "data/expression/bulk-rnaseq-qa.md",
    "data/expression/microarray-qa.md",
    "data/expression/scrna-qa.md",
    "data/genomics/somatic-mutation-qa.md",
    "data/genomics/mutational-signatures-and-selection.md",
    "research/annotation-curation-qa.md",
}


def check_frontmatter(path: Path) -> list[SkillIssue]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return [SkillIssue(path, "missing-frontmatter")]
    end = text.find("\n---\n", 4)
    if end == -1:
        return [SkillIssue(path, "missing-frontmatter", detail="unterminated YAML block")]
    block = text[4:end]
    try:
        parsed = yaml.safe_load(block) or {}
    except yaml.YAMLError as exc:
        return [SkillIssue(path, "invalid-yaml", detail=str(exc))]
    if not isinstance(parsed, dict):
        return [SkillIssue(path, "invalid-yaml", detail="frontmatter is not a mapping")]

    issues: list[SkillIssue] = []
    for field in REQUIRED_FIELDS:
        if not parsed.get(field):
            issues.append(SkillIssue(path, "missing-field", field=field))
    return issues


def check_companion_skills(path: Path) -> list[SkillIssue]:
    text = path.read_text(encoding="utf-8")
    if not re.search(r"^## Companion Skills$", text, re.MULTILINE):
        return [SkillIssue(path, "missing-section", detail="Companion Skills")]
    return []


def check_halt_on_conditions(path: Path, root: Path) -> list[SkillIssue]:
    relative_path = path.relative_to(root).as_posix()
    if relative_path not in HALT_ON_REQUIRED:
        return []

    text = path.read_text(encoding="utf-8")
    if not re.search(r"^## Halt-On Conditions$", text, re.MULTILINE):
        return [SkillIssue(path, "missing-section", detail="Halt-On Conditions")]
    return []


def check_relative_links(path: Path) -> list[SkillIssue]:
    text = path.read_text(encoding="utf-8")
    issues: list[SkillIssue] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1).strip().strip("<>")
        if not _is_relative_markdown_path(target):
            continue
        target_path = target.split("#", 1)[0]
        if not (path.parent / target_path).is_file():
            issues.append(SkillIssue(path, "broken-relative-link", detail=target))
    return issues


def check_skills(root: Path) -> list[SkillIssue]:
    issues: list[SkillIssue] = []
    for path in sorted(root.rglob("*.md")):
        issues.extend(_relative_issues(check_frontmatter(path), root))
        issues.extend(_relative_issues(check_companion_skills(path), root))
        issues.extend(_relative_issues(check_halt_on_conditions(path, root), root))
        issues.extend(_relative_issues(check_relative_links(path), root))
    return issues


def _is_relative_markdown_path(target: str) -> bool:
    if target.startswith(("#", "/", "http://", "https://", "mailto:")):
        return False
    return target.split("#", 1)[0].endswith(".md")


def _relative_issues(issues: list[SkillIssue], root: Path) -> list[SkillIssue]:
    return [
        SkillIssue(
            path=issue.path.relative_to(root),
            kind=issue.kind,
            field=issue.field,
            detail=issue.detail,
        )
        for issue in issues
    ]
