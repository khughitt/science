from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from science_tool.skills_lint.discovery import iter_skill_files
from science_tool.skills_lint.sources import (
    SourcesRegistry,
    leaf_frontmatter,
    leaf_source_refs,
    load_sources,
    sources_wellformed,
)

Severity = Literal["error", "warn"]

IssueKind = Literal[
    "missing-frontmatter",
    "invalid-yaml",
    "missing-field",
    "invalid-field",
    "missing-section",
    "broken-relative-link",
    "missing-index-entry",
    "unknown-source-ref",
    "invalid-source-record",
    "missing-provenance",
    "invalid-provenance",
    "missing-archetype",
]

MISSING_PROVENANCE_SEVERITY: Severity = "error"
MISSING_ARCHETYPE_SEVERITY: Severity = "error"

ProvenanceState = Literal[
    "attributed", "internal", "undeclared", "contradiction", "bad-marker", "malformed-sources"
]


@dataclass(frozen=True)
class SkillIssue:
    path: Path
    kind: IssueKind
    field: str | None = None
    detail: str = ""
    severity: Severity = "error"

    def to_json(self) -> dict[str, str | None]:
        return {
            "path": self.path.as_posix(),
            "kind": self.kind,
            "field": self.field,
            "detail": self.detail,
            "severity": self.severity,
        }


