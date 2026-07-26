"""Every field a kind's schema admits is declared on that kind's projection.

D3 rules that JSON Schema is authoritative for entity fields and Pydantic is a PROJECTION of it.
`test_hypothesis_entity.py` proves that field-by-field for one kind. This file proves the
DECLARATION half for every kind that has a schema, at every live generation.

☠️ Lives in the TOOL suite, not `model/tests/`, because the kind -> model binding is
`CORE_KIND_MODELS` here in `science_tool`, and `science_model` may not import its consumer.
Entity subclasses do not self-declare their kind, so that dict is the only map. That the binding
sits in neither authority's package is a real finding; relocating it is S2's call, not S1a's.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import textwrap
from dataclasses import dataclass

import pytest

from science_model.entities import ProjectEntity
from science_model.entity_schema import admitted_field_names, default_profile_for_kind
from science_model.entity_schema.profile import _MIXIN_VERSION_BY_GENERATION
from science_tool.graph.entity_registry import CORE_KIND_MODELS

PROFILES = sorted(
    (generation, kind)
    for generation, kinds in _MIXIN_VERSION_BY_GENERATION.items()
    for kind in kinds
)


@dataclass(frozen=True, slots=True)
class Reader:
    """A named symbol that performs a keyed read of the field.

    `mapping` is prose naming WHAT is read, and it is load-bearing: the AST check below proves a
    keyed read of the name, not that the mapping is this kind's frontmatter. Necessary, not
    sufficient -- see `test_the_reader_check_is_not_sufficient_on_its_own`.
    """

    module: str
    symbol: str
    mapping: str


@dataclass(frozen=True, slots=True)
class PendingRuling:
    """Explicit debt: someone looked for a reader and found none.

    NOT evidence the gap is benign. S1b/S2 resolves each by declaring the field on the model,
    forbidding it in the mixin, or producing a reader.
    """

    note: str


_BOTH = frozenset({2, 3})
_COMMONS_FOUR = ("dataset", "paper", "theme", "topic")

_DATASET_PRIORITIZE = ("science_tool.dataset_prioritize", "target_coverage")

# (kind, field) -> (generations, reason). Expanded to (generation, kind, field) triples before
# comparison, so a generation 4 inherits NOTHING implicitly: its gaps must be declared or the gate
# fails. Today every entry applies to both generations; that is measured, not assumed.
UNHELD: dict[tuple[str, str], tuple[frozenset[int], Reader | PendingRuling]] = {
    ("hypothesis", "required_capabilities"): (
        _BOTH,
        Reader(*_DATASET_PRIORITIZE, "raw entity frontmatter via _iter_entity_frontmatter, gated on _is_qh"),
    ),
    ("hypothesis", "capability_scope"): (
        _BOTH,
        Reader(*_DATASET_PRIORITIZE, "raw entity frontmatter via _iter_entity_frontmatter, gated on _is_qh"),
    ),
    ("dataset", "provided_capabilities"): (
        _BOTH,
        Reader("science_tool.skills_coverage.evidence", "project_evidence",
               "entity.model_extra, inside `if entity.kind != 'dataset': continue`"),
    ),
    ("dataset", "sources"): (
        _BOTH,
        Reader("science_tool.commons.promote_dataset", "_dataset_recipe_source_hint",
               "the merged dataset entity fields, passed from commons.promote"),
    ),
    ("dataset", "runtime_state"): (
        _BOTH,
        PendingRuling(
            "datasets.semantics.runtime_state_for(fm) DERIVES this from dataset_class_for / "
            "has_runtime_artifact / _access; the row['runtime_state'] reads consume that derived "
            "output and commons.promote writes it. No reader of an AUTHORED value."
        ),
    ),
    ("paper", "paper_kind"): (
        _BOTH,
        Reader("science_tool.validate.checks.document_structure", "_check_documents",
               "ctx.frontmatter(path)"),
    ),
    ("paper", "arxiv"): (
        _BOTH,
        PendingRuling("skills_lint.sources._build_record reads `arxiv` from the SKILLS source registry, not entity frontmatter"),
    ),
    ("paper", "pmcid"): (
        _BOTH,
        PendingRuling("paper_fetch reads `pmcid` from a fetched API record, not entity frontmatter"),
    ),
}

for _kind in _COMMONS_FOUR:
    UNHELD[(_kind, "tags")] = (
        _BOTH,
        Reader("science_tool.commons.registry", "RegistryBuilder._insert_records", "record.frontmatter"),
    )
    UNHELD[(_kind, "schema_profile")] = (
        _BOTH,
        Reader("science_model.entity_schema.validator", "EntityValidator.validate",
               "the entity dict built from frontmatter (the commons path)"),
    )
    UNHELD[(_kind, "version")] = (
        _BOTH,
        Reader("science_tool.commons.dataset_lifecycle", "_validate_entity_frontmatter", "entity frontmatter"),
    )
    UNHELD[(_kind, "contributors")] = (
        _BOTH,
        PendingRuling("no keyed read of `contributors` exists anywhere in science_tool or science_model"),
    )
    UNHELD[(_kind, "licenses")] = (
        _BOTH,
        PendingRuling("no keyed read of `licenses` exists anywhere in science_tool or science_model"),
    )

for _kind in ("paper", "theme", "topic"):
    UNHELD[(_kind, "sources")] = (
        _BOTH,
        PendingRuling(
            "the only keyed `sources` reads are datasets_register._proxy_source_datasets (a nested "
            "identity_contract.assembly.proxy key) and the dataset-only promote_dataset hint"
        ),
    )


def _expanded() -> dict[tuple[int, str, str], Reader | PendingRuling]:
    return {
        (generation, kind, field): reason
        for (kind, field), (generations, reason) in UNHELD.items()
        for generation in generations
    }


def _model_for(kind: str) -> type:
    return CORE_KIND_MODELS.get(kind, ProjectEntity)


def _resolve(module: str, symbol: str) -> object:
    obj: object = importlib.import_module(module)
    for part in symbol.split("."):
        obj = getattr(obj, part)
    return obj


def _reads_key(symbol: object, field: str) -> bool:
    """True if `symbol`'s source performs a keyed read of the literal `field`."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(symbol)))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == field
        ):
            return True
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == field
        ):
            return True
    return False


