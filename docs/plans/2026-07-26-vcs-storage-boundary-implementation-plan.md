# VCS Storage Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the tracked/ignored boundary a declared, generated, and enforced property of a science project instead of a hand-curated `.gitignore` maintained by per-case judgement.

**Architecture:** `science.yaml` gains a `boundary:` block declaring a storage class per path (`versioned` implicit, `payload`, `manifest`). A generator renders those declarations into a managed block in `.gitignore`. Six mechanical validate checks enforce the result — two universal (needing no config), four declaration-derived. Reachability is decided by asking git directly (`git ls-files --cached --others --exclude-standard`) rather than by analysing patterns.

**Tech Stack:** Python 3.12+, pydantic v2 models (mirroring the `ProjectDataConfig` precedent in `project_config.py`), `click` for CLI, `subprocess` for git plumbing, `pytest`. No new third-party dependencies.

**Design:** `docs/plans/2026-07-26-vcs-storage-boundary-design.md` (committed at `8b58e633`).

## Global Constraints

- Package root is `science/`. Run tests as `cd science && uv run --frozen pytest tests/<file> -v`.
- ruff `line-length = 120` (`science/pyproject.toml:41`). Run `uv run --frozen ruff check .` and `uv run --frozen ruff format --check .` from `science/`.
- Nested pydantic config blocks use `model_config = ConfigDict(extra="forbid")`, matching `ProjectDataConfig` (`project_config.py:153`). `ProjectConfig` itself stays `extra="allow"`.
- **Every git invocation that supports `-z` MUST use it.** Newline-delimited output is wrong for paths containing newlines, which are legal in git and are a real input to a boundary tool.
- Validate checks register via `@Check(section=..., order=...)` from `science_tool.validate.checks` and yield `Result(severity, path, line, message, rule, task)` from `science_tool.validate.result`.
- Tests build a context with `ValidateContext.from_project_root(root, strict=False, verbose=False)` (`validate/context.py:43`). There is no `build_context` helper. The fixture must contain a `science.yaml`, or construction raises `ValidateContextError`.
- `git check-ignore --no-index --stdin -z -v` emits **four** NUL-terminated fields per record in the order `source, line, pattern, path` (verified). A `!`-prefixed pattern means the path is **not** ignored: it must be **filtered** where the question is "is this file ignored?" (`tracked_ignored`), and **recorded** where the question is "does an unmanaged rule mention this root?" (`matching_unmanaged_rules`). Filtering it in both places is what made a hand-written pin invisible.
- **`check-ignore` reports the last matching pattern only.** Any check whose predicate is "a rule *matches*" must defeat that — by isolation (the managed block is spliced *after* the hand-written region, so a managed rule always wins) and by peeling (among unmanaged rules the last match still wins, and a `!` winner hides the rule beneath it).
- Check rule names are exactly: `boundary.tracked-ignored`, `boundary.unanchored-pattern`, `boundary.generated-drift`, `boundary.declaration-conflict`, `boundary.unreachable-tracked`, `boundary.ignored-undeclared`, plus `boundary.invalid-declaration` for a malformed `boundary:` block.
- **Nothing fails open.** Every git helper declares the return codes it accepts and raises `BoundaryGitError` on anything else. A malformed `boundary:` block is reported as `boundary.invalid-declaration` (ERROR), never silently downgraded to "undeclared" — that would disable four checks precisely when the config is broken.
- **No check may use text prefixes to decide whether a rule targets a declared root.** Git pattern semantics (wildcards, nested-`.gitignore` scoping) are git's to evaluate; ask git.
- No check may call `data_policy.classify()`. Its only callers are `boundary init` and `data audit`.
- **`git check-ignore` is never the reachability oracle.** Its verdict is index-dependent. Use the visibility oracle.
- MM30's real declaration is a downstream follow-up. Only a sanitized fixture lands here.

---

## File Structure

**New package** `science/src/science_tool/boundary/`:

| File | Responsibility |
|---|---|
| `__init__.py` | Public re-exports only. |
| `config.py` | Pydantic models + grammar validation. Pure; no filesystem, no git. |
| `generate.py` | Render the managed block; splice it into `.gitignore` text. Pure string transforms. |
| `gitio.py` | All git subprocess calls. Visibility oracle, tracked∩ignored, ignore-rule enumeration. |
| `walk.py` | Enumerate extant files under a `manifest` root matching its `tracked:` globs. |
| `probes.py` | Generate synthetic probe paths for a declaration. Pure. |
| `sync.py` | Managed-block install, drift detection, transactional `--verify-current-tree`. |
| `init.py` | Declaration proposal from an existing tree (only `classify()` consumer here). |
| `cli.py` | `science boundary` click group. |

**Modified:**

| File | Change |
|---|---|
| `project_config.py:261` | Add `boundary: BoundaryConfig \| None = None`. |
| `validate/checks/boundary.py` | **New.** The six checks. |
| `validate/checks/__init__.py:~95` | Append `"boundary"` to `CANONICAL_CHECK_MODULES`. |
| `cli.py:18,~200` | Import and register `boundary_group`. |
| `data_audit.py:169` | Re-scope the walk. |
| `commands/create-project.md:199-290` | Retire the ignore-then-pin idiom. |
| `docs/conventions/data-boundary.md` | Rewrite *Policy*; resolve deferred follow-ups. |
| `docs/audits/downstream-project-conventions/synthesis.md` §7.5 | Mark superseded. |

Models live in `boundary/config.py` rather than `project_config.py` despite the `ProjectDataConfig` precedent: the grammar validators are ~80 lines and would bloat an already-large module. `project_config.py` imports from `boundary.config`, which imports only pydantic and stdlib — no cycle.

---

## Task 1: Config models and grammar validation

**Files:**
- Create: `science/src/science_tool/boundary/__init__.py`
- Create: `science/src/science_tool/boundary/config.py`
- Modify: `science/src/science_tool/project_config.py:261`
- Test: `science/tests/test_boundary_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `StorageClass`, `BoundaryRoot`, `AllowEntry`, `BoundaryConfig`, `BoundaryConfigError`. `BoundaryRoot` fields: `path: str`, `storage_class: StorageClass` (YAML key `class`), `tracked: tuple[str, ...]`. `AllowEntry` fields: `source: str`, `pattern: str`. `BoundaryConfig` fields: `roots: tuple[BoundaryRoot, ...]`, `unmanaged_allow: tuple[AllowEntry, ...]`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_boundary_config.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.boundary.config import BoundaryConfig, StorageClass


def _cfg(**kw):
    return BoundaryConfig.model_validate(kw)


def test_payload_root_parses():
    cfg = _cfg(roots=[{"path": "data/raw", "class": "payload"}])
    assert cfg.roots[0].storage_class is StorageClass.PAYLOAD
    assert cfg.roots[0].tracked == ()


def test_manifest_root_parses_tracked():
    cfg = _cfg(roots=[{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}])
    assert cfg.roots[0].tracked == ("datapackage.json",)


def test_manifest_requires_nonempty_tracked():
    # A manifest root tracking nothing IS a payload root. Two spellings of one
    # meaning is the ambiguity this design removes.
    with pytest.raises(ValidationError, match="tracked"):
        _cfg(roots=[{"path": "data/external", "class": "manifest", "tracked": []}])
    with pytest.raises(ValidationError, match="tracked"):
        _cfg(roots=[{"path": "data/external", "class": "manifest"}])


def test_tracked_rejected_on_payload():
    with pytest.raises(ValidationError, match="tracked"):
        _cfg(roots=[{"path": "data/raw", "class": "payload", "tracked": ["a.json"]}])


@pytest.mark.parametrize(
    "bad",
    ["/abs", "..", "a/../b", ".", "a/", "", "a\nb", "a\tb", "a*b", "a?b", "a[b]", "!a", "a\\"],
)
def test_root_path_grammar(bad):
    with pytest.raises(ValidationError):
        _cfg(roots=[{"path": bad, "class": "payload"}])


def test_duplicate_roots_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        _cfg(roots=[{"path": "data/raw", "class": "payload"}, {"path": "data/raw", "class": "payload"}])


def test_nested_roots_rejected():
    # /data/ would stop git descending and silently disable the child's negations.
    with pytest.raises(ValidationError, match="nested"):
        _cfg(
            roots=[
                {"path": "data", "class": "payload"},
                {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]},
            ]
        )


def test_sibling_roots_allowed():
    cfg = _cfg(
        roots=[
            {"path": "data/raw", "class": "payload"},
            {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]},
        ]
    )
    assert len(cfg.roots) == 2


@pytest.mark.parametrize(
    "bad",
    ["/abs", "..", "a/", "", "!x", "#x", "a\nb", "a\\", "a\\b", "[ab].json", "foo/**/bar.json", "a.json "],
)
def test_tracked_glob_grammar(bad):
    with pytest.raises(ValidationError):
        _cfg(roots=[{"path": "data/external", "class": "manifest", "tracked": [bad]}])


def test_interior_space_is_legal_but_trailing_space_is_not():
    """git strips trailing whitespace from a pattern unless it is escaped, so a
    trailing space means the emitted rule is not the declared glob. An interior
    space is a plain literal to both engines."""
    cfg = _cfg(roots=[{"path": "d", "class": "manifest", "tracked": ["read me.json"]}])
    assert cfg.roots[0].tracked == ("read me.json",)


@pytest.mark.parametrize("good", ["datapackage.json", "*.qa.json", "schemas/*.json", "données.json"])
def test_tracked_glob_admits_the_proven_subset(good):
    cfg = _cfg(roots=[{"path": "d", "class": "manifest", "tracked": [good]}])
    assert cfg.roots[0].tracked == (good,)


def test_double_star_is_rejected_because_the_matcher_disagrees_with_git():
    """git's `foo/**/bar.json` matches `foo/bar.json`; PurePosixPath.match does
    not. Admitting syntax the checker evaluates differently would let the
    generator emit a working rule that unreachable-tracked never verifies."""
    from pathlib import PurePosixPath

    assert PurePosixPath("foo/bar.json").match("foo/**/bar.json") is False
    with pytest.raises(ValidationError, match=r"\*\*"):
        _cfg(roots=[{"path": "d", "class": "manifest", "tracked": ["foo/**/bar.json"]}])


def test_question_mark_is_rejected_because_it_is_byte_oriented_in_git():
    """git's `?` matches one BYTE; PurePosixPath's matches one CHARACTER. For
    `?.json` vs `é.json` (two UTF-8 bytes) the matcher says tracked and git
    leaves the file ignored -- the exact silent false negative
    unreachable-tracked exists to prevent. Verified against real git."""
    from pathlib import PurePosixPath

    assert PurePosixPath("é.json").match("?.json") is True  # git: no match
    with pytest.raises(ValidationError, match=r"\?"):
        _cfg(roots=[{"path": "d", "class": "manifest", "tracked": ["run-?.json"]}])


@pytest.mark.parametrize("bad", ["foo//bar.json", "foo/./bar.json", "./a.json"])
def test_non_normalised_segments_rejected(bad):
    """PurePosixPath normalises `//` and `.` away and matches; git's generated
    negation does not, so the file stays ignored while the checker calls it
    reachable. Verified against real git."""
    from pathlib import PurePosixPath

    assert PurePosixPath("foo/bar.json").match("foo//bar.json") is True  # git: no match
    with pytest.raises(ValidationError, match="segment"):
        _cfg(roots=[{"path": "d", "class": "manifest", "tracked": [bad]}])


def test_duplicate_tracked_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        _cfg(roots=[{"path": "d", "class": "manifest", "tracked": ["a.json", "a.json"]}])


def test_allow_entry_shorthand_expands_to_root():
    cfg = _cfg(unmanaged_allow=[".venv/"])
    assert cfg.unmanaged_allow[0].source == ".gitignore"
    assert cfg.unmanaged_allow[0].pattern == ".venv/"


def test_allow_entry_explicit_source():
    cfg = _cfg(unmanaged_allow=[{"source": "inc/shiny/.gitignore", "pattern": "node_modules/"}])
    assert cfg.unmanaged_allow[0].source == "inc/shiny/.gitignore"


def test_allow_source_must_be_a_gitignore_file():
    with pytest.raises(ValidationError, match="gitignore"):
        _cfg(unmanaged_allow=[{"source": "inc/shiny/ignore.txt", "pattern": "x"}])


def test_duplicate_allow_pairs_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        _cfg(unmanaged_allow=[".venv/", {"source": ".gitignore", "pattern": ".venv/"}])


def test_unknown_key_rejected():
    with pytest.raises(ValidationError):
        _cfg(roots=[{"path": "d", "class": "payload", "clazz": "x"}])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_boundary_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.boundary'`

- [ ] **Step 3: Implement the models**

```python
# science/src/science_tool/boundary/config.py
"""Typed, validated `boundary:` declaration.

Pure: no filesystem access, no git. Grammar is closed because every value here
becomes a git pattern -- pass-through would let a declaration emit rules nobody
audited. See docs/plans/2026-07-26-vcs-storage-boundary-design.md.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BoundaryConfigError(Exception):
    """Raised for boundary declaration problems outside pydantic validation."""


class StorageClass(StrEnum):
    PAYLOAD = "payload"
    MANIFEST = "manifest"


_PATH_FORBIDDEN = set("*?[]!\\")
_CONTROL = {chr(c) for c in range(32)}


def _reject_control(value: str, label: str) -> None:
    if any(ch in _CONTROL for ch in value):
        raise ValueError(f"{label} must not contain control characters or newlines: {value!r}")


def _validate_relative(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} must not be empty")
    _reject_control(value, label)
    if value.startswith("/"):
        raise ValueError(f"{label} must be repo-relative, not absolute: {value!r}")
    if value.endswith("/"):
        raise ValueError(f"{label} must not end with '/': {value!r}")
    if value.endswith("\\"):
        raise ValueError(f"{label} must not end with a dangling escape: {value!r}")
    parts = value.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise ValueError(f"{label} must not contain empty, '.' or '..' segments: {value!r}")


