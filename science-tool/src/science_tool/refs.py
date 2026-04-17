"""Cross-reference validation for Science research projects.

Scans markdown files in doc/, specs/, and RESEARCH_PLAN.md for internal
references (hypothesis IDs, citations, markdown links, markers) and validates
them against the project file system and bibliography.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RefIssue:
    """A single broken or unresolved reference."""

    file: str
    line: int
    ref_type: str  # "hypothesis" | "citation" | "link" | "marker"
    ref_value: str
    message: str
    suggestion: str | None = None


# Patterns
_HYPOTHESIS_RE = re.compile(r"\bH(\d{2,})\b")
_CITATION_RE = re.compile(r"\[@([^\]]+)\]")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_UNVERIFIED_RE = re.compile(r"\[UNVERIFIED\]")
_NEEDS_CITATION_RE = re.compile(r"\[NEEDS CITATION\]")
# Task IDs — `tNN` or `tNNN`, optionally inside square brackets. Anchored on
# word boundaries so adjacent letters do not produce false positives.
_TASK_ID_RE = re.compile(r"\bt(\d{2,})\b")
# Task ID *declarations* in tasks/active.md and tasks/done/*.md headers, of the
# form `## [tNN] ...` or `## [tNNN] ...`.
_TASK_DECL_RE = re.compile(r"^\s*#+\s*\[t(\d{2,})\]")
# Tokens that should not trigger task-ID validation when they happen to match
# the regex above (e.g. the `t` of an article slug).
_TASK_FALSE_POSITIVE_PARENTS = (
    ".bib",
    ".csv",
    ".tsv",
    ".bibtex",
)

# Directories/files to scan
_SCAN_DIRS = ("doc", "specs")
_SCAN_FILES = ("RESEARCH_PLAN.md",)
# Skip directories
_SKIP_DIRS = {"templates", ".venv", "data", ".git", "__pycache__"}


def _collect_markdown_files(root: Path) -> list[Path]:
    """Collect all markdown files to scan."""
    try:
        from science_tool.paths import resolve_paths

        pp = resolve_paths(root)
        scan_dirs = [pp.doc_dir, pp.specs_dir]
    except Exception:
        scan_dirs = [root / d for d in _SCAN_DIRS]

    files: list[Path] = []
    for d in scan_dirs:
        if d.is_dir():
            for p in d.rglob("*.md"):
                if not any(part in _SKIP_DIRS for part in p.parts):
                    files.append(p)
    for scan_file in _SCAN_FILES:
        f = root / scan_file
        if f.is_file():
            files.append(f)
    return sorted(files)


def _load_hypothesis_ids(root: Path) -> dict[str, Path]:
    """Map hypothesis IDs (e.g. '01') to their files."""
    hyp_dir = root / "specs" / "hypotheses"
    if not hyp_dir.is_dir():
        return {}
    result: dict[str, Path] = {}
    for p in hyp_dir.glob("h*-*.md"):
        match = re.match(r"h(\d+)-", p.name)
        if match:
            result[match.group(1)] = p
    return result


def _load_task_ids(root: Path) -> set[str]:
    """Collect all declared task IDs from tasks/active.md and tasks/done/*.md.

    A task is "declared" when it appears as a markdown header of the form
    `## [tNN] ...` (the canonical format produced by `science-tool tasks add`).
    Returns the set of bare numeric IDs (e.g. `"75"`, not `"t75"`).
    """
    declared: set[str] = set()
    candidates: list[Path] = []
    active = root / "tasks" / "active.md"
    if active.is_file():
        candidates.append(active)
    done_dir = root / "tasks" / "done"
    if done_dir.is_dir():
        candidates.extend(done_dir.glob("*.md"))
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in _TASK_DECL_RE.finditer(text):
            declared.add(match.group(1))
    return declared


def _load_bib_keys(root: Path) -> set[str]:
    """Extract all BibTeX entry keys from references.bib."""
    bib_path = root / "papers" / "references.bib"
    if not bib_path.is_file():
        return set()
    keys: set[str] = set()
    bib_re = re.compile(r"@\w+\{(\w+),")
    for line in bib_path.read_text(encoding="utf-8").splitlines():
        m = bib_re.match(line.strip())
        if m:
            keys.add(m.group(1))
    return keys


def _is_heading_line(line: str) -> bool:
    """Check if a line is a markdown heading."""
    return line.lstrip().startswith("#")


def _hypothesis_id_from_path(file_path: Path) -> str | None:
    """Extract hypothesis number from a hypothesis file path."""
    match = re.match(r"h(\d+)-", file_path.name)
    return match.group(1) if match else None


def check_refs(root: Path) -> list[RefIssue]:
    """Run all reference checks and return issues found."""
    issues: list[RefIssue] = []
    files = _collect_markdown_files(root)
    hyp_ids = _load_hypothesis_ids(root)
    bib_keys = _load_bib_keys(root)
    task_ids = _load_task_ids(root)

    for file_path in files:
        rel_path = str(file_path.relative_to(root))
        # Determine if this file IS a hypothesis file (skip self-references)
        own_hyp_id = None
        if "hypotheses" in file_path.parts:
            own_hyp_id = _hypothesis_id_from_path(file_path)

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        # Skip task-ID validation in files where `tNN` tokens are noisy
        # (BibTeX-derived bibliographies, exported tabular data).
        skip_task_check = any(rel_path.endswith(suffix) for suffix in _TASK_FALSE_POSITIVE_PARENTS)
        # Files inside tasks/ legitimately reference their own and other task
        # IDs in headers — declarations are not "broken refs". Skip those.
        skip_task_check = skip_task_check or rel_path.startswith("tasks/")

        for line_num, line in enumerate(lines, start=1):
            # Skip headings and frontmatter for hypothesis checks
            if _is_heading_line(line):
                continue

            # --- Task ID references ---
            if not skip_task_check and task_ids:
                for m in _TASK_ID_RE.finditer(line):
                    task_num = m.group(1)
                    if task_num in task_ids:
                        continue
                    issues.append(
                        RefIssue(
                            file=rel_path,
                            line=line_num,
                            ref_type="task",
                            ref_value=f"t{task_num}",
                            message=f"t{task_num} — no matching declaration in tasks/active.md or tasks/done/*.md",
                        )
                    )

            # --- Hypothesis references ---
            for m in _HYPOTHESIS_RE.finditer(line):
                hyp_num = m.group(1)
                if hyp_num == own_hyp_id:
                    continue  # Self-reference in own file
                if hyp_num not in hyp_ids:
                    suggestion = None
                    if hyp_ids:
                        # Suggest closest existing ID
                        existing = sorted(hyp_ids.keys())
                        suggestion = f"Existing hypotheses: {', '.join(f'H{h}' for h in existing)}"
                    issues.append(
                        RefIssue(
                            file=rel_path,
                            line=line_num,
                            ref_type="hypothesis",
                            ref_value=f"H{hyp_num}",
                            message=f"H{hyp_num} — no matching file in specs/hypotheses/",
                            suggestion=suggestion,
                        )
                    )

            # --- Citation references ---
            for m in _CITATION_RE.finditer(line):
                cite_group = m.group(1)
                # Split on ; for multi-cites like [@Smith2024; @Jones2023]
                for part in cite_group.split(";"):
                    key = part.strip().lstrip("@").split(",")[0].split(" ")[0].strip()
                    if not key:
                        continue
                    if key not in bib_keys:
                        issues.append(
                            RefIssue(
                                file=rel_path,
                                line=line_num,
                                ref_type="citation",
                                ref_value=key,
                                message=f"@{key} — not in papers/references.bib",
                            )
                        )

            # --- Markdown links ---
            for m in _LINK_RE.finditer(line):
                target = m.group(2)
                # Skip external URLs and anchors
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                # Resolve relative to the file's directory
                resolved = (file_path.parent / target).resolve()
                if not resolved.exists():
                    # Also try relative to project root
                    resolved_root = (root / target).resolve()
                    if not resolved_root.exists():
                        issues.append(
                            RefIssue(
                                file=rel_path,
                                line=line_num,
                                ref_type="link",
                                ref_value=target,
                                message=f"Link target not found: {target}",
                            )
                        )

            # --- Unresolved markers ---
            for m in _UNVERIFIED_RE.finditer(line):
                issues.append(
                    RefIssue(
                        file=rel_path,
                        line=line_num,
                        ref_type="marker",
                        ref_value="[UNVERIFIED]",
                        message="Unresolved [UNVERIFIED] marker",
                    )
                )
            for m in _NEEDS_CITATION_RE.finditer(line):
                issues.append(
                    RefIssue(
                        file=rel_path,
                        line=line_num,
                        ref_type="marker",
                        ref_value="[NEEDS CITATION]",
                        message="Unresolved [NEEDS CITATION] marker",
                    )
                )

    return issues
