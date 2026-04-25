#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1",
#   "pyyaml>=6.0",
# ]
# ///
"""Phase 1 v0 inventory for the downstream-project conventions audit.

Read-only inventory of a downstream Science project. Emits a deterministic
JSON artifact and a Markdown rendering. See:

    docs/plans/2026-04-25-downstream-project-conventions-audit.md

Usage (the script declares its dependencies via PEP 723; use `uv run`):
    uv run scripts/audit_downstream_project_inventory.py <project_root>

The plan also references `uv run python scripts/...` — that form requires a
project venv that already has click+pyyaml available (e.g. run it from
`science-tool/`). The plain `uv run script.py` form is preferred because it
honours the PEP 723 inline metadata block above and is self-contained.

Outputs (paths inside the Science repo):
    docs/audits/downstream-project-conventions/inventory/<basename>.json
    docs/audits/downstream-project-conventions/inventory/<basename>.md

Read-only contract:
    - Only `git ls-files`, `git rev-parse HEAD`, `git status --porcelain`,
      `git log -1 --format=...` are run inside the project root.
    - Files are read for frontmatter / .gitignore / validate.sh inspection.
    - No writes inside the project root. No git mutating commands.

Determinism:
    - All collections are sorted (alphabetical for paths,
      numeric-then-alphabetical for ids).
    - Timestamp goes into the JSON only as the run timestamp; the rest of
      the document is content-derived. Smoke tests should diff the JSON
      with the timestamp masked (or fix the timestamp).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import yaml

SCIENCE_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = (
    SCIENCE_REPO_ROOT
    / "docs"
    / "audits"
    / "downstream-project-conventions"
    / "inventory"
)
CANONICAL_VALIDATE_PATH = SCIENCE_REPO_ROOT / "meta" / "validate.sh"

SECOND_LEVEL_DIRS: list[str] = [
    "code",
    "data",
    "doc",
    "docs",
    "knowledge",
    "results",
    "scripts",
    "specs",
    "src",
    "tasks",
    "workflow",
    "workflows",
]

UNTRACKED_DIRS_OF_INTEREST: list[str] = [
    ".snakemake",
    ".venv",
    ".worktrees",
    "data",
    "logs",
    "models",
    "node_modules",
    "results",
]

SYMLINK_PATHS_OF_INTEREST: list[str] = [
    "data",
    "models",
    "results",
]

FRONTMATTER_REFERENCE_FIELDS: list[str] = [
    "consumed_by",
    "datapackage",
    "datasets",
    "local_path",
    "produces",
    "related",
    "source",
    "sources",
]

OBSERVED_VALUE_FIELDS: list[str] = [
    "aspects",
    "ontologies",
    "phase",
    "profile",
    "status",
    "type",
]

SECTION_MARKER_RE = re.compile(r"^#\s*─{2,}\s*(?P<title>.+?)\s*─{2,}\s*$")
ENTITY_ID_RE = re.compile(
    r"^(?P<prefix>[A-Za-z][A-Za-z0-9_-]{0,40}?)[-_]?(?P<num>\d+)$"
)
ENTITY_ID_COLON_PREFIX_RE = re.compile(r"^(?P<prefix>[a-z][a-z0-9_-]*)$")
KEY_LINE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,40}\s*:\s*\S")

LONG_FORM_LINES_THRESHOLD = 300
EMBEDDED_BLOCK_LINE_FLOOR = 50

# Standard noise directories ignored when scanning for gitignored top-level dirs.
GITIGNORED_NOISE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".snakemake",
        ".worktrees",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
    }
)


def extract_entity_id_prefix(entity_id: str) -> str:
    """Extract the prefix from an entity id.

    Tries colon-separated form first (e.g. ``paper:foo2024`` -> ``paper``),
    falls back to the trailing-digit form (e.g. ``q42`` -> ``q``, ``t043`` ->
    ``t``), and finally returns ``"<unparseable>"`` for anything else.
    """
    if ":" in entity_id:
        head, _, _ = entity_id.partition(":")
        if ENTITY_ID_COLON_PREFIX_RE.match(head):
            return head
    m = ENTITY_ID_RE.match(entity_id)
    if m:
        return m.group("prefix")
    return "<unparseable>"


def _self_test() -> None:
    """Self-test for prefix extraction. Exits non-zero on failure."""
    cases: list[tuple[str, str]] = [
        ("paper:foo2024", "paper"),
        ("paper:vinyals2024", "paper"),
        ("discussion:2026-04-17-external-dataset-priors-for-mm30", "discussion"),
        ("report:2026-04-22-something-or-other", "report"),
        ("question:q61-variational-as-annotation", "question"),
        ("q42", "q"),
        ("t043", "t"),
        ("hypothesis:h05-phase-e-methodology", "hypothesis"),
        ("<unparseable junk>", "<unparseable>"),
        ("???", "<unparseable>"),
        ("FooBar", "<unparseable>"),
    ]
    failures: list[str] = []
    for entity_id, expected in cases:
        actual = extract_entity_id_prefix(entity_id)
        if actual != expected:
            failures.append(f"  - {entity_id!r}: expected {expected!r}, got {actual!r}")
    if failures:
        click.echo("self-test FAILED:", err=True)
        for line in failures:
            click.echo(line, err=True)
        raise SystemExit(1)
    click.echo(f"self-test passed ({len(cases)} cases)")


# ----------------------------- helpers -----------------------------


@dataclass
class GitInfo:
    is_repo: bool
    head: str | None
    porcelain: list[str]
    last_commit: dict[str, str] | None


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout, result.stderr


def gather_git_info(project_root: Path) -> GitInfo:
    """Collect read-only git metadata. Returns a not_a_git_repo placeholder if needed."""
    rc, out, _ = _run(["git", "rev-parse", "--show-toplevel"], project_root)
    if rc != 0:
        return GitInfo(is_repo=False, head=None, porcelain=[], last_commit=None)
    toplevel = Path(out.strip())
    if toplevel.resolve() != project_root.resolve():
        # Project root is *inside* a larger git repo (e.g. our smoke fixture
        # under templates/research/ inside the Science repo). For audit purposes
        # we treat that as not-a-git-repo to keep determinism.
        return GitInfo(is_repo=False, head=None, porcelain=[], last_commit=None)

    rc, head, _ = _run(["git", "rev-parse", "HEAD"], project_root)
    head_sha = head.strip() if rc == 0 else None

    rc, porc, _ = _run(["git", "status", "--porcelain"], project_root)
    porcelain = sorted(line for line in porc.splitlines() if line.strip())

    rc, last, _ = _run(
        ["git", "log", "-1", "--format=%H%x1f%an%x1f%ae%x1f%aI%x1f%s"], project_root
    )
    last_commit: dict[str, str] | None = None
    if rc == 0 and last.strip():
        parts = last.strip().split("\x1f")
        if len(parts) == 5:
            last_commit = {
                "sha": parts[0],
                "author_name": parts[1],
                "author_email": parts[2],
                "authored": parts[3],
                "subject": parts[4],
            }

    return GitInfo(
        is_repo=True, head=head_sha, porcelain=porcelain, last_commit=last_commit
    )


def science_repo_head() -> str | None:
    rc, out, _ = _run(["git", "rev-parse", "HEAD"], SCIENCE_REPO_ROOT)
    return out.strip() if rc == 0 else None


def list_tracked_files(project_root: Path, git_info: GitInfo) -> list[str]:
    if not git_info.is_repo:
        return []
    rc, out, _ = _run(["git", "ls-files"], project_root)
    if rc != 0:
        return []
    return sorted(line for line in out.splitlines() if line.strip())


def load_audit_ignore(project_root: Path) -> list[str]:
    """Load .audit-ignore patterns. Empty if missing. Returns sorted unique non-comment patterns."""
    ignore_path = project_root / ".audit-ignore"
    if not ignore_path.is_file():
        return []
    patterns: set[str] = set()
    for raw in ignore_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.add(line)
    return sorted(patterns)


def is_path_ignored(rel_path: str, patterns: Iterable[str]) -> bool:
    """Match rel_path against the .audit-ignore glob list."""
    norm = rel_path.replace(os.sep, "/")
    for pat in patterns:
        if fnmatch.fnmatchcase(norm, pat):
            return True
        # Also treat directory-style globs: 'data/**' should match 'data/foo'
        if pat.endswith("/**") and norm.startswith(pat[:-3]):
            return True
        if pat.endswith("/") and norm.startswith(pat):
            return True
    return False


def load_protected_dirs(project_root: Path) -> list[str]:
    """Pull protected/manual data directory paths from science.yaml if shaped that way."""
    science_yaml = project_root / "science.yaml"
    if not science_yaml.is_file():
        return []
    try:
        data = yaml.safe_load(
            science_yaml.read_text(encoding="utf-8", errors="replace")
        )
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    protected: set[str] = set()
    sources = data.get("data_sources")
    if isinstance(sources, list):
        for entry in sources:
            if isinstance(entry, dict):
                kind = str(entry.get("type", "")).lower()
                if kind in {"protected", "manual"}:
                    for key in ("local_path", "path", "directory", "dir"):
                        val = entry.get(key)
                        if isinstance(val, str) and val:
                            protected.add(val.strip("/"))
    # Honour an explicit list at the top level if present.
    explicit = data.get("protected_paths")
    if isinstance(explicit, list):
        for item in explicit:
            if isinstance(item, str) and item:
                protected.add(item.strip("/"))
    return sorted(protected)


# ----------------------------- frontmatter -----------------------------


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return (parsed_yaml, error_message). Both None if no frontmatter present.

    parsed_yaml is None and error_message is set if the block exists but failed
    to parse or is non-YAML (TOML +++ blocks).
    """
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        if text.startswith("+++\n"):
            return None, "non-yaml (toml +++ block)"
        return None, None
    # Find the closing marker.
    lines = text.splitlines()
    if not lines:
        return None, None
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None, "unterminated frontmatter block"
    block = "\n".join(lines[1:end_idx])
    try:
        parsed = yaml.safe_load(block) if block.strip() else {}
    except yaml.YAMLError as exc:
        return None, f"yaml error: {exc.__class__.__name__}"
    if parsed is None:
        return {}, None
    if not isinstance(parsed, dict):
        return None, f"frontmatter is not a mapping (got {type(parsed).__name__})"
    return parsed, None