class BoundaryRoot(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    path: str
    storage_class: StorageClass = Field(alias="class")
    tracked: tuple[str, ...] = ()

    @field_validator("path")
    @classmethod
    def _check_path(cls, value: str) -> str:
        _validate_relative(value, "root path")
        if any(ch in _PATH_FORBIDDEN for ch in value):
            raise ValueError(f"root path must not contain glob metacharacters; globs belong in tracked: {value!r}")
        return value

    @field_validator("tracked")
    @classmethod
    def _check_tracked(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for glob in value:
            # Shares the path rules: non-empty, no control characters, not
            # absolute, no trailing '/', and no empty / '.' / '..' segment. The
            # segment rule matters more here than for a path -- PurePosixPath
            # normalises `foo//bar.json` and `foo/./bar.json` away and matches,
            # while git's generated negation does not fire at all.
            _validate_relative(glob, "tracked glob")
            if glob.startswith("!"):
                raise ValueError(f"tracked glob must not start with '!'; negation is the generator's job: {glob!r}")
            if glob.startswith("#"):
                raise ValueError(f"tracked glob must not start with '#': {glob!r}")
            if glob != glob.strip():
                raise ValueError(
                    f"tracked glob must not have leading or trailing whitespace: {glob!r}. "
                    f"git strips trailing whitespace from an unescaped pattern, so the emitted "
                    f"rule would not be the declared glob."
                )
            # PROVEN SHARED SUBSET. The checker matches with
            # PurePosixPath.match; the generator emits `!/root/**/<glob>` and git
            # matches that. Every construct admitted here must mean the SAME
            # thing to both, because a construct they read differently lets the
            # generator emit a WORKING git rule that unreachable-tracked silently
            # never verifies -- the precise false negative this check exists to
            # prevent. Each exclusion below was reproduced against real git:
            #
            #   `**`  git's `foo/**/bar.json` matches `foo/bar.json`;
            #         PurePosixPath.match returns False.
            #   `?`   git's `?` matches one BYTE, PurePosixPath's one CHARACTER,
            #         so `?.json` vs `é.json` disagrees.
            #   `[]`  a character class has no synthesisable probe witness.
            #   `\`   escapes are honoured by git and not by the matcher.
            #
            # (Empty and `.` segments are the same class of divergence and are
            # rejected by _validate_relative above.)
            #
            # Literals (including non-ASCII) and `*` are byte-for-byte identical
            # in both engines, and dotfiles are matched by `*` in both, so those
            # are admitted without restriction.
            if "**" in glob:
                raise ValueError(f"tracked glob must not use '**'; a bare '*' already spans one segment: {glob!r}")
            illegal = set(glob) & set("?[]\\")
            if illegal:
                raise ValueError(
                    f"tracked glob must not use {''.join(sorted(illegal))!r} in {glob!r}. "
                    f"'?' is byte-oriented in git and character-oriented in the checker, "
                    f"character classes have no probe witness, and escapes are honoured only "
                    f"by git -- all three would make the checker disagree with git silently. "
                    f"Literals and '*' are admitted."
                )
        if len(set(value)) != len(value):
            raise ValueError("duplicate tracked glob")
        return value

    @model_validator(mode="after")
    def _check_class_pairing(self) -> "BoundaryRoot":
        if self.storage_class is StorageClass.MANIFEST and not self.tracked:
            raise ValueError(
                f"manifest root {self.path!r} needs a non-empty tracked list; "
                "a manifest root that tracks nothing is a payload root"
            )
        if self.storage_class is StorageClass.PAYLOAD and self.tracked:
            raise ValueError(f"tracked is only valid on class: manifest, not on payload root {self.path!r}")
        return self


class AllowEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = ".gitignore"
    pattern: str

    @model_validator(mode="before")
    @classmethod
    def _expand_shorthand(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"source": ".gitignore", "pattern": value}
        return value

    @field_validator("source")
    @classmethod
    def _check_source(cls, value: str) -> str:
        _validate_relative(value, "allow source")
        if value != ".gitignore" and not value.endswith("/.gitignore"):
            raise ValueError(f"allow source must be a .gitignore file: {value!r}")
        return value

    @field_validator("pattern")
    @classmethod
    def _check_pattern(cls, value: str) -> str:
        # GRAMMAR NOTE: an allow pattern is matched against `.gitignore` RULE
        # TEXT by equality, so it is NOT a `tracked:` glob and does NOT share its
        # grammar. A leading `/` (anchored) and a trailing `/` (directory) are
        # both legal and common -- `/data/raw/` and `.venv/` are the shapes
        # actually written. What is rejected is text that cannot be a rule:
        # empty, control characters, a comment, or a negation (allowing a
        # negation is meaningless -- it does not ignore anything).
        if not value:
            raise ValueError("allow pattern must not be empty")
        _reject_control(value, "allow pattern")
        if value.startswith("#"):
            raise ValueError(f"allow pattern must not be a comment: {value!r}")
        if value.startswith("!"):
            raise ValueError(f"allow pattern must not be a negation; negations ignore nothing: {value!r}")
        if value != value.strip():
            raise ValueError(f"allow pattern must match rule text exactly, without surrounding whitespace: {value!r}")
        return value


# Must match the scaffolded .gitignore in commands/create-project.md EXACTLY, or
# a freshly created project warns on day one. There is no shape heuristic behind
# this list: an entry is silenced because it was declared, never because it
# "looks like" tooling.
DEFAULT_UNMANAGED_ALLOW: tuple[str, ...] = (
    ".env",
    "__pycache__/",
    "*.pyc",
    ".venv/",
    "*.egg-info/",
    ".mypy_cache/",
    ".ipynb_checkpoints/",
    ".worktrees/",
    "*.pre-update*.bak",
    "doc/meta/next-steps-*.md",
    "docs/meta/next-steps-*.md",
    "doc/plans/*-plan-review.md",
    "docs/plans/*-plan-review.md",
    ".DS_Store",
)


class BoundaryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roots: tuple[BoundaryRoot, ...] = ()
    unmanaged_allow: tuple[AllowEntry, ...] = Field(
        default_factory=lambda: tuple(AllowEntry(pattern=p) for p in DEFAULT_UNMANAGED_ALLOW)
    )

    @model_validator(mode="after")
    def _check_roots(self) -> "BoundaryConfig":
        paths = [r.path for r in self.roots]
        if len(set(paths)) != len(paths):
            raise ValueError("duplicate root path")
        for outer in paths:
            for inner in paths:
                if outer != inner and (inner + "/").startswith(outer + "/"):
                    raise ValueError(
                        f"nested roots are not supported: {outer!r} contains {inner!r}. "
                        f"An anchored exclude for {outer!r} stops git descending, silently "
                        f"disabling every negation {inner!r} would generate."
                    )
        pairs = [(a.source, a.pattern) for a in self.unmanaged_allow]
        if len(set(pairs)) != len(pairs):
            raise ValueError("duplicate unmanaged_allow entry")
        return self
```

```python
# science/src/science_tool/boundary/__init__.py
"""Declared VCS storage boundary: config, generation, git introspection, checks."""

from science_tool.boundary.config import (
    AllowEntry,
    BoundaryConfig,
    BoundaryConfigError,
    BoundaryRoot,
    StorageClass,
)

__all__ = [
    "AllowEntry",
    "BoundaryConfig",
    "BoundaryConfigError",
    "BoundaryRoot",
    "StorageClass",
]
```

- [ ] **Step 4: Wire the block onto `ProjectConfig`**

In `science/src/science_tool/project_config.py`, add the import near the other model imports and the field after `data_policy` (line 262):

```python
from science_tool.boundary.config import BoundaryConfig
```

```python
    boundary: BoundaryConfig | None = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_boundary_config.py -v`
Expected: PASS (all)

- [ ] **Step 6: Verify no import cycle and lint**

```bash
cd science
uv run --frozen python -c "from science_tool.project_config import ProjectConfig; print(ProjectConfig.model_fields['boundary'])"
uv run --frozen ruff check . && uv run --frozen ruff format --check .
```
Expected: field prints; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/boundary/ science/src/science_tool/project_config.py science/tests/test_boundary_config.py
git commit -m "feat(boundary): add validated boundary declaration models"
```

---

## Task 2: Managed-block generation

**Files:**
- Create: `science/src/science_tool/boundary/generate.py`
- Test: `science/tests/test_boundary_generate.py`

**Interfaces:**
- Consumes: `BoundaryConfig`, `BoundaryRoot`, `StorageClass` from Task 1.
- Produces: `MANAGED_BEGIN: str`, `MANAGED_END: str`, `render_managed_block(cfg: BoundaryConfig) -> str`, `splice_managed_block(text: str, block: str) -> str`, `extract_managed_block(text: str) -> str | None`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_boundary_generate.py
from __future__ import annotations

import subprocess
from pathlib import Path

from science_tool.boundary.config import BoundaryConfig
from science_tool.boundary.generate import (
    MANAGED_BEGIN,
    MANAGED_END,
    extract_managed_block,
    render_managed_block,
    splice_managed_block,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_payload_root_is_anchored():
    cfg = BoundaryConfig.model_validate({"roots": [{"path": "data/raw", "class": "payload"}]})
    assert "/data/raw/" in render_managed_block(cfg)


def test_no_generated_pattern_is_unanchored():
    cfg = BoundaryConfig.model_validate(
        {
            "roots": [
                {"path": "pdfs", "class": "payload"},
                {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]},
            ]
        }
    )
    for line in render_managed_block(cfg).splitlines():
        if not line or line.startswith("#"):
            continue
        body = line[1:] if line.startswith("!") else line
        assert body.startswith("/"), f"unanchored generated pattern: {line}"


def test_manifest_emits_descend_preserving_form():
    cfg = BoundaryConfig.model_validate(
        {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    )
    block = render_managed_block(cfg)
    assert "/data/external/**" in block
    assert "!/data/external/**/" in block
    assert "!/data/external/**/datapackage.json" in block
    # A bare anchored exclude would stop descent and disable the negations.
    assert "\n/data/external/\n" not in "\n" + block


def test_generation_is_deterministic():
    payload = {
        "roots": [
            {"path": "pdfs", "class": "payload"},
            {"path": "data/raw", "class": "payload"},
        ]
    }
    a = render_managed_block(BoundaryConfig.model_validate(payload))
    payload["roots"].reverse()
    b = render_managed_block(BoundaryConfig.model_validate(payload))
    assert a == b


def test_splice_appends_when_absent():
    out = splice_managed_block(".venv/\n", "X\n")
    assert out.startswith(".venv/\n")
    assert MANAGED_BEGIN in out and MANAGED_END in out


def test_splice_replaces_in_place_and_preserves_surroundings():
    original = splice_managed_block("head\n", "OLD\n")
    updated = splice_managed_block(original + "tail\n", "NEW\n")
    assert "OLD" not in updated
    assert "NEW" in updated
    assert updated.startswith("head\n")
    assert updated.rstrip().endswith("tail")


def test_splice_is_idempotent():
    once = splice_managed_block("head\n", "B\n")
    assert splice_managed_block(once, "B\n") == once


def test_extract_roundtrip():
    text = splice_managed_block("head\n", "B\n")
    assert extract_managed_block(text) == "B\n"
    assert extract_managed_block("no markers\n") is None


def test_manifest_descriptor_is_really_visible_to_git(tmp_path: Path):
    """Real git, not string comparison. The trap is that negations LOOK right."""
    repo = _repo(tmp_path)
    (repo / "data/external/ot/25.03").mkdir(parents=True)
    (repo / "data/external/ot/25.03/datapackage.json").write_text("{}\n")
    (repo / "data/external/ot/25.03/big.parquet").write_text("x\n")
    cfg = BoundaryConfig.model_validate(
        {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    )
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    staged = _git(repo, "ls-files").split()
    assert "data/external/ot/25.03/datapackage.json" in staged
    assert "data/external/ot/25.03/big.parquet" not in staged


def test_payload_root_stages_nothing(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/x.csv").write_text("a\n")
    cfg = BoundaryConfig.model_validate({"roots": [{"path": "data/raw", "class": "payload"}]})
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    assert "data/raw/x.csv" not in _git(repo, "ls-files").split()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_boundary_generate.py -v`
Expected: FAIL — `ModuleNotFoundError: ... boundary.generate`

- [ ] **Step 3: Implement the generator**

```python
# science/src/science_tool/boundary/generate.py
"""Render a BoundaryConfig into the managed .gitignore block, and splice it in.

Pure string transforms; no filesystem access. Two invariants the tests pin:
every generated pattern is anchored, and a manifest root never emits a bare
directory exclude (which would stop git descending and silently disable its own
negations).
"""

from __future__ import annotations

from science_tool.boundary.config import BoundaryConfig, BoundaryRoot, StorageClass

MANAGED_BEGIN = "# BEGIN science-managed boundary — edit science.yaml, not this block"
MANAGED_END = "# END science-managed boundary"


def _render_root(root: BoundaryRoot) -> list[str]:
    if root.storage_class is StorageClass.PAYLOAD:
        return [f"/{root.path}/"]
    # manifest: `**` + directory re-inclusion keeps git descending so the
    # per-glob negations below actually apply.
    lines = [f"/{root.path}/**", f"!/{root.path}/**/"]
    lines.extend(f"!/{root.path}/**/{glob}" for glob in sorted(root.tracked))
    return lines


def render_managed_block(cfg: BoundaryConfig) -> str:
    """Deterministic: roots sorted by path, tracked globs sorted within a root."""
    lines: list[str] = []
    for root in sorted(cfg.roots, key=lambda r: r.path):
        lines.extend(_render_root(root))
    return "".join(f"{line}\n" for line in lines)


def extract_managed_block(text: str) -> str | None:
    """Return the block body between the markers, or None if not present."""
    start = text.find(MANAGED_BEGIN)
    if start == -1:
        return None
    end = text.find(MANAGED_END, start)
    if end == -1:
        return None
    body_start = start + len(MANAGED_BEGIN)
    return text[body_start:end].lstrip("\n")


def splice_managed_block(text: str, block: str) -> str:
    """Replace the managed block in `text`, or append it if absent."""
    rendered = f"{MANAGED_BEGIN}\n{block}{MANAGED_END}\n"
    start = text.find(MANAGED_BEGIN)
    if start != -1:
        end = text.find(MANAGED_END, start)
        if end != -1:
            return text[:start] + rendered + text[end + len(MANAGED_END) :].lstrip("\n")
    prefix = text if text.endswith("\n") or not text else text + "\n"
    separator = "\n" if prefix else ""
    return f"{prefix}{separator}{rendered}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_boundary_generate.py -v`
Expected: PASS (all, including both real-git tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/boundary/generate.py science/tests/test_boundary_generate.py
git commit -m "feat(boundary): render the managed .gitignore block"
```

---

## Task 3: Git introspection layer

Defines the **source universe** split from the design: rule-text reads only tracked in-worktree `.gitignore` files; effect checks use git's full effective resolution.

**Files:**
- Create: `science/src/science_tool/boundary/gitio.py`
- Test: `science/tests/test_boundary_gitio.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `IgnoreHit(path: str, source: str, line: int, pattern: str)`, `IgnoreRule(source: str, line: int, pattern: str)`, `BoundaryGitError`, `visible_paths(project_root: Path) -> set[str]`, `tracked_ignored(project_root: Path) -> list[IgnoreHit]`, `governed_ignore_files(project_root: Path) -> list[str]`, `unmanaged_rules(project_root: Path) -> list[IgnoreRule]`, `matching_unmanaged_rules(project_root: Path, paths: list[str]) -> dict[str, list[IgnoreRule]]`.

**Semantics fixed here** (each has a test below):

| Concern | Behaviour |
|---|---|
| Output framing | Every git call uses `-z`; parse on `\0`. |
| Symlinks | Never followed. `visible_paths` reports the link itself; the walk (Task 4) does not descend into a symlinked directory. |
| Nested repositories | A submodule or nested `.git` is opaque: git reports the gitlink path only, and we never recurse into it. |
| Rule sources | `governed_ignore_files` returns only `.gitignore` files that are **tracked and present on disk**; `.git/info/exclude` and `core.excludesFile` are excluded. |
| Unreadable source | Raises `BoundaryGitError`. An unreadable rule file is not an empty one. |
| Rule attribution | `matching_unmanaged_rules` reports every unmanaged rule that **matches** a path — never just the winner — including negations, via isolation plus peeling. |
| Ordering | All returned lists are sorted by `(source, line)` or `path` so output is stable. |

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_boundary_gitio.py
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.boundary.gitio import (
    governed_ignore_files,
    tracked_ignored,
    unmanaged_rules,
    visible_paths,
    matching_unmanaged_rules,
)


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    return tmp_path


def _write(repo: Path, rel: str, body: str = "x\n") -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


def test_visible_paths_excludes_ignored(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "keep.txt")
    _write(repo, "skip.log")
    _write(repo, ".gitignore", "*.log\n")
    vis = visible_paths(repo)
    assert "keep.txt" in vis
    assert "skip.log" not in vis


def test_visible_paths_includes_tracked_even_if_later_ignored(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "a.log")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "a.log"], check=True)
    _write(repo, ".gitignore", "*.log\n")
    assert "a.log" in visible_paths(repo)


def test_visible_paths_matches_git_add_for_file_level_negation(tmp_path: Path):
    """The oracle must agree with staging, where check-ignore does not."""
    repo = _repo(tmp_path)
    _write(repo, "s/m/archive/a.py")
    _write(repo, "gi", "archive\n")
    subprocess.run(["git", "-C", str(repo), "config", "core.excludesFile", str(repo / "gi")], check=True)
    _write(repo, ".gitignore", "!/s/m/archive/a.py\n")
    assert "s/m/archive/a.py" not in visible_paths(repo)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    staged = subprocess.run(
        ["git", "-C", str(repo), "ls-files"], capture_output=True, text=True
    ).stdout.split()
    assert "s/m/archive/a.py" not in staged


def test_visible_paths_directory_level_negation_works(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "s/m/archive/a.py")
    _write(repo, "gi", "archive\n")
    subprocess.run(["git", "-C", str(repo), "config", "core.excludesFile", str(repo / "gi")], check=True)
    _write(repo, ".gitignore", "!/s/m/archive/\n")
    assert "s/m/archive/a.py" in visible_paths(repo)


def test_visible_paths_handles_newline_in_filename(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "we\nird.txt")
    assert "we\nird.txt" in visible_paths(repo)


def test_tracked_ignored_reports_source_and_line(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "data/raw/big.csv")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "data/raw/big.csv"], check=True)
    _write(repo, ".gitignore", "# c\n/data/raw/\n")
    hits = tracked_ignored(repo)
    assert [h.path for h in hits] == ["data/raw/big.csv"]
    assert hits[0].source.endswith(".gitignore")
    assert hits[0].line == 2
    assert hits[0].pattern == "/data/raw/"


def test_tracked_ignored_filters_negation_matches(tmp_path: Path):
    """`check-ignore -v` reports `!`-prefixed matches; those files are NOT ignored."""
    repo = _repo(tmp_path)
    _write(repo, "data/keep.tsv")
    _write(repo, ".gitignore", "data/*\n!data/keep.tsv\n")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "data/keep.tsv"], check=True)
    assert tracked_ignored(repo) == []


