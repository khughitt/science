# science/src/science_tool/text_scan.py
"""Which files a corpus-wide text scan may decode.

`entities._iter_reference_scan_files` returns EVERY file under the project root
(rglob("*"), filtered only by directory name). That is correct for its caller,
which greps for terms, but a rewriter that decodes each hit as UTF-8 will raise
on the first PNG. This module is the surface a rewriter is allowed to touch.

Two independent guards, because neither is sufficient:

  * an allowlist of suffixes -- a .png is never a reference site, and reading it
    to discover that is waste; and
  * a decode that REPORTS a skip instead of raising -- a .md CAN contain
    undecodable bytes, and one bad file must not abort a corpus-wide pass, but
    it must not vanish either.

Scannable is not the same as rewritable. Code suffixes are here so that a path
reference inside a .py or .ts file is SEEN and reported for manual handling; the
rewriter writes prose only. See reference_rewrite._rewrite_links.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.entities import _REFERENCE_SCAN_SKIP_DIRS

# Prose and data: eligible for automatic rewriting.
_PROSE_SUFFIXES: frozenset[str] = frozenset(
    {".md", ".markdown", ".yaml", ".yml", ".json", ".trig", ".txt", ".toml", ".cfg", ".bib"}
)

# Code: scanned for VISIBILITY only, reported as ManualHit, never auto-rewritten.
# A path in a string literal may be constructed or sliced; substituting into it
# is a code change, and this tool does not make code changes.
_CODE_SUFFIXES: frozenset[str] = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sh", ".smk"}
)

TEXT_SUFFIXES: frozenset[str] = _PROSE_SUFFIXES | _CODE_SUFFIXES


@dataclass(frozen=True)
class Skip:
    """A file that could not be examined. Never silently discarded."""

    rel_path: str
    reason: str


def iter_scannable_files(
    project_root: Path, *, exclude: frozenset[Path] = frozenset()
) -> list[Path]:
    """Every file a reference scan may decode, sorted for deterministic reports.

    `exclude` names resolved paths to skip. A saved import plan is a serialised
    ImportPlan whose JSON body repeats the moving source path; `.json` is a
    scannable prose suffix, so a plan left inside the corpus would be re-read as a
    referrer and every replay of it would drift against itself. The applying
    invocation excludes the plan artifact it was handed; see apply_import.
    """
    project_root = Path(project_root).resolve()
    excluded = {p.resolve() for p in exclude}
    files: list[Path] = []
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() in excluded:
            continue
        rel_parts = path.relative_to(project_root).parts
        if any(part in _REFERENCE_SCAN_SKIP_DIRS for part in rel_parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def read_text_or_skip(path: Path, rel_path: str) -> tuple[str | None, Skip | None]:
    """(text, None) on success, or (None, Skip) with the reason.

    Exactly one element is ever non-None. Returning the reason rather than a bare
    None is the point: an unreadable file that CONTAINS a reference is
    indistinguishable, to a bare-None caller, from a file with no references --
    so the caller reports a clean rewrite over a stale pointer it never read.

    Decode failure and OSError are reported separately because they mean
    different things: the first is a genuine binary-in-prose-clothing, the second
    is an environment fault (permissions, broken symlink, I/O) that a human must
    look at.
    """
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as exc:
        return None, Skip(rel_path=rel_path, reason=f"not utf-8: {exc.reason}")
    except OSError as exc:
        return None, Skip(rel_path=rel_path, reason=f"unreadable: {exc.strerror or exc}")
