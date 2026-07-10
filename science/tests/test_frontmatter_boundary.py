"""Frontmatter-emitter boundary guard (convergence Phase 2).

Additive ratchet: a *new* hand-rolled frontmatter emitter must not appear
outside the canonical module (science_model/frontmatter.py) and the named
legacy allowlist below. It also asserts the reader name `parse_frontmatter` is
defined in exactly one place, so the namesake collision cannot regrow.

Detection (Rule A): a function is a frontmatter emitter if it contains a `---`
*fence line* inside a string literal that is NOT a parsing-method argument, AND
emits YAML — either a direct `yaml.safe_dump`/`yaml.dump` call, or a call to a
module-local helper that itself calls one. Fence detection is line-based (any
line of any string constant equal to `---`), so it survives CPython folding
implicitly-concatenated literals into one `Constant`; `ast.walk` descends into
`JoinedStr` values, so f-strings are covered. Parsing-method arguments
(`split`/`partition`/`startswith`/…) are excluded so a fence *reader* is not
mistaken for an emitter. This is necessary-but-not-sufficient: it will not catch
a fence constructed at runtime, emitted via an unknown cross-module helper, or
written through `str.format`. None exist today; this guard stops the bare form
that recurred.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_MODEL_SRC = Path(__file__).resolve().parents[1] / "model" / "src" / "science_model"

# Canonical module: the one place a frontmatter renderer/dumper may co-exist
# with fence literals without allowlisting.
_CANONICAL = _MODEL_SRC / "frontmatter.py"

# String methods that *read* a fence rather than emit one; a fence literal
# passed to one of these is not evidence of emission.
_PARSING_METHODS = {
    "split", "rsplit", "partition", "rpartition",
    "startswith", "endswith", "find", "rfind", "index", "rindex", "count",
}


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root in (_SCIENCE_SRC, _MODEL_SRC):
        files.extend(p for p in root.rglob("*.py"))
    return files


def _contains_fence(value: str) -> bool:
    """True if any line of ``value`` is exactly a ``---`` frontmatter fence.

    Line-based (not exact-equality) so it matches the merged ``Constant`` that
    results from implicitly-concatenating ``"---\\n"`` with an adjacent
    f-string (e.g. ``"---\\nschema_profile: \\""``).
    """
    return any(line.rstrip("\r") == "---" for line in value.split("\n"))


def _is_yaml_dump_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"safe_dump", "dump"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "yaml"
    )


def _local_dumper_names(tree: ast.Module) -> set[str]:
    """Names of module-level functions whose body calls yaml.safe_dump/dump."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            _is_yaml_dump_call(n) for n in ast.walk(node)
        ):
            names.add(node.name)
    return names


def _parsing_arg_constant_ids(func: ast.AST) -> set[int]:
    """id()s of string constants passed to fence-*parsing* methods, so a
    ``text.split("---")`` validator is not read as an emitter."""
    ids: set[int] = set()
    for n in ast.walk(func):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in _PARSING_METHODS
        ):
            for arg in n.args:
                ids.add(id(arg))
    return ids


def _function_is_emitter(func: ast.AST, dumpers: set[str]) -> bool:
    parsing_ids = _parsing_arg_constant_ids(func)
    has_emitting_fence = False
    emits = False
    for n in ast.walk(func):
        if (
            isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and _contains_fence(n.value)
            and id(n) not in parsing_ids
        ):
            has_emitting_fence = True
        if _is_yaml_dump_call(n):
            emits = True
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in dumpers:
            emits = True
    return has_emitting_fence and emits


def _emitter_functions() -> list[tuple[str, str]]:
    """Return (relative_path, function_name) for every frontmatter emitter."""
    found: list[tuple[str, str]] = []
    repo_root = Path(__file__).resolve().parents[1]
    for path in _source_files():
        if path == _CANONICAL:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        dumpers = _local_dumper_names(tree)
        rel = str(path.relative_to(repo_root))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _function_is_emitter(
                node, dumpers
            ):
                found.append((rel, node.name))
    return found