def test_tracked_ignored_sees_global_excludes(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, "archive/a.py")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "archive/a.py"], check=True)
    _write(repo, "gi", "archive\n")
    subprocess.run(["git", "-C", str(repo), "config", "core.excludesFile", str(repo / "gi")], check=True)
    hits = tracked_ignored(repo)
    assert [h.path for h in hits] == ["archive/a.py"]
    assert hits[0].source.endswith("gi")


def test_governed_files_exclude_untracked_and_info_exclude(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "/data/**\n!/data/**/\n")
    _write(repo, "src/.gitignore", "build/\n")
    _write(repo, "data/nested/.gitignore", "x\n")
    (repo / ".git/info").mkdir(parents=True, exist_ok=True)
    (repo / ".git/info/exclude").write_text("secret/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "src/.gitignore"], check=True)
    files = governed_ignore_files(repo)
    assert ".gitignore" in files
    assert "src/.gitignore" in files
    assert "data/nested/.gitignore" not in files  # untracked -> not shareable
    assert not any("info/exclude" in f for f in files)


def test_unmanaged_rules_skip_the_managed_block_and_comments(tmp_path: Path):
    from science_tool.boundary.generate import splice_managed_block

    repo = _repo(tmp_path)
    text = splice_managed_block("# note\n.venv/\n\n", "/data/raw/\n")
    _write(repo, ".gitignore", text)
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    rules = unmanaged_rules(repo)
    patterns = [r.pattern for r in rules]
    assert patterns == [".venv/"]
    assert rules[0].source == ".gitignore"


def test_unmanaged_rules_report_a_duplicate_of_a_generated_line(tmp_path: Path):
    """Text equality must NOT suppress: a hand-written duplicate outside the
    block is exactly what declaration-conflict exists to reject."""
    from science_tool.boundary.generate import splice_managed_block

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", splice_managed_block("/data/raw/\n", "/data/raw/\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert [r.pattern for r in unmanaged_rules(repo)] == ["/data/raw/"]


def test_git_failure_raises_rather_than_reporting_clean(tmp_path: Path):
    from science_tool.boundary.gitio import BoundaryGitError

    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    with pytest.raises(BoundaryGitError):
        visible_paths(not_a_repo)


def test_matching_rules_use_git_semantics_for_wildcards(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "*.parquet\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/external/ds/part.parquet"])
    assert [r.pattern for r in hits["data/external/ds/part.parquet"]] == ["*.parquet"]


def test_matching_rules_respect_nested_gitignore_scope(tmp_path: Path):
    """`data/raw` inside inc/.gitignore scopes to inc/, not the repo root."""
    repo = _repo(tmp_path)
    _write(repo, "inc/.gitignore", "data/raw\n")
    subprocess.run(["git", "-C", str(repo), "add", "inc/.gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/raw/x.csv", "inc/data/raw/y.csv"])
    assert "data/raw/x.csv" not in hits
    assert hits["inc/data/raw/y.csv"][0].source == "inc/.gitignore"


