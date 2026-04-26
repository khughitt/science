from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


def check_skills(root: Path) -> list[SkillIssue]:
    issues: list[SkillIssue] = []
    for path in sorted(root.rglob("*.md")):
        issues.extend(_relative_issues(check_frontmatter(path), root))
    return issues


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
