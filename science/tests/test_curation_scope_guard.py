"""Design acceptance test 1: exactly one decider resolves curation scope."""

import ast
from pathlib import Path

from science_model.entities import Entity

# Both real source roots. The test lives at science/tests/, so science/ is parents[1];
# the model package is science/model/, NOT repository-root model/.
_TOOL_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_MODEL_SRC = Path(__file__).resolve().parents[1] / "model" / "src" / "science_model"
assert _TOOL_SRC.is_dir() and _MODEL_SRC.is_dir(), (
    _TOOL_SRC,
    _MODEL_SRC,
)  # fail loud on a path typo

# The single legitimate home of scope DECISION: the enum lives in identity.py; the
# default is applied in entity_registry.py. Everything else may only CALL the decider
# and compare its RESULT.
_DECIDER = _TOOL_SRC / "graph" / "entity_registry.py"
_ENUM_HOME = _MODEL_SRC / "identity.py"

# The deleted closed list (design §4). Its reappearance anywhere is the two-taxonomy
# split re-emerging.
_CLOSED_LIST = {
    "task",
    "dataset",
    "workflow-run",
    "data-package",
    "paper",
    "prose-source",
    "book",
    "experiment",
    "code-file",
}


def _py_files(root: Path):
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _all_src():
    return _py_files(_TOOL_SRC) + _py_files(_MODEL_SRC)


def _literal_strings(node: ast.AST):
    if not isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        return None
    if not all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in node.elts):
        return None
    return {item.value for item in node.elts}


def _contains_closed_list_literal(tree: ast.AST):
    for node in ast.walk(tree):
        values = None
        if isinstance(node, ast.Set):
            values = _literal_strings(node)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "frozenset"
            and len(node.args) == 1
            and not node.keywords
        ):
            values = _literal_strings(node.args[0])
        if values is not None and _CLOSED_LIST <= values:
            return True
    return False


def test_validator_is_gone():
    assert not hasattr(Entity, "_validate_review_state_kind"), (
        "the model-layer scope validator must be deleted (design §6.1)"
    )


def test_closed_list_literal_appears_nowhere():
    """No module reconstructs the closed set as a review gate (both source roots)."""
    offenders = []
    for path in _all_src():
        if _contains_closed_list_literal(ast.parse(path.read_text())):
            offenders.append(str(path))
    assert offenders == [], f"closed-list knowledge resurfaced in: {offenders}"


def test_closed_list_detector_requires_one_collection_literal():
    values = ", ".join(repr(kind) for kind in sorted(_CLOSED_LIST))
    assert _contains_closed_list_literal(ast.parse(f"kinds = {{{values}}}"))
    assert _contains_closed_list_literal(ast.parse(f"kinds = frozenset([{values}])"))

    scattered = "\n".join(
        f"{kind.replace('-', '_')} = {kind!r}" for kind in sorted(_CLOSED_LIST)
    )
    assert not _contains_closed_list_literal(ast.parse(scattered))


def test_only_one_module_applies_the_scope_default():
    """The DEFAULT-application polarity (undeclared → correspondence/none) is what
    'deciding scope' means. A second decider under ANY function name would have to
    name a CurationScope default value to return it. The only production module
    permitted to reference `CurationScope.CORRESPONDENCE` / `CurationScope.NONE` as a
    RETURNED default is the decider; the enum's own definition lives in identity.py.
    Consumers may compare against the decider's result but must not re-derive it.

    This catches a renamed second decider that `def curation_scope_for_kind`-name
    matching would miss, and does not enumerate an allow-list of trusted modules —
    it names only the one legitimate home."""
    offenders = []
    for path in _all_src():
        if path in (_DECIDER, _ENUM_HOME):
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            # a `return <...CurationScope.CORRESPONDENCE/NONE...>` is default application
            if isinstance(node, ast.Return) and node.value is not None:
                src = ast.dump(node.value)
                if "CORRESPONDENCE" in src or (
                    "attr='NONE'" in src and "CurationScope" in src
                ):
                    offenders.append(f"{path}:{node.lineno}")
    assert offenders == [], f"a second scope decider applies the default in: {offenders}"


def test_decider_exists_where_expected():
    """The one decider is a method on EntityRegistry named curation_scope_for_kind."""
    tree = ast.parse(_DECIDER.read_text())
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "curation_scope_for_kind" in names


def test_entity_review_does_not_branch_on_entity_class_for_scope():
    """The old EntityClass gate is gone from the review path."""
    text = (_TOOL_SRC / "entity_review.py").read_text()
    assert "EntityClass" not in text, "review scope must not consult EntityClass (design §6.1)"
    assert "curation_scope_for_kind" in text