def test_matching_rules_see_past_a_later_managed_rule(tmp_path: Path):
    """The managed block is spliced AFTER the hand-written region, so it always
    WINS. Isolation is what makes the shadowed unmanaged rule visible."""
    from science_tool.boundary.generate import splice_managed_block

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", splice_managed_block("*.parquet\n", "/data/external/**\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    target = "data/external/ds/part.parquet"
    # Real resolution: the managed rule wins.
    assert tracked_ignored(repo) == []  # nothing tracked yet
    hits = matching_unmanaged_rules(repo, [target])
    assert [r.pattern for r in hits[target]] == ["*.parquet"]
    assert hits[target][0].line == 1, "managed lines are blanked, so line numbers still match"


def test_matching_rules_report_a_duplicate_shadowed_by_the_managed_block(tmp_path: Path):
    from science_tool.boundary.generate import splice_managed_block

    repo = _repo(tmp_path)
    _write(repo, ".gitignore", splice_managed_block("/data/raw/\n", "/data/raw/\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/raw/x.csv"])
    assert hits["data/raw/x.csv"][0].line == 1


def test_matching_rules_see_past_an_unmanaged_negation(tmp_path: Path):
    """Isolation alone is not enough: among unmanaged rules the last match still
    wins, and git reports the NEGATION here. Peeling is what surfaces the ignore
    rule underneath it. Both lines are reported -- the negation is itself an
    unauthorised per-case exception."""
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "/data/raw/**\n!/data/raw/**\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/raw/x.csv"])
    assert [(r.line, r.pattern) for r in hits["data/raw/x.csv"]] == [
        (1, "/data/raw/**"),
        (2, "!/data/raw/**"),
    ]


def test_matching_rules_report_a_standalone_negation(tmp_path: Path):
    """A lone `!` rule ignores nothing, so no ignore-rule search would find it --
    but pinning one file out of a declared payload root by hand is exactly the
    per-case exception the declaration replaces."""
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "!/data/raw/keep.csv\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    hits = matching_unmanaged_rules(repo, ["data/raw/keep.csv", "data/raw/other.csv"])
    assert [r.pattern for r in hits["data/raw/keep.csv"]] == ["!/data/raw/keep.csv"]
    assert "data/raw/other.csv" not in hits


def test_matching_rules_attribute_one_rule_to_every_path_it_matches(tmp_path: Path):
    """Peeling blanks a rule only AFTER the whole round is recorded; blanking
    mid-round would drop every path after the first."""
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "*.parquet\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    paths = ["data/external/a.parquet", "data/external/b.parquet", "data/external/c.parquet"]
    hits = matching_unmanaged_rules(repo, paths)
    assert sorted(hits) == sorted(paths)


def test_matching_rules_terminate_when_nothing_matches(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "/unrelated/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert matching_unmanaged_rules(repo, ["data/external/a.parquet"]) == {}


def test_governed_ignore_files_skip_a_tracked_but_deleted_file(tmp_path: Path):
    """`ls-files` still lists it; it governs nothing."""
    repo = _repo(tmp_path)
    _write(repo, "inc/.gitignore", "build/\n")
    subprocess.run(["git", "-C", str(repo), "add", "inc/.gitignore"], check=True)
    (repo / "inc" / ".gitignore").unlink()
    assert governed_ignore_files(repo) == []


def test_unmanaged_rules_from_nested_file_carry_their_source(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "build/\n")
    _write(repo, "inc/shiny/.gitignore", "build/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "inc/shiny/.gitignore"], check=True)
    rules = unmanaged_rules(repo)
    sources = sorted((r.source, r.pattern) for r in rules)
    assert sources == [(".gitignore", "build/"), ("inc/shiny/.gitignore", "build/")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_boundary_gitio.py -v`
Expected: FAIL — `ModuleNotFoundError: ... boundary.gitio`

- [ ] **Step 3: Implement the git layer**

```python
# science/src/science_tool/boundary/gitio.py
"""Every git subprocess call the boundary tooling makes.

SOURCE UNIVERSE (design: "govern what is shareable, diagnose whatever bites"):

* Rule-text inspection (`governed_ignore_files`, `unmanaged_rules`) sees only
  TRACKED, in-worktree `.gitignore` files. `.git/info/exclude` is per-clone and
  `core.excludesFile` is machine-wide; a finding against either could not be
  fixed in the repository or seen by anyone else.
* Effect inspection (`visible_paths`, `tracked_ignored`) uses git's FULL
  effective resolution, including both of those, because it asks what actually
  happened. Such a hit is reported with its source path and never rewritten.

`git check-ignore` is NOT the reachability oracle: without `--no-index` it
reports a tracked path as un-ignored regardless of the rules, so it answers
"do the patterns match?" rather than "will git surface this file?".
`visible_paths` answers the second, and agrees with `git add .`.

All output framing is NUL-delimited: newlines are legal in git paths.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IgnoreHit:
    path: str
    source: str
    line: int
    pattern: str


@dataclass(frozen=True)
class IgnoreRule:
    source: str
    line: int
    pattern: str


class BoundaryGitError(Exception):
    """A git invocation failed in a way that must not be read as 'clean'."""


def _git(project_root: Path, *args: str, stdin: bytes | None = None, ok: tuple[int, ...] = (0,)) -> bytes:
    """Run git, accepting ONLY documented return codes.

    Fails closed: 'not a git repository', a malformed invocation, or any other
    git failure must never be silently reported as an empty (clean) result.
    `check-ignore` documents 1 as "nothing matched", which is a success here.
    """
    proc = subprocess.run(
        ["git", "-C", str(project_root), *args],
        input=stdin,
        capture_output=True,
        check=False,
    )
    if proc.returncode not in ok:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise BoundaryGitError(f"git {' '.join(args)} failed ({proc.returncode}): {detail}")
    return proc.stdout


def _git_plain(*args: str) -> None:
    """A git call with no project root -- scratch `init` and `config`.

    Same fail-closed contract as `_git`: a scratch repo that silently failed to
    initialise would make every conflict check report clean.
    """
    proc = subprocess.run(["git", *args], capture_output=True, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise BoundaryGitError(f"git {' '.join(args)} failed ({proc.returncode}): {detail}")


def _read_governed(project_root: Path, rel: str) -> str:
    """Read a governed `.gitignore`, failing closed.

    An unreadable rule source is not an empty one. Swallowing `OSError` here
    would silently drop every rule in that file from `unmanaged_rules` and from
    conflict detection -- the file would be governed on paper and ungoverned in
    fact.
    """
    try:
        return (project_root / rel).read_text(encoding="utf-8")
    except OSError as exc:
        raise BoundaryGitError(f"cannot read governed ignore file {rel}: {exc}") from exc


def _split_z(payload: bytes) -> list[str]:
    return [chunk.decode("utf-8", "surrogateescape") for chunk in payload.split(b"\0") if chunk]


def visible_paths(project_root: Path) -> set[str]:
    """Paths git will surface: tracked, plus untracked-and-not-ignored.

    This is the reachability oracle. A file absent from this set will not be
    staged by `git add .`, whatever `check-ignore` says about it.
    """
    return set(_split_z(_git(project_root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")))


def tracked_ignored(project_root: Path) -> list[IgnoreHit]:
    """Tracked files that nonetheless match an ignore rule.

    Uses `--no-index` so ignore rules apply to tracked paths at all, which also
    brings global excludes into scope by design.
    """
    tracked = _git(project_root, "ls-files", "-z")
    if not tracked:
        return []
    # check-ignore exits 1 when nothing matched -- the clean case, not a failure.
    raw = _git(project_root, "check-ignore", "--no-index", "--stdin", "-z", "-v", stdin=tracked, ok=(0, 1))
    fields = raw.split(b"\0")
    hits: list[IgnoreHit] = []
    # -v -z emits 4 NUL-terminated fields per record: source, line, pattern, path.
    for i in range(0, len(fields) - 3, 4):
        source, line, pattern, path = (f.decode("utf-8", "surrogateescape") for f in fields[i : i + 4])
        if not path:
            continue
        # A `!`-prefixed pattern means the path is NOT ignored. Reporting these
        # would be a false positive; MM30 produced 7 of them.
        if pattern.startswith("!"):
            continue
        hits.append(IgnoreHit(path=path, source=source, line=int(line or 0), pattern=pattern))
    return sorted(hits, key=lambda h: h.path)


def governed_ignore_files(project_root: Path) -> list[str]:
    """Tracked AND present `.gitignore` files -- the shareable rule surface.

    `git ls-files` lists index entries, including a file deleted from the
    worktree but not yet staged as removed. Such a file governs nothing, yet an
    earlier draft let it satisfy `unmanaged_allow` source validation -- an
    allowlist entry could name a source that no longer exists and be accepted.
    Requiring the file to be present on disk keeps "governed" and "in effect"
    the same set.
    """
    tracked = _split_z(_git(project_root, "ls-files", "-z"))
    named = (p for p in tracked if p == ".gitignore" or p.endswith("/.gitignore"))
    return sorted(p for p in named if (project_root / p).is_file())


def unmanaged_rules(project_root: Path) -> list[IgnoreRule]:
    """Every hand-written rule in the governed files, excluding the managed block.

    Membership is decided ONLY by the marker range. An earlier draft also
    suppressed any rule whose TEXT equalled a generated line, which made a
    duplicated `/data/raw/` outside the block invisible to
    `declaration-conflict` -- the check that exists to reject exactly that.
    """
    from science_tool.boundary.generate import MANAGED_BEGIN, MANAGED_END

    rules: list[IgnoreRule] = []
    for rel in governed_ignore_files(project_root):
        text = _read_governed(project_root, rel)
        inside = False
        for number, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if MANAGED_BEGIN in raw:
                inside = True
                continue
            if MANAGED_END in raw:
                inside = False
                continue
            if inside or not line or line.startswith("#"):
                continue
            rules.append(IgnoreRule(source=rel, line=number, pattern=line))
    return sorted(rules, key=lambda r: (r.source, r.line))


def matching_unmanaged_rules(project_root: Path, paths: list[str]) -> dict[str, list[IgnoreRule]]:
    """EVERY unmanaged rule that matches each path -- winner or not, sign or not.

    Two distinct winner-takes-all failures had to be designed out here, both
    reproduced against real git:

    1. `check-ignore` reports only the LAST matching pattern, and the managed
       block is spliced AFTER the hand-written region, so a managed rule always
       wins and an unmanaged rule beneath a declared root is never reported.
    2. Even among unmanaged rules alone the last match wins, and a `!` winner
       used to be discarded as a false positive. With

           /data/raw/**
           !/data/raw/**

       git reports the negation, the negation is dropped, and NO conflict is
       reported -- while a standalone unmanaged negation aimed at a declared
       root, which is precisely the per-case exception this design exists to
       abolish, is likewise invisible.

    So this reports MATCHES, never winners, in two layers:

    * ISOLATION removes managed-vs-unmanaged shadowing. A scratch repository is
      built containing only the governed `.gitignore` files with every
      managed-block line BLANKED (not deleted, so reported line numbers still
      match the real file), global excludes disabled, and no index. Nested
      `.gitignore` scoping survives because the files keep their relative
      locations.
    * PEELING removes unmanaged-vs-unmanaged shadowing. Each round records the
      reported rule for every path, then blanks those rule lines and asks again,
      until a round reports nothing new. Blanking a `!` winner lets the rule it
      shadowed surface on the next round. Each round blanks at least one line,
      so the loop is bounded by the number of unmanaged rules; in practice it
      converges in one or two rounds because most rules match nothing.

    A negation is recorded as a match on purpose. `!/data/raw/keep.csv` under a
    declared root is an unauthorised per-case exception even when some other
    rule renders it inert -- flagging the text is the point.

    git's own pattern engine does all the matching; nothing is reimplemented.
    """
    from science_tool.boundary.generate import MANAGED_BEGIN, MANAGED_END

    if not paths:
        return {}
    governed = governed_ignore_files(project_root)
    if not governed:
        return {}

    # Managed-block lines start blanked; peeled lines are added as we go.
    blanked: dict[str, set[int]] = {}
    sources: dict[str, list[str]] = {}
    for rel in governed:
        text = _read_governed(project_root, rel)
        lines = text.splitlines()
        sources[rel] = lines
        managed = set()
        inside = False
        for number, raw in enumerate(lines, start=1):
            if MANAGED_BEGIN in raw:
                inside = True
                managed.add(number)
                continue
            if MANAGED_END in raw:
                inside = False
                managed.add(number)
                continue
            if inside:
                managed.add(number)
        blanked[rel] = managed

    matches: dict[str, list[IgnoreRule]] = {}
    payload = "\0".join(paths).encode("utf-8", "surrogateescape") + b"\0"

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "scratch"
        scratch.mkdir()
        _git_plain("init", "-q", str(scratch))
        empty = Path(tmp) / "empty-excludes"
        empty.write_text("")
        _git_plain("-C", str(scratch), "config", "core.excludesFile", str(empty))

        while True:
            for rel, lines in sources.items():
                rendered = [
                    "" if number in blanked[rel] else raw
                    for number, raw in enumerate(lines, start=1)
                ]
                target = scratch / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("\n".join(rendered) + "\n", encoding="utf-8")

            raw_out = _git(
                scratch, "check-ignore", "--no-index", "--stdin", "-z", "-v",
                stdin=payload, ok=(0, 1),
            )
            fields = raw_out.split(b"\0")
            # Record the WHOLE round before blanking anything. Blanking inside
            # this loop would drop the second and later paths matched by the same
            # rule in the same round -- they would see it already blanked.
            newly: set[tuple[str, int]] = set()
            for i in range(0, len(fields) - 3, 4):
                source, line, pattern, path = (
                    f.decode("utf-8", "surrogateescape") for f in fields[i : i + 4]
                )
                if not path or source not in blanked:
                    continue
                number = int(line or 0)
                if number in blanked[source]:
                    continue
                matches.setdefault(path, []).append(
                    IgnoreRule(source=source, line=number, pattern=pattern)
                )
                newly.add((source, number))
            if not newly:
                break
            for source, number in newly:
                blanked[source].add(number)

    for hits in matches.values():
        hits.sort(key=lambda r: (r.source, r.line))
    return matches
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_boundary_gitio.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/boundary/gitio.py science/tests/test_boundary_gitio.py
git commit -m "feat(boundary): git introspection layer with an explicit source universe"
```

---

## Task 4: Manifest-root walk, with symlink/nested-repo/pruning semantics and a benchmark

**Files:**
- Create: `science/src/science_tool/boundary/walk.py`
- Test: `science/tests/test_boundary_walk.py`
- Test: `science/tests/test_boundary_walk_perf.py`

**Interfaces:**
- Consumes: `BoundaryRoot` (Task 1), `visible_paths` (Task 3).
- Produces: `manifest_candidates(project_root: Path, root: BoundaryRoot) -> list[str]`.

**Why a walk at all:** `unreachable-tracked` must find files that git cannot see, so it cannot ask git for them. It walks the filesystem under `manifest` roots and matches `tracked:` globs.

**Semantics fixed here:**

| Concern | Behaviour | Rationale |
|---|---|---|
| Symlinked directories | Not descended into | Prevents cycles and escaping the root; a symlinked tree is not *in* the repo |
| Symlinked files | Reported if the name matches | Git tracks the link itself |
| Symlinked root | Not traversed at all | `followlinks=False` does not protect the top directory, so a symlinked root would escape the repo |
| Nested repositories | A directory containing `.git` as **file or directory** is pruned. Only the **project root** is exempt — not the supplied `base` | Submodules and linked worktrees use the file form; git treats both as opaque gitlinks. Exempting `base` would traverse a submodule declared as a root in full |
| The `.git` marker itself | Excluded from **filenames** as well as directory names | In a linked worktree the root's `.git` is a file, not a directory |
| Glob matching | Right-anchored against the path **relative to the root** | Mirrors the generated `!/root/**/<glob>` rule, so multi-segment globs like `schemas/*.json` work |
| Pruning | Skip `.git` | Bounded by the benchmark, not by prefix analysis |
| Ordering | Sorted | Stable findings |

No glob-prefix pruning: an earlier draft claimed it and did not implement it. The benchmark below is what bounds the walk.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_boundary_walk.py
from __future__ import annotations

from pathlib import Path

from science_tool.boundary.config import BoundaryRoot
from science_tool.boundary.walk import manifest_candidates


def _root() -> BoundaryRoot:
    return BoundaryRoot.model_validate(
        {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json", "*.qa.json"]}
    )


def _mk(base: Path, rel: str, body: str = "x") -> Path:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


def test_matches_at_any_depth(tmp_path: Path):
    _mk(tmp_path, "data/external/a/datapackage.json")
    _mk(tmp_path, "data/external/a/b/c/datapackage.json")
    _mk(tmp_path, "data/external/a/big.parquet")
    found = manifest_candidates(tmp_path, _root())
    assert found == ["data/external/a/b/c/datapackage.json", "data/external/a/datapackage.json"]


def test_matches_glob_pattern(tmp_path: Path):
    _mk(tmp_path, "data/external/a/run.qa.json")
    assert manifest_candidates(tmp_path, _root()) == ["data/external/a/run.qa.json"]


def test_missing_root_is_empty(tmp_path: Path):
    assert manifest_candidates(tmp_path, _root()) == []


def test_does_not_descend_into_symlinked_directory(tmp_path: Path):
    _mk(tmp_path, "outside/datapackage.json")
    (tmp_path / "data/external").mkdir(parents=True)
    (tmp_path / "data/external/link").symlink_to(tmp_path / "outside", target_is_directory=True)
    assert manifest_candidates(tmp_path, _root()) == []


def test_symlinked_file_is_reported(tmp_path: Path):
    target = _mk(tmp_path, "outside/datapackage.json")
    (tmp_path / "data/external/a").mkdir(parents=True)
    (tmp_path / "data/external/a/datapackage.json").symlink_to(target)
    assert manifest_candidates(tmp_path, _root()) == ["data/external/a/datapackage.json"]


def test_symlink_cycle_terminates(tmp_path: Path):
    (tmp_path / "data/external/a").mkdir(parents=True)
    (tmp_path / "data/external/a/loop").symlink_to(tmp_path / "data/external", target_is_directory=True)
    _mk(tmp_path, "data/external/a/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == ["data/external/a/datapackage.json"]


def test_nested_repository_dir_form_is_pruned(tmp_path: Path):
    _mk(tmp_path, "data/external/sub/.git/HEAD", "ref: refs/heads/main\n")
    _mk(tmp_path, "data/external/sub/datapackage.json")
    _mk(tmp_path, "data/external/own/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == ["data/external/own/datapackage.json"]


def test_nested_repository_file_form_is_pruned(tmp_path: Path):
    """Submodules and linked worktrees carry `.git` as a FILE."""
    _mk(tmp_path, "data/external/sub/.git", "gitdir: /elsewhere/.git/modules/sub\n")
    _mk(tmp_path, "data/external/sub/datapackage.json")
    _mk(tmp_path, "data/external/own/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == ["data/external/own/datapackage.json"]


def test_declared_root_that_is_itself_a_nested_repo_is_pruned(tmp_path: Path):
    """The exemption from pruning belongs to the PROJECT ROOT alone. Exempting
    the supplied `base` traversed a submodule declared as a root in full."""
    _mk(tmp_path, "data/external/.git", "gitdir: /elsewhere/.git/modules/external\n")
    _mk(tmp_path, "data/external/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == []


def test_project_root_git_file_is_not_reported(tmp_path: Path):
    """A linked worktree's root `.git` is a FILE, and filtering only directory
    names returned it as a repository file."""
    from science_tool.boundary.walk import iter_repo_files

    _mk(tmp_path, ".git", "gitdir: /elsewhere/.git/worktrees/wt\n")
    _mk(tmp_path, "README.md")
    assert iter_repo_files(tmp_path) == ["README.md"]


def test_project_root_git_directory_is_not_reported(tmp_path: Path):
    from science_tool.boundary.walk import iter_repo_files

    _mk(tmp_path, ".git/HEAD", "ref: refs/heads/main\n")
    _mk(tmp_path, "README.md")
    assert iter_repo_files(tmp_path) == ["README.md"]


def test_symlinked_root_is_not_traversed(tmp_path: Path):
    _mk(tmp_path, "outside/a/datapackage.json")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/external").symlink_to(tmp_path / "outside", target_is_directory=True)
    assert manifest_candidates(tmp_path, _root()) == []


def test_multi_segment_glob_is_matched(tmp_path: Path):
    root = BoundaryRoot.model_validate(
        {"path": "data/external", "class": "manifest", "tracked": ["schemas/*.json"]}
    )
    _mk(tmp_path, "data/external/ds/schemas/x.json")
    _mk(tmp_path, "data/external/ds/other.json")
    assert manifest_candidates(tmp_path, root) == ["data/external/ds/schemas/x.json"]


def test_dot_git_directory_is_skipped(tmp_path: Path):
    _mk(tmp_path, "data/external/.git/datapackage.json")
    assert manifest_candidates(tmp_path, _root()) == []
```

```python
# science/tests/test_boundary_walk_perf.py
from __future__ import annotations

import time
from pathlib import Path

import pytest

from science_tool.boundary.config import BoundaryRoot
from science_tool.boundary.walk import manifest_candidates

# Open Targets 25.03 alone is ~1526 files under one manifest root, and the walk
# runs inside the pre-commit profile. Budget is deliberately loose so this
# guards against an accidental O(n^2) rewrite, not against normal I/O variance.
FILE_COUNT = 5000
BUDGET_SECONDS = 2.0


@pytest.fixture
def big_tree(tmp_path: Path) -> Path:
    for shard in range(50):
        d = tmp_path / "data/external/ds" / f"{shard:03d}"
        d.mkdir(parents=True)
        (d / "datapackage.json").write_text("{}")
        for n in range(FILE_COUNT // 50 - 1):
            (d / f"part-{n:05d}.parquet").write_text("x")
    return tmp_path


def test_walk_stays_within_budget(big_tree: Path):
    root = BoundaryRoot.model_validate(
        {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}
    )
    start = time.perf_counter()
    found = manifest_candidates(big_tree, root)
    elapsed = time.perf_counter() - start
    assert len(found) == 50
    assert elapsed < BUDGET_SECONDS, f"walk took {elapsed:.2f}s over {FILE_COUNT} files"


CONFLICT_BUDGET_SECONDS = 5.0


def test_conflict_detection_stays_within_budget(big_tree: Path):
    """The conflict algorithm feeds EVERY extant path under a declared root to a
    check-ignore call per peeling round, over a scratch repo. Uncapped by design
    (a sampled ERROR check would be probabilistic) and round count is data
    dependent, so it needs its own budget rather than the walk's.
    """
    import subprocess

    from science_tool.boundary.gitio import matching_unmanaged_rules
    from science_tool.validate.checks.boundary import _conflict_subjects

    subprocess.run(["git", "init", "-q", str(big_tree)], check=True)
    (big_tree / ".gitignore").write_text("*.parquet\n")
    subprocess.run(["git", "-C", str(big_tree), "add", "-f", ".gitignore"], check=True)

    start = time.perf_counter()
    subjects = _conflict_subjects(big_tree, "data/external")
    hits = matching_unmanaged_rules(big_tree, subjects)
    elapsed = time.perf_counter() - start

    assert len(subjects) >= FILE_COUNT, "every extant path must be fed in, not a sample"
    assert hits, "the wildcard rule must be detected"
    assert elapsed < CONFLICT_BUDGET_SECONDS, f"conflict pass took {elapsed:.2f}s over {FILE_COUNT} files"


def test_conflict_detection_worst_case_peeling_stays_within_budget(big_tree: Path):
    """Peeling runs one check-ignore per round and blanks at least one rule per
    round, so rounds are bounded by the number of MATCHING unmanaged rules. This
    pins the worst realistic case -- every rule matching -- rather than assuming
    the one-round happy path holds."""
    import subprocess

    from science_tool.boundary.gitio import matching_unmanaged_rules
    from science_tool.validate.checks.boundary import _conflict_subjects

    subprocess.run(["git", "init", "-q", str(big_tree)], check=True)
    rules = "\n".join(f"*.parquet\n!/data/external/ds/{shard:03d}/**" for shard in range(20))
    (big_tree / ".gitignore").write_text(rules + "\n")
    subprocess.run(["git", "-C", str(big_tree), "add", "-f", ".gitignore"], check=True)

    start = time.perf_counter()
    hits = matching_unmanaged_rules(big_tree, _conflict_subjects(big_tree, "data/external"))
    elapsed = time.perf_counter() - start

    assert hits
    assert elapsed < CONFLICT_BUDGET_SECONDS, f"peeling took {elapsed:.2f}s over 40 rules"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_boundary_walk.py tests/test_boundary_walk_perf.py -v`
Expected: FAIL — `ModuleNotFoundError: ... boundary.walk`

- [ ] **Step 3: Implement the walk**

```python
# science/src/science_tool/boundary/walk.py
"""Filesystem walk under a manifest root.

`unreachable-tracked` must find files git CANNOT see, so it cannot ask git for
them. Semantics fixed here:

* symlinked DIRECTORIES are never descended into -- prevents cycles and stops
  the walk escaping the root; a symlinked tree is not in the repository
* symlinked FILES are reported, because git tracks the link itself
* a directory containing `.git` is pruned: git treats a nested repository as an
  opaque gitlink and never looks inside
* `.git` itself is always skipped
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from science_tool.boundary.config import BoundaryRoot


def _matches(rel_to_root: str, globs: tuple[str, ...]) -> bool:
    """Match the path RELATIVE TO THE ROOT, right-anchored, at any depth.

    `PurePosixPath.match` is right-anchored, which is exactly the generated
    rule's semantics (`!/root/**/<glob>`): `datapackage.json` matches
    `a/b/datapackage.json`, and a multi-segment glob such as `schemas/*.json`
    matches `a/schemas/x.json`. Matching only the BASENAME -- an earlier draft --
    made every glob containing `/` invisible to the checker even though the
    generator emitted a working git rule for it.
    """
    candidate = PurePosixPath(rel_to_root)
    return any(candidate.match(glob) for glob in globs)


def _is_nested_repo(directory: Path) -> bool:
    """A submodule or linked worktree has `.git` as a FILE, not a directory."""
    marker = directory / ".git"
    return marker.is_dir() or marker.is_file()


def iter_repo_files(project_root: Path, base: Path | None = None) -> list[str]:
    """THE raw-walk primitive. Every caller that enumerates the tree uses this.

    Repo-relative posix paths, sorted, with `.git` skipped, nested repositories
    pruned (file OR directory form), and symlinked directories never descended.
    The conflict sampler, the transactional enumeration and the adoption walker
    all route through here so the traversal semantics are defined once.
    """
    top = base if base is not None else project_root
    if top.is_symlink() or not top.is_dir():
        return []
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(top, followlinks=False):
        current = Path(dirpath)
        # Only the PROJECT ROOT is exempt from nested-repo pruning, not every
        # supplied `base`. An earlier draft exempted `top`, so a declared root
        # that is itself a submodule or linked worktree was traversed in full --
        # precisely the case pruning exists for.
        if current != project_root and _is_nested_repo(current):
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames if d != ".git" and not (current / d).is_symlink())
        # `.git` must be dropped from FILENAMES too. In a linked worktree the
        # project root's `.git` is a file, so filtering directory names alone
        # returned it as a repository file.
        for name in sorted(n for n in filenames if n != ".git"):
            found.append((current / name).relative_to(project_root).as_posix())
    return sorted(found)


def manifest_candidates(project_root: Path, root: BoundaryRoot) -> list[str]:
    """Repo-relative paths under `root` matching one of its tracked globs."""
    base = project_root / root.path
    prefix = f"{root.path}/"
    return [
        rel
        for rel in iter_repo_files(project_root, base)
        if _matches(rel[len(prefix) :], root.tracked)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_boundary_walk.py tests/test_boundary_walk_perf.py -v`
Expected: PASS (all)

- [ ] **Step 5: Record the benchmark result**

Run the perf test with timing shown and note the measured figure in the commit body:

```bash
cd science && uv run --frozen pytest tests/test_boundary_walk_perf.py -v -s
```

Reference figures from a prototype of the same algorithm over the same 5000-file
shape, so a large regression is recognisable rather than merely under budget:

| Case | Rounds | Measured |
|---|---|---|
| Conflict pass, 1 matching rule | 2 | 0.07 s |
| Conflict pass, 40 rules all matching | 21 | 0.76 s |

If either lands near its budget rather than near these figures, the peeling loop
is re-running more rounds than the rule count justifies — investigate before
raising the budget.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/boundary/walk.py science/tests/test_boundary_walk.py science/tests/test_boundary_walk_perf.py
git commit -m "feat(boundary): manifest-root walk with symlink, nested-repo and pruning semantics"
```

---

## Task 5: The six validate checks

**Files:**
- Create: `science/src/science_tool/validate/checks/boundary.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (append `"boundary"` to `CANONICAL_CHECK_MODULES`)
- Test: `science/tests/test_boundary_checks.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4, plus `render_managed_block`/`extract_managed_block` (Task 2).
- Produces: `check_boundary(ctx: ValidateContext) -> Iterator[Result]`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_boundary_checks.py
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from science_tool.boundary.config import BoundaryConfig
from science_tool.boundary.generate import render_managed_block, splice_managed_block
from science_tool.validate.checks.boundary import check_boundary
from science_tool.validate.context import ValidateContext


def _repo(tmp_path: Path, boundary: dict | None = None) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    payload: dict = {"name": "Demo", "id": "demo"}
    if boundary is not None:
        payload["boundary"] = boundary
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
    return tmp_path


def _results(root: Path) -> list:
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_boundary(ctx))


def _rules(root: Path) -> list[str]:
    return [r.rule for r in _results(root)]


def test_tracked_ignored_fires_without_any_declaration(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data/big.csv").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "data/big.csv"], check=True)
    (repo / ".gitignore").write_text("/data/\n")
    assert "boundary.tracked-ignored" in _rules(repo)


def test_clean_undeclared_project_is_silent(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("/papers/pdfs/\n")
    # Implicit-versioned semantics begin at enrollment: no declaration, no
    # ignored-undeclared finding.
    assert _rules(repo) == []


def test_unanchored_pattern_warns(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("archive\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unanchored-pattern" in _rules(repo)


def test_generated_drift_fires_when_block_is_stale(tmp_path: Path):
    repo = _repo(tmp_path, {"roots": [{"path": "data/raw", "class": "payload"}]})
    (repo / ".gitignore").write_text(splice_managed_block("", "/wrong/\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.generated-drift" in _rules(repo)


def test_no_drift_when_block_matches(tmp_path: Path):
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.generated-drift" not in _rules(repo)


def test_declaration_conflict_catches_a_bare_wildcard(tmp_path: Path):
    """`*.parquet` names no root but governs paths inside one. Text prefix
    comparison misses this entirely; asking git does not."""
    decl = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("*.parquet\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_declaration_conflict_catches_a_subdirectory_scoped_rule(tmp_path: Path):
    """No generic probe visits `foo/`; the real-tree sample is what finds it."""
    decl = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / "data/external/foo").mkdir(parents=True)
    (repo / "data/external/foo/part.parquet").write_text("x")
    (repo / ".gitignore").write_text(
        splice_managed_block("data/external/foo/*.parquet\n", render_managed_block(cfg))
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_nested_gitignore_scope_is_not_a_false_conflict(tmp_path: Path):
    """`data/raw` inside inc/.gitignore scopes to inc/, NOT the declared root."""
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    (repo / "inc").mkdir()
    (repo / "inc/.gitignore").write_text("data/raw\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "inc/.gitignore"], check=True)
    assert "boundary.declaration-conflict" not in _rules(repo)


def test_allowlist_cannot_excuse_a_conflict(tmp_path: Path):
    """The allowlist excuses undeclared noise; it may NEVER excuse a rule that
    targets a declared root, or it reopens the adjudication this check closes."""
    decl = {
        "roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}],
        "unmanaged_allow": ["*.parquet"],
    }
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("*.parquet\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_declaration_conflict_catches_a_hand_written_pin(tmp_path: Path):
    """A `!` rule pinning one file out of a declared payload root IS the per-case
    exception the declaration replaces. It ignores nothing, so no ignore-rule
    search finds it -- only reporting matches rather than winners does."""
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/keep.csv").write_text("x")
    (repo / ".gitignore").write_text(
        splice_managed_block("!/data/raw/keep.csv\n", render_managed_block(cfg))
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_declaration_conflict_sees_a_rule_shadowed_by_a_hand_written_negation(tmp_path: Path):
    """Among unmanaged rules the LAST match still wins, and git reports the
    negation here. Peeling is what surfaces the ignore rule underneath."""
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/x.csv").write_text("x")
    (repo / ".gitignore").write_text(
        splice_managed_block("/data/raw/**\n!/data/raw/**\n", render_managed_block(cfg))
    )
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    findings = [r for r in _results(repo) if r.rule == "boundary.declaration-conflict"]
    assert sorted(f.line for f in findings) == [1, 2], "both rules must be reported, not just the winner"


def test_duplicate_of_a_generated_line_is_a_conflict(tmp_path: Path):
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("/data/raw/\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.declaration-conflict" in _rules(repo)


def test_invalid_declaration_is_an_error_not_silence(tmp_path: Path):
    repo = _repo(tmp_path, {"roots": [{"path": "data", "class": "payload"},
                                      {"path": "data/external", "class": "manifest",
                                       "tracked": ["datapackage.json"]}]})
    rules = _rules(repo)
    assert "boundary.invalid-declaration" in rules


def test_universal_checks_survive_an_invalid_declaration(tmp_path: Path):
    """Both universal checks run BEFORE the declaration is loaded. Running them
    after the early return made them universal in name only -- and a broken
    declaration is exactly when an unanchored rule is most likely to be lurking."""
    repo = _repo(tmp_path, {"roots": [{"path": "data", "class": "payload"},
                                      {"path": "data/external", "class": "manifest",
                                       "tracked": ["datapackage.json"]}]})
    (repo / ".gitignore").write_text("archive\n")
    (repo / "data").mkdir()
    (repo / "data/big.csv").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "-f", ".gitignore", "data/big.csv"], check=True)
    (repo / ".gitignore").write_text("archive\n/data/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    rules = _rules(repo)
    assert "boundary.invalid-declaration" in rules
    assert "boundary.unanchored-pattern" in rules
    assert "boundary.tracked-ignored" in rules


def test_ignored_undeclared_warns_and_allowlist_silences_it(tmp_path: Path):
    decl = {"roots": [{"path": "data/raw", "class": "payload"}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("/papers/pdfs/\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.ignored-undeclared" in _rules(repo)

    decl_allowed = dict(decl, unmanaged_allow=["/papers/pdfs/"])
    repo2 = _repo(tmp_path / "two", decl_allowed)
    (repo2 / ".gitignore").write_text(splice_managed_block("/papers/pdfs/\n", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo2), "add", ".gitignore"], check=True)
    assert "boundary.ignored-undeclared" not in _rules(repo2)


def test_allowlist_is_source_scoped(tmp_path: Path):
    """Same text in root and nested file are DIFFERENT rules."""
    decl = {"roots": [{"path": "data/raw", "class": "payload"}], "unmanaged_allow": ["build/"]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / ".gitignore").write_text(splice_managed_block("build/\n", render_managed_block(cfg)))
    (repo / "inc").mkdir()
    (repo / "inc/.gitignore").write_text("build/\n")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "inc/.gitignore"], check=True)
    ctx = ValidateContext.from_project_root(repo, strict=False, verbose=False)
    findings = [r for r in check_boundary(ctx) if r.rule == "boundary.ignored-undeclared"]
    assert len(findings) == 1
    assert "inc/.gitignore" in str(findings[0].path)


def test_unreachable_tracked_fires_on_shadowed_descriptor(tmp_path: Path):
    decl = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    repo = _repo(tmp_path, decl)
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.json").write_text("{}")
    # Bare exclude instead of the descend-preserving form: descriptor unreachable.
    (repo / ".gitignore").write_text(splice_managed_block("", "/data/external/\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unreachable-tracked" in _rules(repo)


def test_unreachable_tracked_quiet_on_correct_generation(tmp_path: Path):
    decl = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    repo = _repo(tmp_path, decl)
    cfg = BoundaryConfig.model_validate(decl)
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.json").write_text("{}")
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unreachable-tracked" not in _rules(repo)


def test_unreachable_tracked_catches_glob_negation_case(tmp_path: Path):
    """`!build/**/README.md` under `/build/` -- no parent-directory analysis
    could evaluate this; the oracle can."""
    decl = {"roots": [{"path": "build", "class": "manifest", "tracked": ["README.md"]}]}
    repo = _repo(tmp_path, decl)
    (repo / "build/sub").mkdir(parents=True)
    (repo / "build/sub/README.md").write_text("x")
    (repo / ".gitignore").write_text(splice_managed_block("", "/build/\n!build/**/README.md\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    assert "boundary.unreachable-tracked" in _rules(repo)


def test_check_ignore_would_disagree_regression(tmp_path: Path):
    """Pin that the check follows the oracle, not check-ignore. Someone will try
    to 'simplify' this back onto check-ignore; this test stops them."""
    decl = {"roots": [{"path": "build", "class": "manifest", "tracked": ["README.md"]}]}
    repo = _repo(tmp_path, decl)
    (repo / "build/sub").mkdir(parents=True)
    (repo / "build/sub/README.md").write_text("x")
    (repo / ".gitignore").write_text(splice_managed_block("", "/build/\n!/build/sub/README.md\n"))
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    # check-ignore without --no-index reports it un-ignored; the file is still
    # unreachable because traversal never enters the excluded directory.
    rc = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", "build/sub/README.md"]).returncode
    assert rc != 0, "fixture precondition: check-ignore reports NOT ignored"
    assert "boundary.unreachable-tracked" in _rules(repo)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_boundary_checks.py -v`
