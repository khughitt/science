"""Annotation-token scanner — single source of truth for marker scanning.

Used by both `science refs check` and `validate.sh` (via
`science markers scan --format json`). See
`docs/conventions/annotation-tokens.md` for the vocabulary and severity rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.markdown_utils import is_fence_line

# Canonical token names, ordered for stable display.
TOKENS: tuple[str, ...] = ("UNVERIFIED", "MISSING_CITATION", "SPECULATION", "INACCESSIBLE")

# Default severity per token. `--strict` promotes any "info" entry to "warn".
DEFAULT_SEVERITY: dict[str, str] = {
    "UNVERIFIED": "warn",
    "MISSING_CITATION": "warn",
    "SPECULATION": "info",
    "INACCESSIBLE": "info",
}

@dataclass(frozen=True)
class MarkerHit:
    """One marker occurrence found by the scanner."""

    file: Path
    line: int
    token: str  # one of TOKENS
    severity: str  # "warn" | "info"
    in_documentation: bool  # True if backticked or inside a fenced code block


def severity_for(token: str, *, strict: bool) -> str:
    """Resolve effective severity for a canonical token under the strict flag."""
    base = DEFAULT_SEVERITY[token]
    if strict and base == "info":
        return "warn"
    return base


# Pattern matches every literal canonical marker token. Anything else inside
# brackets is left alone.
_RECOGNIZED_INNER = "|".join(sorted(TOKENS, key=len, reverse=True))
_TOKEN_RE = re.compile(rf"\[(?P<inner>{_RECOGNIZED_INNER})\]")


def _frontmatter_end_line(lines: list[str]) -> int:
    """Return the 1-based line number of the closing `---` of frontmatter, or 0.

    A return of 0 means: no frontmatter present (or unterminated). Callers
    skip lines `<= return value` from prose scanning.
    """
    if not lines or lines[0].strip() != "---":
        return 0
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return index
    return 0


def _backtick_spans(line: str) -> list[tuple[int, int]]:
    """Return (start, end) char ranges (inclusive-exclusive) inside backtick spans.

    Single-line spans only. CommonMark inline-code spans do not cross newlines,
    so this is sufficient for marker classification.
    """
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(line):
        if line[i] == "`":
            j = line.find("`", i + 1)
            if j == -1:
                break
            spans.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return spans


def _position_inside_any(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def scan_text(file: Path, text: str, *, strict: bool) -> list[MarkerHit]:
    """Scan a single document's text and return all marker hits.

    Tokens are classified as `in_documentation=True` when they appear inside
    a backtick span on a prose line OR anywhere on a line within a fenced
    code block. Tokens on the fence-delimiter line itself are also treated
    as documentation.

    `file` is recorded on each hit but not opened — pass any `Path` (callers
    typically pass the on-disk path so consumers can render `file:line`).
    """
    lines = text.splitlines()
    fm_end = _frontmatter_end_line(lines)
    hits: list[MarkerHit] = []
    in_fenced = False

    for idx, raw_line in enumerate(lines, start=1):
        if idx <= fm_end:
            continue

        is_fence = is_fence_line(raw_line)
        # Compute backtick spans only when needed (prose lines outside fence).
        backticks = [] if (in_fenced or is_fence) else _backtick_spans(raw_line)

        for m in _TOKEN_RE.finditer(raw_line):
            token = m.group("inner")
            in_doc = in_fenced or is_fence or _position_inside_any(m.start(), backticks)
            hits.append(
                MarkerHit(
                    file=file,
                    line=idx,
                    token=token,
                    severity=severity_for(token, strict=strict),
                    in_documentation=in_doc,
                )
            )

        if is_fence:
            in_fenced = not in_fenced

    return hits


_SCAN_DIRS = ("doc", "entities")
_SCAN_FILES = ("RESEARCH_PLAN.md",)
_SKIP_DIRS = {"templates", ".venv", "data", ".git", "__pycache__"}


def _collect_markdown_files(root: Path) -> list[Path]:
    """Collect all markdown files to scan under a project root.

    Mirrors `refs.py`'s `_collect_markdown_files`. Resolves doc/ and entities/
    via the project's `paths` config when available, falling back to the
    conventional layout.
    """
    try:
        from science_tool.paths import resolve_paths

        pp = resolve_paths(root)
        scan_dirs = [pp.doc_dir, pp.entities_dir]
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


def scan_markers(
    root: Path,
    *,
    strict: bool = False,
    include_documentation: bool = False,
) -> list[MarkerHit]:
    """Scan an entire project root and return all marker hits.

    By default, hits with `in_documentation=True` (backticked or fenced) are
    excluded — those are references to the convention itself, not annotations.
    Pass `include_documentation=True` for migration / audit workflows that
    want every occurrence.
    """
    out: list[MarkerHit] = []
    for path in _collect_markdown_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for hit in scan_text(path, text, strict=strict):
            if hit.in_documentation and not include_documentation:
                continue
            out.append(hit)
    return out
