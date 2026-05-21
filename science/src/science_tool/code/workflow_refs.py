"""Static Snakemake workflow-reference scanner (harvested from MM30's auditor).

Text-based by design: a `.smk` file contains `rule x:` / `shell:` directives
that are not valid Python, so `ast.parse` would fail before reaching the script
references we need. The scanner builds a cross-file symbol table of
`NAME = Path("...")` and `NAME = BASE / "..."` assignments by fixpoint
iteration, splits each `rule` block, and detects four script-reference forms —
literal paths, `{SYMBOL}`-indirected paths, `str(SYMBOL / "x.py")` path
expressions, and `python -m <code-root>.<module>` invocations — expanding any
leftover `{wildcards.*}` directory placeholder by globbing the filesystem.

Generalized from MM30 (which hardcoded the `scripts/` and `workflows/` directory
names): the caller passes the discovered Snakemake files and the declared
code-root names, and every reference resolves to a project-relative posix path so
it matches `SourceRef.path` directly. A reference is the static string
`"<workflow-file>::<rule>"`; this is a *static* reference scan, distinct from
Plan C's materialized `implements`/`executes` graph edges.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

_RULE_RE = re.compile(r"^\s*rule\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", re.MULTILINE)
_PATH_ASSIGN_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*Path\([\"']([^\"']+)[\"']\)")
_JOIN_ASSIGN_RE = re.compile(
    r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*([A-Z][A-Z0-9_]*)\s*((?:/\s*[\"'][^\"']+[\"']\s*)+)"
)
_JOIN_PART_RE = re.compile(r"/\s*[\"']([^\"']+)[\"']")
_GLOBAL_SCRIPT_RE = re.compile(
    r"\{([A-Z][A-Z0-9_]*)\}/([A-Za-z0-9_./{}-]+\.(?:py|R|r|sh))"
)
# `str(SYMBOL / "rel/path.py")` — a Path-expression script reference.
_GLOBAL_PATH_EXPR_SCRIPT_RE = re.compile(
    r"str\(\s*([A-Z][A-Z0-9_]*)\s*/\s*[\"']([A-Za-z0-9_./{}-]+\.(?:py|R|r|sh))[\"']\s*\)"
)


def _literal_re(code_root_names: tuple[str, ...]) -> re.Pattern[str]:
    """Match a literal script path: a `../`-relative path, or a code-root-prefixed path."""
    branches = [r"(?:\.\./)+[A-Za-z0-9_./{}-]+"]
    if code_root_names:
        roots = "|".join(re.escape(name) for name in code_root_names)
        branches.append(rf"(?:{roots})/[A-Za-z0-9_./{{}}-]+")
    return re.compile(rf"(?:{'|'.join(branches)})\.(?:py|R|r|sh)")


def _python_module_re(code_root_names: tuple[str, ...]) -> re.Pattern[str]:
    """Match `python ... -m <code-root>.<pkg>...<module>` invocations.

    Generalizes MM30's `scripts`-anchored module regex to the declared code roots.
    With no code roots there is nothing to anchor, so the pattern never matches.
    """
    if not code_root_names:
        return re.compile(r"(?!)")  # never matches
    roots = "|".join(re.escape(name) for name in code_root_names)
    return re.compile(
        rf"\bpython\s+(?:-[A-Za-z0-9_-]+\s+)*-m\s+((?:{roots})(?:\.[A-Za-z_][A-Za-z0-9_]*)+)"
    )


def _relpath_from_code_root(path: Path, code_root_names: tuple[str, ...]) -> str:
    parts = path.parts
    for name in code_root_names:
        if name in parts:
            idx = parts.index(name)
            return Path(*parts[idx:]).as_posix()
    return path.as_posix()


def _normalize_candidate(
    project_root: Path,
    code_root_names: tuple[str, ...],
    smk_path: Path,
    raw_path: str,
) -> str:
    """Resolve a raw script reference to a project-relative posix path.

    A code-root-prefixed path resolves against the project root; anything else
    (notably `../`-relative paths) resolves against the workflow file's directory.
    """
    if any(raw_path == name or raw_path.startswith(name + "/") for name in code_root_names):
        candidate = project_root / raw_path
    else:
        candidate = smk_path.parent / raw_path
    try:
        return candidate.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return _relpath_from_code_root(candidate, code_root_names)


def _add_reference(
    refs: dict[str, list[str]],
    project_root: Path,
    code_root_names: tuple[str, ...],
    smk_path: Path,
    raw_path: str,
    reference: str,
) -> None:
    normalized = _normalize_candidate(project_root, code_root_names, smk_path, raw_path)
    if "{" not in normalized:
        refs.setdefault(normalized, [])
        if reference not in refs[normalized]:
            refs[normalized].append(reference)
        return
    # A `{wildcards.*}` placeholder remained: expand by globbing the directory.
    suffix_match = re.search(r"\}([^{}]*)$", normalized)
    suffix = suffix_match.group(1) if suffix_match else ""
    parent_text = normalized[: normalized.find("{")].rstrip("/")
    parent_dir = project_root / Path(parent_text)
    pattern = f"*{suffix}" if suffix else "*"
    for concrete in sorted(parent_dir.glob(pattern)):
        if not concrete.is_file():
            continue
        rel = concrete.relative_to(project_root).as_posix()
        refs.setdefault(rel, [])
        if reference not in refs[rel]:
            refs[rel].append(reference)


def _build_path_symbols(sources: list[tuple[Path, str]]) -> dict[str, str]:
    lines = [line for _path, text in sources for line in text.splitlines()]
    symbols: dict[str, str] = {}

    def set_symbol(name: str, value: str) -> bool:
        existing = symbols.get(name)
        if existing == value:
            return False
        if existing is not None:
            return False  # conflicting redefinition: keep the first, ignore the rest
        symbols[name] = value
        return True

    changed = True
    while changed:
        changed = False
        for line in lines:
            path_match = _PATH_ASSIGN_RE.match(line)
            if path_match:
                changed = set_symbol(path_match.group(1), path_match.group(2)) or changed
                continue
            join_match = _JOIN_ASSIGN_RE.match(line)
            if not join_match:
                continue
            name, base, rest = join_match.groups()
            if base not in symbols:
                continue
            value = symbols[base]
            for part in _JOIN_PART_RE.findall(rest):
                value = f"{value.rstrip('/')}/{part}"
            changed = set_symbol(name, value) or changed
    return symbols


def _rule_blocks(text: str) -> Iterable[tuple[str, str]]:
    matches = list(_RULE_RE.finditer(text))
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        yield match.group(1), text[match.start() : end]


def find_workflow_references(
    workflow_files: Iterable[Path],
    *,
    project_root: Path,
    code_root_names: tuple[str, ...],
) -> dict[str, list[str]]:
    """Map each statically-referenced code file to the `"<workflow-file>::<rule>"`
    references that invoke it. Keys and the workflow-file portion are
    project-relative posix paths."""
    files = sorted(set(workflow_files))
    sources: list[tuple[Path, str]] = []
    for path in files:
        try:
            sources.append((path, path.read_text(errors="replace")))
        except OSError:
            # Vanished/unreadable between discovery and this scan. The main check
            # loop reports it as `code.unreadable`; dropping it here can only
            # over-report orphans (fail-closed), never hide one — so the anomaly
            # is surfaced, not silently swallowed.
            continue
    symbols = _build_path_symbols(sources)
    literal_re = _literal_re(code_root_names)
    module_re = _python_module_re(code_root_names)
    refs: dict[str, list[str]] = {}
    for smk_path, text in sources:
        rel_smk = smk_path.relative_to(project_root).as_posix()
        for rule_name, block in _rule_blocks(text):
            reference = f"{rel_smk}::{rule_name}"
            for literal in literal_re.findall(block):
                _add_reference(refs, project_root, code_root_names, smk_path, literal, reference)
            for symbol, rest in _GLOBAL_SCRIPT_RE.findall(block):
                base = symbols.get(symbol)
                if base is None:
                    continue
                _add_reference(
                    refs, project_root, code_root_names, smk_path, f"{base}/{rest}", reference
                )
            for symbol, rest in _GLOBAL_PATH_EXPR_SCRIPT_RE.findall(block):
                base = symbols.get(symbol)
                if base is None:
                    continue
                _add_reference(
                    refs, project_root, code_root_names, smk_path, f"{base}/{rest}", reference
                )
            for module in module_re.findall(block):
                _add_reference(
                    refs,
                    project_root,
                    code_root_names,
                    smk_path,
                    f"{module.replace('.', '/')}.py",
                    reference,
                )
    return refs
