"""Verify orchestration: walk a project, classify selector resolution outcomes.

Pure read-side: parses sidecars, resolves selectors, returns a report.
The write-back path (apply_supersessions) lives next door but is opt-in
and called separately by the CLI's --apply branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from science_tool.annotation.io import read_sidecar
from science_tool.annotation.model import Status
from science_tool.annotation.selector import (
    ResolutionStatus,
    resolve_selector,
)

# Directory names we never descend into when walking for sidecars.
_SKIP_DIRS: frozenset[str] = frozenset(
    {".git", ".venv", "node_modules", ".worktrees", "worktrees", "__pycache__"}
)

ISSUE_KINDS: tuple[str, ...] = ("broken", "degraded", "fuzzy", "source-missing", "parse-error")


@dataclass(frozen=True)
class VerifyIssue:
    sidecar: Path
    annotation_id: str
    source: str
    kind: str
    exact_preview: str

    def __post_init__(self) -> None:
        if self.kind not in ISSUE_KINDS:
            raise ValueError(f"unknown issue kind: {self.kind!r}")


@dataclass(frozen=True)
class VerifyReport:
    sidecars: int
    annotations: int
    superseded_skipped: int
    issues: tuple[VerifyIssue, ...]

    @property
    def broken(self) -> int:
        return sum(1 for i in self.issues if i.kind == "broken")

    @property
    def degraded(self) -> int:
        return sum(1 for i in self.issues if i.kind == "degraded")

    @property
    def fuzzy(self) -> int:
        return sum(1 for i in self.issues if i.kind == "fuzzy")

    @property
    def source_missing(self) -> int:
        return sum(1 for i in self.issues if i.kind == "source-missing")

    @property
    def parse_errors(self) -> int:
        return sum(1 for i in self.issues if i.kind == "parse-error")


def iter_sidecars(root: Path) -> Iterable[Path]:
    """Yield every `*.anno.trig` under `root` in deterministic sorted order.

    Skips a fixed set of noise directories. The yielded paths are absolute.
    """
    out: list[Path] = []
    root_resolved = root.resolve()
    for path in root.rglob("*.anno.trig"):
        rel = path.resolve().relative_to(root_resolved)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        out.append(path.resolve())
    out.sort()
    return out


def verify_path(root: Path) -> VerifyReport:
    """Walk `root`, parse every sidecar, classify every annotation."""
    issues: list[VerifyIssue] = []
    sidecar_count = 0
    annotation_count = 0
    superseded_skipped = 0
    source_cache: dict[Path, Optional[str]] = {}

    for sidecar_path in iter_sidecars(root):
        sidecar_count += 1
        try:
            sidecar = read_sidecar(sidecar_path)
        except Exception as exc:  # parse failures must not abort the walk
            issues.append(
                VerifyIssue(
                    sidecar=sidecar_path,
                    annotation_id="",
                    source="",
                    kind="parse-error",
                    exact_preview=_truncate(str(exc), 80),
                )
            )
            continue

        for ann in sidecar.annotations:
            annotation_count += 1
            if ann.status is Status.SUPERSEDED:
                superseded_skipped += 1
                continue

            source_str = ann.target.source
            text = _load_source(sidecar_path, source_str, source_cache)
            preview = _truncate(ann.target.selector.exact, 80)

            if text is None:
                issues.append(
                    VerifyIssue(
                        sidecar=sidecar_path,
                        annotation_id=ann.id,
                        source=source_str,
                        kind="source-missing",
                        exact_preview=preview,
                    )
                )
                continue

            result = resolve_selector(text, ann.target.selector)
            kind = _classify(result.status)
            if kind is None:
                continue
            issues.append(
                VerifyIssue(
                    sidecar=sidecar_path,
                    annotation_id=ann.id,
                    source=source_str,
                    kind=kind,
                    exact_preview=preview,
                )
            )

    return VerifyReport(
        sidecars=sidecar_count,
        annotations=annotation_count,
        superseded_skipped=superseded_skipped,
        issues=tuple(issues),
    )


def _classify(status: ResolutionStatus) -> Optional[str]:
    if status is ResolutionStatus.RESOLVED:
        return None
    if status is ResolutionStatus.DEGRADED:
        return "degraded"
    if status is ResolutionStatus.FUZZY:
        return "fuzzy"
    if status is ResolutionStatus.SUPERSEDED:
        return "broken"
    raise ValueError(f"unhandled resolution status: {status!r}")


def _load_source(
    sidecar_path: Path,
    source: str,
    cache: dict[Path, Optional[str]],
) -> Optional[str]:
    """Resolve and read a source file referenced from a sidecar.

    Returns None when the source is absent or is an absolute (non-file)
    URI. Caches successful and unsuccessful reads alike.
    """
    if "://" in source:
        return None
    resolved = (sidecar_path.parent / source).resolve()
    if resolved in cache:
        return cache[resolved]
    if not resolved.is_file():
        cache[resolved] = None
        return None
    text = resolved.read_text(encoding="utf-8")
    cache[resolved] = text
    return text


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"