Expected: FAIL — `ModuleNotFoundError: ... validate.checks.boundary`

- [ ] **Step 3: Implement the checks**

```python
# science/src/science_tool/validate/checks/boundary.py
"""VCS storage boundary checks.

Two universal (no configuration needed), four declaration-derived. All six are
mechanical: no heuristic classifier participates in enforcement, so a finding is
always a genuine self-contradiction in the repository's own configuration.

See docs/plans/2026-07-26-vcs-storage-boundary-design.md.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.boundary.config import StorageClass
from science_tool.boundary.generate import extract_managed_block, render_managed_block
from science_tool.boundary.gitio import (
    governed_ignore_files,
    tracked_ignored,
    unmanaged_rules,
    visible_paths,
    matching_unmanaged_rules,
)
from science_tool.boundary.walk import iter_repo_files, manifest_candidates
from science_tool.project_config import load_project_config
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

GITIGNORE = Path(".gitignore")


def _is_unanchored_dir_pattern(pattern: str) -> bool:
    body = pattern[1:] if pattern.startswith("!") else pattern
    if body.startswith("/") or "/" in body.rstrip("/"):
        return False
    return body.endswith("/") or "." not in body


def _conflict_subjects(project_root: Path, root_path: str) -> list[str]:
    """Every extant path under a declared root, plus generic future shapes.

    NOT sampled. An earlier draft capped this at 500 paths, which made an ERROR
    check probabilistic -- a scoped rule affecting the 501st file was silently
    missed. All paths go into one NUL-framed check-ignore call per peeling round,
    so the cost is a couple of subprocesses regardless of tree size; the
    benchmark below bounds it.
    """
    base = project_root / root_path
    probes = [
        f"{root_path}/probe.bin",
        f"{root_path}/probe.parquet",
        f"{root_path}/d1/probe.bin",
        f"{root_path}/d1/d2/d3/probe.bin",
        f"{root_path}/d1/datapackage.json",
    ]
    return sorted(set(probes) | set(iter_repo_files(project_root, base)))




@Check(section="version-control boundary", order=14)
def check_boundary(ctx: ValidateContext) -> Iterator[Result]:
    root = ctx.project_root
    if not (root / ".git").exists():
        return

    # ---- universal: tracked-ignored -------------------------------------
    for hit in tracked_ignored(root):
        yield Result(
            severity=Severity.ERROR,
            path=Path(hit.path),
            line=None,
            message=(
                f"{hit.path} is tracked but matches ignore rule {hit.pattern!r} "
                f"({hit.source}:{hit.line}). Ignore rules are not retroactive, so git will "
                f"never report this on its own, and ripgrep, editor search and ruff all stop "
                f"seeing the file. Resolve by `git rm --cached` if it belongs outside version "
                f"control, or by moving it / narrowing the rule if it belongs inside. Do not "
                f"use `git add -f` or a `!` negation: that records the conflict instead of "
                f"removing it."
            ),
            rule="boundary.tracked-ignored",
            task=None,
        )

    # ---- universal: unanchored-pattern ----------------------------------
    # BEFORE the declaration load, not after. Both universal checks must survive
    # a broken `boundary:` block; running this one after the early return made it
    # universal in name only, and an invalid declaration is exactly when an
    # unanchored rule is most likely to be lurking.
    all_unmanaged = unmanaged_rules(root)
    for rule in all_unmanaged:
        if _is_unanchored_dir_pattern(rule.pattern):
            yield Result(
                severity=Severity.WARN,
                path=Path(rule.source),
                line=rule.line,
                message=(
                    f"ignore pattern {rule.pattern!r} is unanchored and matches a directory of "
                    f"that name at ANY depth. Anchor it (`/{rule.pattern.lstrip('/')}`) so it "
                    f"cannot silently swallow tracked source in an unrelated subtree."
                ),
                rule="boundary.unanchored-pattern",
                task=None,
            )

    # ---- declaration load, after BOTH universal checks -------------------
    try:
        cfg = load_project_config(root).boundary
    except Exception as exc:  # noqa: BLE001
        # NEVER downgrade a broken declaration to "undeclared": that would
        # disable four checks exactly when the configuration is wrong.
        yield Result(
            severity=Severity.ERROR,
            path=Path("science.yaml"),
            line=None,
            message=f"boundary declaration is invalid, so no declared-root check can run: {exc}",
            rule="boundary.invalid-declaration",
            task=None,
        )
        return

    if cfg is None or not cfg.roots:
        # Implicit-versioned semantics begin at enrollment.
        return

    gitignore_text = ""
    if (root / GITIGNORE).is_file():
        gitignore_text = (root / GITIGNORE).read_text(encoding="utf-8")
    managed_body = extract_managed_block(gitignore_text)

    declared = [r.path for r in cfg.roots]
    allowed = {(a.source, a.pattern) for a in cfg.unmanaged_allow}

    # ---- declared: generated-drift --------------------------------------
    expected = render_managed_block(cfg)
    if managed_body != expected:
        yield Result(
            severity=Severity.ERROR,
            path=GITIGNORE,
            line=None,
            message=(
                "the science-managed boundary block is missing or stale. Run "
                "`science boundary sync` to regenerate it from science.yaml."
            ),
            rule="boundary.generated-drift",
            task=None,
        )

    # ---- declared: allowlist integrity ----------------------------------
    governed = set(governed_ignore_files(root))
    for entry in cfg.unmanaged_allow:
        # Source membership is checked on its own. An earlier draft also required
        # the pattern to be non-default, which exempted
        # {source: "typo/.gitignore", pattern: ".venv/"} -- a silent no-op.
        if entry.source not in governed:
            yield Result(
                severity=Severity.ERROR,
                path=Path("science.yaml"),
                line=None,
                message=(
                    f"boundary.unmanaged_allow names {entry.source!r}, which is not a tracked "
                    f"in-worktree .gitignore file. The entry can never match, so it is a silent "
                    f"no-op rather than an excuse."
                ),
                rule="boundary.invalid-declaration",
                task=None,
            )

    by_location = {(r.source, r.line): r for r in all_unmanaged}

    # ---- declared: declaration-conflict ---------------------------------
    # Ask GIT which rules match each declared root. Text prefix comparison
    # cannot: `*.parquet` affects data/external without naming it, and
    # `data/raw` inside inc/.gitignore scopes to inc/, not the repo root.
    # NOTE the ordering -- the allowlist is deliberately NOT consulted here. It
    # excuses undeclared noise; it may never excuse a rule that targets a
    # declared root, or it would reopen the adjudication this check closes.
    conflicted: set[tuple[str, int]] = set()
    for declared_root in declared:
        subjects = _conflict_subjects(root, declared_root)
        for probe, owners in sorted(matching_unmanaged_rules(root, subjects).items()):
            for owner in owners:
                key = (owner.source, owner.line)
                if key not in by_location or key in conflicted:
                    continue  # already reported
                conflicted.add(key)
                yield Result(
                    severity=Severity.ERROR,
                    path=Path(owner.source),
                    line=owner.line,
                    message=(
                        f"hand-written rule {owner.pattern!r} matches {probe} inside declared "
                        f"root {declared_root!r}. The declaration in science.yaml is the single "
                        f"authority for that root; a rule outside the managed block re-opens "
                        f"per-case adjudication. (Detected by evaluating the unmanaged rules in "
                        f"isolation under git's own engine and peeling away each reported rule, "
                        f"so wildcards and nested .gitignore scoping are accounted for and a rule "
                        f"shadowed by the managed block, or by another hand-written rule, is "
                        f"still reported.)"
                    ),
                    rule="boundary.declaration-conflict",
                    task=None,
                )

    # ---- declared: ignored-undeclared -----------------------------------
    for rule in all_unmanaged:
        if (rule.source, rule.pattern) in allowed or (rule.source, rule.line) in conflicted:
            continue
        yield Result(
            severity=Severity.WARN,
            path=Path(rule.source),
            line=rule.line,
            message=(
                f"rule {rule.pattern!r} ignores project material with no declared storage class. "
                f"Declare a root in science.yaml, or add it to boundary.unmanaged_allow. There is "
                f"no shape heuristic here: a rule is excused because it was declared, never "
                f"because it looks like tooling."
            ),
            rule="boundary.ignored-undeclared",
            task=None,
        )

    # ---- declared: unreachable-tracked ----------------------------------
    visible = visible_paths(root)
    for declared_root in cfg.roots:
        if declared_root.storage_class is not StorageClass.MANIFEST:
            continue
        for candidate in manifest_candidates(root, declared_root):
            if candidate in visible:
                continue
            yield Result(
                severity=Severity.ERROR,
                path=Path(candidate),
                line=None,
                message=(
                    f"{candidate} matches a tracked: glob of manifest root "
                    f"{declared_root.path!r} but git will not surface it -- `git add .` stages "
                    f"nothing and no diagnostic reports a problem. The usual cause is a bare "
                    f"directory exclude stopping git descending. Run `science boundary sync`."
                ),
                rule="boundary.unreachable-tracked",
                task=None,
            )

```

