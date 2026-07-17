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
    return {
        item.value
        for item in node.elts
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    }


def _contains_closed_list_literal(tree: ast.AST):
    for node in ast.walk(tree):
        values = None
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            values = _literal_strings(node)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"frozenset", "list", "set", "tuple"}
            and len(node.args) == 1
            and not node.keywords
        ):
            values = _literal_strings(node.args[0])
        if values is not None and _CLOSED_LIST <= values:
            return True
    return False


def _curation_scope_names(tree: ast.AST):
    names = {"CurationScope"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for imported in node.names:
            if imported.name == "CurationScope":
                names.add(imported.asname or imported.name)
    return names


def _is_scope_default_reference(node: ast.AST, scope_names: set[str]):
    if not isinstance(node, ast.Attribute) or node.attr not in {
        "NONE",
        "CORRESPONDENCE",
    }:
        return False
    qualifier = node.value
    return (
        isinstance(qualifier, ast.Name) and qualifier.id in scope_names
    ) or (isinstance(qualifier, ast.Attribute) and qualifier.attr == "CurationScope")


def _contains_scope_default_value(
    node: ast.AST,
    scope_names: set[str],
    *,
    permit_declarative_keyword: bool = False,
):
    if isinstance(node, ast.Compare):
        operands = [node.left, *node.comparators]
        return any(
            not _is_scope_default_reference(operand, scope_names)
            and _contains_scope_default_value(
                operand,
                scope_names,
                permit_declarative_keyword=permit_declarative_keyword,
            )
            for operand in operands
        )
    if _is_scope_default_reference(node, scope_names):
        return True
    if isinstance(node, ast.Call):
        values = [*node.args]
        values.extend(
            keyword.value
            for keyword in node.keywords
            if not (
                permit_declarative_keyword and keyword.arg == "curation_scope"
            )
        )
        return any(
            _contains_scope_default_value(
                value,
                scope_names,
                permit_declarative_keyword=permit_declarative_keyword,
            )
            for value in values
        )
    return any(
        _contains_scope_default_value(
            child,
            scope_names,
            permit_declarative_keyword=permit_declarative_keyword,
        )
        for child in ast.iter_child_nodes(node)
    )


def _scope_default_offense_lines(tree: ast.AST):
    scope_names = _curation_scope_names(tree)
    module_declarations = {
        id(node)
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
    }
    offenders = []
    for node in ast.walk(tree):
        values = []
        if isinstance(node, (ast.Return, ast.Assign, ast.NamedExpr)):
            if node.value is not None:
                values.append(node.value)
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None:
                values.append(node.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            values.extend(node.args.defaults)
            values.extend(default for default in node.args.kw_defaults if default is not None)
        if any(
            _contains_scope_default_value(
                value,
                scope_names,
                permit_declarative_keyword=id(node) in module_declarations,
            )
            for value in values
        ):
            offenders.append(node.lineno)
    return sorted(set(offenders))


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
    assert _contains_closed_list_literal(ast.parse(f"kinds = [{values}]"))
    assert _contains_closed_list_literal(ast.parse(f"kinds = ({values},)"))
    assert _contains_closed_list_literal(ast.parse(f"kinds = frozenset([{values}])"))
    assert _contains_closed_list_literal(ast.parse(f"kinds = set(({values},))"))
    assert _contains_closed_list_literal(ast.parse(f"kinds = {{{values}, OTHER}}"))
    assert _contains_closed_list_literal(
        ast.parse(f"kinds = frozenset([{values}, *OTHER])")
    )

    scattered = "\n".join(
        f"{kind.replace('-', '_')} = {kind!r}" for kind in sorted(_CLOSED_LIST)
    )
    assert not _contains_closed_list_literal(ast.parse(scattered))


def test_scope_default_detector_rejects_defaults_but_permits_comparisons():
    direct_return = ast.parse("def decide():\n    return CurationScope.NONE")
    aliased_return = ast.parse(
        "from science_model.identity import CurationScope as Scope\n"
        "def decide():\n"
        "    return Scope.CORRESPONDENCE"
    )
    assigned_return = ast.parse(
        "def decide():\n"
        "    fallback = CurationScope.NONE\n"
        "    return fallback"
    )
    indirect_return = ast.parse(
        "def decide(defaults, kind):\n"
        "    return defaults.get(kind, CurationScope.NONE)"
    )
    keyword_default = ast.parse(
        "def decide(resolver):\n"
        "    return resolver(default=CurationScope.CORRESPONDENCE)"
    )
    nested_comparison = ast.parse(
        "def decide(defaults, kind):\n"
        "    return defaults.get(kind, CurationScope.NONE) is CurationScope.NONE"
    )
    returned_curation_scope = ast.parse(
        "def decide(resolver):\n"
        "    return resolver(curation_scope=CurationScope.NONE)"
    )
    comparison = ast.parse(
        "def consume(scope):\n    return scope is CurationScope.NONE"
    )
    declaration = ast.parse(
        "PROFILE = EntityKind(curation_scope=CurationScope.CORRESPONDENCE)"
    )
    positional_parameter_default = ast.parse(
        "def decide(scope=CurationScope.NONE):\n"
        "    return scope"
    )
    keyword_only_parameter_default = ast.parse(
        "def decide(*, scope=CurationScope.CORRESPONDENCE):\n"
        "    return scope"
    )
    async_parameter_default = ast.parse(
        "async def decide(scope=CurationScope.NONE):\n"
        "    return scope"
    )
    lambda_parameter_default = ast.parse(
        "(lambda scope=CurationScope.CORRESPONDENCE: scope)"
    )
    lambda_keyword_only_parameter_default = ast.parse(
        "(lambda *, scope=CurationScope.NONE: scope)"
    )

    assert _scope_default_offense_lines(direct_return)
    assert _scope_default_offense_lines(aliased_return)
    assert _scope_default_offense_lines(assigned_return)
    assert _scope_default_offense_lines(indirect_return)
    assert _scope_default_offense_lines(keyword_default)
    assert _scope_default_offense_lines(nested_comparison)
    assert _scope_default_offense_lines(returned_curation_scope)
    assert _scope_default_offense_lines(positional_parameter_default)
    assert _scope_default_offense_lines(keyword_only_parameter_default)
    assert _scope_default_offense_lines(async_parameter_default)
    assert _scope_default_offense_lines(lambda_parameter_default)
    assert _scope_default_offense_lines(lambda_keyword_only_parameter_default)
    assert not _scope_default_offense_lines(comparison)
    assert not _scope_default_offense_lines(declaration)


def test_only_one_module_applies_the_scope_default():
    """The DEFAULT-application polarity (undeclared → correspondence/none) is what
    'deciding scope' means. A second decider under ANY function name would have to
    name a CurationScope default value to return it. The only production module
    permitted to reference `CurationScope.CORRESPONDENCE` / `CurationScope.NONE` as a
    returned or assigned default is the decider; the enum's own definition lives in
    identity.py. Consumers may compare against the decider's result but must not
    re-derive it.

    This catches a renamed second decider that `def curation_scope_for_kind`-name
    matching would miss, and does not enumerate an allow-list of trusted modules —
    it names only the one legitimate home."""
    offenders = []
    for path in _all_src():
        if path in (_DECIDER, _ENUM_HOME):
            continue
        tree = ast.parse(path.read_text())
        offenders.extend(
            f"{path}:{lineno}" for lineno in _scope_default_offense_lines(tree)
        )
    assert offenders == [], f"a second scope decider applies the default in: {offenders}"


def test_decider_exists_where_expected():
    """The one decider is a method on EntityRegistry named curation_scope_for_kind."""
    tree = ast.parse(_DECIDER.read_text())
    registry_classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "EntityRegistry"
    ]
    assert len(registry_classes) == 1
    methods = {
        node.name
        for node in registry_classes[0].body
        if isinstance(node, ast.FunctionDef)
    }
    assert "curation_scope_for_kind" in methods


def test_entity_review_does_not_branch_on_entity_class_for_scope():
    """The old EntityClass gate is gone from the review path."""
    text = (_TOOL_SRC / "entity_review.py").read_text()
    tree = ast.parse(text)
    assert "EntityClass" not in text, "review scope must not consult EntityClass (design §6.1)"
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "curation_scope_for_kind"
        for node in ast.walk(tree)
    )