def detect_long_form(text: str) -> tuple[int, list[int]]:
    """Return (line_count, candidate_embedded_block_starts).

    Embedded blocks are extra `---` runs after EMBEDDED_BLOCK_LINE_FLOOR, plus
    runs of ≥3 consecutive `key: value` lines after that floor.
    """
    lines = text.splitlines()
    block_starts: list[int] = []
    inside = False
    run_start: int | None = None
    run_len = 0
    # Skip the opening frontmatter block; only mark *additional* `---` tokens.
    started_initial = lines[:1] == ["---"]
    seen_close = False
    for idx, line in enumerate(lines):
        if started_initial and not seen_close and idx > 0 and line.rstrip() == "---":
            seen_close = True
            continue
        if idx + 1 <= EMBEDDED_BLOCK_LINE_FLOOR:
            continue
        stripped = line.rstrip()
        if stripped == "---":
            if not inside:
                block_starts.append(idx + 1)
                inside = True
            else:
                inside = False
            continue
        if KEY_LINE_RE.match(line):
            if run_start is None:
                run_start = idx + 1
                run_len = 1
            else:
                run_len += 1
        else:
            if run_len >= 3 and run_start is not None:
                block_starts.append(run_start)
            run_start = None
            run_len = 0
    if run_len >= 3 and run_start is not None:
        block_starts.append(run_start)
    return len(lines), sorted(set(block_starts))


# ----------------------------- inventory body -----------------------------