- [ ] **Step 4: Register the module**

In `science/src/science_tool/validate/checks/__init__.py`, append to `CANONICAL_CHECK_MODULES` (after `"autonomous_runs"`):

```python
    "boundary",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_boundary_checks.py -v`
Expected: PASS (all)

- [ ] **Step 6: Verify registration and no regression in the wider suite**

```bash
cd science
uv run --frozen python -c "
from science_tool.validate.checks import CANONICAL_CHECKS
print([e.fn.__name__ for e in CANONICAL_CHECKS if 'boundary' in e.fn.__name__])"
uv run --frozen pytest tests/ -q -x -k "validate or check"
```
Expected: `['check_boundary']`; existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/validate/checks/boundary.py science/src/science_tool/validate/checks/__init__.py science/tests/test_boundary_checks.py
git commit -m "feat(boundary): six mechanical validate checks"
```

---

## Task 6: Probes and transactional sync

**Files:**
- Create: `science/src/science_tool/boundary/probes.py`
- Create: `science/src/science_tool/boundary/sync.py`
- Test: `science/tests/test_boundary_sync.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `probe_paths(cfg: BoundaryConfig) -> list[str]`, `SyncResult(changed: bool, block: str)`, `sync(project_root: Path) -> SyncResult`, `verify_current_tree(project_root: Path) -> list[tuple[str, bool, bool]]`, `BoundaryDirtyError`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_boundary_sync.py
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from science_tool.boundary.config import BoundaryConfig
from science_tool.boundary.probes import probe_paths
from science_tool.boundary.sync import BoundaryDirtyError, sync, verify_current_tree


def _repo(tmp_path: Path, boundary: dict, gitignore: str = "") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "D", "id": "d", "boundary": boundary}))
    (tmp_path / ".gitignore").write_text(gitignore)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)
    return tmp_path


DECL = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}


def test_probes_cover_depth_and_each_glob():
    cfg = BoundaryConfig.model_validate(DECL)
    probes = probe_paths(cfg)
    assert any(p.count("/") == 2 for p in probes)
    assert any(p.count("/") >= 4 for p in probes)
    assert any(p.endswith("datapackage.json") for p in probes)
    assert any(p.endswith(".parquet") for p in probes)


def test_sync_installs_block_and_is_idempotent(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    first = sync(repo)
    assert first.changed
    text = (repo / ".gitignore").read_text()
    second = sync(repo)
    assert not second.changed
    assert (repo / ".gitignore").read_text() == text


def test_verify_refuses_dirty_gitignore(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / ".gitignore").write_text("dirty\n")
    with pytest.raises(BoundaryDirtyError):
        verify_current_tree(repo)


def test_verify_restores_original_on_change(tmp_path: Path):
    repo = _repo(tmp_path, DECL, gitignore="/data/external/\n")
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.json").write_text("{}")
    before = (repo / ".gitignore").read_text()
    diff = verify_current_tree(repo)
    assert diff, "descriptor decision must change"
    assert (repo / ".gitignore").read_text() == before


def test_verify_restores_original_when_clean(tmp_path: Path):
    repo = _repo(tmp_path, DECL, gitignore="")
    before = (repo / ".gitignore").read_text()
    verify_current_tree(repo)
    assert (repo / ".gitignore").read_text() == before


def test_verify_detects_a_flip_on_an_already_tracked_file(tmp_path: Path):
    """The reachability oracle CANNOT see this: an indexed file stays visible
    before and after, so the decision change would be reported as no change."""
    repo = _repo(tmp_path, DECL, gitignore="")
    (repo / "data/external/ot").mkdir(parents=True)
    target = repo / "data/external/ot/mm.parquet"
    target.write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "-f", str(target)], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "add"], check=True)
    changed = {p for p, _was, _now in verify_current_tree(repo)}
    assert "data/external/ot/mm.parquet" in changed


def test_verify_restores_absence_when_gitignore_did_not_exist(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / ".gitignore").unlink()
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "--cached", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "drop"], check=True)
    verify_current_tree(repo)
    assert not (repo / ".gitignore").exists(), "must restore absence, not write an empty file"


def test_verify_restores_on_exception(tmp_path: Path, monkeypatch):
    repo = _repo(tmp_path, DECL)
    before = (repo / ".gitignore").read_text()
    import science_tool.boundary.sync as sync_mod

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(sync_mod, "_probe_decisions", boom)
    with pytest.raises(RuntimeError):
        verify_current_tree(repo)
    assert (repo / ".gitignore").read_text() == before
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_boundary_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: ... boundary.probes`

- [ ] **Step 3: Implement probes**

```python
# science/src/science_tool/boundary/probes.py
"""Synthetic probe paths for a declaration.

`--verify-current-tree` can only speak for paths that exist. Probes cover the
shapes that do not exist yet -- a new dataset version, a deeper nesting level.
`git check-ignore --no-index` evaluates hypothetical paths, so probes need no
files on disk.
"""

from __future__ import annotations

from science_tool.boundary.config import BoundaryConfig, StorageClass

_DEEP = "p1/p2/p3"


def probe_paths(cfg: BoundaryConfig) -> list[str]:
    probes: list[str] = []
    for root in sorted(cfg.roots, key=lambda r: r.path):
        probes.append(f"{root.path}/probe.bin")
        probes.append(f"{root.path}/{_DEEP}/probe.bin")
        probes.append(f"{root.path}/probe.parquet")
        probes.append(f"{root.path}/.hidden")
        if root.storage_class is StorageClass.MANIFEST:
            for glob in sorted(root.tracked):
                name = glob.replace("*", "probe")
                probes.append(f"{root.path}/d1/{name}")
                probes.append(f"{root.path}/{_DEEP}/{name}")
    return sorted(set(probes))
```

- [ ] **Step 4: Implement sync**

```python
# science/src/science_tool/boundary/sync.py
"""Install the managed block, detect drift, and verify a migration.

`verify_current_tree` is a VERIFICATION mode: it must never leave a candidate
block installed merely because it found a change. It refuses a dirty
`.gitignore`, and restores the original on every path -- success, failure, and
exception.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from science_tool.boundary.config import BoundaryConfig, BoundaryConfigError
from science_tool.boundary.generate import extract_managed_block, render_managed_block, splice_managed_block
from science_tool.boundary.gitio import BoundaryGitError
from science_tool.boundary.probes import probe_paths
from science_tool.boundary.walk import iter_repo_files
from science_tool.project_config import load_project_config

GITIGNORE = ".gitignore"


class BoundaryDirtyError(Exception):
    """Raised when `.gitignore` has uncommitted changes and must not be touched."""


@dataclass(frozen=True)
class SyncResult:
    changed: bool
    block: str


def _config(project_root: Path) -> BoundaryConfig:
    cfg = load_project_config(project_root).boundary
    if cfg is None or not cfg.roots:
        raise BoundaryConfigError("science.yaml declares no boundary.roots")
    return cfg


def _read(project_root: Path) -> str:
    path = project_root / GITIGNORE
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def sync(project_root: Path) -> SyncResult:
    cfg = _config(project_root)
    block = render_managed_block(cfg)
    original = _read(project_root)
    updated = splice_managed_block(original, block)
    if updated == original:
        return SyncResult(changed=False, block=block)
    (project_root / GITIGNORE).write_text(updated, encoding="utf-8")
    return SyncResult(changed=True, block=block)


def has_drift(project_root: Path) -> bool:
    cfg = _config(project_root)
    return extract_managed_block(_read(project_root)) != render_managed_block(cfg)


def _probe_decisions(project_root: Path, probes: list[str]) -> dict[str, bool]:
    if not probes:
        return {}
    # `surrogateescape`, matching the decode on the way back out. A legal git
    # filename need not be valid UTF-8; `iter_repo_files` surfaces those bytes as
    # surrogates, and a plain `.encode()` raises UnicodeEncodeError on them --
    # crashing verification on a tree git itself handles fine.
    payload = "\0".join(probes).encode("utf-8", "surrogateescape") + b"\0"
    proc = subprocess.run(
        ["git", "-C", str(project_root), "check-ignore", "--no-index", "--stdin", "-z"],
        input=payload,
        capture_output=True,
        check=False,
    )
    if proc.returncode not in (0, 1):  # 1 == "nothing matched", the clean case
        raise BoundaryGitError(f"check-ignore failed ({proc.returncode}): {proc.stderr.decode('utf-8', 'replace')}")
    ignored = {c.decode("utf-8", "surrogateescape") for c in proc.stdout.split(b"\0") if c}
    return {p: (p in ignored) for p in probes}


def _assert_clean(project_root: Path) -> None:
    # Fail closed like every other git helper. Treating a nonzero status as
    # "clean" would let verification proceed to rewrite a .gitignore whose state
    # it could not read -- the one situation where the restore matters most.
    proc = subprocess.run(
        ["git", "-C", str(project_root), "status", "--porcelain", "-z", "--", GITIGNORE],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise BoundaryGitError(f"git status failed ({proc.returncode}) before verification: {detail}")
    if proc.stdout.strip():
        raise BoundaryDirtyError(
            f"{GITIGNORE} has uncommitted changes; commit or stash before verifying so a "
            f"failed verification cannot discard them"
        )


def _enumerate_tree(project_root: Path) -> list[str]:
    """Every file on disk except `.git`, regardless of ignore state.

    `visible_paths` is WRONG here: an indexed file stays in it whatever the rules
    say, so a new rule that flips a tracked file's ignore decision would compare
    equal before and after and the verification would report "no change".

    Routed through the shared primitive so nested-repository pruning is not
    reimplemented per caller.
    """
    return iter_repo_files(project_root)


def verify_current_tree(project_root: Path) -> list[tuple[str, bool, bool]]:
    """Return (path, was_ignored, now_ignored) for every decision that changed.

    Compares IGNORE DECISIONS via `check-ignore --no-index` over a raw
    filesystem enumeration, plus probes for paths that do not exist yet.
    Always restores the original `.gitignore`, including restoring its ABSENCE.
    """
    _assert_clean(project_root)
    cfg = _config(project_root)
    gitignore = project_root / GITIGNORE
    existed = gitignore.is_file()
    original = _read(project_root)

    subjects = _enumerate_tree(project_root) + probe_paths(cfg)
    before = _probe_decisions(project_root, subjects)
    try:
        gitignore.write_text(splice_managed_block(original, render_managed_block(cfg)), encoding="utf-8")
        after = _probe_decisions(project_root, subjects)
    finally:
        if existed:
            gitignore.write_text(original, encoding="utf-8")
        else:
            # Restoring absence, not an empty file: writing "" would leave a
            # `.gitignore` the project never had.
            gitignore.unlink(missing_ok=True)

    return [
        (path, before.get(path, False), after.get(path, False))
        for path in subjects
        if before.get(path, False) != after.get(path, False)
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_boundary_sync.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/boundary/probes.py science/src/science_tool/boundary/sync.py science/tests/test_boundary_sync.py
git commit -m "feat(boundary): probes and transactional sync verification"
```

---

## Task 7: `science boundary` CLI

**Files:**
- Create: `science/src/science_tool/boundary/cli.py`
- Create: `science/src/science_tool/boundary/init.py`
- Modify: `science/src/science_tool/cli.py:18` (import) and `:~200` (register)
- Test: `science/tests/test_boundary_cli.py`

**Interfaces:**
- Consumes: Tasks 1–6, plus `science_tool.data_policy.classify` and `science_tool.project_config.resolve_data_policy`.
- Produces: `boundary_group` (click group with `check`, `sync`, `init`), `propose_declaration(project_root: Path) -> dict`.

`boundary check` runs **only the two universal checks**, so it needs no config load and stays fast enough for a pre-commit hook.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_boundary_cli.py
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.boundary.cli import boundary_group


def _repo(tmp_path: Path, boundary: dict | None = None) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    payload: dict = {"name": "D", "id": "d"}
    if boundary:
        payload["boundary"] = boundary
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(payload))
    return tmp_path


DECL = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}


def test_check_exits_zero_on_clean_repo(tmp_path: Path):
    repo = _repo(tmp_path)
    result = CliRunner().invoke(boundary_group, ["check", "--project-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "clean" in result.output


def test_check_exits_one_and_names_the_rule(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data/x.csv").write_text("a")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "data/x.csv"], check=True)
    (repo / ".gitignore").write_text("/data/\n")
    result = CliRunner().invoke(boundary_group, ["check", "--project-root", str(repo)])
    assert result.exit_code == 1
    assert "data/x.csv" in result.output
    assert ".gitignore:1" in result.output


def test_sync_writes_the_block(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    result = CliRunner().invoke(boundary_group, ["sync", "--project-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "/data/external/**" in (repo / ".gitignore").read_text()


def test_sync_check_flag_reports_drift_without_writing(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / ".gitignore").write_text("")
    result = CliRunner().invoke(boundary_group, ["sync", "--check", "--project-root", str(repo)])
    assert result.exit_code == 1
    assert (repo / ".gitignore").read_text() == ""


def test_init_discovers_an_already_ignored_payload_root(tmp_path: Path):
    """The whole point of an adoption aid: find roots that are ALREADY ignored."""
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("data/raw/*\n")
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/big.parquet").write_text("x" * 200_000)
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.json").write_text("{}")
    result = CliRunner().invoke(boundary_group, ["init", "--project-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "data/raw" in result.output
    assert "data/external" in result.output
    assert "boundary:" not in (repo / "science.yaml").read_text()


def test_init_proposes_only_the_descriptor_names_it_saw(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.yaml").write_text("{}")
    output = CliRunner().invoke(boundary_group, ["init", "--project-root", str(repo)]).output
    assert "datapackage.yaml" in output
    assert "datapackage.json" not in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_boundary_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: ... boundary.cli`

- [ ] **Step 3: Implement the proposal engine**

```python
# science/src/science_tool/boundary/init.py
"""Propose a boundary declaration from an existing tree.