# (rel_path, function_name) -> reason. Genuinely-divergent legacy emitters =
# the format-normalization worklist. Filled in Step 2 from the Step-1 report.
_ALLOWED_EMITTERS: dict[tuple[str, str], str] = {
    # --- byte-preservation: allow_unicode=False core-entity format; folds onto
    #     render_frontmatter only in the future format-normalization phase.
    ("src/science_tool/entities.py", "_render_markdown"): "pending-normalization: allow_unicode=False core-entity renderer",
    ("src/science_tool/entities.py", "build_entity_markdown"): "pending-normalization: allow_unicode=False core-entity renderer",
    ("src/science_tool/entities.py", "_merge_extra_frontmatter"): "pending-normalization: allow_unicode=False core-entity renderer",
    ("src/science_tool/dag/workbench_apply.py", "_render_entity_text_from_frontmatter"): "pending-normalization: allow_unicode=False entity update on RMW path",
    # --- structural: fence spacing / body handling differ from canonical.
    ("src/science_tool/annotation/source_text.py", "render_source_md"): "structural: ---\\n\\n spacing + passage-offset fixpoint loop",
    ("src/science_tool/graph/decision_log.py", "render_owner_file"): "structural: ---\\n\\n spacing + rstrip body",
    ("src/science_tool/questions.py", "_render_stub"): "structural: yaml.dump + rstrip + ---\\n\\n",
    ("src/science_tool/cli.py", "_render_inquiry_source"): "structural: Variant D kwargs + ---\\n\\n",
    ("src/science_tool/datasets_identity.py", "_render_entity"): "structural: no newline after closing fence (body_suffix)",
    ("src/science_tool/datasets_catalog.py", "_render_candidate"): "structural: ---\\n\\n spacing",
    ("src/science_tool/datasets_catalog.py", "_render_entity"): "structural: ---\\n\\n + body .strip()",
    ("src/science_tool/datasets_catalog.py", "verify_access"): "structural: ---\\n\\n + body lstrip; fm mutated in place",
    ("src/science_tool/datasets_register.py", "_rewrite_run_frontmatter"): "byte-preservation: Variant C kwargs, no force-quoting on run entities",
    ("src/science_tool/commons/reference_graph_promotion.py", "_render_entity"): "byte-preservation: no allow_unicode; frontmatter-only block",
    # --- hand-template: top-level frontmatter is hand-written, not dumped.
    ("src/science_tool/datasets_register.py", "_entity_yaml_block"): "hand-template: force-quoted f-string scaffold; safe_dump only for sub-blocks",
    ("src/science_tool/commons/dataset_lifecycle.py", "_entity_text"): "hand-template: triple-quoted scaffold; safe_dump only for sub-blocks",
    # --- pending-normalization: templated-entity renderer inside science_model.
    ("model/src/science_model/templates.py", "render"): "pending-normalization: templated-entity Renderer, placeholder substitution, no allow_unicode",
}

# (rel_path, function_name) -> reason. Consumers/validators that trip the
# heuristic but emit nothing distinct (e.g. call a renderer AND parse fences).
# Kept OUT of _ALLOWED_EMITTERS so the normalization worklist stays clean.
_DETECTOR_FALSE_POSITIVES: dict[tuple[str, str], str] = {}


def _exempt() -> set[tuple[str, str]]:
    return set(_ALLOWED_EMITTERS) | set(_DETECTOR_FALSE_POSITIVES)


def test_no_new_frontmatter_emitters() -> None:
    offenders = [pair for pair in _emitter_functions() if pair not in _exempt()]
    assert not offenders, (
        "New hand-rolled frontmatter emitter(s) found outside the canonical "
        "module (science_model/frontmatter.py) and the named allowlist. Route "
        "new writers through render_frontmatter(fields, body); if the byte form "
        "is deliberately divergent add an _ALLOWED_EMITTERS entry with a reason; "
        "if it is a consumer the detector misclassified, add a "
        f"_DETECTOR_FALSE_POSITIVES entry. Offenders: {sorted(offenders)}"
    )


def test_allowlist_has_no_stale_entries() -> None:
    live = set(_emitter_functions())
    stale = [pair for pair in _exempt() if pair not in live]
    assert not stale, (
        "Allowlisted/false-positive entries no longer detected as emitters "
        f"(migrated or removed?). Delete these stale entries: {sorted(stale)}"
    )


def test_parse_frontmatter_defined_once() -> None:
    definitions: list[str] = []
    repo_root = Path(__file__).resolve().parents[1]
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "parse_frontmatter":
                definitions.append(str(path.relative_to(repo_root)))
    assert definitions == ["model/src/science_model/frontmatter.py"], (
        "parse_frontmatter must be defined in exactly one place "
        "(science_model/frontmatter.py). A same-named reader elsewhere is the "
        f"namesake collision Phase 2 removed. Definitions found: {sorted(definitions)}"
    )