def count_top_level(tracked: list[str]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for path in tracked:
        first = path.split("/", 1)[0]
        counter[first] += 1
    return dict(sorted(counter.items()))


def count_second_level(
    tracked: list[str], dirs: list[str]
) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for top in dirs:
        sub: Counter[str] = Counter()
        prefix = top + "/"
        for path in tracked:
            if path.startswith(prefix):
                rest = path[len(prefix) :]
                second = rest.split("/", 1)[0] if "/" in rest else "<files>"
                sub[second] += 1
        if sub:
            out[top] = dict(sorted(sub.items()))
    return out


def find_gitignored_top_level_dirs(
    project_root: Path,
    tracked: list[str],
    ignore_patterns: list[str],
    already_listed: set[str],
) -> list[dict[str, Any]]:
    """Enumerate top-level directories that are present-on-disk but untracked,
    that are not in the noise set or already-listed set.

    Returns a list of ``{name, file_count, total_size_bytes, sample_paths}``
    records. Walks each candidate to depth 3 max for perf bounding.
    """
    tracked_top_dirs: set[str] = set()
    for path in tracked:
        first = path.split("/", 1)[0]
        tracked_top_dirs.add(first)

    out: list[dict[str, Any]] = []
    try:
        entries = sorted(project_root.iterdir(), key=lambda p: p.name)
    except OSError:
        return out

    for entry in entries:
        name = entry.name
        if not entry.is_dir() or entry.is_symlink():
            continue
        if name in tracked_top_dirs:
            continue
        if name in already_listed:
            continue
        if name in GITIGNORED_NOISE_DIRS:
            continue
        if is_path_ignored(name, ignore_patterns) or is_path_ignored(
            name + "/", ignore_patterns
        ):
            continue

        file_count = 0
        total_size = 0
        sample_paths: list[str] = []
        max_depth = 3
        # BFS-ish walk respecting max_depth.
        stack: list[tuple[Path, int]] = [(entry, 0)]
        while stack:
            current, depth = stack.pop()
            try:
                children = sorted(current.iterdir(), key=lambda p: p.name)
            except OSError:
                continue
            for child in children:
                rel = str(child.relative_to(project_root))
                if child.is_symlink():
                    continue
                if child.is_dir():
                    if depth + 1 <= max_depth:
                        stack.append((child, depth + 1))
                    continue
                if not child.is_file():
                    continue
                file_count += 1
                try:
                    total_size += child.stat().st_size
                except OSError:
                    pass
                if len(sample_paths) < 5:
                    sample_paths.append(rel)
        out.append(
            {
                "name": name,
                "file_count": file_count,
                "total_size_bytes": total_size,
                "sample_paths": sorted(sample_paths),
            }
        )

    return sorted(out, key=lambda d: d["name"])


def find_present_untracked(project_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in UNTRACKED_DIRS_OF_INTEREST:
        path = project_root / name
        if not path.exists():
            continue
        try:
            entries = sum(1 for _ in path.iterdir())
        except OSError:
            entries = -1
        out.append(
            {
                "path": name,
                "exists": True,
                "is_symlink": path.is_symlink(),
                "entry_count": entries,
            }
        )
    return sorted(out, key=lambda d: d["path"])


def find_symlinks(project_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in SYMLINK_PATHS_OF_INTEREST:
        path = project_root / name
        if path.is_symlink():
            try:
                target = os.readlink(path)
            except OSError as exc:
                target = f"<unreadable: {exc.__class__.__name__}>"
            out.append({"path": name, "target": target})
    # Also scan top-level for any other symlinks.
    try:
        for entry in project_root.iterdir():
            if entry.is_symlink() and entry.name not in SYMLINK_PATHS_OF_INTEREST:
                try:
                    target = os.readlink(entry)
                except OSError as exc:
                    target = f"<unreadable: {exc.__class__.__name__}>"
                out.append({"path": entry.name, "target": target})
    except OSError:
        pass
    # Deduplicate by path, sort.
    by_path: dict[str, dict[str, Any]] = {}
    for entry in out:
        by_path[entry["path"]] = entry
    return sorted(by_path.values(), key=lambda d: d["path"])


def summarize_science_yaml(project_root: Path) -> dict[str, Any]:
    path = project_root / "science.yaml"
    if not path.is_file():
        return {"present": False}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return {"present": True, "parse_error": f"{exc.__class__.__name__}"}
    if not isinstance(data, dict):
        return {
            "present": True,
            "shape_error": f"top-level is {type(data).__name__}, not mapping",
        }

    keys = sorted(data.keys())
    summary: dict[str, Any] = {"present": True, "keys": keys}
    summary["profile"] = (
        data.get("profile") if isinstance(data.get("profile"), str) else None
    )
    aspects = data.get("aspects")
    summary["aspects"] = (
        sorted(aspects)
        if isinstance(aspects, list) and all(isinstance(a, str) for a in aspects)
        else aspects
    )
    layout_version = data.get("layout_version")
    summary["layout_version"] = (
        layout_version if isinstance(layout_version, (int, str)) else None
    )

    # data_sources shape inspection
    sources = data.get("data_sources")
    sources_shape: dict[str, Any] = {"present": sources is not None}
    if isinstance(sources, list):
        sources_shape["count"] = len(sources)
        kinds: Counter[str] = Counter()
        for entry in sources:
            if isinstance(entry, str):
                kinds["string"] += 1
            elif isinstance(entry, dict):
                kinds["object"] += 1
            else:
                kinds[type(entry).__name__] += 1
        sources_shape["entry_kinds"] = dict(sorted(kinds.items()))
        # Capture object-key usage frequency.
        obj_keys: Counter[str] = Counter()
        type_values: Counter[str] = Counter()
        for entry in sources:
            if isinstance(entry, dict):
                for k in entry.keys():
                    obj_keys[k] += 1
                if isinstance(entry.get("type"), str):
                    type_values[entry["type"]] += 1
        if obj_keys:
            sources_shape["object_key_counts"] = dict(sorted(obj_keys.items()))
        if type_values:
            sources_shape["type_value_counts"] = dict(sorted(type_values.items()))
    elif sources is not None:
        sources_shape["unexpected_type"] = type(sources).__name__
    summary["data_sources_shape"] = sources_shape

    ontologies = data.get("ontologies")
    if isinstance(ontologies, list):
        summary["ontologies"] = sorted(o for o in ontologies if isinstance(o, str))
    elif ontologies is not None:
        summary["ontologies"] = ontologies

    knowledge_profiles = data.get("knowledge_profiles")
    if isinstance(knowledge_profiles, dict):
        summary["knowledge_profiles_keys"] = sorted(knowledge_profiles.keys())

    return summary


def summarize_gitignore(project_root: Path) -> dict[str, Any]:
    path = project_root / ".gitignore"
    if not path.is_file():
        return {"present": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    buckets = {
        "data": ["data/", "*.csv", "*.tsv", "*.parquet", "*.h5", "*.hdf5", "*.feather"],
        "results": ["results/", "out/", "outputs/"],
        "models": ["models/", "*.pt", "*.pth", "*.onnx", "*.safetensors", "*.pkl"],
        "logs": ["logs/", "*.log"],
        "pdfs": ["*.pdf"],
        "archives": ["*.zip", "*.tar", "*.tar.gz", "*.tgz", "*.gz"],
        "worktrees": [".worktrees/"],
        "node": ["node_modules/", "dist/", "build/"],
        "python_caches": [
            "__pycache__/",
            ".venv/",
            "venv/",
            ".mypy_cache/",
            ".ruff_cache/",
            ".pytest_cache/",
        ],
        "snakemake": [".snakemake/"],
    }
    hits: dict[str, list[str]] = {k: [] for k in buckets}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for bucket, needles in buckets.items():
            for needle in needles:
                if (
                    line == needle.rstrip("/")
                    or line == needle
                    or needle.rstrip("/") in line
                ):
                    hits[bucket].append(line)
                    break
    cleaned = {k: sorted(set(v)) for k, v in hits.items() if v}
    return {
        "present": True,
        "line_count": len(lines),
        "non_blank_non_comment": sum(
            1 for line in lines if line.strip() and not line.strip().startswith("#")
        ),
        "matched": cleaned,
    }


def parse_validate_sections(text: str) -> list[str]:
    sections: list[str] = []
    for line in text.splitlines():
        m = SECTION_MARKER_RE.match(line)
        if m:
            sections.append(m.group("title").strip())
    return sections


def split_validate_sections(text: str) -> dict[str, list[str]]:
    """Return {section_title: [lines]} for the lines belonging to each section.

    Lines before the first section marker are bucketed under ``"<preamble>"``.
    The marker line itself is included as the first line of the section so
    that section-internal sha256 covers the marker text too.
    """
    buckets: dict[str, list[str]] = {}
    current = "<preamble>"
    buckets[current] = []
    for line in text.splitlines():
        m = SECTION_MARKER_RE.match(line)
        if m:
            current = m.group("title").strip()
            buckets.setdefault(current, [])
        buckets[current].append(line)
    return buckets


def compute_content_diff(
    canonical_sections: dict[str, list[str]],
    local_sections: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], int]:
    """Per-section sha256 diff plus aggregate changed-line count.

    Returns ``(records, total_changed_lines)`` where ``records`` only contains
    sections whose canonical/local sha differ. Sections present in only one
    side are recorded too. ``total_changed_lines`` is the sum of differing
    line counts (max(canon_lines, local_lines) - common_lines isn't ideal but
    simple aggregate `abs(canon - local) + symmetric_diff_size` is overkill;
    we use a plain unified-diff line count via difflib for honesty).
    """
    import difflib

    records: list[dict[str, Any]] = []
    all_titles = sorted(set(canonical_sections) | set(local_sections))
    total_changed = 0
    for title in all_titles:
        canon_lines = canonical_sections.get(title)
        local_lines = local_sections.get(title)
        canon_text = "\n".join(canon_lines) if canon_lines is not None else ""
        local_text = "\n".join(local_lines) if local_lines is not None else ""
        canon_sha = (
            hashlib.sha256(canon_text.encode("utf-8")).hexdigest()
            if canon_lines is not None
            else None
        )
        local_sha = (
            hashlib.sha256(local_text.encode("utf-8")).hexdigest()
            if local_lines is not None
            else None
        )
        if canon_sha == local_sha:
            continue
        diff_lines = list(
            difflib.unified_diff(
                canon_lines or [],
                local_lines or [],
                lineterm="",
                n=0,
            )
        )
        # Count actual changed/added/removed lines (skip headers & hunk markers).
        changed = sum(
            1
            for line in diff_lines
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        )
        total_changed += changed
        records.append(
            {
                "kind": "content_changed",
                "section": title,
                "canonical_sha256": canon_sha,
                "local_sha256": local_sha,
                "canonical_lines": len(canon_lines) if canon_lines is not None else 0,
                "local_lines": len(local_lines) if local_lines is not None else 0,
                "changed_lines": changed,
            }
        )
    return records, total_changed


def summarize_validate(project_root: Path) -> dict[str, Any]:
    path = project_root / "validate.sh"
    if not path.is_file():
        return {"present": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    header = "\n".join(lines[:15])
    sections = parse_validate_sections(text)
    summary: dict[str, Any] = {
        "present": True,
        "line_count": len(lines),
        "header": header,
        "sections": sections,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    if CANONICAL_VALIDATE_PATH.is_file():
        canon_text = CANONICAL_VALIDATE_PATH.read_text(
            encoding="utf-8", errors="replace"
        )
        canon_sections = parse_validate_sections(canon_text)
        summary["canonical_path"] = str(
            CANONICAL_VALIDATE_PATH.relative_to(SCIENCE_REPO_ROOT)
        )
        summary["canonical_sha256"] = hashlib.sha256(
            canon_text.encode("utf-8")
        ).hexdigest()
        summary["structural_diff"] = compute_structural_diff(canon_sections, sections)
        canon_buckets = split_validate_sections(canon_text)
        local_buckets = split_validate_sections(text)
        content_diff, total_changed = compute_content_diff(canon_buckets, local_buckets)
        summary["content_diff"] = content_diff
        summary["content_diff_total_lines"] = total_changed
    else:
        summary["canonical_path"] = None
    return summary


def compute_structural_diff(
    canonical: list[str], local: list[str]
) -> list[dict[str, Any]]:
    """Return added/removed/reordered section records (no whitespace findings)."""
    diff: list[dict[str, Any]] = []
    canon_set = set(canonical)
    local_set = set(local)
    for title in sorted(local_set - canon_set):
        diff.append({"kind": "added", "section": title})
    for title in sorted(canon_set - local_set):
        diff.append({"kind": "removed", "section": title})
    # Reordering: for sections present in both, compare relative order.
    common = [s for s in canonical if s in local_set]
    local_common = [s for s in local if s in canon_set]
    if common != local_common:
        diff.append(
            {
                "kind": "reordered",
                "canonical_order": common,
                "local_order": local_common,
            }
        )
    return diff


# ----------------------------- frontmatter sweep -----------------------------


def sweep_markdown_files(
    project_root: Path,
    tracked: list[str],
    ignore_patterns: list[str],
    protected_dirs: list[str],
) -> dict[str, Any]:
    """Walk tracked .md files, parse frontmatter, collect aggregate stats."""
    md_files = sorted(p for p in tracked if p.endswith(".md"))
    parse_errors: list[dict[str, str]] = []
    long_form: list[dict[str, Any]] = []
    embedded_blocks: list[dict[str, Any]] = []
    frontmatter_unparsed: list[str] = []
    key_count_by_dir: dict[str, Counter[str]] = {}
    files_by_dir: Counter[str] = Counter()
    field_paths: dict[str, list[str]] = {f: [] for f in FRONTMATTER_REFERENCE_FIELDS}
    observed_values: dict[str, Counter[Any]] = {
        f: Counter() for f in OBSERVED_VALUE_FIELDS
    }
    entity_id_paths: dict[str, list[str]] = {}
    entity_id_prefix_counts: Counter[str] = Counter()
    template_files_skipped = 0

    for rel in md_files:
        if is_path_ignored(rel, ignore_patterns):
            continue
        if any(rel == d or rel.startswith(d + "/") for d in protected_dirs):
            continue
        path = project_root / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            parse_errors.append(
                {"path": rel, "error": f"read failed: {exc.__class__.__name__}"}
            )
            continue
        top_dir = rel.split("/", 1)[0] if "/" in rel else "<root>"
        files_by_dir[top_dir] += 1

        # Skip template files for entity / frontmatter accounting, but keep
        # them in markdown_file_count and files_by_top_dir for honest totals.
        is_template = "templates" in rel.split("/")
        if is_template:
            template_files_skipped += 1
            # Still measure long-form / embedded heuristics on templates? No —
            # those exist to surface real-content drift, and templates would
            # only generate noise. Skip them entirely after totals.
            continue

        line_count, blocks = detect_long_form(text)
        if line_count > LONG_FORM_LINES_THRESHOLD:
            long_form.append({"path": rel, "lines": line_count})
        if blocks:
            embedded_blocks.append(
                {"path": rel, "lines": line_count, "candidate_starts": blocks}
            )

        fm, error = split_frontmatter(text)
        if error:
            if "non-yaml" in error or "toml" in error:
                frontmatter_unparsed.append(rel)
            else:
                parse_errors.append({"path": rel, "error": error})
            continue
        if fm is None:
            continue

        bucket = key_count_by_dir.setdefault(top_dir, Counter())
        for key in fm.keys():
            if isinstance(key, str):
                bucket[key] += 1

        for field in FRONTMATTER_REFERENCE_FIELDS:
            if field in fm and fm[field] not in (None, "", [], {}):
                field_paths[field].append(rel)

        for field in OBSERVED_VALUE_FIELDS:
            value = fm.get(field)
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, (str, int, float, bool)):
                        observed_values[field][str(item)] += 1
            elif isinstance(value, (str, int, float, bool)):
                observed_values[field][str(value)] += 1
            else:
                observed_values[field][f"<{type(value).__name__}>"] += 1

        ent_id = fm.get("id")
        if isinstance(ent_id, (str, int)):
            ent_id_str = str(ent_id)
            entity_id_paths.setdefault(ent_id_str, []).append(rel)
            entity_id_prefix_counts[extract_entity_id_prefix(ent_id_str)] += 1

    # Duplicates: ids with >1 path.
    duplicate_ids = {
        eid: sorted(paths) for eid, paths in entity_id_paths.items() if len(paths) > 1
    }

    # Sort numerically-then-alphabetically for entity_id_paths keys.
    def id_sort_key(s: str) -> tuple[int, str]:
        m = ENTITY_ID_RE.match(s)
        if m:
            try:
                return (0, f"{m.group('prefix')}-{int(m.group('num')):08d}")
            except ValueError:
                return (1, s)
        return (1, s)

    sorted_id_paths = {
        k: sorted(entity_id_paths[k]) for k in sorted(entity_id_paths, key=id_sort_key)
    }
    sorted_dup_ids = {
        k: duplicate_ids[k] for k in sorted(duplicate_ids, key=id_sort_key)
    }

    return {
        "markdown_file_count": len(md_files),
        "scanned_count": sum(files_by_dir.values()),
        "template_files_skipped": template_files_skipped,
        "files_by_top_dir": dict(sorted(files_by_dir.items())),
        "frontmatter_key_counts_by_dir": {
            d: dict(sorted(c.items())) for d, c in sorted(key_count_by_dir.items())
        },
        "frontmatter_unparsed": sorted(frontmatter_unparsed),
        "frontmatter_parse_errors": sorted(parse_errors, key=lambda e: e["path"]),
        "observed_values": {
            f: dict(sorted(observed_values[f].items())) for f in OBSERVED_VALUE_FIELDS
        },
        "entity_id_prefix_counts": dict(sorted(entity_id_prefix_counts.items())),
        "entity_id_paths": sorted_id_paths,
        "duplicate_entity_ids": sorted_dup_ids,
        "frontmatter_reference_field_paths": {
            f: sorted(field_paths[f])
            for f in FRONTMATTER_REFERENCE_FIELDS
            if field_paths[f]
        },
        "long_form_files": sorted(long_form, key=lambda d: d["path"]),
        "embedded_metadata_candidates": sorted(
            embedded_blocks, key=lambda d: d["path"]
        ),
    }


# ----------------------------- code/workflow layout -----------------------------


def code_layout_summary(project_root: Path, tracked: list[str]) -> dict[str, Any]:
    layout: dict[str, Any] = {}
    for top in ["code", "scripts", "src", "workflow", "workflows"]:
        path = project_root / top
        if not path.exists():
            continue
        tracked_count = sum(1 for p in tracked if p.startswith(top + "/"))
        layout[top] = {
            "tracked_files": tracked_count,
            "is_dir": path.is_dir(),
        }
    notebook_paths = sorted(p for p in tracked if p.endswith(".ipynb"))
    layout["notebooks"] = {
        "count": len(notebook_paths),
        "paths": notebook_paths[:25],  # cap for size; full count above
        "truncated": len(notebook_paths) > 25,
    }
    test_paths = sorted(
        p for p in tracked if "/tests/" in "/" + p or p.startswith("tests/")
    )
    layout["tests"] = {
        "count": len(test_paths),
        "top_dirs": sorted({p.split("/", 1)[0] for p in test_paths}),
    }
    return layout


def find_datapackages(tracked: list[str]) -> list[str]:
    return sorted(
        p for p in tracked if p.endswith("/datapackage.json") or p == "datapackage.json"
    )


# ----------------------------- top-level orchestration -----------------------------


def build_inventory(project_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    git_info = gather_git_info(project_root)
    tracked = list_tracked_files(project_root, git_info)
    ignore_patterns = load_audit_ignore(project_root)
    protected_dirs = load_protected_dirs(project_root)

    science_yaml = summarize_science_yaml(project_root)
    gitignore = summarize_gitignore(project_root)
    validate = summarize_validate(project_root)
    md = sweep_markdown_files(project_root, tracked, ignore_patterns, protected_dirs)
    present_untracked = find_present_untracked(project_root)
    already_listed = {entry["path"] for entry in present_untracked}
    gitignored_dirs = find_gitignored_top_level_dirs(
        project_root, tracked, ignore_patterns, already_listed
    )

    inventory: dict[str, Any] = {
        "schema_version": "v0",
        "generator": "scripts/audit_downstream_project_inventory.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": {
            "root": str(project_root),
            "name": project_root.name,
        },
        "science_repo": {
            "root": str(SCIENCE_REPO_ROOT),
            "head": science_repo_head(),
        },
        "audit_ignore_patterns": ignore_patterns,
        "protected_data_dirs": protected_dirs,
        "git": {
            "is_repo": git_info.is_repo,
            "head": git_info.head,
            "status_porcelain": git_info.porcelain,
            "status_porcelain_summary": _porcelain_summary(git_info.porcelain),
            "last_commit": git_info.last_commit,
            "git_status": "ok" if git_info.is_repo else "not_a_git_repo",
        },
        "tracked_top_level_counts": count_top_level(tracked),
        "tracked_second_level_counts": count_second_level(tracked, SECOND_LEVEL_DIRS),
        "present_untracked_dirs": present_untracked,
        "gitignored_top_level_dirs": gitignored_dirs,
        "symlinks": find_symlinks(project_root),
        "science_yaml": science_yaml,
        "gitignore": gitignore,
        "validate": validate,
        "datapackages": find_datapackages(tracked),
        "code_layout": code_layout_summary(project_root, tracked),
        "markdown": md,
    }
    return inventory


def _porcelain_summary(lines: list[str]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for line in lines:
        if not line:
            continue
        code = line[:2].strip() or "??"
        counter[code] += 1
    return dict(sorted(counter.items()))


# ----------------------------- markdown rendering -----------------------------


def render_markdown(inv: dict[str, Any]) -> str:
    out: list[str] = []
    name = inv["project"]["name"]
    out.append(f"# Inventory: {name}")
    out.append("")
    out.append("_Generated by `scripts/audit_downstream_project_inventory.py` (v0)._")
    out.append("")
    out.append("## Header")
    out.append("")
    out.append(f"- Project root: `{inv['project']['root']}`")
    out.append(f"- Generated at: `{inv['generated_at_utc']}`")
    out.append(f"- Science repo head: `{inv['science_repo']['head']}`")
    g = inv["git"]
    out.append(f"- Git status: `{g['git_status']}`")
    out.append(f"- Project HEAD: `{g['head']}`")
    if g["last_commit"]:
        lc = g["last_commit"]
        out.append(
            f"- Last commit: `{lc['sha'][:12]}` {lc['authored']} — {lc['subject']}"
        )
    porc = g["status_porcelain"]
    out.append(f"- Dirty entries: {len(porc)}")
    if g["status_porcelain_summary"]:
        kv = ", ".join(f"`{k}`={v}" for k, v in g["status_porcelain_summary"].items())
        out.append(f"- Porcelain summary: {kv}")
    if porc:
        out.append("")
        out.append("<details><summary>Full porcelain</summary>")
        out.append("")
        out.append("```")
        out.extend(porc)
        out.append("```")
        out.append("")
        out.append("</details>")
    out.append("")

    if inv["audit_ignore_patterns"]:
        out.append("## .audit-ignore")
        out.append("")
        for pat in inv["audit_ignore_patterns"]:
            out.append(f"- `{pat}`")
        out.append("")

    if inv["protected_data_dirs"]:
        out.append("## Protected data directories")
        out.append("")
        for p in inv["protected_data_dirs"]:
            out.append(f"- `{p}`")
        out.append("")

    out.append("## Tracked top-level counts")
    out.append("")
    out.append("| path | files |")
    out.append("| --- | ---: |")
    for k, v in inv["tracked_top_level_counts"].items():
        out.append(f"| `{k}` | {v} |")
    out.append("")

    out.append("## Tracked second-level counts")
    out.append("")
    for top, sub in inv["tracked_second_level_counts"].items():
        out.append(f"### `{top}/`")
        out.append("")
        out.append("| sub | files |")
        out.append("| --- | ---: |")
        for k, v in sub.items():
            out.append(f"| `{k}` | {v} |")
        out.append("")

    out.append("## Present-but-untracked directories of interest")
    out.append("")
    if inv["present_untracked_dirs"]:
        out.append("| path | symlink | entries |")
        out.append("| --- | :---: | ---: |")
        for entry in inv["present_untracked_dirs"]:
            sym = "yes" if entry["is_symlink"] else "no"
            out.append(f"| `{entry['path']}` | {sym} | {entry['entry_count']} |")
    else:
        out.append("_None._")
    out.append("")

    out.append("## Other gitignored top-level directories")
    out.append("")
    git_dirs = inv.get("gitignored_top_level_dirs", [])
    if git_dirs:
        out.append("| name | files | bytes | sample paths |")
        out.append("| --- | ---: | ---: | --- |")
        for entry in git_dirs:
            samples = ", ".join(f"`{p}`" for p in entry["sample_paths"])
            out.append(
                f"| `{entry['name']}` | {entry['file_count']} | {entry['total_size_bytes']} | {samples} |"
            )
    else:
        out.append("_None._")
    out.append("")

    out.append("## Symlinks")
    out.append("")
    if inv["symlinks"]:
        out.append("| path | target |")
        out.append("| --- | --- |")
        for s in inv["symlinks"]:
            out.append(f"| `{s['path']}` | `{s['target']}` |")
    else:
        out.append("_None._")
    out.append("")

    out.append("## science.yaml")
    out.append("")
    sy = inv["science_yaml"]
    if not sy.get("present"):
        out.append("_Not present._")
    elif "parse_error" in sy or "shape_error" in sy:
        out.append(f"_Parse error: {sy.get('parse_error') or sy.get('shape_error')}_")
    else:
        out.append(f"- Profile: `{sy.get('profile')}`")
        out.append(f"- Layout version: `{sy.get('layout_version')}`")
        out.append(
            f"- Top-level keys ({len(sy['keys'])}): {', '.join(f'`{k}`' for k in sy['keys'])}"
        )
        if sy.get("aspects"):
            out.append(f"- Aspects: {', '.join(f'`{a}`' for a in sy['aspects'])}")
        if sy.get("ontologies"):
            out.append(f"- Ontologies: {sy['ontologies']}")
        ds = sy.get("data_sources_shape", {})
        if ds.get("present"):
            out.append(
                f"- data_sources: count={ds.get('count')}, kinds={ds.get('entry_kinds')}"
            )
            if ds.get("object_key_counts"):
                out.append(f"  - object key counts: {ds['object_key_counts']}")
            if ds.get("type_value_counts"):
                out.append(f"  - type value counts: {ds['type_value_counts']}")
    out.append("")

    out.append("## .gitignore")
    out.append("")
    gi = inv["gitignore"]
    if not gi.get("present"):
        out.append("_Not present._")
    else:
        out.append(
            f"- Lines: {gi['line_count']}, non-blank/comment: {gi['non_blank_non_comment']}"
        )
        if gi.get("matched"):
            for bucket, hits in gi["matched"].items():
                out.append(f"- **{bucket}**: {', '.join(f'`{h}`' for h in hits)}")
    out.append("")

    out.append("## validate.sh")
    out.append("")
    v = inv["validate"]
    if not v.get("present"):
        out.append("_Not present._")
    else:
        out.append(f"- Lines: {v['line_count']}")
        out.append(f"- sha256: `{v['sha256']}`")
        if v.get("canonical_path"):
            out.append(
                f"- Canonical comparator: `{v['canonical_path']}` (sha256 `{v['canonical_sha256']}`)"
            )
        out.append("")
        out.append("**Header:**")
        out.append("")
        out.append("```")
        out.append(v["header"])
        out.append("```")
        out.append("")
        out.append("**Sections:**")
        out.append("")
        for s in v["sections"]:
            out.append(f"- {s}")
        out.append("")
        if v.get("structural_diff"):
            out.append("**Structural diff vs canonical:**")
            out.append("")
            for entry in v["structural_diff"]:
                if entry["kind"] in ("added", "removed"):
                    out.append(f"- {entry['kind']}: `{entry['section']}`")
                elif entry["kind"] == "reordered":
                    out.append("- reordered:")
                    out.append(f"  - canonical: {entry['canonical_order']}")
                    out.append(f"  - local: {entry['local_order']}")
            out.append("")
        else:
            out.append("_No structural differences._")
            out.append("")
        if "content_diff" in v:
            total = v.get("content_diff_total_lines", 0)
            content = v["content_diff"]
            out.append(
                f"**Content diff vs canonical:** {total} changed/added/removed line(s) across {len(content)} section(s)."
            )
            out.append("")
            if content:
                out.append(
                    "| section | canonical lines | local lines | changed lines |"
                )
                out.append("| --- | ---: | ---: | ---: |")
                for entry in content:
                    out.append(
                        f"| `{entry['section']}` | {entry['canonical_lines']} | "
                        f"{entry['local_lines']} | {entry['changed_lines']} |"
                    )
                out.append("")

    out.append("## datapackage.json paths")
    out.append("")
    if inv["datapackages"]:
        for p in inv["datapackages"]:
            out.append(f"- `{p}`")
    else:
        out.append("_None._")
    out.append("")

    out.append("## Code / workflow / test layout")
    out.append("")
    cl = inv["code_layout"]
    for key in ["code", "scripts", "src", "workflow", "workflows"]:
        if key in cl:
            out.append(f"- `{key}/`: tracked_files={cl[key]['tracked_files']}")
    nb = cl.get("notebooks", {})
    out.append(f"- notebooks: count={nb.get('count', 0)}")
    if nb.get("count"):
        for p in nb.get("paths", []):
            out.append(f"  - `{p}`")
        if nb.get("truncated"):
            out.append("  - _(truncated)_")
    tests = cl.get("tests", {})
    out.append(
        f"- tests: count={tests.get('count', 0)}, top_dirs={tests.get('top_dirs', [])}"
    )
    out.append("")

    md = inv["markdown"]
    out.append("## Markdown sweep")
    out.append("")
    out.append(f"- Markdown files: {md['markdown_file_count']}")
    out.append(f"- Scanned (after .audit-ignore / protected): {md['scanned_count']}")
    if md.get("template_files_skipped"):
        out.append(
            f"- Template files skipped from entity accounting: {md['template_files_skipped']}"
        )
    if md["frontmatter_unparsed"]:
        out.append(
            f"- Frontmatter unparsed (TOML/non-YAML): {len(md['frontmatter_unparsed'])}"
        )
    if md["frontmatter_parse_errors"]:
        out.append(f"- Frontmatter parse errors: {len(md['frontmatter_parse_errors'])}")
    out.append("")
    out.append("### Frontmatter key counts by top-level dir")
    out.append("")
    for d, counts in md["frontmatter_key_counts_by_dir"].items():
        out.append(f"#### `{d}/`")
        out.append("")
        out.append("| key | count |")
        out.append("| --- | ---: |")
        for k, c in counts.items():
            out.append(f"| `{k}` | {c} |")
        out.append("")

    out.append("### Observed values")
    out.append("")
    for field in OBSERVED_VALUE_FIELDS:
        values = md["observed_values"].get(field, {})
        if not values:
            continue
        out.append(f"**`{field}`**")
        out.append("")
        out.append("| value | count |")
        out.append("| --- | ---: |")
        for v_, c in values.items():
            out.append(f"| `{v_}` | {c} |")
        out.append("")

    out.append("### Entity id prefixes")
    out.append("")
    if md["entity_id_prefix_counts"]:
        out.append("| prefix | count |")
        out.append("| --- | ---: |")
        for p, c in md["entity_id_prefix_counts"].items():
            out.append(f"| `{p}` | {c} |")
    else:
        out.append("_No entity ids discovered in frontmatter._")
    out.append("")

    out.append("### Duplicate entity ids")
    out.append("")
    if md["duplicate_entity_ids"]:
        for eid, paths in md["duplicate_entity_ids"].items():
            out.append(f"- `{eid}`")
            for p in paths:
                out.append(f"  - `{p}`")
    else:
        out.append("_None._")
    out.append("")

    out.append("### Frontmatter reference fields")
    out.append("")
    for f in FRONTMATTER_REFERENCE_FIELDS:
        paths = md["frontmatter_reference_field_paths"].get(f, [])
        if not paths:
            continue
        out.append(f"**`{f}`** ({len(paths)})")
        out.append("")
        for p in paths[:25]:
            out.append(f"- `{p}`")
        if len(paths) > 25:
            out.append(f"- _(+{len(paths) - 25} more)_")
        out.append("")

    out.append("### Long-form files (>300 lines)")
    out.append("")
    if md["long_form_files"]:
        for entry in md["long_form_files"][:50]:
            out.append(f"- `{entry['path']}` ({entry['lines']} lines)")
        if len(md["long_form_files"]) > 50:
            out.append(f"- _(+{len(md['long_form_files']) - 50} more)_")
    else:
        out.append("_None._")
    out.append("")

    out.append("### Embedded metadata candidates")
    out.append("")
    if md["embedded_metadata_candidates"]:
        for entry in md["embedded_metadata_candidates"][:50]:
            out.append(
                f"- `{entry['path']}` (lines={entry['lines']}, candidates={entry['candidate_starts']})"
            )
        if len(md["embedded_metadata_candidates"]) > 50:
            out.append(f"- _(+{len(md['embedded_metadata_candidates']) - 50} more)_")
    else:
        out.append("_None._")
    out.append("")

    if md["frontmatter_parse_errors"]:
        out.append("### Frontmatter parse errors")
        out.append("")
        for entry in md["frontmatter_parse_errors"]:
            out.append(f"- `{entry['path']}`: {entry['error']}")
        out.append("")

    return "\n".join(out) + "\n"


# ----------------------------- CLI -----------------------------


@click.command()
@click.argument(
    "project_root",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=False,
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    show_default=True,
    help="Directory to write <basename>.json and <basename>.md into.",
)
@click.option(
    "--name",
    type=str,
    default=None,
    help="Override the output basename. Defaults to project_root.basename.",
)
@click.option(
    "--fixed-timestamp",
    type=str,
    default=None,
    help="Force a fixed generated_at_utc value (used by smoke tests).",
)
@click.option(
    "--self-test",
    is_flag=True,
    default=False,
    help="Run internal sanity checks (entity-id prefix extraction) and exit.",
)
def main(
    project_root: Path | None,
    output_dir: Path,
    name: str | None,
    fixed_timestamp: str | None,
    self_test: bool,
) -> None:
    """Build a v0 inventory for a downstream Science project."""
    if self_test:
        _self_test()
        return
    if project_root is None:
        raise click.UsageError("PROJECT_ROOT is required unless --self-test is given.")
    project_root = project_root.resolve()
    inv = build_inventory(project_root)
    if fixed_timestamp:
        inv["generated_at_utc"] = fixed_timestamp

    base = name or project_root.name
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{base}.json"
    md_path = output_dir / f"{base}.md"

    json_path.write_text(
        json.dumps(inv, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(inv), encoding="utf-8")

    click.echo(f"wrote {json_path}")
    click.echo(f"wrote {md_path}")


if __name__ == "__main__":
    main()