The ONLY place a heuristic touches the boundary. `classify()` is good at
suggesting and bad at enforcing, so its output here is a proposal a human reads
and edits -- never something written without review.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from science_tool.boundary.walk import iter_repo_files
from science_tool.data_policy import FileClass, classify
from science_tool.project_config import load_project_config, resolve_data_policy

_RECORD_NAMES = ("datapackage.json", "datapackage.yaml")
_CANDIDATE_TOPS = frozenset({"data", "pdfs", "results"})


def _walk_candidates(project_root: Path) -> list[Path]:
    """Every file under the candidate top-level directories, INCLUDING ignored ones.

    Deliberately NOT `visible_paths`: an adoption aid whose whole job is to
    discover already-ignored payload roots cannot use an oracle that excludes
    ignored files. A tree with a pre-existing `data/raw/*` rule would otherwise
    yield nothing to propose.
    """
    found: list[Path] = []
    for top in sorted(_CANDIDATE_TOPS):
        found.extend(Path(rel) for rel in iter_repo_files(project_root, project_root / top))
    return sorted(found)


def propose_declaration(project_root: Path) -> dict:
    """Return a `boundary:` mapping proposal. Never writes."""
    # NOTE: resolve_data_policy takes a ProjectConfig, not a path
    # (project_config.py:453). Deliberately NOT wrapped in a try/except: a
    # science.yaml that will not validate is a real error, and silently
    # substituting the default policy would make the proposal a guess derived
    # from a config the operator believes is in effect.
    policy = resolve_data_policy(load_project_config(project_root))

    payload_dirs: Counter[str] = Counter()
    manifest_dirs: Counter[str] = Counter()
    # Propose the descriptor names ACTUALLY FOUND, per root -- proposing
    # `datapackage.json` when discovery only ever saw `datapackage.yaml` would
    # emit a declaration that matches nothing.
    observed: dict[str, set[str]] = {}

    for path in _walk_candidates(project_root):
        try:
            size = (project_root / path).stat().st_size
        except OSError:
            # NOT the fail-open pattern removed elsewhere. This is a file that
            # vanished between the walk and the stat; skipping one candidate
            # weakens a suggestion, whereas swallowing an unreadable RULE SOURCE
            # would silently drop governance. Rule sources raise; races skip.
            continue
        top = "/".join(path.parts[:2]) if len(path.parts) > 2 else path.parts[0]
        if path.name in _RECORD_NAMES:
            manifest_dirs[top] += 1
            observed.setdefault(top, set()).add(path.name)
        elif classify(path, size, policy) is FileClass.PAYLOAD:
            payload_dirs[top] += 1

    roots: list[dict] = []
    for name in sorted(manifest_dirs):
        roots.append({"path": name, "class": "manifest", "tracked": sorted(observed[name])})
    for name in sorted(payload_dirs):
        if name in manifest_dirs:
            continue
        roots.append({"path": name, "class": "payload"})
    return {"roots": roots}
```

- [ ] **Step 4: Implement the CLI**

```python
# science/src/science_tool/boundary/cli.py
"""`science boundary` -- declare, generate, and check the VCS storage boundary."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import yaml

from science_tool.boundary.config import BoundaryConfigError
from science_tool.boundary.gitio import tracked_ignored, unmanaged_rules
from science_tool.boundary.init import propose_declaration
from science_tool.boundary.sync import BoundaryDirtyError, has_drift, sync, verify_current_tree

_ROOT_OPTION = click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)


@click.group("boundary")
def boundary_group() -> None:
    """Declared version-control storage boundary."""


@boundary_group.command("check")
@_ROOT_OPTION
def check_command(project_root: Path) -> None:
    """Run the two universal checks. No config load; fast enough for pre-commit."""
    from science_tool.validate.checks.boundary import _is_unanchored_dir_pattern

    hits = tracked_ignored(project_root)
    warnings = [r for r in unmanaged_rules(project_root) if _is_unanchored_dir_pattern(r.pattern)]
    for rule in warnings:
        click.echo(f"warn  {rule.source}:{rule.line}: unanchored pattern {rule.pattern!r}", err=True)
    if not hits:
        click.echo("vcs-boundary: clean (no tracked file matches an ignore rule)")
        return
    click.echo(f"vcs-boundary: FAIL -- {len(hits)} tracked file(s) match an ignore rule:", err=True)
    for hit in hits[:50]:
        click.echo(f"  {hit.path}  ({hit.source}:{hit.line}: {hit.pattern})", err=True)
    if len(hits) > 50:
        click.echo(f"  ... and {len(hits) - 50} more", err=True)
    sys.exit(1)


@boundary_group.command("sync")
@_ROOT_OPTION
@click.option("--check", "check_only", is_flag=True, help="Report drift; write nothing.")
@click.option("--verify-current-tree", "verify", is_flag=True, help="Diff ignore decisions; restore the original.")
def sync_command(project_root: Path, check_only: bool, verify: bool) -> None:
    """Regenerate the managed .gitignore block from science.yaml."""
    try:
        if check_only:
            if has_drift(project_root):
                click.echo("boundary: managed block is stale; run `science boundary sync`", err=True)
                sys.exit(1)
            click.echo("boundary: managed block is current")
            return
        if verify:
            changes = verify_current_tree(project_root)
            if changes:
                click.echo(f"boundary: {len(changes)} ignore decision(s) would change:", err=True)
                for path, was_ignored, now_ignored in changes:
                    click.echo(f"  {path}: ignored={was_ignored} -> {now_ignored}", err=True)
                sys.exit(1)
            click.echo("boundary: no ignore decision changes")
            return
        result = sync(project_root)
        click.echo("boundary: managed block updated" if result.changed else "boundary: already current")
    except BoundaryDirtyError as exc:
        click.echo(f"boundary: {exc}", err=True)
        sys.exit(2)
    except BoundaryConfigError as exc:
        click.echo(f"boundary: {exc}", err=True)
        sys.exit(2)


@boundary_group.command("init")
@_ROOT_OPTION
def init_command(project_root: Path) -> None:
    """Propose a boundary declaration for review. Writes nothing."""
    proposal = propose_declaration(project_root)
    if not proposal["roots"]:
        click.echo("boundary: no candidate roots found; declare them by hand in science.yaml")
        return
    click.echo("# Proposed for science.yaml -- REVIEW before pasting:")
    click.echo(yaml.safe_dump({"boundary": proposal}, sort_keys=False).rstrip())
    click.echo("\n# Then: science boundary sync --verify-current-tree")
```

- [ ] **Step 5: Register the group**

In `science/src/science_tool/cli.py`, add near line 18:

```python
from science_tool.boundary.cli import boundary_group
```

and near line 200, beside the other `add_command` calls:

```python
main.add_command(boundary_group)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_boundary_cli.py -v`
Expected: PASS (all)

- [ ] **Step 7: Verify the command is reachable**

```bash
cd science && uv run --frozen science boundary --help
```
Expected: lists `check`, `init`, `sync`.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/boundary/cli.py science/src/science_tool/boundary/init.py science/src/science_tool/cli.py science/tests/test_boundary_cli.py
git commit -m "feat(boundary): science boundary check/sync/init commands"
```

---

## Task 8: Re-scope `data audit`

MM30's audit reports 51,073 violations, ~45,000 of them correctly-ignored `.venv` / `node_modules` / `.snakemake` / `.opencode`. Blanket-pruning ignored paths would be wrong — a `stranded_record` inside an ignored payload root is exactly what the audit exists to find.

**New predicate:** skip a path if it is ignored **and** outside every declared root. Always inspect paths inside a declared root.

**Files:**
- Modify: `science/src/science_tool/data_audit.py:164-183` (`audit_project`)
- Test: `science/tests/test_data_audit_scope.py`

**Interfaces:**
- Consumes: `visible_paths` (Task 3), `load_project_config(...).boundary` (Task 1).
- Produces: unchanged public signature `audit_project(project_root, policy, data_dirs) -> list[Violation]`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_data_audit_scope.py
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from science_tool.data_audit import audit_project


def _repo(tmp_path: Path, boundary: dict | None = None, gitignore: str = "") -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    payload: dict = {"name": "D", "id": "d"}
    if boundary:
        payload["boundary"] = boundary
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(payload))
    (tmp_path / ".gitignore").write_text(gitignore)
    return tmp_path


def test_ignored_tooling_noise_is_skipped(tmp_path: Path):
    repo = _repo(tmp_path, gitignore=".venv/\n")
    (repo / ".venv/lib").mkdir(parents=True)
    (repo / ".venv/lib/blob.parquet").write_text("x" * 200_000)
    assert all(".venv" not in v.path for v in audit_project(repo))


def test_stranded_record_inside_declared_root_is_still_found(tmp_path: Path):
    decl = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    repo = _repo(tmp_path, decl, gitignore="/data/external/**\n!/data/external/**/\n")
    (repo / "data/external/ds").mkdir(parents=True)
    (repo / "data/external/ds/RESULTS.md").write_text("# r\n")
    paths = [v.path for v in audit_project(repo)]
    assert "data/external/ds/RESULTS.md" in paths


def test_undeclared_project_audits_visible_files_only(tmp_path: Path):
    repo = _repo(tmp_path, gitignore="build/\n")
    (repo / "build").mkdir()
    (repo / "build/x.parquet").write_text("x" * 200_000)
    (repo / "keep.parquet").write_text("x" * 200_000)
    paths = [v.path for v in audit_project(repo)]
    assert "keep.parquet" in paths
    assert "build/x.parquet" not in paths
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_data_audit_scope.py -v`
Expected: FAIL — `.venv` paths present / stranded record missing

- [ ] **Step 3: Implement the re-scope**

In `science/src/science_tool/data_audit.py`, add imports at the top:

```python
from science_tool.boundary.gitio import visible_paths
```

and replace the body of `audit_project` (currently lines 164–183) with:

```python
def audit_project(
    project_root: Path,
    policy: DataPolicy = DEFAULT_DATA_POLICY,
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> list[Violation]:
    """Advisory discovery pass. Blocks nothing; enforcement is the boundary checks.

    SCOPE: skip a path that is ignored AND outside every declared boundary root.
    Ignored tooling noise (.venv, node_modules) is not the audit's business, but
    a stranded record inside an ignored payload root is exactly what it exists to
    find -- so blanket-pruning ignored paths would be wrong.
    """
    tracked = git_tracked_set(project_root)
    # Deliberately NOT wrapped: treating an invalid declaration as absent would
    # drop every declared root out of scope and hide the stranded records inside
    # them -- failing open exactly where the config is broken.
    boundary = load_project_config(project_root).boundary
    declared = tuple(r.path for r in boundary.roots) if boundary else ()
    visible = visible_paths(project_root)

    violations: list[Violation] = []
    for abs_path, rel in _iter_project_files(project_root, data_dirs):
        posix = rel.as_posix()
        in_declared_root = any(posix == d or posix.startswith(d + "/") for d in declared)
        if posix not in visible and not in_declared_root:
            continue
        try:
            size = abs_path.stat().st_size
        except OSError:
            continue  # vanished mid-walk; see the note in the discovery walk
        cls = classify(rel, size, policy)
        loc = location(rel, data_dirs)
        is_tracked = posix in tracked
        v = _violation_for(project_root, rel, cls, loc, is_tracked, data_dirs)
        if v is not None:
            violations.append(v)
    violations.sort(key=lambda v: v.path)
    return violations
```

Add the config import beside the existing ones if not already present:

```python
from science_tool.project_config import load_project_config
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_data_audit_scope.py -v`
Expected: PASS (all)

- [ ] **Step 5: Confirm no regression in existing audit tests**

```bash
cd science && uv run --frozen pytest tests/ -q -k "data_audit or data_cli"
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/data_audit.py science/tests/test_data_audit_scope.py
git commit -m "fix(data-audit): scope the walk to visible paths plus declared roots"
```

---

## Task 9: Retire the ignore-then-pin convention

Without this the declaration is a fourth opinion rather than the authority: `create-project.md` currently prescribes the `dir/*` + negation idiom, and conventions-audit §7.5 recommends blessing it.

**Files:**
- Modify: `commands/create-project.md:199-290`
- Modify: `docs/conventions/data-boundary.md`
- Modify: `docs/audits/downstream-project-conventions/synthesis.md` (§7.5)
- Test: `science/tests/test_command_docs.py`, `science/tests/test_user_guide_docs.py` (existing guard suites)

- [ ] **Step 1: Rewrite the `create-project.md` `.gitignore` section**

Replace the `### .gitignore` section body (from "Include at minimum:" through the `models/` guidance ending "never emit a bare `models/` exclude.") with:

````markdown
Include at minimum the tooling, OS, and secret noise that is not project data:

```gitignore
# Secrets
.env

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
.mypy_cache/

# Notebooks
.ipynb_checkpoints/

# Worktrees
.worktrees/

# Managed artifact rollback backups
*.pre-update*.bak

# Transient agent outputs
doc/meta/next-steps-*.md
docs/meta/next-steps-*.md
doc/plans/*-plan-review.md
docs/plans/*-plan-review.md

# OS
.DS_Store
```

**Do not hand-write ignore rules for project data.** Declare a storage class in
`science.yaml` and let `science boundary sync` generate them:

```yaml
boundary:
  roots:
    - path: data/raw
      class: payload
    - path: data/external
      class: manifest
      tracked: [datapackage.json]
```

`versioned` is the implicit default, so only exceptions are declared. `payload`
means nothing under the path is tracked; `manifest` means the declared
descriptor globs are tracked and everything else is not.

Generated patterns are anchored, so an unanchored `archive` cannot match a
directory of that name at any depth. A `manifest` root emits the
descend-preserving `dir/**` + `!dir/**/` form, so its negations actually apply —
hand-writing a bare `dir/` exclude is the classic trap, because git does not
descend into a fully-excluded directory and a `git add` then appears to succeed
while committing nothing.

Prefer separating payload from records by directory rather than mixing them: put
regenerable dumps in their own root and keep the source directory fully tracked.
Where a descriptor genuinely belongs beside its payload, `manifest` expresses
that once, uniformly, instead of per-dataset negations.

Keep version-controlled provenance outside the configured data root. Prefer
`provenance/` or `research/packages/` for lightweight manifests, QA reports, and
small summary frames. Do not use `data/provenance/` when the project uses the
default `./data` data root, because that puts committed provenance inside the
non-version-controlled root.

When a project configures an out-of-tree data root, document the same resolution
order in local onboarding notes: `SCIENCE_DATA_ROOT`, then `science.yaml`
`data.root`, then global `data.root` plus the project id, then `./data`. Keep
logical references stable: `data/raw` maps to `<resolved-root>/raw`,
`data/processed` maps to `<resolved-root>/processed`, and `data/external` maps
to `<resolved-root>/external`.
````

- [ ] **Step 2: Rewrite the `data-boundary.md` Policy and Audit sections**

Replace the *Policy* section with a pointer to the declaration, and replace the
closing "Deferred follow-ups" paragraph with:

```markdown
## Enforcement

The boundary is declared in `science.yaml` under `boundary:` and generated into
a managed block in `.gitignore` by `science boundary sync`. Six validate checks
enforce it — `boundary.tracked-ignored` and `boundary.unanchored-pattern` on
every project, and `boundary.generated-drift`,
`boundary.declaration-conflict`, `boundary.unreachable-tracked`,
`boundary.ignored-undeclared` once a project declares roots. See
`docs/plans/2026-07-26-vcs-storage-boundary-design.md`.

`science data audit` is advisory discovery, not enforcement. It classifies files
heuristically to surface candidates; it blocks nothing and no validate check
consults its classifier.
```

- [ ] **Step 3: Annotate conventions-audit §7.5 as superseded**

In `docs/audits/downstream-project-conventions/synthesis.md`, insert immediately after the §7.5 heading:

```markdown
> **Superseded (2026-07-26).** This recommendation — bless ignore-then-pin as
> the canonical pattern — was reversed. The pattern requires per-case
> adjudication and `git add -f`, and its whole-directory form silently disables
> its own negations. Replaced by the declared storage boundary in
> `docs/plans/2026-07-26-vcs-storage-boundary-design.md`.
```

- [ ] **Step 4: Replace the known guard assertions**

This is not hypothetical: `science/tests/test_command_docs.py:1448`
(`test_create_project_docs_keep_data_payload_dirs_gitignored`) asserts the
retired text directly. Replace its body with:

```python
def test_create_project_docs_declare_data_payload_boundary() -> None:
    text = _read("commands/create-project.md")

    # The declaration replaces the hand-written ignore-then-pin idiom.
    assert "boundary:" in text
    assert "class: payload" in text
    assert "class: manifest" in text
    assert "science boundary sync" in text
    assert "tracked: [datapackage.json]" in text

    # Retired: per-case negation adjudication.
    assert "data/raw/*" not in text
    assert "!data/raw/.gitkeep" not in text
    assert "never emit a bare" not in text

    # Retained: data-root resolution guidance, which is orthogonal.
    assert "provenance/" in text
    assert "data/provenance/" in text
    assert "SCIENCE_DATA_ROOT" in text
    assert "science.yaml" in text
    assert "data.root" in text
    assert "`data/raw` maps to" in text
```

- [ ] **Step 5: Run the doc guard suites**

```bash
cd science && uv run --frozen pytest tests/test_command_docs.py tests/test_user_guide_docs.py -v
```
Expected: PASS. If any other guard asserts on removed text, update its anchor in this same commit.

- [ ] **Step 6: Confirm the retired idiom is gone**

```bash
cd ~/d/science/.worktrees/vcs-boundary
grep -rn 'never emit a bare' commands/ docs/ || echo "retired idiom removed"
grep -rn 'papers/pdfs' commands/ || echo "hardcoded papers/pdfs removed"
```
Expected: both print the confirmation line.

- [ ] **Step 7: Commit**

```bash
git add commands/create-project.md docs/conventions/data-boundary.md docs/audits/downstream-project-conventions/synthesis.md science/tests/
git commit -m "docs(boundary): retire the ignore-then-pin convention"
```

---

## Task 10: MM30-derived fixture as the acceptance case

MM30's real declaration is a downstream follow-up. What lands here is a sanitized fixture exercising all three classes end to end.

**Files:**
- Create: `science/tests/fixtures/boundary_mm30/README.md`
- Create: `science/tests/test_boundary_acceptance.py`

**Interfaces:**
- Consumes: everything.
- Produces: nothing importable.

- [ ] **Step 1: Write the acceptance test**

```python
# science/tests/test_boundary_acceptance.py
"""End-to-end acceptance on a sanitized MM30-shaped tree.

