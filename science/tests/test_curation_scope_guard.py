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


def _is_curation_scope_type(node: ast.AST, scope_names: set[str]):
    return (
        isinstance(node, ast.Name) and node.id in scope_names
    ) or (isinstance(node, ast.Attribute) and node.attr == "CurationScope")


def _fixed_scope_constructor_argument(node: ast.Call):
    """Return the argument from ordinary one-value Enum construction syntax."""
    if len(node.args) == 1 and not node.keywords:
        return node.args[0]
    if (
        not node.args
        and len(node.keywords) == 1
        and node.keywords[0].arg == "value"
    ):
        return node.keywords[0].value
    return None


def _is_scope_default_reference(node: ast.AST, scope_names: set[str]):
    """Recognize ordinary fixed Enum spellings without evaluating Python.

    Covered forms are member attributes, member-name subscription, and value
    construction by one positional argument or the equivalent ``value=``
    keyword. Imported aliases and module-qualified ``CurationScope`` names are
    accepted by ``_is_curation_scope_type``. Dynamic expressions, reflection,
    and ``*``/``**`` unpacking are intentionally not statically evaluated.
    """
    if (
        isinstance(node, ast.Attribute)
        and node.attr in {"NONE", "CORRESPONDENCE"}
        and _is_curation_scope_type(node.value, scope_names)
    ):
        return True
    if (
        isinstance(node, ast.Call)
        and _is_curation_scope_type(node.func, scope_names)
    ):
        value = _fixed_scope_constructor_argument(node)
        return isinstance(value, ast.Constant) and value.value in {
            "none",
            "correspondence",
        }
    if isinstance(node, ast.Subscript) and _is_curation_scope_type(
        node.value,
        scope_names,
    ):
        member = node.slice
        return isinstance(member, ast.Constant) and member.value in {
            "NONE",
            "CORRESPONDENCE",
        }
    return False


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


def test_scope_default_detector_catches_fixed_enum_construction_and_subscription():
    literal_call = ast.parse(
        "def decide():\n"
        "    return CurationScope('none')"
    )
    aliased_literal_call = ast.parse(
        "from science_model.identity import CurationScope as Scope\n"
        "def decide():\n"
        "    return Scope('correspondence')"
    )
    member_subscription = ast.parse(
        "def decide():\n"
        "    return CurationScope['NONE']"
    )
    aliased_member_subscription = ast.parse(
        "from science_model.identity import CurationScope as Scope\n"
        "def decide():\n"
        "    return Scope['CORRESPONDENCE']"
    )
    parameter_default = ast.parse(
        "def decide(scope=CurationScope('none')):\n"
        "    return scope"
    )
    lambda_keyword_default = ast.parse(
        "(lambda *, scope=CurationScope['CORRESPONDENCE']: scope)"
    )
    dynamic_call = ast.parse(
        "def parse(value):\n"
        "    return CurationScope(value)"
    )
    dynamic_subscription = ast.parse(
        "def parse(name):\n"
        "    return CurationScope[name]"
    )
    comparison = ast.parse(
        "def consume(scope):\n"
        "    return scope == CurationScope('none')"
    )
    declaration = ast.parse(
        "PROFILE = EntityKind(curation_scope=CurationScope('correspondence'))"
    )

    assert _scope_default_offense_lines(literal_call)
    assert _scope_default_offense_lines(aliased_literal_call)
    assert _scope_default_offense_lines(member_subscription)
    assert _scope_default_offense_lines(aliased_member_subscription)
    assert _scope_default_offense_lines(parameter_default)
    assert _scope_default_offense_lines(lambda_keyword_default)
    assert not _scope_default_offense_lines(dynamic_call)
    assert not _scope_default_offense_lines(dynamic_subscription)
    assert not _scope_default_offense_lines(comparison)
    assert not _scope_default_offense_lines(declaration)


def test_scope_default_detector_catches_fixed_enum_value_keyword():
    literal_keyword = ast.parse(
        "def decide():\n"
        "    return CurationScope(value='none')"
    )
    aliased_literal_keyword = ast.parse(
        "from science_model.identity import CurationScope as Scope\n"
        "def decide():\n"
        "    return Scope(value='correspondence')"
    )
    qualified_literal_keyword = ast.parse(
        "import science_model.identity as identity\n"
        "def decide():\n"
        "    return identity.CurationScope(value='none')"
    )
    parameter_default = ast.parse(
        "def decide(scope=CurationScope(value='correspondence')):\n"
        "    return scope"
    )
    dynamic_keyword = ast.parse(
        "def parse(value):\n"
        "    return CurationScope(value=value)"
    )
    comparison = ast.parse(
        "def consume(scope):\n"
        "    return scope == CurationScope(value='none')"
    )
    declaration = ast.parse(
        "PROFILE = EntityKind(curation_scope=CurationScope(value='correspondence'))"
    )

    assert _scope_default_offense_lines(literal_keyword)
    assert _scope_default_offense_lines(aliased_literal_keyword)
    assert _scope_default_offense_lines(qualified_literal_keyword)
    assert _scope_default_offense_lines(parameter_default)
    assert not _scope_default_offense_lines(dynamic_keyword)
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
