# Code-file Registration & Validation (Spec 1, Plan B2) — Classification, Orphans & Hardcoded Paths — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Spec 1/B by harvesting MM30's auditor into science — a static Snakemake reference scanner, code-file classification, decision-bearing-orphan detection (gate Tier 2 `code.orphaned-executable`), and hardcoded-path detection (gate hygiene `code.hardcoded-path`) — wired into the existing `code_files` `@Check` and the `--fail-on` gate ladder B1 already shipped.

**Architecture:** Three new pure modules under `science_tool/code/` — `workflow_refs.py` (the "hard-won" Snakemake path-indirection parser, generalized from MM30's `find_workflow_references`), `classification.py` (executable detection + role classification, generalizing `_is_executable_script`/`classify_script`), and `hardcoded_paths.py` (a built-in absolute-path heuristic extensible via `science.yaml`). The existing `code_files` check (B1) gains: a one-time workflow-reference scan over the Snakemake files it already discovers, an orphan finding on registered executables, and a per-file hardcoded-path scan. The two new rules slot into B1's already-stable `_TIER_RULES` map (`decision-bearing-orphans` → `code.orphaned-executable`; `hygiene` → `code.hardcoded-path`) — no runner/CLI/API change, no JSON-contract change. Every finding stays **WARN** (the §6 fragility firewall); only an active `--fail-on`/`code_gate` makes them block.

**Tech Stack:** Python 3.12+, `click`, pydantic v2, `pyyaml`. Single `uv` package touched: `science_tool` (in `science/`, tests in `science/tests/`). Run tool tests with `cd science && uv run pytest …`. **No `science-model` change** — `CodeFileEntity` already carries `decision_bearing`/`task_ids`. Builds entirely on B1's committed work: the `code_files` check, the gate ladder (`science_tool.validate.gates`), `CODE_FILE_STATUSES`, `known_task_ids`, `parse_code_metadata`, `CodeAdapter.discover`, and `resolve_paths`.

**Harvest source (decision 5 — "harvest, don't clean-room"):** `~/d/cancer/cancer-types/multiple-myeloma/scripts/qa/script_workflow_audit.py` and its tests `tests/test_script_workflow_audit.py`. The regexes, the fixpoint symbol table, the rule-block split, the `{SYMBOL}`/wildcard expansion, the classifier, and the hardcoded-path scanner are taken from there and **generalized**: MM30 hardcodes the `scripts/` (script root) and `workflows/` (workflow root) directory names and keys references relative to `scripts/`; science instead passes the *declared* `code_roots` and the *already-discovered* Snakemake files, and keys references by **project-relative posix path** so they match `SourceRef.path` directly.

**Conventions observed (from B1):**
- A check is `def check_x(ctx: ValidateContext) -> Iterator[Result]` decorated `@Check(section=…, order=N)`. `code_files` is already registered (`order=6`) in `validate/checks/__init__.py::_load_canonical_checks` — B2 does **not** touch the registration tuple or the parity/snapshot test tuples (no new module is canonical; only new findings).
- `Result(severity, path, line, message, rule, task)` — frozen positional dataclass. All B2 findings are `Severity.WARN`.
- Snakemake files in science live under `code_roots` (convention: `code/workflows/`; `directory_structure.py` warns about legacy `code/pipelines/`). `.smk` and `Snakefile` are already in `CodeAdapter`'s suffix set, so they appear in `discover()`'s `refs` — the reference scanner reads those, needing **no new `science.yaml` roots key**.
- The gate ladder vocabulary (`report` → `ghost-files` → `decision-bearing-orphans` → `hygiene`) shipped in B1; B2 only populates the two reserved-but-empty rule sets.

---

## File Structure

**New files:**
- `science/src/science_tool/code/workflow_refs.py` — the static Snakemake reference scanner. One responsibility: given the discovered Snakemake files + the code-root names, return `{project-relative-code-path: ["<smk>::<rule>", …]}`. Pure (reads files, no graph/Result coupling).
- `science/src/science_tool/code/classification.py` — `is_executable()` + `classify_code_file()` returning a `CodeClassification`. One responsibility: derive a code file's structural role and effective decision-bearing flag.
- `science/src/science_tool/code/hardcoded_paths.py` — `find_hardcoded_paths()` + `DEFAULT_HARDCODED_PREFIXES`. One responsibility: flag absolute-path string literals.
- `science/tests/code/test_workflow_refs.py`, `science/tests/code/test_classification.py`, `science/tests/code/test_hardcoded_paths.py`, `science/tests/test_paths_hardcoded.py` — tests.

**Modified files:**
- `science/src/science_tool/code/lifecycle.py` — add `ORPHAN_GATING_EXEMPT_STATUSES` (`exploratory`, `retired`).
- `science/src/science_tool/validate/gates.py` — populate `_TIER_RULES["decision-bearing-orphans"]` and add `code.hardcoded-path` to the hygiene set.
- `science/src/science_tool/paths.py` — add `hardcoded_path_patterns` to `ProjectPaths` and resolve it from `science.yaml`.
- `science/src/science_tool/validate/checks/code_files.py` — one-time reference scan; orphan finding in the valid-block branch; per-file hardcoded-path scan; `_result` gains an optional `line`.
- `science/tests/validate/test_gates.py`, `science/tests/validate/test_checks_code_files.py`, `science/tests/test_code_lifecycle.py` — add cases (existing files from B1).
- `docs/conventions/validate.md` — document the two new rules, the now-populated `decision-bearing-orphans` tier, the classification/reference scan, and the `hardcoded_path_patterns` config.

The parity/snapshot tuples (`test_parity_corpus.py`, `test_parity_canonical_body.py`, `test_formatter_snapshots.py`) and the canonical registration tuple are **unchanged**: `code_files` is already in all of them; B2 adds findings, not a module.

---

## Task 1: The Snakemake workflow-reference scanner

**Files:**
- Create: `science/src/science_tool/code/workflow_refs.py`
- Test: `science/tests/code/test_workflow_refs.py`

The "hard-won" parser (umbrella §5/§8). Text-based by design — a `.smk` file contains `rule x:`/`shell:` directives that are not valid Python, so `ast.parse` would fail. It builds a cross-file symbol table of `NAME = Path("…")` and `NAME = BASE / "…"` assignments by fixpoint, splits each `rule` block, and detects literal and `{SYMBOL}`-indirected script paths, expanding leftover `{wildcards.*}` directory placeholders by globbing. Generalized from MM30: the caller passes the discovered `.smk`/`Snakefile` paths and the code-root names; references resolve to project-relative posix paths.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/code/test_workflow_refs.py`:

```python
from pathlib import Path

from science_tool.code.workflow_refs import find_workflow_references


def _refs(project_root: Path, *smk_paths: Path) -> dict[str, list[str]]:
    return find_workflow_references(
        list(smk_paths), project_root=project_root, code_root_names=("code",)
    )


def test_detects_literal_script_and_shell_paths(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "stages"
    wf.mkdir(parents=True)
    smk = wf / "example.smk"
    smk.write_text(
        'rule direct_script:\n'
        '    script:\n'
        '        "../../analysis/example/run.py"\n'
        '\n'
        'rule shell_module:\n'
        '    shell:\n'
        '        "uv run python code/qa/example_audit.py --out {output}"\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, smk)
    assert refs["code/analysis/example/run.py"] == [
        "code/workflows/stages/example.smk::direct_script"
    ]
    assert refs["code/qa/example_audit.py"] == [
        "code/workflows/stages/example.smk::shell_module"
    ]


def test_expands_path_symbol_indirection_across_files(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "hyp"
    wf.mkdir(parents=True)
    shared = wf / "shared.smk"
    shared.write_text(
        'from pathlib import Path\n\nHYP_SCRIPTS = Path("code/analysis/hyp")\n',
        encoding="utf-8",
    )
    h2 = wf / "h2.smk"
    h2.write_text(
        'H2_SCRIPTS = HYP_SCRIPTS / "h2"\n'
        '\n'
        'rule h2_enrich:\n'
        '    shell:\n'
        '        "uv run python {H2_SCRIPTS}/enrich.py "\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, shared, h2)
    assert refs["code/analysis/hyp/h2/enrich.py"] == [
        "code/workflows/hyp/h2.smk::h2_enrich"
    ]


def test_expands_multiline_f_string_reference(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "external"
    wf.mkdir(parents=True)
    smk = wf / "walker.smk"
    smk.write_text(
        'from pathlib import Path\n'
        '\n'
        'WALKER_SCRIPTS = Path("code/analysis/external/walker")\n'
        '\n'
        'rule walker_build:\n'
        '    shell:\n'
        '        "uv run python "\n'
        '        f"{WALKER_SCRIPTS}/build.py "\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, smk)
    assert refs["code/analysis/external/walker/build.py"] == [
        "code/workflows/external/walker.smk::walker_build"
    ]


def test_expands_wildcard_script_directory(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "stages"
    wf.mkdir(parents=True)
    smk = wf / "geo.smk"
    smk.write_text(
        'rule geo_normalize:\n'
        '    script:\n'
        '        "../../analysis/geo/normalize/{wildcards.acc}.R"\n',
        encoding="utf-8",
    )
    norm = tmp_path / "code" / "analysis" / "geo" / "normalize"
    norm.mkdir(parents=True)
    (norm / "GSE9782.R").write_text("# concrete\n", encoding="utf-8")
    (norm / "GSE6477.R").write_text("# concrete\n", encoding="utf-8")
    refs = _refs(tmp_path, smk)
    assert refs["code/analysis/geo/normalize/GSE9782.R"] == [
        "code/workflows/stages/geo.smk::geo_normalize"
    ]
    assert refs["code/analysis/geo/normalize/GSE6477.R"] == [
        "code/workflows/stages/geo.smk::geo_normalize"
    ]


def test_expands_str_path_expression_reference(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows"
    wf.mkdir(parents=True)
    smk = wf / "t413.smk"
    smk.write_text(
        'from pathlib import Path\n'
        '\n'
        'T413_SCRIPTS = Path("code/analysis/h1/t413")\n'
        '\n'
        'rule t413_de:\n'
        '    input:\n'
        '        r_driver=str(T413_SCRIPTS / "_t413_de.R"),\n'
        '    shell:\n'
        '        "uv run python {T413_SCRIPTS}/de_families.py --r-driver {input.r_driver:q}"\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, smk)
    # `{SYMBOL}/...` (shell) and `str(SYMBOL / "...")` (input) both resolve.
    assert refs["code/analysis/h1/t413/de_families.py"] == ["code/workflows/t413.smk::t413_de"]
    assert refs["code/analysis/h1/t413/_t413_de.R"] == ["code/workflows/t413.smk::t413_de"]


def test_detects_python_module_invocation(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "stages"
    wf.mkdir(parents=True)
    smk = wf / "cyto.smk"
    smk.write_text(
        'rule cn_matrix:\n'
        '    shell:\n'
        '        "uv run --frozen python -m code.stages.cyto.cn_matrix "\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, smk)
    assert refs["code/stages/cyto/cn_matrix.py"] == [
        "code/workflows/stages/cyto.smk::cn_matrix"
    ]


def test_no_workflow_files_is_empty(tmp_path: Path) -> None:
    assert find_workflow_references([], project_root=tmp_path, code_root_names=("code",)) == {}


def test_unreadable_workflow_file_is_skipped(tmp_path: Path) -> None:
    missing = tmp_path / "code" / "workflows" / "gone.smk"
    refs = find_workflow_references(
        [missing], project_root=tmp_path, code_root_names=("code",)
    )
    assert refs == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/code/test_workflow_refs.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.code.workflow_refs`.

- [ ] **Step 3: Implement the scanner**

Create `science/src/science_tool/code/workflow_refs.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/code/test_workflow_refs.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/code/workflow_refs.py science/tests/code/test_workflow_refs.py
git commit -m "feat(code): add static Snakemake workflow-reference scanner"
```

---

## Task 2: Executable detection + code-file classification

**Files:**
- Create: `science/src/science_tool/code/classification.py`
- Modify: `science/src/science_tool/code/lifecycle.py` (add `ORPHAN_GATING_EXEMPT_STATUSES`)
- Test: `science/tests/code/test_classification.py`
- Test: `science/tests/test_code_lifecycle.py` (add a case)

Generalizes MM30's `_is_executable_script` + `classify_script`. Reconciles MM30's *derived* classification with science's *declared* lifecycle (decision 7): classification is purely structural; the orphan finding (Task 5) applies the status-based exemption. MM30 always passed `imported_by_owned=set()`, so its library-owned/unowned split was dead code — dropped here (YAGNI); a non-executable, non-test, non-package file is simply `library`. `.smk`/`Snakefile` are workflow *definitions*, never executables (they are the workflow, not run by it).

- [ ] **Step 1: Write the failing test for the lifecycle constant**

Add to `science/tests/test_code_lifecycle.py`:

```python
def test_orphan_gating_exempt_statuses() -> None:
    from science_tool.code.lifecycle import ORPHAN_GATING_EXEMPT_STATUSES

    assert ORPHAN_GATING_EXEMPT_STATUSES == frozenset({"exploratory", "retired"})
```

- [ ] **Step 2: Add the lifecycle constant**

In `science/src/science_tool/code/lifecycle.py`, after `CODE_FILE_STATUSES`:

```python
# Statuses exempt from Tier-2 (decision-bearing-orphans) gating. `exploratory`
# is the pressure-release valve (umbrella design §6: exempt from
# workflow-ownership gating but never from registration); `retired` code is no
# longer expected to be workflow-reachable.
ORPHAN_GATING_EXEMPT_STATUSES: frozenset[str] = frozenset({"exploratory", "retired"})
```

- [ ] **Step 3: Write the failing tests for classification**

Create `science/tests/code/test_classification.py`:

```python
from science_tool.code.classification import (
    CodeClassification,
    classify_code_file,
    is_executable,
)


def test_r_and_sh_are_always_executable() -> None:
    assert is_executable("code/a.R", "x <- 1\n")
    assert is_executable("code/a.sh", "echo hi\n")


def test_python_with_main_is_executable() -> None:
    assert is_executable("code/a.py", 'if __name__ == "__main__":\n    pass\n')


def test_python_with_argparse_is_executable() -> None:
    assert is_executable("code/a.py", "p = argparse.ArgumentParser()\n")


def test_python_library_is_not_executable() -> None:
    assert not is_executable("code/a.py", "def helper():\n    return 1\n")


def test_smk_and_snakefile_are_not_executable() -> None:
    assert not is_executable("code/workflows/x.smk", "rule a:\n    shell: 'echo'\n")
    assert not is_executable("code/workflows/Snakefile", "rule a:\n    shell: 'echo'\n")


def test_orphaned_executable_when_unreferenced() -> None:
    c = classify_code_file(
        "code/a.py",
        'if __name__ == "__main__":\n    pass\n',
        declared_decision_bearing=None,
        workflow_referenced=False,
    )
    assert c.classification == "orphaned-executable"
    assert c.effective_decision_bearing is True  # fail-closed default


def test_workflow_owned_executable_when_referenced() -> None:
    c = classify_code_file(
        "code/a.py",
        'if __name__ == "__main__":\n    pass\n',
        declared_decision_bearing=None,
        workflow_referenced=True,
    )
    assert c.classification == "workflow-owned-executable"
    assert c.effective_decision_bearing is False


def test_declared_non_decision_bearing_overrides_default() -> None:
    c = classify_code_file(
        "code/a.py",
        'if __name__ == "__main__":\n    pass\n',
        declared_decision_bearing=False,
        workflow_referenced=False,
    )
    assert c.classification == "orphaned-executable"
    assert c.effective_decision_bearing is False


def test_package_marker() -> None:
    c = classify_code_file(
        "code/pkg/__init__.py", "", declared_decision_bearing=None, workflow_referenced=False
    )
    assert c.classification == "package-marker"
    assert c.executable is False


def test_test_file_is_classified_test() -> None:
    c = classify_code_file(
        "code/tests/test_x.py",
        'if __name__ == "__main__":\n    pass\n',
        declared_decision_bearing=None,
        workflow_referenced=False,
    )
    assert c.classification == "test"


def test_workflow_definition_is_classified() -> None:
    c = classify_code_file(
        "code/workflows/main.smk",
        "rule a:\n    shell: 'echo'\n",
        declared_decision_bearing=None,
        workflow_referenced=False,
    )
    assert c.classification == "workflow-definition"


def test_non_executable_is_library() -> None:
    c = classify_code_file(
        "code/lib.py", "def f():\n    return 1\n", declared_decision_bearing=None, workflow_referenced=False
    )
    assert c.classification == "library"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/code/test_classification.py tests/test_code_lifecycle.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.code.classification` (the lifecycle test passes after Step 2).

- [ ] **Step 5: Implement classification**

Create `science/src/science_tool/code/classification.py`:

```python
"""Structural classification of a code file (harvested from MM30's classify_script).

Classification is *derived* from path + content + a precomputed workflow-reference
flag; it is deliberately independent of the *declared* lifecycle `status`
(umbrella decision 7). The orphan check (validate/checks/code_files.py) layers the
status-based exemption on top. `effective_decision_bearing` is fail-closed: an
executable with no explicit `decision_bearing` is treated as decision-bearing,
matching MM30 and umbrella §6.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_EXECUTABLE_SUFFIXES = {".R", ".r", ".sh"}
_WORKFLOW_SUFFIXES = {".smk"}
_PYTHON_ENTRY_POINTS = (
    'if __name__ == "__main__"',
    "if __name__ == '__main__'",
    "@click.command",
    "argparse.ArgumentParser",
    "snakemake",
)


@dataclass(frozen=True)
class CodeClassification:
    classification: str
    executable: bool
    workflow_referenced: bool
    effective_decision_bearing: bool


def is_executable(rel_path: str, text: str) -> bool:
    """True for a file that is run as a program. Workflow definitions are not
    executables (they are the workflow, not invoked by it)."""
    path = Path(rel_path)
    if path.suffix in _WORKFLOW_SUFFIXES or path.name == "Snakefile":
        return False
    if path.suffix in _EXECUTABLE_SUFFIXES:
        return True
    return any(marker in text for marker in _PYTHON_ENTRY_POINTS)


def classify_code_file(
    rel_path: str,
    text: str,
    *,
    declared_decision_bearing: bool | None,
    workflow_referenced: bool,
) -> CodeClassification:
    path = Path(rel_path)
    executable = is_executable(rel_path, text)
    if path.suffix in _WORKFLOW_SUFFIXES or path.name == "Snakefile":
        classification = "workflow-definition"
    elif path.name == "__init__.py":
        classification = "package-marker"
    elif "/tests/" in f"/{rel_path}" or path.name.startswith("test_"):
        classification = "test"
    elif executable and workflow_referenced:
        classification = "workflow-owned-executable"
    elif executable:
        classification = "orphaned-executable"
    else:
        classification = "library"

    if declared_decision_bearing is not None:
        effective_decision_bearing = declared_decision_bearing
    else:
        effective_decision_bearing = classification == "orphaned-executable"

    return CodeClassification(
        classification=classification,
        executable=executable,
        workflow_referenced=workflow_referenced,
        effective_decision_bearing=effective_decision_bearing,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/code/test_classification.py tests/test_code_lifecycle.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/code/classification.py science/src/science_tool/code/lifecycle.py science/tests/code/test_classification.py science/tests/test_code_lifecycle.py
git commit -m "feat(code): add code-file classification and orphan-exempt statuses"
```

---

## Task 3: The hardcoded-path detector

**Files:**
- Create: `science/src/science_tool/code/hardcoded_paths.py`
- Test: `science/tests/code/test_hardcoded_paths.py`

Generalizes MM30's `find_hardcoded_paths`, whose absolute-path prefixes were project-specific (`/mnt/ssd/Dropbox`, `/home/keith`, `/data/proj/mm30/`). Per the chosen design, science ships a **built-in heuristic** (absolute paths under common roots + a Windows-drive check) that a project **extends** via `hardcoded_path_patterns` in `science.yaml` (wired in Task 6). Substring matching, like MM30; a line may yield several findings if it trips several prefixes.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/code/test_hardcoded_paths.py`:

```python
from science_tool.code.hardcoded_paths import (
    DEFAULT_HARDCODED_PREFIXES,
    find_hardcoded_paths,
)


def test_flags_home_and_mnt_paths() -> None:
    findings = find_hardcoded_paths(
        'p = "/home/keith/data/x.tsv"\nq = "/mnt/ssd/Dropbox/y.tsv"\n'
    )
    patterns = {f.pattern for f in findings}
    assert "/home/" in patterns
    assert "/mnt/" in patterns


def test_clean_relative_path_has_no_findings() -> None:
    assert find_hardcoded_paths("x = read('data/in.tsv')\n") == []


def test_extra_prefixes_extend_builtins() -> None:
    findings = find_hardcoded_paths(
        "P = 'site/proj/special/x'\n", extra_prefixes=("site/proj/special/",)
    )
    assert any(f.pattern == "site/proj/special/" for f in findings)


def test_line_numbers_are_one_based() -> None:
    findings = find_hardcoded_paths('a = 1\nb = "/home/keith/x"\n')
    assert findings[0].line_number == 2
    assert findings[0].line == 'b = "/home/keith/x"'


def test_windows_drive_is_flagged() -> None:
    findings = find_hardcoded_paths('p = "C:\\\\Users\\\\keith\\\\x"\n')
    assert any(f.pattern == "<windows-drive>" for f in findings)


def test_default_prefixes_are_absolute_roots() -> None:
    assert "/home/" in DEFAULT_HARDCODED_PREFIXES
    assert all(p.startswith("/") for p in DEFAULT_HARDCODED_PREFIXES)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/code/test_hardcoded_paths.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.code.hardcoded_paths`.

- [ ] **Step 3: Implement the detector**

Create `science/src/science_tool/code/hardcoded_paths.py`:

```python
"""Hardcoded absolute-path detection (generalized from MM30's find_hardcoded_paths).

MM30 used a project-specific absolute-prefix list. Science ships a built-in
heuristic (absolute paths under common roots + a Windows drive letter) and lets a
project extend it via `hardcoded_path_patterns` in science.yaml. Matching is
substring-based, so a single line may produce several findings.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

DEFAULT_HARDCODED_PREFIXES: tuple[str, ...] = (
    "/home/",
    "/Users/",
    "/mnt/",
    "/data/",
    "/opt/",
    "/srv/",
    "/proj/",
)
_WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:\\")


@dataclass(frozen=True)
class HardcodedPathFinding:
    pattern: str
    line_number: int
    line: str


def find_hardcoded_paths(
    text: str, *, extra_prefixes: Iterable[str] = ()
) -> list[HardcodedPathFinding]:
    prefixes = DEFAULT_HARDCODED_PREFIXES + tuple(extra_prefixes)
    findings: list[HardcodedPathFinding] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        for prefix in prefixes:
            if prefix in raw_line:
                findings.append(
                    HardcodedPathFinding(prefix, line_number, raw_line.strip())
                )
        if _WINDOWS_DRIVE_RE.search(raw_line):
            findings.append(
                HardcodedPathFinding("<windows-drive>", line_number, raw_line.strip())
            )
    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/code/test_hardcoded_paths.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/code/hardcoded_paths.py science/tests/code/test_hardcoded_paths.py
git commit -m "feat(code): add hardcoded absolute-path detector"
```

---

## Task 4: Populate the gate ladder's reserved tiers

**Files:**
- Modify: `science/src/science_tool/validate/gates.py` (`_TIER_RULES`)
- Test: `science/tests/validate/test_gates.py` (add cases)

B1 shipped the four-tier vocabulary with `decision-bearing-orphans` empty and a Plan-B2 placeholder comment in `hygiene`. B2 fills them. Because the ladder is cumulative, `code.orphaned-executable` is gated at `decision-bearing-orphans` and above; `code.hardcoded-path` at `hygiene`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/validate/test_gates.py`:

```python
def test_decision_bearing_orphans_tier_gates_orphan_and_lower() -> None:
    rules = cumulative_rules("decision-bearing-orphans")
    assert "code.orphaned-executable" in rules
    assert {"code.ghost", "code.malformed-block"} <= rules  # cumulative
    assert "code.metadata-gap" not in rules  # hygiene is higher


def test_hygiene_tier_includes_hardcoded_path_and_orphan() -> None:
    rules = cumulative_rules("hygiene")
    assert "code.hardcoded-path" in rules
    assert "code.orphaned-executable" in rules  # cumulative from lower tier
```

Also extend the existing `test_hygiene_tier_is_cumulative` with one line so it reflects the populated tiers (add after its existing asserts):

```python
    assert "code.hardcoded-path" in rules
    assert "code.orphaned-executable" in rules
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/validate/test_gates.py -q`
Expected: FAIL — `code.orphaned-executable` / `code.hardcoded-path` not yet gated.

- [ ] **Step 3: Populate `_TIER_RULES`**

In `science/src/science_tool/validate/gates.py`, replace the `decision-bearing-orphans` and `hygiene` entries of `_TIER_RULES`:

```python
    "decision-bearing-orphans": frozenset({"code.orphaned-executable"}),
    "hygiene": frozenset(
        {
            "code.metadata-gap",
            "code.unresolved-task",
            "code.uncommitted",
            "code.hardcoded-path",
        }
    ),
```

(The `report` and `ghost-files` entries are unchanged. Remove the now-stale `# Plan B2 …` comments.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_gates.py -q`
Expected: PASS — including the unchanged exact-equality tests for `report` and `ghost-files`.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/gates.py science/tests/validate/test_gates.py
git commit -m "feat(validate): gate code.orphaned-executable and code.hardcoded-path"
```

---

## Task 5: Orphan detection in the code-files check

**Files:**
- Modify: `science/src/science_tool/validate/checks/code_files.py`
- Test: `science/tests/validate/test_checks_code_files.py` (add cases)

Run the reference scan once over the discovered Snakemake files, then in the valid-block branch classify each file and emit `code.orphaned-executable` for a decision-bearing executable that no workflow references and whose declared `status` is not orphan-exempt. Ghost/malformed files keep their own (lower-tier) rules and are not double-flagged.

The `_ctx`, `_by_rule`, `_git`, and `_commit_all` helpers already exist in this test file (from B1).

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/validate/test_checks_code_files.py`:

```python
def test_orphaned_executable_is_flagged(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# status: workflow-owned\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.orphaned-executable"]) == 1
    assert by_rule["code.orphaned-executable"][0].severity is Severity.WARN


def test_workflow_referenced_executable_is_not_orphan(tmp_path: Path) -> None:
    (tmp_path / "code" / "workflows").mkdir(parents=True)
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# status: workflow-owned\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    (tmp_path / "code" / "workflows" / "main.smk").write_text(
        'rule r:\n    script:\n        "../run.py"\n', encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.orphaned-executable" not in _by_rule(list(check_code_files(ctx)))


def test_exploratory_executable_is_exempt_from_orphan(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# status: exploratory\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.orphaned-executable" not in _by_rule(list(check_code_files(ctx)))


def test_declared_non_decision_bearing_executable_is_not_orphan(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# status: workflow-owned\n# decision_bearing: false\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.orphaned-executable" not in _by_rule(list(check_code_files(ctx)))


def test_library_valid_block_is_not_orphan(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "lib.py").write_text(
        '# science:code\n# status: library\n# science:end\ndef f():\n    return 1\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.orphaned-executable" not in _by_rule(list(check_code_files(ctx)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/validate/test_checks_code_files.py -k orphan -q`
Expected: FAIL — no `code.orphaned-executable` rule is emitted yet.

- [ ] **Step 3: Add imports and the workflow-file helper**

In `science/src/science_tool/validate/checks/code_files.py`, extend the imports. Change the existing lifecycle import line and add the two new imports:

```python
from science_tool.code.classification import classify_code_file
from science_tool.code.lifecycle import CODE_FILE_STATUSES, ORPHAN_GATING_EXEMPT_STATUSES
from science_tool.code.workflow_refs import find_workflow_references
```

Add a module-level helper (next to `_result`):

```python
def _is_workflow_file(rel_path: str) -> bool:
    name = Path(rel_path).name
    return name == "Snakefile" or name.endswith(".smk")
```

- [ ] **Step 4: Build the reference map once, and thread it into the valid-block check**

In `check_code_files`, after the existing `task_ids = known_task_ids(paths.tasks_dir)` line, add:

```python
    code_root_names = tuple(
        root.relative_to(ctx.project_root).as_posix() for root in paths.code_roots
    )
    workflow_files = [
        ctx.project_root / ref.path for ref in refs if _is_workflow_file(ref.path)
    ]
    workflow_refs = find_workflow_references(
        workflow_files, project_root=ctx.project_root, code_root_names=code_root_names
    )
```

Change the valid-block dispatch line in the loop to pass `text` and `workflow_refs`:

```python
        yield from _check_valid_block(ctx, ref.path, metadata.fields, task_ids, text, workflow_refs)
```

- [ ] **Step 5: Extend `_check_valid_block` with orphan detection**

Change the `_check_valid_block` signature and append the orphan block after the existing `code.uncommitted` check:

```python
def _check_valid_block(
    ctx: ValidateContext,
    rel_path: str,
    fields: dict[str, object],
    task_ids: set[str],
    text: str,
    workflow_refs: dict[str, list[str]],
) -> Iterator[Result]:
```

```python
    raw_decision_bearing = fields.get("decision_bearing")
    declared_decision_bearing = (
        raw_decision_bearing if isinstance(raw_decision_bearing, bool) else None
    )
    classification = classify_code_file(
        rel_path,
        text,
        declared_decision_bearing=declared_decision_bearing,
        workflow_referenced=rel_path in workflow_refs,
    )
    if (
        classification.classification == "orphaned-executable"
        and classification.effective_decision_bearing
        and status not in ORPHAN_GATING_EXEMPT_STATUSES
    ):
        yield _result(
            Severity.WARN,
            rel_path,
            f"Decision-bearing executable not referenced by any workflow (orphaned): {rel_path}",
            "code.orphaned-executable",
        )
```

(`status` is the local already computed at the top of `_check_valid_block` in B1.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_checks_code_files.py -q`
Expected: PASS — the new orphan cases plus every B1 case (B1 cases declare `library`/`workflow-owned` statuses or non-executable bodies, so none newly trips the orphan rule; confirm by running the whole module).

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/validate/checks/code_files.py science/tests/validate/test_checks_code_files.py
git commit -m "feat(validate): flag decision-bearing orphaned executables"
```

---

## Task 6: `hardcoded_path_patterns` in `science.yaml`

**Files:**
- Modify: `science/src/science_tool/paths.py` (`ProjectPaths` + `resolve_paths`)
- Test: `science/tests/test_paths_hardcoded.py`

Add the per-project extension list for the hardcoded-path detector. Reuses the module's existing `_str_list` validator (raises on a non-list-of-strings, per "fail early").

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_paths_hardcoded.py`:

```python
from pathlib import Path

import pytest

from science_tool.paths import resolve_paths


def test_hardcoded_path_patterns_parsed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nhardcoded_path_patterns:\n  - /data/proj/mm30/\n  - /scratch/\n",
        encoding="utf-8",
    )
    paths = resolve_paths(tmp_path)
    assert paths.hardcoded_path_patterns == ("/data/proj/mm30/", "/scratch/")


def test_hardcoded_path_patterns_default_empty(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    assert resolve_paths(tmp_path).hardcoded_path_patterns == ()


def test_hardcoded_path_patterns_must_be_list_of_strings(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nhardcoded_path_patterns: nope\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="hardcoded_path_patterns"):
        resolve_paths(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_paths_hardcoded.py -q`
Expected: FAIL — `ProjectPaths` has no `hardcoded_path_patterns` attribute.

- [ ] **Step 3: Add the field and resolve it**

In `science/src/science_tool/paths.py`, add the field to `ProjectPaths` (after `code_excludes`):

```python
    hardcoded_path_patterns: tuple[str, ...] = ()
```

In `resolve_paths`, add the resolved value to the `ProjectPaths(...)` constructor (after `code_excludes=…`):

```python
        hardcoded_path_patterns=tuple(_str_list(data, "hardcoded_path_patterns")),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_paths_hardcoded.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/paths.py science/tests/test_paths_hardcoded.py
git commit -m "feat(paths): add hardcoded_path_patterns project extension list"
```

---

## Task 7: Hardcoded-path detection in the code-files check

**Files:**
- Modify: `science/src/science_tool/validate/checks/code_files.py`
- Test: `science/tests/validate/test_checks_code_files.py` (add cases)

Scan every readable discovered code file (registered or not — hygiene is orthogonal to registration) and emit one `code.hardcoded-path` WARN per finding, carrying the line number. `_result` gains an optional `line`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/validate/test_checks_code_files.py`:

```python
def test_hardcoded_path_in_valid_file_is_flagged(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        '# science:code\n# status: library\n# science:end\nP = "/home/keith/data/x.tsv"\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.hardcoded-path"]) == 1
    assert by_rule["code.hardcoded-path"][0].line == 4


def test_extra_hardcoded_pattern_from_manifest_is_flagged(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        '# science:code\n# status: library\n# science:end\nP = "scratch/special/x"\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path, extra="hardcoded_path_patterns:\n  - scratch/special/")
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.hardcoded-path"]) == 1


def test_hardcoded_path_in_ghost_file_is_flagged(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text('P = "/home/keith/x"\n', encoding="utf-8")
    ctx = _ctx(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert "code.ghost" in by_rule
    assert "code.hardcoded-path" in by_rule


def test_clean_file_has_no_hardcoded_finding(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        '# science:code\n# status: library\n# science:end\nP = "data/in.tsv"\n',
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.hardcoded-path" not in _by_rule(list(check_code_files(ctx)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/validate/test_checks_code_files.py -k hardcoded -q`
Expected: FAIL — no `code.hardcoded-path` rule is emitted yet.

- [ ] **Step 3: Add the import and make `_result` carry a line**

In `science/src/science_tool/validate/checks/code_files.py`, add the import:

```python
from science_tool.code.hardcoded_paths import find_hardcoded_paths
```

Change `_result` to accept an optional line (existing positional callers are unaffected):

```python
def _result(severity: Severity, rel_path: str, message: str, rule: str, *, line: int | None = None) -> Result:
    return Result(severity, Path(rel_path), line, message, rule, None)
```

- [ ] **Step 4: Resolve the extra prefixes and scan each readable file**

In `check_code_files`, capture the configured prefixes alongside the other one-time setup (after the `workflow_refs = …` block from Task 5):

```python
    hardcoded_prefixes = paths.hardcoded_path_patterns
```

In the per-file loop, immediately after the successful `text = abs_path.read_text(...)` (i.e. after the `except OSError` block, before `metadata = parse_code_metadata(text)`), add:

```python
        for finding in find_hardcoded_paths(text, extra_prefixes=hardcoded_prefixes):
            yield _result(
                Severity.WARN,
                ref.path,
                f"Hardcoded path {finding.pattern!r} at line {finding.line_number}: {finding.line}",
                "code.hardcoded-path",
                line=finding.line_number,
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_checks_code_files.py -q`
Expected: PASS — the new hardcoded cases plus every prior case in the module.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/checks/code_files.py science/tests/validate/test_checks_code_files.py
git commit -m "feat(validate): flag hardcoded absolute paths in code files"
```

---

## Task 8: Documentation + full-suite regression

**Files:**
- Modify: `docs/conventions/validate.md`
- Test: the `science_tool` and `science-model` suites

- [ ] **Step 1: Add the two new rules to the code-file rules table**

In `docs/conventions/validate.md`, in the `### Code-file rules` table, add two rows after the `code.unreadable` row:

```
| `code.orphaned-executable` | A registered, decision-bearing executable code file (an `.R`/`.sh`, or a `.py` with a `__main__`/`@click.command`/`argparse`/`snakemake` entry point) that no workflow statically references. Fail-closed: an executable with no `decision_bearing: false` is treated as decision-bearing. `exploratory` and `retired` files are exempt. |
| `code.hardcoded-path` | A code file containing an absolute filesystem path literal under a common root (`/home`, `/Users`, `/mnt`, `/data`, `/opt`, `/srv`, `/proj`, or a Windows drive), or a project-declared `hardcoded_path_patterns` prefix. |
```

- [ ] **Step 2: Correct the gate-ladder table's tier rows**

The `ghost-files` row currently lists only `code.ghost`, but `_TIER_RULES["ghost-files"]` has included `code.malformed-block` since B1 — correct that understatement at the same time. Replace the adjacent `ghost-files` and `decision-bearing-orphans` rows of the gate-ladder table with:

```
| `ghost-files` | `code.ghost` + `code.malformed-block` |
| `decision-bearing-orphans` | `code.ghost` + `code.malformed-block` + `code.orphaned-executable` |
```

The `hygiene` row already reads "All `code.*` rules except `code.unreadable`", which now correctly subsumes `code.hardcoded-path` — leave it as is.

- [ ] **Step 3: Document classification, the reference scan, and the config field**

After the gate-ladder table, add the following subsection. (It is shown here
inside a **four-backtick** fence so the inner `yaml` example renders intact; add
its contents — not the outer fence — to `docs/conventions/validate.md`.)

````markdown
### Classification & the static workflow-reference scan

To decide whether an executable is orphaned, the check first runs a static scan
over the Snakemake files it discovers under `code_roots` (`.smk` files and
`Snakefile`). The scan resolves `script:`/`shell:` references to project-relative
code paths, covering literal paths, `{SYMBOL}`-indirected paths,
`str(SYMBOL / "x.py")` path expressions, `python -m <code-root>.<module>`
invocations, and `{wildcards.*}` directory globbing. A file is then classified
structurally: `workflow-definition` (`.smk`/`Snakefile`), `package-marker`
(`__init__.py`), `test` (under `tests/` or `test_*`), `workflow-owned-executable`
(executable and referenced), `orphaned-executable` (executable and unreferenced),
or `library`. Classification is independent of the declared `status`; the orphan
finding then applies the `exploratory`/`retired` exemption. This scan is static —
distinct from the materialized provenance edges that arrive with the workflow
adapter (Spec 2 / Plan C).

Projects extend the hardcoded-path detector with site-specific prefixes:

```yaml
# science.yaml
hardcoded_path_patterns:
  - /data/proj/mm30/
  - /scratch/
```
````

Use `~/d/` (not absolute) for any in-repo path references.

- [ ] **Step 4: Run the full tool suite and remediate fixture drift**

Run: `cd science && uv run pytest -q`
Expected: PASS. B2 adds two WARN rules to a canonical check, so watch for fixtures that now gain findings:
- A fixture with executable `.py`/`.R`/`.sh` files carrying a valid block but **no** workflow reference and a non-exempt status will gain `code.orphaned-executable` (WARN). A fixture file containing an absolute path under a built-in prefix will gain `code.hardcoded-path` (WARN). Remediate any test asserting exact warning counts by adjusting the fixture (give it no code root, mark the file `exploratory`, or add `decision_bearing: false`) or updating the expected count — **never weaken the check**. All findings are WARN, so on the default `report` tier no exit code flips.
- `tests/validate/test_parity_canonical_body.py` (the `validate.sh` shim vs. Python `run()` over real downstream projects) compares the two *sides*, both of which now run the identical `code_files` check including the new rules, so parity stays exact. Confirm it still passes.
- The formatter snapshot (`tests/validate/snapshots/text_default.txt`) is driven by the code-less `_combined` fixture, so `code_files` still emits nothing and the snapshot is unchanged. Confirm with `cd science && uv run pytest -m snapshot tests/validate/test_formatter_snapshots.py -q`.

- [ ] **Step 5: Run the model suite (sanity — untouched, must stay green)**

Run: `cd science/model && uv run pytest -q`
Expected: PASS (B2 does not touch `science-model`).

- [ ] **Step 6: Commit**

```bash
git add docs/conventions/validate.md
git commit -m "docs(validate): document orphan and hardcoded-path code checks"
```

---

## What B2 completes (and what remains)

**Spec 1/B is complete after B2.** The acceptance test (umbrella §7): MM30 can delete `script_workflow_audit.py` and consume the science check instead — every harvested piece (the Snakemake symbol-table parser, `classify_script`, `_is_executable_script`, `find_hardcoded_paths`, the orphan/hardcoded gate tiers) now lives in `science_tool` and is reachable via `science validate --fail-on …`. natural-systems can register its unregistered scripts; full retirement of its exporter waits on Plan C.

**Deliberately not in B2 (and why):**
- **Triage-table TSV output.** Findings travel as validation `Result`s (the §6 fragility firewall) and `--format json` is machine-readable; any triage table is derivable from that, so no new output format is added.
- **Materialized provenance edges.** The reference scan is *static* (string `"<smk>::<rule>"` references), used only to classify orphans. Turning `implements`/`executes`/`produces`/`consumed_by` into resolved graph edges that derive `bears_on` is **Plan C** (Spec 2), per umbrella §5/§6 and decision 9b.
- **Imported-by-owned library tracing.** MM30's library-owned/unowned split was dead code (`imported_by_owned` was always empty); a Python import graph is out of scope.
```