Shape derived from MM30 as of 2026-07-26: an external-dataset root whose
descriptors are tracked beside ignored bulk parquet and an ignored raw/ subtree,
a flat gitignored PDF store, and tracked source that an unanchored pattern had
been hiding. No MM30 content, only its layout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.boundary.cli import boundary_group
from science_tool.validate.checks.boundary import check_boundary
from science_tool.validate.context import ValidateContext

DECL = {
    "roots": [
        {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json", "*.qa_verdict.json"]},
        {"path": "data/raw", "class": "payload"},
        {"path": "pdfs", "class": "payload"},
    ]
}


def _mm30(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "MM", "id": "mm", "boundary": DECL}))

    def w(rel: str, body: str = "x") -> None:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    w("data/external/opentargets/25.03/datapackage.json", "{}")
    w("data/external/opentargets/25.03/opentargets.qa_verdict.json", "{}")
    w("data/external/opentargets/25.03/mm-associations.parquet")
    w("data/external/opentargets/25.03/raw/target/part-0.parquet")
    w("data/raw/GSE1234_series_matrix.txt")
    w("pdfs/2024_Author_Title.pdf")
    w("tests/migration/archive/test_pilot.py", "def test_x(): pass\n")
    w("entities/hypotheses/h0001.md", "# h\n")
    w(".gitignore", ".venv/\narchive\n")
    return tmp_path


def _rules(root: Path) -> list[str]:
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return [r.rule for r in check_boundary(ctx)]


def test_acceptance_sync_then_clean(tmp_path: Path):
    repo = _mm30(tmp_path)
    runner = CliRunner()

    assert runner.invoke(boundary_group, ["sync", "--project-root", str(repo)]).exit_code == 0
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    staged = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True).stdout.split()

    # Descriptors tracked; payload not.
    assert "data/external/opentargets/25.03/datapackage.json" in staged
    assert "data/external/opentargets/25.03/opentargets.qa_verdict.json" in staged
    assert "data/external/opentargets/25.03/mm-associations.parquet" not in staged
    assert "data/external/opentargets/25.03/raw/target/part-0.parquet" not in staged
    assert "data/raw/GSE1234_series_matrix.txt" not in staged
    assert "pdfs/2024_Author_Title.pdf" not in staged

    # The unanchored bare `archive` rule STILL hides this file: `sync` manages
    # declared roots and deliberately does not rewrite unmanaged rules. Verified
    # against real git -- an earlier draft asserted the opposite.
    assert "tests/migration/archive/test_pilot.py" not in staged

    rules = _rules(repo)
    assert "boundary.tracked-ignored" not in rules  # ignored AND untracked, so no contradiction
    assert "boundary.generated-drift" not in rules
    assert "boundary.unreachable-tracked" not in rules
    assert "boundary.unanchored-pattern" in rules  # the bare `archive` is reported


def test_acceptance_anchoring_the_warned_rule_is_the_remedy(tmp_path: Path):
    """Following the WARN's advice makes the hidden source reachable again.

    This is the check earning its keep: nothing else in the toolchain reports
    that a tracked-looking test file is invisible to git, ripgrep, and ruff.
    """
    repo = _mm30(tmp_path)
    CliRunner().invoke(boundary_group, ["sync", "--project-root", str(repo)])
    text = (repo / ".gitignore").read_text().replace("archive\n", "/archive/\n", 1)
    (repo / ".gitignore").write_text(text)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    staged = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True).stdout.split()
    assert "tests/migration/archive/test_pilot.py" in staged
    assert "boundary.unanchored-pattern" not in _rules(repo)


def test_acceptance_verify_current_tree_is_transactional(tmp_path: Path):
    repo = _mm30(tmp_path)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    before = (repo / ".gitignore").read_text()
    result = CliRunner().invoke(boundary_group, ["sync", "--verify-current-tree", "--project-root", str(repo)])
    assert result.exit_code in (0, 1)
    assert (repo / ".gitignore").read_text() == before


def test_acceptance_init_proposes_the_same_shape(tmp_path: Path):
    repo = _mm30(tmp_path)
    (repo / "science.yaml").write_text(yaml.safe_dump({"name": "MM", "id": "mm"}))
    output = CliRunner().invoke(boundary_group, ["init", "--project-root", str(repo)]).output
    assert "data/external" in output
    assert "manifest" in output
```

- [ ] **Step 2: Write the fixture README**

```markdown
<!-- science/tests/fixtures/boundary_mm30/README.md -->
# MM30-shaped boundary fixture

Layout derived from MM30 as of 2026-07-26, with no MM30 content. It reproduces
the three shapes that motivated the design:

- `data/external/<ds>/<ver>/` — tracked `datapackage.json` and QA verdict beside
  ignored bulk parquet and an ignored `raw/` subtree (`manifest`)
- `data/raw/`, `pdfs/` — wholly ignored (`payload`)
- `tests/migration/archive/` — tracked source that an unanchored bare `archive`
  pattern had been hiding from git, ripgrep, and ruff alike

MM30's real declaration is a downstream follow-up; this fixture is the in-branch
acceptance case. The tests live in `science/tests/test_boundary_acceptance.py`.
```

- [ ] **Step 3: Run the acceptance suite**

Run: `cd science && uv run --frozen pytest tests/test_boundary_acceptance.py -v`
Expected: PASS (all four)

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_boundary_acceptance.py science/tests/fixtures/boundary_mm30/
git commit -m "test(boundary): MM30-shaped end-to-end acceptance case"
```

---

## Task 11: Full-suite verification

- [ ] **Step 1: Run the whole suite**

```bash
cd science && uv run --frozen pytest tests/ -q
```
Expected: no failures introduced by this branch. Compare any failure against `main` before assuming this branch caused it.

Do **not** pipe this into `tail`: the shell here is zsh, which does not set `pipefail` by default, so `pytest ... | tail` exits with `tail`'s status and a red suite reports success. If you need the output trimmed, run `set -o pipefail` first.

- [ ] **Step 2: Lint and format**

```bash
cd science && uv run --frozen ruff check . && uv run --frozen ruff format --check .
```
Expected: clean.

- [ ] **Step 3: Self-check the tool against its own repository**

```bash
cd ~/d/science/.worktrees/vcs-boundary && uv run --frozen --project science science boundary check --project-root .
```
Expected: exits 0, or reports genuine violations in the science repo itself. If it reports any, resolve them per the message — that is the tool working.

- [ ] **Step 4: Commit any residue**

```bash
git add -A && git commit -m "chore(boundary): full-suite verification" || echo "nothing to commit"
```

---

## Self-Review Notes

**Spec coverage.** Declaration model → Task 1. Generation contract and both invariants → Task 2. Source universe → Task 3. Manifest walk plus symlink/nested-repo/NUL/pruning semantics and the benchmark → Tasks 3–4. Six checks → Task 5. Probes and transactional verification → Task 6. Three commands, `classify()` demoted to proposal → Task 7. `data_audit` re-scope → Task 8. Convention retirement → Task 9. MM30 fixture → Task 10.

**Deliberately deferred.** `science health` gets no change: `collect_validation_findings` already surfaces every non-info result, so registering in `CANONICAL_CHECKS` (Task 5) is sufficient and a separate section would double-count. `boundary.declaration-missing` is not implemented — undeclared projects stay silent in v1 by design.

**Naming consistency.** `storage_class` (Python) ↔ `class` (YAML alias) throughout; `visible_paths` is the single oracle used by Tasks 5, 6, and 8; `manifest_candidates` is used only by Task 5; `_is_unanchored_dir_pattern` is defined in Task 5 and imported by Task 7's CLI.

**No heuristic survives in enforcement.** An earlier draft carried `_is_tooling_shaped` to keep `ignored-undeclared` quiet on `.venv/`-style rules. It was deleted: the default `unmanaged_allow` already silences those by exact match *before* the heuristic could run, so its only remaining effect was to broaden silence to undeclared patterns like `.private-data/` and `*.pdf` — precisely the material the check exists to surface. `DEFAULT_UNMANAGED_ALLOW` is now kept byte-identical to the scaffolded `.gitignore` in `create-project.md`, which is what keeps a fresh project quiet without any shape guessing.

**Conflict detection is match-based, not winner-based.** `check-ignore` reports only the last matching pattern, and two separate things shadow the rule that must be seen. The managed block is spliced *after* the hand-written region, so a managed rule always wins — defeated by **isolation** (a scratch repository holding only the governed `.gitignore` files, managed lines blanked to preserve line numbers, global excludes disabled). Among unmanaged rules the last match still wins, and a `!` winner reports the path as un-ignored — defeated by **peeling** (record the reported rule for every path, blank those lines, ask again, until a round reports nothing new; bounded because each round blanks at least one line). Negations are recorded rather than filtered, because a hand-written pin beneath a declared root is exactly the per-case exception the declaration abolishes. The predicate is therefore "an unmanaged rule *matches* a path under a declared root", matching the design, while git's own pattern engine does all the matching end to end.

**Grammar exclusions are divergence-driven, not taste-driven.** Every construct `tracked:` rejects (`**`, `?`, character classes, backslashes, empty/`.` segments, surrounding whitespace) is one where `PurePosixPath.match` and git disagree, each reproduced against real git and pinned by a test that asserts *both* engines' answers. Admitting one would let the generator emit a working git rule that `unreachable-tracked` silently never verifies.

**Nothing is sampled.** All extant paths under a declared root go into one NUL-framed `check-ignore` call. An earlier draft capped this at 500, which made an ERROR check probabilistic and filesystem-order dependent.
