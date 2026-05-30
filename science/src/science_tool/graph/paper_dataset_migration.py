"""Mechanical migration from paper.datasets to paper.dataset_usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml

ConflictReason = Literal[
    "malformed-frontmatter",
    "malformed-datasets",
    "malformed-usage",
    "role-conflict",
    "roundtrip-failure",
]


@dataclass(frozen=True, slots=True)
class PaperDatasetMigrationConflict:
    path: str
    paper_id: str | None
    dataset_ref: str | None
    reason: ConflictReason
    detail: str

    def to_json(self) -> dict[str, str | None]:
        return {
            "path": self.path,
            "paper_id": self.paper_id,
            "dataset_ref": self.dataset_ref,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class PaperDatasetMigrationResult:
    path: str
    changed: bool
    updated_text: str
    conflicts: list[PaperDatasetMigrationConflict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PaperDatasetMigrationReport:
    project_root: str
    apply: bool
    changed_files: list[str]
    conflicts: list[PaperDatasetMigrationConflict]

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def changed_file_count(self) -> int:
        return len(self.changed_files)

    def to_json(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "apply": self.apply,
            "changed_files": self.changed_files,
            "changed_file_count": self.changed_file_count,
            "conflicts": [conflict.to_json() for conflict in self.conflicts],
            "conflict_count": self.conflict_count,
        }


def is_paper_dataset_role_conflict(entry: Mapping[str, Any]) -> bool:
    return entry.get("role") != "analyzed"


def plan_paper_dataset_migration(project_root: Path, *, apply: bool = False) -> PaperDatasetMigrationReport:
    root = project_root.resolve()
    changed_files: list[str] = []
    conflicts: list[PaperDatasetMigrationConflict] = []
    for path in _candidate_markdown_files(root):
        text = path.read_text(encoding="utf-8")
        result = migrate_paper_frontmatter(path, text)
        if result.conflicts:
            if _looks_like_paper_source_path(root, path):
                conflicts.extend(result.conflicts)
            continue
        if result.changed:
            changed_files.append(str(path))
            if apply:
                path.write_text(result.updated_text, encoding="utf-8")
    return PaperDatasetMigrationReport(
        project_root=str(root),
        apply=apply,
        changed_files=sorted(changed_files),
        conflicts=sorted(conflicts, key=lambda item: (item.path, item.reason, item.dataset_ref or "")),
    )


def migrate_paper_frontmatter(path: str | Path, text: str) -> PaperDatasetMigrationResult:
    path_str = str(path)
    split = _split_frontmatter(text)
    if split is None:
        return PaperDatasetMigrationResult(path=path_str, changed=False, updated_text=text)
    prefix, yaml_text, suffix = split
    try:
        loaded = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        return PaperDatasetMigrationResult(
            path=path_str,
            changed=False,
            updated_text=text,
            conflicts=[
                PaperDatasetMigrationConflict(
                    path=path_str,
                    paper_id=None,
                    dataset_ref=None,
                    reason="malformed-frontmatter",
                    detail=str(exc).splitlines()[0],
                )
            ],
        )
    if not isinstance(loaded, dict):
        return _single_conflict(path_str, text, None, None, "malformed-frontmatter", "frontmatter must be a mapping")
    kind = loaded.get("kind") or loaded.get("type")
    if kind != "paper":
        return PaperDatasetMigrationResult(path=path_str, changed=False, updated_text=text)

    paper_id = loaded.get("id") if isinstance(loaded.get("id"), str) else None
    raw_datasets = loaded.get("datasets")
    if raw_datasets is None:
        return PaperDatasetMigrationResult(path=path_str, changed=False, updated_text=text)
    if raw_datasets == []:
        updated = dict(loaded)
        updated.pop("datasets", None)
        return _dump_result(path_str, text, prefix, updated, suffix)
    if not isinstance(raw_datasets, list) or any(
        not isinstance(ref, str) or not ref.startswith("dataset:") for ref in raw_datasets
    ):
        return _single_conflict(
            path_str,
            text,
            paper_id,
            None,
            "malformed-datasets",
            "datasets must be a list of dataset: strings",
        )

    usage = loaded.get("dataset_usage", [])
    if usage is None:
        usage = []
    if not isinstance(usage, list):
        return _single_conflict(path_str, text, paper_id, None, "malformed-usage", "dataset_usage must be a list")
    for index, entry in enumerate(usage):
        defect = _usage_defect(entry)
        if defect is not None:
            return _single_conflict(
                path_str,
                text,
                paper_id,
                None,
                "malformed-usage",
                f"dataset_usage[{index}] {defect}",
            )

    explicit_by_ref = {str(entry["ref"]): entry for entry in usage}
    deduped_legacy = list(dict.fromkeys(raw_datasets))
    for ref in deduped_legacy:
        explicit = explicit_by_ref.get(ref)
        if explicit is not None and is_paper_dataset_role_conflict(explicit):
            return _single_conflict(
                path_str,
                text,
                paper_id,
                ref,
                "role-conflict",
                f"legacy paper.datasets implies role analyzed but explicit dataset_usage has role {explicit.get('role')}",
            )

    updated = dict(loaded)
    updated_usage = list(usage)
    explicit_refs = {str(entry["ref"]) for entry in updated_usage}
    for ref in deduped_legacy:
        if ref not in explicit_refs:
            updated_usage.append({"ref": ref, "role": "analyzed", "overlap": "unknown"})
            explicit_refs.add(ref)
    updated["dataset_usage"] = updated_usage
    updated.pop("datasets", None)
    return _dump_result(path_str, text, prefix, updated, suffix)


def _usage_defect(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "must be an object"
    if not isinstance(entry.get("ref"), str) or not str(entry["ref"]).startswith("dataset:"):
        return "must have a dataset: ref"
    if not isinstance(entry.get("role"), str):
        return "must have a role"
    overlap = entry.get("overlap")
    if overlap is not None and not isinstance(overlap, str):
        return "overlap must be a string"
    return None


def _split_frontmatter(text: str) -> tuple[str, str, str] | None:
    if not text.startswith("---\n"):
        return None
    close = text.find("\n---", 4)
    if close < 0:
        return None
    end = close + len("\n---")
    if text[end : end + 1] == "\n":
        end += 1
    return "---\n", text[4:close], text[end:]


def _dump_result(
    path: str,
    original: str,
    prefix: str,
    frontmatter: dict[str, Any],
    suffix: str,
) -> PaperDatasetMigrationResult:
    dumped = yaml.safe_dump(frontmatter, sort_keys=False)
    updated_text = f"{prefix}{dumped}---\n{suffix}"
    if not updated_text.startswith("---\n") or "\n---\n" not in updated_text:
        return _single_conflict(path, original, _paper_id(frontmatter), None, "roundtrip-failure", "frontmatter roundtrip failed")
    return PaperDatasetMigrationResult(path=path, changed=updated_text != original, updated_text=updated_text)


def _single_conflict(
    path: str,
    text: str,
    paper_id: str | None,
    dataset_ref: str | None,
    reason: ConflictReason,
    detail: str,
) -> PaperDatasetMigrationResult:
    return PaperDatasetMigrationResult(
        path=path,
        changed=False,
        updated_text=text,
        conflicts=[PaperDatasetMigrationConflict(path, paper_id, dataset_ref, reason, detail)],
    )


def _paper_id(frontmatter: Mapping[str, Any]) -> str | None:
    value = frontmatter.get("id")
    return value if isinstance(value, str) else None


def _candidate_markdown_files(project_root: Path) -> list[Path]:
    roots = [project_root / "doc" / "papers", project_root / "doc" / "background" / "papers"]
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(path for path in root.rglob("*.md") if path.is_file())
    doc_root = project_root / "doc"
    if doc_root.is_dir():
        files.extend(path for path in doc_root.rglob("*.md") if path.is_file())
    return sorted(set(files))


def _looks_like_paper_source_path(project_root: Path, path: Path) -> bool:
    try:
        rel = path.relative_to(project_root)
    except ValueError:
        return False
    parts = rel.parts
    return len(parts) >= 3 and parts[0] == "doc" and parts[-2] == "papers"
