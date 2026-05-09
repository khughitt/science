"""Cross-reference validation for Science research projects.

Scans markdown files in doc/, specs/, and RESEARCH_PLAN.md for internal
references (hypothesis IDs, citations, markdown links, markers) and validates
them against the project file system and bibliography.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from science_model.frontmatter import parse_frontmatter

from science_tool.addressing import classify_entity_ref
from science_tool.bibliography import bibliography_key_from_reference, load_bib_keys
from science_tool.project_config import load_project_config


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
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_BIBLIOGRAPHY_CITATION_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*[0-9][A-Za-z0-9_.-]*$")
# DOIs in prose: ``10.<registrant>/<suffix>``, optionally preceded by ``doi:`` or
# a ``https://doi.org/`` URL prefix. The character class for the suffix follows
# Crossref's spec (``[-._;()/:A-Z0-9]`` plus letters); we trim trailing
# punctuation that is almost certainly sentence-final.
_DOI_RE = re.compile(r"\b(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s)\]]+)", re.IGNORECASE)
# PMIDs in prose: ``PMID: 12345`` / ``PMID 12345``. The bare-number form
# (``12345``) without context is too ambiguous to flag, so we require the
# ``PMID`` prefix.
_PMID_REF_RE = re.compile(r"\bPMID[:\s]+(\d{6,9})\b", re.IGNORECASE)
# BibTeX field values: ``doi = {…}`` / ``doi = "…"`` (whitespace tolerant).
_BIB_DOI_FIELD_RE = re.compile(r"^\s*doi\s*=\s*[{\"]([^}\"]+)[}\"]", re.IGNORECASE | re.MULTILINE)
_BIB_PMID_FIELD_RE = re.compile(r"^\s*pmid\s*=\s*[{\"]?(\d+)[}\"]?", re.IGNORECASE | re.MULTILINE)
# Task IDs — `tNN` or `tNNN`, optionally inside square brackets. Anchored on
# word boundaries so adjacent letters do not produce false positives.
_TASK_ID_RE = re.compile(r"\bt(\d{2,})\b")
# Task ID *declarations* in task ledger/archive headers, of the form
# `## [tNN] ...` or `## [tNNN] ...`.
_TASK_DECL_RE = re.compile(r"^\s*#+\s*\[t(\d{2,})\]", re.MULTILINE)
_TASK_REF_SOURCES = "tasks/active.md, tasks/done/*.md, or tasks/archive.md"
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
_LOCAL_ENTITY_KINDS = frozenset(
    {
        "assumption",
        "concept",
        "data-package",
        "dataset",
        "discussion",
        "experiment",
        "finding",
        "hypothesis",
        "inquiry",
        "interpretation",
        "mechanism",
        "method",
        "model",
        "observation",
        "paper",
        "pre-registration",
        "proposition",
        "question",
        "report",
        "source",
        "story",
        "task",
        "theme",
        "topic",
        "validation-report",
        "workflow",
        "workflow-run",
        "meta",
    }
)


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
    """Map legacy HNN aliases (e.g. '03') to hypothesis files."""
    hyp_dir = root / "specs" / "hypotheses"
    if not hyp_dir.is_dir():
        return {}
    result: dict[str, Path] = {}
    for p in hyp_dir.glob("*.md"):
        for alias in _hypothesis_aliases_from_path(p):
            result.setdefault(alias, p)
    return result


def _load_task_ids(root: Path) -> set[str]:
    """Collect all declared task IDs from task ledger/archive files.

    A task is "declared" when it appears as a markdown header of the form
    `## [tNN] ...` (the canonical format produced by `science tasks add`).
    `tasks/archive.md` is reserved for historical aliases that should resolve
    old prose references without reintroducing them into active/done ledgers.
    Returns the set of bare numeric IDs (e.g. `"75"`, not `"t75"`).
    """
    declared: set[str] = set()
    candidates: list[Path] = []
    active = root / "tasks" / "active.md"
    if active.is_file():
        candidates.append(active)
    archive = root / "tasks" / "archive.md"
    if archive.is_file():
        candidates.append(archive)
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


def _load_project_ids(root: Path) -> set[str]:
    try:
        cfg = load_project_config(root)
    except FileNotFoundError:
        return set()
    ids: set[str] = set()
    from science_tool.peers import make_local_resolver  # noqa: PLC0415

    ids.update(make_local_resolver(root).known_ids())
    if cfg.id:
        ids.add(cfg.id)
    return ids


def _extract_frontmatter_refs(path: Path) -> list[tuple[str, str]]:
    parsed = parse_frontmatter(path)
    if parsed is None:
        return []
    fm, _body = parsed
    refs: list[tuple[str, str]] = []
    for key in ("related", "blocked_by", "blocked-by", "source_refs", "evidence_refs"):
        value = fm.get(key)
        if isinstance(value, str):
            refs.append((key, value))
        elif isinstance(value, list):
            refs.extend((key, item) for item in value if isinstance(item, str))
    return refs


def _frontmatter_line_numbers(path: Path) -> set[int]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return set()
    if not lines or lines[0].strip() != "---":
        return set()
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return set(range(1, index + 1))
    return set()


def _load_bib_keys(root: Path) -> set[str]:
    """Extract all BibTeX entry keys from references.bib."""
    return load_bib_keys(root)


def _normalize_doi_token(value: str) -> str:
    """Trim trailing punctuation/quotes/whitespace and lowercase a DOI token."""
    cleaned = value.strip().rstrip(".,;:'\"`)>]}*")
    return cleaned.lower()


def _load_doi_corpus(root: Path) -> set[str]:
    """DOIs declared in the project bibliography or paper notes.

    Sources (in order of authority):
    - ``papers/references.bib`` — the canonical citation database; DOIs appear
      in the ``doi = {…}`` field.
    - ``doc/papers/*.md`` — per-paper note files often record the DOI in
      free-text ``DOI: 10.…`` lines (per the paper template).
    """
    dois: set[str] = set()
    bib_path = root / "papers" / "references.bib"
    if bib_path.is_file():
        try:
            text = bib_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        for m in _BIB_DOI_FIELD_RE.finditer(text):
            dois.add(_normalize_doi_token(m.group(1)))
    papers_dir = root / "doc" / "papers"
    if papers_dir.is_dir():
        for path in papers_dir.rglob("*.md"):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for m in _DOI_RE.finditer(text):
                dois.add(_normalize_doi_token(m.group(1)))
    return dois


def _load_pmid_corpus(root: Path) -> set[str]:
    """PMIDs declared in the bibliography or paper notes."""
    pmids: set[str] = set()
    bib_path = root / "papers" / "references.bib"
    if bib_path.is_file():
        try:
            text = bib_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        for m in _BIB_PMID_FIELD_RE.finditer(text):
            pmids.add(m.group(1))
    papers_dir = root / "doc" / "papers"
    if papers_dir.is_dir():
        for path in papers_dir.rglob("*.md"):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for m in _PMID_REF_RE.finditer(text):
                pmids.add(m.group(1))
    return pmids


def _is_heading_line(line: str) -> bool:
    """Check if a line is a markdown heading."""
    return line.lstrip().startswith("#")


def _is_fence_line(line: str) -> bool:
    return _FENCE_RE.match(line) is not None


def _strip_inline_code(line: str) -> str:
    return _INLINE_CODE_RE.sub("", line)


def _looks_like_bibtex_citation_key(key: str) -> bool:
    """Return True for project-style BibTeX keys, not semantic ref tokens."""
    return _BIBLIOGRAPHY_CITATION_KEY_RE.match(key) is not None


def _hypothesis_id_from_path(file_path: Path) -> str | None:
    """Extract the primary legacy HNN alias from a hypothesis file path, if any."""
    aliases = _hypothesis_aliases_from_path(file_path)
    if aliases:
        return sorted(aliases)[0]

    return None


def _extract_hypothesis_aliases_from_id(entity_id: object) -> set[str]:
    """Extract HNN aliases from a canonical ``hypothesis:<slug>`` id."""
    if not isinstance(entity_id, str) or not entity_id.startswith("hypothesis:"):
        return set()

    slug = entity_id.split(":", 1)[1]
    match = re.match(r"h(\d+)-", slug)
    if not match:
        match = re.match(r"h(\d+)$", slug)
    return {match.group(1)} if match else set()


def _extract_hypothesis_aliases_from_heading(body: str) -> set[str]:
    """Extract the leading HNN label from the first markdown heading in the body."""
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^#+\s*H(\d{2,})\b", stripped)
        return {match.group(1)} if match else set()
    return set()


def _hypothesis_aliases_from_path(file_path: Path) -> set[str]:
    """Return all legacy HNN aliases discoverable for a hypothesis markdown file."""
    aliases: set[str] = set()

    frontmatter = parse_frontmatter(file_path)
    if frontmatter is not None:
        fm, body = frontmatter
        aliases.update(_extract_hypothesis_aliases_from_id(fm.get("id")))
        aliases.update(_extract_hypothesis_aliases_from_heading(body))

    filename_match = re.match(r"h(\d+)-", file_path.name)
    if filename_match:
        aliases.add(filename_match.group(1))

    return aliases


def check_refs(root: Path) -> list[RefIssue]:
    """Run all reference checks and return issues found."""
    issues: list[RefIssue] = []
    files = _collect_markdown_files(root)
    hyp_ids = _load_hypothesis_ids(root)
    bib_keys = _load_bib_keys(root)
    task_ids = _load_task_ids(root)
    project_ids = _load_project_ids(root)
    doi_corpus = _load_doi_corpus(root)
    pmid_corpus = _load_pmid_corpus(root)

    for file_path in files:
        rel_path = str(file_path.relative_to(root))
        frontmatter_lines = _frontmatter_line_numbers(file_path)
        for field_name, raw_ref in _extract_frontmatter_refs(file_path):
            if field_name in {"source_refs", "evidence_refs"}:
                bibkey = bibliography_key_from_reference(raw_ref)
                if bibkey is not None:
                    if bibkey not in bib_keys:
                        issues.append(
                            RefIssue(
                                file=rel_path,
                                line=1,
                                ref_type="citation",
                                ref_value=raw_ref,
                                message=f"{raw_ref} — not in papers/references.bib",
                            )
                        )
                    continue
            parsed_ref = classify_entity_ref(
                raw_ref,
                local_kinds=_LOCAL_ENTITY_KINDS,
                project_ids=frozenset(project_ids),
            )
            if parsed_ref.shape == "cross-project-entity":
                continue
            if parsed_ref.shape == "unknown-namespace":
                issues.append(
                    RefIssue(
                        file=rel_path,
                        line=1,
                        ref_type="namespace",
                        ref_value=raw_ref,
                        message=(
                            f"Unknown project namespace '{parsed_ref.project_id}' in ref '{raw_ref}'. "
                            "Add it to science.yaml peers: or use a local ref."
                        ),
                    )
                )
            elif parsed_ref.shape == "legacy-cross-project":
                issues.append(
                    RefIssue(
                        file=rel_path,
                        line=1,
                        ref_type="legacy-cross-project",
                        ref_value=raw_ref,
                        message=(
                            f"Legacy cross-project ref '{raw_ref}' is missing an entity kind. "
                            f"Use '{parsed_ref.project_id}:question:{parsed_ref.slug}' or another explicit "
                            "<project-id>:<kind>:<slug> ref."
                        ),
                    )
                )
        # Determine if this file IS a hypothesis file (skip self-references)
        own_hyp_ids: set[str] = set()
        if "hypotheses" in file_path.parts:
            own_hyp_id = _hypothesis_id_from_path(file_path)
            if own_hyp_id is not None:
                own_hyp_ids.add(own_hyp_id)
            own_hyp_ids.update(_hypothesis_aliases_from_path(file_path))

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
        # DOI/PMID corpus is built FROM doc/papers/ — checking it against
        # itself would flag every newly added paper note before its bib entry
        # exists. The bibliography is the source of truth; paper notes are
        # corpus contributors, not consumers.
        skip_doi_pmid_check = rel_path.startswith("doc/papers/")

        in_fenced_code = False
        for line_num, line in enumerate(lines, start=1):
            if line_num in frontmatter_lines:
                continue
            if _is_fence_line(line):
                in_fenced_code = not in_fenced_code
                continue
            if in_fenced_code:
                continue

            scan_line = _strip_inline_code(line)

            # Skip headings and frontmatter for hypothesis checks
            if _is_heading_line(scan_line):
                continue

            # --- Task ID references ---
            if not skip_task_check and task_ids:
                for m in _TASK_ID_RE.finditer(scan_line):
                    task_num = m.group(1)
                    if task_num in task_ids:
                        continue
                    issues.append(
                        RefIssue(
                            file=rel_path,
                            line=line_num,
                            ref_type="task",
                            ref_value=f"t{task_num}",
                            message=f"t{task_num} — no matching declaration in {_TASK_REF_SOURCES}",
                        )
                    )

            # --- DOI references ---
            if not skip_doi_pmid_check and doi_corpus:
                for m in _DOI_RE.finditer(scan_line):
                    doi = _normalize_doi_token(m.group(1))
                    if doi in doi_corpus:
                        continue
                    issues.append(
                        RefIssue(
                            file=rel_path,
                            line=line_num,
                            ref_type="doi",
                            ref_value=doi,
                            message=f"DOI {doi} not declared in papers/references.bib or doc/papers/",
                            suggestion="Add the entry to references.bib (with `doi = {…}`) or create a doc/papers/<key>.md note.",
                        )
                    )

            # --- PMID references ---
            if not skip_doi_pmid_check and pmid_corpus:
                for m in _PMID_REF_RE.finditer(scan_line):
                    pmid = m.group(1)
                    if pmid in pmid_corpus:
                        continue
                    issues.append(
                        RefIssue(
                            file=rel_path,
                            line=line_num,
                            ref_type="pmid",
                            ref_value=f"PMID:{pmid}",
                            message=f"PMID {pmid} not declared in papers/references.bib or doc/papers/",
                        )
                    )

            # --- Hypothesis references ---
            for m in _HYPOTHESIS_RE.finditer(scan_line):
                hyp_num = m.group(1)
                if hyp_num in own_hyp_ids:
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
            for m in _CITATION_RE.finditer(scan_line):
                cite_group = m.group(1)
                # Split on ; for multi-cites like [@Smith2024; @Jones2023]
                for part in cite_group.split(";"):
                    key = part.strip().lstrip("@").split(",")[0].split(" ")[0].strip()
                    if not key or not _looks_like_bibtex_citation_key(key):
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
            for m in _LINK_RE.finditer(scan_line):
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
            for m in _UNVERIFIED_RE.finditer(scan_line):
                issues.append(
                    RefIssue(
                        file=rel_path,
                        line=line_num,
                        ref_type="marker",
                        ref_value="[UNVERIFIED]",
                        message="Unresolved [UNVERIFIED] marker",
                    )
                )
            for m in _NEEDS_CITATION_RE.finditer(scan_line):
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
