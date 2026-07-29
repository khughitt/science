"""Gate 3: every load path that can emit a schema-closed kind validates BEFORE projection.

The Markdown adapter is not the only path. The structured-source loader builds entities from a
mapping it assembles itself, so a check placed there inspects the toolkit's own output. These
tests pin the ORDER -- lossless parse, declared normalization, composed validation, projection --
because a check downstream of a lossy step validates the loss, not the input.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml

from science_model.source_contracts import StructuredEntitySource
from science_tool.entity_profiles import ProjectSchema, load_project_schema_if_pinned
from science_tool.graph.entity_registry import EntityRegistry
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.schema import KindCategory
from science_tool.graph.sources import load_project_sources, registry_for_project


_REGISTRY_MODULE = "entity_registry.py"


def _entity_loading_package() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "science_tool" / "graph"


def _entity_class_names() -> frozenset[str]:
    """Every concrete entity model name, DERIVED -- 24 of them, not a literal list.

    `endswith("Entity")` was tried and is wrong: it matches `SkippedEntity`, a plain dataclass
    constructed five times in `sources.py`, and the guard would have failed on it forever with no
    way out but an exemption. Ask the model package which classes are actually entities.
    """
    import science_model.entities as entities_module
    from science_model.patch_definition import PatchDefinitionEntity
    from science_model.propositions import PropositionEntity

    names = {
        name
        for name, obj in vars(entities_module).items()
        if isinstance(obj, type) and issubclass(obj, entities_module.Entity)
    }
    # These two live outside `entities.py` but are registered entity models like any other.
    return frozenset(names | {PatchDefinitionEntity.__name__, PropositionEntity.__name__})


def _dotted(func: ast.expr) -> list[str] | None:
    """Flatten a call target into its dotted segments, or None if it is not a plain name path.

    `entities.MethodEntity.model_validate` -> ["entities", "MethodEntity", "model_validate"].
    Matching on SEGMENTS rather than on AST shape is what makes the guard blind to import style:
    a bare name, a module-qualified name, and a `self._registry` chain all reduce to the same
    question -- does any segment name an entity class, or the resolver.
    """
    parts: list[str] = []
    node: ast.expr = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None  # a subscript or call result -- not a name path we can rule on
    parts.append(node.id)
    return list(reversed(parts))


def _local_entity_names(tree: ast.Module, entity_names: frozenset[str]) -> frozenset[str]:
    """Entity class names PLUS every local name this module binds to one.

    Three binding forms, all ordinary code rather than evasion:
      `from science_model.entities import MethodEntity as ME`  -> ME       (ImportFrom)
      `EntityType = MethodEntity`                              -> EntityType  (Assign)
      `Annotated: type[Entity] = MethodEntity`                 -> Annotated   (AnnAssign)

    The annotated form is a separate AST node, not a flavour of `Assign`, and a draft that handled
    only `Assign` missed it -- adding a type annotation is the single most likely edit to make to
    a line like this, so missing it is missing the common case.

    There is nothing in the names `ME` or `EntityType` to recognize, so the binding has to be
    derived from the module's own statements. The pass runs to a fixed point because rebinding
    chains (`A = MethodEntity; B = A`) are one edit away from being written.
    """
    local = set(entity_names)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in entity_names and alias.asname:
                    local.add(alias.asname)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                target, value = node.target, node.value  # `X: type[Entity] = MethodEntity`
            else:
                continue
            if not isinstance(target, ast.Name) or target.id in local:
                continue
            segments = _dotted(value) if isinstance(value, ast.Name | ast.Attribute) else None
            if segments and any(s in local for s in segments):
                local.add(target.id)
                changed = True
    return frozenset(local)


def _class_obtaining_lines(module: Path) -> list[int]:
    """Lines that obtain an entity class in order to build from it.

    Two things count: the resolver (`…resolve_class(kind)`, any receiver) and any call whose
    target path passes through an entity class (`MethodEntity(**raw)`,
    `MethodEntity.model_validate(raw)`, `entities.MethodEntity(**raw)`, `ME(**raw)` after an
    aliased import). Earlier drafts matched AST SHAPE and kept missing spellings one at a time:
    an Attribute-only walk never sees the ordinary constructor (`ast.Name` func), and a
    Name-or-one-Attribute walk never sees `entities.MethodEntity(...)`, which is not obfuscation
    but an ordinary import style. Reducing the target to segments removes the whole category.

    No receiver-name heuristic either: an earlier draft matched the bare name `resolve` and had to
    discriminate on whether the receiver variable was called `registry`, which enforces a naming
    convention -- `reg.resolve(kind)` slipped straight through. Task 5 Step 4 renamed the method
    to `resolve_class`, which occurs nowhere else in the tree, so ANY receiver spelling is caught.

    Deliberately over-broad in one direction: `MethodEntity.model_fields` inside a call target
    also matches. That is a class being obtained to read from, which is what
    `EntityRegistry.declares_field` now exists to answer without handing the class out. The tree
    has zero such calls today, so the strictness costs nothing and closes the near-miss.
    """
    entity_names = _entity_class_names()
    tree = ast.parse(module.read_text(encoding="utf-8"))
    local = _local_entity_names(tree, entity_names)
    hits: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        segments = _dotted(node.func)
        if segments and any(s == "resolve_class" or s in local for s in segments):
            hits.add(node.lineno)
    return sorted(hits)  # ast.walk is breadth-first, so raw order is not source order


def test_NOTHING_in_the_loading_package_resolves_a_class_to_build_from() -> None:
    # The guard is over CALLS, not imports. Twelve modules in this package import `Entity` for
    # isinstance checks and annotations and construct nothing -- banning the import would make
    # those the violation and force either a rewrite of unrelated code or an exemption list, and
    # an exemption list is the enumerated-scope hole this project has been bitten by before.
    #
    # Obtaining a class in order to build from it reduces to one question: does the call target's
    # dotted path pass through `resolve_class` or an entity class (under any import spelling)?
    # There were five such sites; `build` makes it zero. Scope is DERIVED from the package tree,
    # so a sixth adapter is inside it automatically.
    offenders: dict[str, list[int]] = {}
    for module in sorted(_entity_loading_package().rglob("*.py")):
        if module.name == _REGISTRY_MODULE:
            continue  # `build` calls it -- the one legitimate call, by construction
        lines = _class_obtaining_lines(module)
        if lines:
            offenders[module.name] = lines
    assert not offenders, (
        f"modules obtaining an entity class outside the registry: {offenders}. "
        "Construct through `registry.build(kind, raw, ...)`, which validates first."
    )


def test_the_guarded_METHOD_still_exists() -> None:
    # Without this, the gate above is disarmed by a rename rather than by a fix: if
    # `resolve_class` is ever renamed back to `resolve`, every call site stops matching and the
    # guard goes permanently, silently green. The name is load-bearing, so assert it.
    from science_tool.graph.entity_registry import EntityRegistry

    assert hasattr(EntityRegistry, "resolve_class")
    assert not hasattr(EntityRegistry, "resolve"), (
        "`resolve` is back; the guard matches `resolve_class` and no longer sees the call sites"
    )


def test_the_guard_can_actually_SEE_every_violation_spelling(tmp_path: Path) -> None:
    # An AST guard that silently matches nothing passes forever. Pin the detector against all
    # TWELVE bypass spellings -- including the ones that defeated five earlier drafts -- so a
    # refactor that breaks the matching fails HERE rather than turning the gate into a no-op.
    #
    # The probe carries real imports and real assignments because `_local_entity_names` reads
    # both: `ME` is invisible without the `as` clause that bound it, and `EntityType` without the
    # assignment that did.
    probe = tmp_path / "probe.py"
    probe.write_text(
        "from science_model import entities\n"
        "from science_model.entities import Entity, MethodEntity\n"
        "from science_model.entities import MethodEntity as ME\n"
        "from science_tool.graph.sources import SkippedEntity\n"
        "\n"
        "EntityType = MethodEntity\n"  # local rebinding
        "Indirect = EntityType\n"  # and a chain, to pin the fixed point
        "Annotated: type[Entity] = MethodEntity\n"  # ANNOTATED rebinding -- ast.AnnAssign
        "\n"
        "def f(registry, context, reg, resolver, path, kind, raw):\n"
        "    registry.resolve_class(kind)\n"
        "    context.registry.resolve_class(kind)\n"
        "    reg.resolve_class(kind)\n"  # arbitrary receiver -- must match
        "    MethodEntity.model_validate(raw)\n"  # classmethod construction -- must match
        "    MethodEntity(**raw)\n"  # ORDINARY constructor -- must match
        "    entities.MethodEntity(**raw)\n"  # module-qualified -- must match
        "    entities.MethodEntity.model_validate(raw)\n"  # module-qualified classmethod -- match
        "    ME(**raw)\n"  # ALIASED import -- must match
        "    ME.model_validate(raw)\n"  # aliased classmethod -- must match
        "    EntityType(**raw)\n"  # LOCAL REBINDING -- must match
        "    Indirect.model_validate(raw)\n"  # rebinding chain -- must match
        "    Annotated(**raw)\n"  # annotated rebinding -- must match
        "    resolver.resolve(kind)\n"  # a DIFFERENT resolver -- must not match
        "    path.resolve()\n"  # pathlib -- must not match
        "    SkippedEntity(path='x')\n"  # a dataclass, not an entity -- no match
        "    isinstance(raw, Entity)\n",  # a type USE, not construction -- no match
        encoding="utf-8",
    )
    assert _class_obtaining_lines(probe) == [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]


def _armed_registry(tmp_path: Path) -> tuple[EntityRegistry, ProjectSchema]:
    """A registry plus a project schema that is actually ARMED.

    The assert is the point. `load_project_schema_if_pinned` returns None for an unpinned
    project, `validate_against_schema` returns on its first line when handed None, and every
    refusal test in this file would then pass by never validating anything. A fixture that fails
    silently open is worse than no fixture.
    """
    root = tmp_path / "armed"
    root.mkdir()
    (root / "science.yaml").write_text(
        "name: demo\nentity_schema_version: 2\n", encoding="utf-8"
    )
    project_schema = load_project_schema_if_pinned(root)
    assert project_schema is not None, "fixture is not pinned; the refusal tests would be vacuous"
    return registry_for_project(root), project_schema


def _valid_hypothesis_mapping() -> dict[str, Any]:
    """A hypothesis mapping that passes `unevaluatedProperties: false` under base 2.0 + mixin 1.0.

    Not invented: this is the record `tests/test_undeclared_key_diagnostic.py:33-40` writes and
    loads through `load_project_sources` on a project pinned to `entity_schema_version: 2`, in a
    test asserting `hypothesis` is in `strict_schema_kinds` -- i.e. a record already proven to
    survive the closed path. `mixin-hypothesis-1.0.json` requires exactly `id`, `kind`, `status`;
    the rest are base-2.0-admitted and present because the proven fixture carries them.
    """
    return {
        "id": "hypothesis:h1",
        "kind": "hypothesis",
        "title": "H1",
        "status": "active",
        "related": [],
        "source_refs": [],
        "created": "2026-03-12",
        "updated": "2026-03-12",
    }


def _an_open_kind() -> str:
    """A kind with no mixin, DERIVED rather than named.

    This was hard-coded to `concept` until the concept slice closed it, at which point the
    open-kind test started asserting closed-kind behaviour and failed. Naming the next
    victim (`method`, then `search`, ...) just moves the same breakage one slice along --
    the tranche is going to close all five. Deriving it means the test keeps testing what
    its name says for as long as any open kind exists.
    """
    return next(
        kind.name
        for kind in sorted(CORE_PROFILE.entity_kinds, key=lambda k: k.name)
        if not kind.schema_closed and kind.category is KindCategory.AUTHORED_CORE
    )


def _valid_open_kind_mapping() -> dict[str, Any]:
    """A minimal record for the open kind, which has no mixin -- only base 2.0 applies."""
    kind = _an_open_kind()
    return {
        "id": f"{kind}:c1",
        "kind": kind,
        "title": "C1",
        "status": "active",
        "related": [],
        "source_refs": [],
        "created": "2026-03-12",
        "updated": "2026-03-12",
    }


def _enrich_projection_fields(raw: dict[str, Any]) -> frozenset[str]:
    """Supply model bookkeeping only after composed validation has accepted the authored view."""
    raw.update(
        {
            "project": "demo",
            "ontology_terms": [],
            "content_preview": "",
            "file_path": "entities/test.md",
        }
    )
    return frozenset()


def test_an_unknown_key_SURVIVES_the_source_contract() -> None:
    # extra="allow", not "ignore". This is what lets a shadow key reach schema validation at all.
    # extra="forbid" is rejected as the alternative: every existing row carries `kind`, which the
    # loader legitimately ignores, so forbidding would reject the whole corpus for a key the
    # design agrees is fine.
    record = StructuredEntitySource.model_validate(
        {"canonical_id": "finding:0001-x", "shadow_key": "value"}
    )
    assert record.model_extra == {"shadow_key": "value"}


def test_only_AUTHORED_keys_are_normalized() -> None:
    # The declared fields still DEFAULT (title="", profile="", source_path="", five empty lists).
    # Normalizing from the parsed record would promote those defaults into the mapping that gets
    # schema-validated -- an absent title would arrive as "" and fail minLength: 1, and an absent
    # evidence_refs would arrive as [] and read as an authored empty list.
    from science_tool.graph.source_normalization import normalize_structured_row

    normalized = normalize_structured_row({"canonical_id": "finding:0001-x"})
    assert normalized == {"id": "finding:0001-x"}
    assert "title" not in normalized
    assert "evidence_refs" not in normalized


def test_the_declared_key_mapping_is_applied() -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    normalized = normalize_structured_row(
        {"canonical_id": "finding:0001-x", "source_path": "knowledge/sources/x.yaml"}
    )
    assert normalized["id"] == "finding:0001-x"
    assert normalized["file_path"] == "knowledge/sources/x.yaml"
    assert "canonical_id" not in normalized
    assert "source_path" not in normalized


@pytest.mark.parametrize(
    "row",
    [
        {"canonical_id": "finding:0001-x", "id": "shadow"},
        {"id": "shadow", "canonical_id": "finding:0001-x"},
        {"canonical_id": "finding:0001-x", "id": "finding:0001-x"},
        {"id": "finding:0001-x", "canonical_id": "finding:0001-x"},
    ],
)
def test_canonical_id_and_id_collision_is_refused_for_any_order_or_value(
    row: dict[str, Any],
) -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    with pytest.raises(
        ValueError,
        match="authored keys 'canonical_id' and 'id' both normalize to 'id'",
    ):
        normalize_structured_row(row)


@pytest.mark.parametrize(
    "row",
    [
        {"source_path": "authored.yaml", "file_path": "shadow.yaml"},
        {"file_path": "shadow.yaml", "source_path": "authored.yaml"},
        {"source_path": "same.yaml", "file_path": "same.yaml"},
        {"file_path": "same.yaml", "source_path": "same.yaml"},
    ],
)
def test_source_path_and_file_path_collision_is_refused_for_any_order_or_value(
    row: dict[str, Any],
) -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    with pytest.raises(
        ValueError,
        match="authored keys 'file_path' and 'source_path' both normalize to 'file_path'",
    ):
        normalize_structured_row(row)


def test_kind_is_the_only_declared_DROP() -> None:
    # `kind` is authoritative from the manifest and deliberately ignored on the row, so it is a
    # legitimately dropped key rather than a shadow field. A drop that is not DECLARED is
    # indistinguishable from a bug, which is the whole reason this set is written down.
    from science_tool.graph.source_normalization import STRUCTURED_DROP_KEYS

    assert STRUCTURED_DROP_KEYS == frozenset({"kind"})


def test_a_shadow_key_reaches_the_normalized_mapping() -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    normalized = normalize_structured_row({"canonical_id": "finding:0001-x", "shadow_key": "v"})
    assert normalized["shadow_key"] == "v", "a shadow key must survive to be REFUSED downstream"


def _write_structured_project(root: Path, rows: list[dict]) -> None:
    """A project whose local profile declares one structured-source kind."""
    (root / "science.yaml").write_text(
        yaml.safe_dump({"name": "demo", "knowledge_profiles": {"local": "project_specific"}}),
        encoding="utf-8",
    )
    sources = root / "knowledge" / "sources" / "project_specific"
    sources.mkdir(parents=True)
    (sources / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "project_specific",
                "imports": [],
                "relation_kinds": [],
                "strictness": "typed-extension",
                "entity_kinds": [
                    {
                        "name": "widget",
                        "canonical_prefix": "widget",
                        "layer": "layer/local",
                        "description": "d",
                        "entity_class": "reference",
                        "structured_source": "widget.yaml",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (sources / "widget.yaml").write_text(yaml.safe_dump({"widget": rows}), encoding="utf-8")


def test_an_authored_shadow_key_SURVIVES_the_whole_load_path(tmp_path: Path) -> None:
    _write_structured_project(
        tmp_path, [{"canonical_id": "widget:0001-x", "title": "W", "shadow_key": "v"}]
    )
    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "widget:0001-x")
    assert (entity.model_extra or {}).get("shadow_key") == "v"


def test_an_alias_collision_is_refused_through_the_whole_load_path(tmp_path: Path) -> None:
    _write_structured_project(
        tmp_path,
        [{"canonical_id": "widget:0001-x", "id": "widget:shadow", "title": "W"}],
    )
    with pytest.raises(
        ValueError,
        match="authored keys 'canonical_id' and 'id' both normalize to 'id'",
    ):
        load_project_sources(tmp_path)


def _write_closed_kind_project(root: Path, rows: list[dict]) -> None:
    """A pinned project whose local profile attaches a structured source to core hypothesis."""
    _write_structured_project(root, [])
    (root / "science.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "demo",
                "knowledge_profiles": {"local": "project_specific"},
                "entity_schema_version": 2,
            }
        ),
        encoding="utf-8",
    )
    sources_dir = root / "knowledge" / "sources" / "project_specific"
    manifest = yaml.safe_load((sources_dir / "manifest.yaml").read_text())
    manifest["core_structured_sources"] = [
        {"kind": "hypothesis", "structured_source": "hypothesis.yaml"}
    ]
    (sources_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (sources_dir / "hypothesis.yaml").write_text(
        yaml.safe_dump({"hypothesis": rows}), encoding="utf-8"
    )


def _valid_hypothesis_row() -> dict[str, Any]:
    """The same valid hypothesis, in structured-row spelling."""
    return {
        "canonical_id": "hypothesis:h1",
        "title": "H1",
        "status": "active",
        "created": "2026-03-12",
        "updated": "2026-03-12",
    }


def test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path(
    tmp_path: Path,
) -> None:
    _write_closed_kind_project(tmp_path, [{**_valid_hypothesis_row(), "shadow_key": "v"}])
    with pytest.raises(ValueError, match="does not satisfy its schema"):
        load_project_sources(tmp_path)


def test_the_same_closed_row_WITHOUT_the_shadow_key_loads(tmp_path: Path) -> None:
    _write_closed_kind_project(tmp_path, [_valid_hypothesis_row()])
    sources = load_project_sources(tmp_path)
    assert any(e.canonical_id == _valid_hypothesis_row()["canonical_id"] for e in sources.entities)


def test_an_unauthored_optional_field_is_absent_from_what_VALIDATION_SEES(
    tmp_path: Path, monkeypatch
) -> None:
    # The defaults-promotion failure. Asserting `entity.evidence_refs == []` on the loaded entity
    # would be INERT: `_enrich_raw` does `raw.setdefault("evidence_refs", [])` on every record, so
    # that assertion holds whether the value was authored, promoted from the source-model default,
    # or injected by enrichment. The claim is about the mapping VALIDATION is shown, upstream of
    # enrichment -- so spy on that.
    import science_tool.graph.entity_registry as reg_mod

    # Record the AUTHORED VIEW -- `raw` minus `injected` -- because that is the mapping the
    # validator ranges over. Spying on `raw` alone would assert the wrong thing now that
    # bookkeeping is subtracted inside the validator rather than absent from `raw`.
    seen: list[dict] = []
    real = reg_mod.validate_against_schema

    def _spy(raw, **kw):
        seen.append({k: v for k, v in raw.items() if k not in kw["injected"]})
        return real(raw, **kw)

    monkeypatch.setattr(reg_mod, "validate_against_schema", _spy)
    _write_structured_project(tmp_path, [{"canonical_id": "widget:0002-y", "title": "W2"}])
    load_project_sources(tmp_path)

    row = next(m for m in seen if m.get("id") == "widget:0002-y")
    assert "evidence_refs" not in row, "an unauthored field reached validation as an authored one"
    assert row["title"] == "W2"  # the authored ones DO arrive -- not a vacuously empty mapping


def test_structured_validation_sees_normalized_authored_destinations(
    tmp_path: Path, monkeypatch
) -> None:
    import science_tool.graph.entity_registry as reg_mod

    seen: list[dict] = []
    real = reg_mod.validate_against_schema

    def _spy(raw, **kw):
        seen.append({k: v for k, v in raw.items() if k not in kw["injected"]})
        return real(raw, **kw)

    monkeypatch.setattr(reg_mod, "validate_against_schema", _spy)
    _write_structured_project(
        tmp_path,
        [
            {
                "canonical_id": "widget:0003-z",
                "title": "W3",
                "source_path": "authored/widget.yaml",
                "evidence_refs": ["paper:p1"],
                "content": "authored prose",
            }
        ],
    )
    load_project_sources(tmp_path)

    row = next(m for m in seen if m.get("id") == "widget:0003-z")
    assert row["id"] == "widget:0003-z"
    assert "canonical_id" not in row
    assert row["file_path"] == "authored/widget.yaml"
    assert row["evidence_refs"] == ["paper:p1"]
    assert row["content"] == "authored prose"


def test_the_loaders_OWN_bookkeeping_keys_do_not_refuse_the_row(tmp_path: Path) -> None:
    # The control above passes only if `type`, `canonical_id`, `file_path` and the backfilled
    # `evidence_refs` are hidden from the composed schema -- each is refused by the hypothesis
    # profile, and the structured loader adds all four to every row.
    from science_tool.graph.sources import _STRUCTURED_INJECTED_KEYS

    assert {"type", "canonical_id", "file_path", "evidence_refs"} <= _STRUCTURED_INJECTED_KEYS
    assert not {"id", "kind", "title"} & _STRUCTURED_INJECTED_KEYS, (
        "id/kind/title are REQUIRED by the composed schema; hiding them refuses every record"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("content", "prose"), ("evidence_refs", ["paper:p1"])],
)
def test_an_AUTHORED_bookkeeping_key_is_still_refused(
    tmp_path: Path, field: str, value: object
) -> None:
    # These names are bookkeeping in some paths, but a structured-row author who writes either
    # authored it. The composed hypothesis schema must see and refuse it.
    _write_closed_kind_project(tmp_path, [{**_valid_hypothesis_row(), field: value}])
    with pytest.raises(ValueError, match="does not satisfy its schema"):
        load_project_sources(tmp_path)


def test_build_validates_a_closed_kind_before_projecting(tmp_path) -> None:
    # The load-bearing order. `hypothesis` is the one closed kind on this branch, so it is what
    # can demonstrate refusal at all.
    #
    # `ValueError`, not EntityValidationError: `validate_against_schema` CATCHES the model-layer
    # EntityValidationError and re-raises a ValueError carrying the path and the pinned
    # generation (sources.py:1431, moved in Step 3). Asserting the inner type would fail.
    registry, project_schema = _armed_registry(tmp_path)
    with pytest.raises(ValueError, match="does not satisfy its schema"):
        registry.build(
            "hypothesis",
            {**_valid_hypothesis_mapping(), "shadow_key": "v"},
            project_schema=project_schema,
            path="entities/hypotheses/0001-x.md",
            injected=frozenset(),
        )


def test_build_admits_a_valid_closed_kind(tmp_path) -> None:
    registry, project_schema = _armed_registry(tmp_path)
    entity = registry.build(
        "hypothesis",
        _valid_hypothesis_mapping(),
        project_schema=project_schema,
        path="entities/hypotheses/0001-x.md",
        injected=frozenset(),  # the mapping is entirely authored -- nothing to hide
        enrich=_enrich_projection_fields,
    )
    assert entity.kind == "hypothesis"


def test_build_does_not_validate_an_OPEN_kind(tmp_path) -> None:
    # Open kinds keep loading exactly as before -- this branch closes nothing. A shadow key on an
    # open kind is preserved, not refused; that is the `extra="allow"` projection doing its job.
    registry, project_schema = _armed_registry(tmp_path)
    kind = _an_open_kind()
    entity = registry.build(
        kind,
        {**_valid_open_kind_mapping(), "shadow_key": "v"},
        project_schema=project_schema,
        path=f"entities/{kind}/0001-x.md",
        injected=frozenset(),
        enrich=_enrich_projection_fields,
    )
    assert entity.kind == kind