REQUIRED_FIELDS = ("name", "description")
VALID_DEPTHS = {"standard", "deep-reference"}
VALID_ARCHETYPES = {
    "measurement-qa", "method-guide", "analysis-discipline",
    "normative-reference", "tool-guide", "practice-guide",
}
STRUCTURAL_FILENAMES = {"SKILL.md", "INDEX.md"}
MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`([^`]+\.md)`")
HALT_ON_REQUIRED = {
    "bio/genomics/somatic-mutation-qa.md",
    "bio/genomics/mutational-signatures-and-selection.md",
    "bio/transcriptomics/bulk-rnaseq-qa.md",
    "bio/transcriptomics/microarray-qa.md",
    "bio/transcriptomics/scrna-qa.md",
    "bio/proteomics/protein-sequence-structure-qa.md",
    "bio/functional-genomics-qa.md",
    "ml/embeddings-manifold-qa.md",
    "epistemics/annotation-curation-qa.md",
}


def check_frontmatter(path: Path) -> list[SkillIssue]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return [SkillIssue(path, "missing-frontmatter")]
    end = text.find("\n---\n", 3)
    if end == -1:
        return [SkillIssue(path, "missing-frontmatter", detail="unterminated YAML block")]
    block = text[4:end]
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        return [SkillIssue(path, "invalid-yaml", detail=str(exc))]
    if parsed is None:
        parsed = {}  # empty frontmatter block is a valid, empty mapping
    if not isinstance(parsed, dict):
        return [SkillIssue(path, "invalid-yaml", detail="frontmatter is not a mapping")]

    issues: list[SkillIssue] = []
    for field in REQUIRED_FIELDS:
        if not parsed.get(field):
            issues.append(SkillIssue(path, "missing-field", field=field))
    if "type" in parsed:
        issues.append(SkillIssue(path, "invalid-field", field="type", detail="'type' was renamed to 'depth'"))
    if "depth" in parsed and (not isinstance(parsed["depth"], str) or parsed["depth"] not in VALID_DEPTHS):
        issues.append(SkillIssue(path, "invalid-field", field="depth", detail=str(parsed["depth"])))
    if "archetype" in parsed:
        archetype = parsed["archetype"]
        if path.name in STRUCTURAL_FILENAMES:
            issues.append(SkillIssue(path, "invalid-field", field="archetype", detail="leaf-only field; routers and INDEX derive structural role"))
        elif not isinstance(archetype, str) or archetype not in VALID_ARCHETYPES:
            issues.append(SkillIssue(path, "invalid-field", field="archetype", detail=str(archetype)))
    elif path.name not in STRUCTURAL_FILENAMES:
        issues.append(
            SkillIssue(
                path,
                "missing-archetype",
                field="archetype",
                detail="every leaf must declare exactly one recognized archetype",
                severity=MISSING_ARCHETYPE_SEVERITY,
            )
        )
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


def check_index_coverage(root: Path) -> list[SkillIssue]:
    index_path = root / "INDEX.md"
    if not index_path.is_file():
        return [SkillIssue(Path("INDEX.md"), "missing-index-entry", detail="INDEX.md")]

    indexed_paths = _collect_indexed_paths(index_path.read_text(encoding="utf-8"))
    issues: list[SkillIssue] = []
    for path in iter_skill_files(root):
        relative_path = path.relative_to(root).as_posix()
        if relative_path == "INDEX.md" or relative_path in indexed_paths:
            continue
        issues.append(SkillIssue(Path("INDEX.md"), "missing-index-entry", detail=relative_path))
    return issues


def check_source_refs(path: Path, registry: SourcesRegistry) -> list[SkillIssue]:
    refs, error = leaf_source_refs(path)
    if error is not None:
        return [SkillIssue(path, "invalid-field", field="sources", detail=error)]
    if refs is None:
        return []
    return [
        SkillIssue(path, "unknown-source-ref", detail=ref)
        for ref in refs
        if ref not in registry.declared_ids
    ]


def classify_provenance(frontmatter: dict[str, Any]) -> ProvenanceState:
    has_sources = "sources" in frontmatter
    has_provenance = "provenance" in frontmatter
    if has_sources and has_provenance:
        return "contradiction"
    if has_sources:
        # A present `sources` key is a declaration attempt; well-formedness is the
        # source-ref check's job to REPORT, but the classifier must not call a
        # malformed list "attributed" (design: sources: [] is invalid, not attributed).
        return "attributed" if sources_wellformed(frontmatter["sources"]) else "malformed-sources"
    if has_provenance:
        return "internal" if frontmatter.get("provenance") == "internal" else "bad-marker"
    return "undeclared"


def check_provenance(path: Path) -> list[SkillIssue]:
    frontmatter = leaf_frontmatter(path)
    if frontmatter is None:
        return []  # missing/unterminated/unparsable/non-mapping frontmatter already reported; no cascade
    state = classify_provenance(frontmatter)
    if state == "undeclared":
        return [SkillIssue(path, "missing-provenance", severity=MISSING_PROVENANCE_SEVERITY)]
    if state == "contradiction":
        return [SkillIssue(path, "invalid-provenance", detail="sources: and provenance: are mutually exclusive")]
    if state == "bad-marker":
        value = frontmatter.get("provenance")
        return [SkillIssue(path, "invalid-provenance", field="provenance", detail=f"unknown value {value!r}; only 'internal' is allowed")]
    # attributed / internal → clean. malformed-sources → silent HERE; check_source_refs
    # reports it as invalid-field (single report, no missing-provenance cascade).
    return []


def check_skills(root: Path) -> list[SkillIssue]:
    issues: list[SkillIssue] = []
    registry = load_sources(root / "sources.yaml")
    issues.extend(
        _relative_issues(
            [
                SkillIssue(root / "sources.yaml", "invalid-source-record", field=sid, detail="; ".join(problems))
                for sid, problems in registry.errors.items()
            ],
            root,
        )
    )
    for path in iter_skill_files(root):
        issues.extend(_relative_issues(check_frontmatter(path), root))
        issues.extend(_relative_issues(check_companion_skills(path), root))
        issues.extend(_relative_issues(check_halt_on_conditions(path, root), root))
        issues.extend(_relative_issues(check_relative_links(path), root))
        issues.extend(_relative_issues(check_source_refs(path, registry), root))
        if path != root / "INDEX.md":
            issues.extend(_relative_issues(check_provenance(path), root))
    issues.extend(check_index_coverage(root))
    return issues


def _is_relative_markdown_path(target: str) -> bool:
    if target.startswith(("#", "/", "http://", "https://", "mailto:")):
        return False
    return target.split("#", 1)[0].endswith(".md")


def _collect_indexed_paths(index_text: str) -> set[str]:
    targets = [match.group(1) for match in MARKDOWN_LINK_RE.finditer(index_text)]
    targets.extend(match.group(1) for match in INLINE_CODE_RE.finditer(index_text))
    indexed_paths: set[str] = set()
    for target in targets:
        normalized = _normalize_index_target(target)
        if normalized is not None:
            indexed_paths.add(normalized)
    return indexed_paths


def _normalize_index_target(target: str) -> str | None:
    clean_target = target.strip().strip("<>").split("#", 1)[0]
    if not _is_relative_markdown_path(clean_target):
        return None
    if clean_target.startswith("./"):
        clean_target = clean_target[2:]
    if clean_target.startswith("skills/"):
        clean_target = clean_target.removeprefix("skills/")
    if clean_target.startswith("../"):
        return None
    return Path(clean_target).as_posix()


def _relative_issues(issues: list[SkillIssue], root: Path) -> list[SkillIssue]:
    return [
        SkillIssue(
            path=issue.path.relative_to(root),
            kind=issue.kind,
            field=issue.field,
            detail=issue.detail,
            severity=issue.severity,
        )
        for issue in issues
    ]
