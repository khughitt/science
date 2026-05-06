"""Per-entry ref validation for DAG edges.yaml records.

Complements science_tool.refs.check_refs (which is project-wide) by offering
per-entry validation for use inside the DAG schema layer.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

import yaml

from science_tool.dag.schema import RefEntry

logger = logging.getLogger(__name__)


class RefResolutionError(ValueError):
    """Raised when a ref entry's kind tag does not resolve to an on-disk artifact."""


_DOI_RE = re.compile(r"^10\.\d{4,}/\S+$")

# Known accession format regexes. Unknown formats are warn-only.
_ACCESSION_REGEXES: dict[str, re.Pattern[str]] = {
    "GEO": re.compile(r"^GSE\d+$|^GSM\d+$|^GPL\d+$"),
    "SRA": re.compile(r"^SR[APRXRSS]\d+$|^ERR\d+$|^DRR\d+$"),
    "dbGaP": re.compile(r"^phs\d+\.v\d+\.p\d+$"),
    "Synapse": re.compile(r"^syn\d+$"),
    "ArrayExpress": re.compile(r"^E-[A-Z]+-\d+$"),
}

# All valid kind tags (must match REF_KINDS in schema.py).
_ALL_KINDS: frozenset[str] = frozenset(
    {
        "task",
        "interpretation",
        "discussion",
        "proposition",
        "paper",
        "doi",
        "accession",
        "dataset",
    }
)


def _single_kind(entry: RefEntry) -> tuple[str, str]:
    """Return (kind, value) for the one kind tag set on the entry."""
    extra: dict = entry.__pydantic_extra__ or {}
    kinds = {k: v for k, v in extra.items() if v is not None and k in _ALL_KINDS}
    if len(kinds) != 1:
        # Schema validation should have caught this; guard anyway.
        raise RefResolutionError(f"ref entry must have exactly one kind tag; got {list(kinds)}")
    kind, value = next(iter(kinds.items()))
    return kind, str(value)


@lru_cache(maxsize=32)
def _papers_doi_index(project_root: Path) -> frozenset[str]:
    """Return the set of DOIs declared in `doc/papers/*.md` frontmatter.

    Scans each paper file's YAML frontmatter and extracts the `doi` field
    (case-insensitive). Used to distinguish DOI refs that are already backed
    by a local paper summary from ones that actually lack coverage.

    Cached per-project_root; safe because paper-file edits are rare within
    a single audit invocation.
    """
    papers_dir = project_root / "doc" / "papers"
    if not papers_dir.is_dir():
        return frozenset()
    dois: set[str] = set()
    for md in papers_dir.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.startswith("---\n"):
            continue
        try:
            _, fm_raw, _ = text.split("---\n", 2)
        except ValueError:
            continue
        try:
            fm = yaml.safe_load(fm_raw) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(fm, dict):
            continue
        doi = fm.get("doi")
        if isinstance(doi, str) and doi.strip():
            dois.add(doi.strip().lower())
    return frozenset(dois)


def _task_exists(task_id: str, project_root: Path) -> bool:
    """Return True if task_id is declared in tasks/active.md or tasks/done/*.md."""
    pattern = re.compile(rf"^##\s+\[{re.escape(task_id)}\]")
    candidates: list[Path] = [project_root / "tasks/active.md"]
    done_dir = project_root / "tasks/done"
    if done_dir.exists():
        candidates.extend(sorted(done_dir.glob("*.md")))
    for md in candidates:
        if not md.exists():
            continue
        for line in md.read_text(encoding="utf-8").splitlines():
            if pattern.match(line):
                return True
    return False


def validate_ref_entry(entry: RefEntry, project_root: Path) -> None:
    """Validate that a ref entry resolves to an on-disk artifact.

    Fail-fast: task / interpretation / discussion / proposition / paper refs
    that do not resolve raise ``RefResolutionError``. DOI refs with missing
    paper files warn-only. Accession refs with unknown format warn-only.
    """
    kind, value = _single_kind(entry)

    if kind == "task":
        if not _task_exists(value, project_root):
            raise RefResolutionError(f"task {value} not found in tasks/active.md or tasks/done/*.md")

    elif kind == "interpretation":
        path = project_root / "doc/interpretations" / f"{value}.md"
        if not path.exists():
            raise RefResolutionError(f"interpretation {value!r} not found at {path}")

    elif kind == "discussion":
        path = project_root / "doc/discussions" / f"{value}.md"
        if not path.exists():
            raise RefResolutionError(f"discussion {value!r} not found at {path}")

    elif kind == "proposition":
        path = project_root / "specs/propositions" / f"{value}.md"
        if not path.exists():
            raise RefResolutionError(f"proposition {value!r} not found at {path}")

    elif kind == "paper":
        path = project_root / "doc/papers" / f"{value}.md"
        if not path.exists():
            raise RefResolutionError(f"paper {value!r} not found at {path}")

    elif kind == "doi":
        if not _DOI_RE.match(value):
            raise RefResolutionError(f"invalid DOI syntax: {value!r}")
        # Warn only when no `doc/papers/*.md` declares this DOI in frontmatter.
        if value.lower() not in _papers_doi_index(project_root):
            logger.warning("doi ref %r not backed by a doc/papers/ file (warn-only per spec)", value)

    elif kind == "accession":
        if not any(regex.match(value) for regex in _ACCESSION_REGEXES.values()):
            logger.warning("accession %r does not match known registry formats (warn-only)", value)

    elif kind == "dataset":
        # v1: accept any value; datapackage.json validation is a follow-up.
        pass