@pytest.mark.parametrize("generation,kind", PROFILES)
def test_every_admitted_field_is_declared_on_the_projection(generation: int, kind: str) -> None:
    """EXACT equality against the frozen manifest, not a subset.

    A stale exemption fails as loudly as a new gap. The hand-written half is the half that falls
    behind, and it falls behind in both directions -- an exemption for a field that is now declared
    reads like known debt that no longer exists.
    """
    admitted = admitted_field_names(default_profile_for_kind(kind, generation=generation))
    gaps = admitted - set(_model_for(kind).model_fields)
    exempt = {f for (g, k, f) in _expanded() if (g, k) == (generation, kind)}

    assert gaps == exempt, (
        f"gen {generation} {kind}: undeclared gap {sorted(gaps - exempt)}; "
        f"stale exemption {sorted(exempt - gaps)}"
    )


@pytest.mark.parametrize(
    "kind,field",
    sorted(k for k, (_, reason) in UNHELD.items() if isinstance(reason, Reader)),
)
def test_every_declared_reader_exists_and_reads_its_field(kind: str, field: str) -> None:
    reader = UNHELD[(kind, field)][1]
    assert isinstance(reader, Reader)
    symbol = _resolve(reader.module, reader.symbol)
    assert _reads_key(symbol, field), (
        f"{reader.module}.{reader.symbol} is cited as the reader of {kind}.{field}, "
        f"but its source performs no keyed read of {field!r}"
    )


def test_the_reader_check_is_not_sufficient_on_its_own() -> None:
    """The check proves a keyed read of the NAME, never that the mapping is the right one.

    This is not a caveat in prose -- it is demonstrable. `_proxy_source_datasets` reads
    `identity_contract['assembly']['proxy']['sources']`, nothing to do with an entity's `sources`
    field, and it satisfies the check. That is why every `Reader` carries a `mapping` note and why
    `paper`/`theme`/`topic` `sources` is `PendingRuling` despite this function existing.
    """
    from science_tool.datasets_register import _proxy_source_datasets

    assert _reads_key(_proxy_source_datasets, "sources")
    assert isinstance(UNHELD[("paper", "sources")][1], PendingRuling)


def test_every_exemption_names_a_live_profile() -> None:
    # A manifest entry for a (generation, kind) that no longer exists never runs, and reads like
    # debt that is being tracked when it is not.
    orphans = {(g, k) for (g, k, _) in _expanded()} - set(PROFILES)
    assert not orphans, f"exemptions for profiles that do not exist: {sorted(orphans)}"
