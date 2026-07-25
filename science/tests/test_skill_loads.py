from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph
from rdflib import Literal as RDFLiteral
from rdflib.namespace import RDF
from science_model.entities import Entity, EntityType

from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.skill_loads import (
    SkillLoadRecord,
    SkillLoadValidationError,
    add_skill_load_record_to_graph,
    build_skill_load_records,
    canonicalize_skill_id,
    collect_skill_loads,
    load_skill_aliases,
    skill_load_node_uri,
    validate_skill_aliases,
    validate_skill_aliases_yaml,
)
from science_tool.graph.store import SCI_NS
from science_tool.graph.sources import load_project_sources

from _fixtures.entity_helpers import seed_project, write_markdown_entity


def test_add_record_emits_reified_triples() -> None:
    rec = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="why")
    graph = Graph()
    add_skill_load_record_to_graph(rec, graph)
    node = skill_load_node_uri(rec)
    # project_entity_uri("plan:0001-x") == PROJECT_NS["plan/0001-x"] (slash, slug lowercased) — the
    # same helper the emitter uses, so this asserts the emitter's exact plan URI, not a guess.
    plan = project_entity_uri("plan:0001-x")
    assert set(graph) == {
        (plan, SCI_NS.hasSkillLoad, node),
        (node, RDF.type, SCI_NS.SkillLoad),
        (node, SCI_NS.skill, SCI_NS["skill/driver-selection"]),
        (node, SCI_NS.loadReason, RDFLiteral("why")),
        (node, SCI_NS.usageSource, RDFLiteral("authored")),
    }


def test_registry_declares_skill_load_predicates() -> None:
    from science_tool.graph.store.constants import (
        GRAPH_EXPORT_EDGE_METADATA_PREDICATES,
        PREDICATE_REGISTRY,
    )

    declared = {entry["predicate"]: entry["layer"] for entry in PREDICATE_REGISTRY}
    for pred in ("sci:hasSkillLoad", "sci:skill", "sci:loadReason"):
        assert declared.get(pred) == "graph/provenance"
    assert SCI_NS.loadReason in GRAPH_EXPORT_EDGE_METADATA_PREDICATES
    assert SCI_NS.hasSkillLoad not in GRAPH_EXPORT_EDGE_METADATA_PREDICATES
    assert SCI_NS.skill not in GRAPH_EXPORT_EDGE_METADATA_PREDICATES


def test_identity_excludes_reason() -> None:
    a = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="one")
    b = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="two")
    assert skill_load_node_uri(a) == skill_load_node_uri(b)
    assert a.source == "authored"
    assert "reason" not in a.identity_payload()
    assert a.payload()["reason"] == "one"


def test_identity_distinguishes_plan_and_skill() -> None:
    base = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="r")
    other_skill = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="mutational-signatures-qa", reason="r")
    other_plan = SkillLoadRecord(plan_id="plan:0002-y", canonical_skill_id="driver-selection", reason="r")
    assert skill_load_node_uri(base) != skill_load_node_uri(other_skill)
    assert skill_load_node_uri(base) != skill_load_node_uri(other_plan)


def test_node_uri_is_under_project_skill_load_namespace() -> None:
    rec = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="r")
    assert "skill-load/" in str(skill_load_node_uri(rec))


def test_source_must_be_authored() -> None:
    with pytest.raises(ValueError, match="source must be 'authored'"):
        SkillLoadRecord(
            plan_id="plan:0001-x",
            canonical_skill_id="driver-selection",
            reason="r",
            source="imported",  # type: ignore[arg-type]
        )


def test_packaged_alias_table_loads() -> None:
    # The shipped table must parse and validate (it may be empty).
    assert isinstance(load_skill_aliases(), dict)


def test_validate_aliases_accepts_valid_map() -> None:
    assert validate_skill_aliases({"old-skill-name": "driver-selection"}) == {
        "old-skill-name": "driver-selection"
    }


def test_validate_aliases_rejects_chain() -> None:
    # A target that is itself a key is a chain (a -> b -> c); prohibited.
    with pytest.raises(SkillLoadValidationError, match="chain"):
        validate_skill_aliases({"a": "b", "b": "c"})


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "Bad-Case",
        "has_underscore",
        "a/b",
        "sci:skill/x",
        "-leading",
        "driver-selection\n",
    ],
)
def test_validate_aliases_rejects_non_grammar(bad: str) -> None:
    with pytest.raises(SkillLoadValidationError):
        validate_skill_aliases({bad: "driver-selection"})
    with pytest.raises(SkillLoadValidationError):
        validate_skill_aliases({"old-name": bad})


def test_validate_aliases_rejects_duplicate_keys() -> None:
    with pytest.raises(SkillLoadValidationError, match="duplicate"):
        validate_skill_aliases_yaml(
            "old-name: driver-selection\nold-name: mutational-signatures-qa\n"
        )


def test_validate_aliases_rejects_yaml_equivalent_duplicate_keys() -> None:
    # `yes:` and `true:` are different raw scalar TEXT but both resolve to `True`, so a
    # duplicate check comparing `key_node.value` misses the pair while `yaml.safe_load`
    # collapses it to a single last-wins entry. Comparing constructed objects catches it.
    with pytest.raises(SkillLoadValidationError, match="duplicate"):
        validate_skill_aliases_yaml("yes: driver-selection\ntrue: mutational-signatures-qa\n")


def test_validate_aliases_rejects_merge_key() -> None:
    with pytest.raises(SkillLoadValidationError, match="merge"):
        validate_skill_aliases_yaml(
            "<<: &base {old-name: driver-selection}\nold-name: other-skill\n"
        )


@pytest.mark.parametrize("text", ["", "null\n", "[]\n", "false\n", "0\n"])
def test_validate_aliases_yaml_rejects_falsey_non_mapping(text: str) -> None:
    # An empty document, null, an empty list, false, or 0 must fail — never coerce to an empty map.
    with pytest.raises(SkillLoadValidationError, match="mapping"):
        validate_skill_aliases_yaml(text)


def test_canonicalize_resolves_alias() -> None:
    assert canonicalize_skill_id("old-name", {"old-name": "driver-selection"}) == "driver-selection"


def test_canonicalize_passes_through_unknown() -> None:
    assert canonicalize_skill_id("driver-selection", {}) == "driver-selection"


@pytest.mark.parametrize(
    "bad", ["", "  ", "a/b", "sci:skill/x", "Bad", "driver-selection\n"]
)
def test_canonicalize_rejects_malformed_post_alias_id(bad: str) -> None:
    # A raw id absent from the table is treated as canonical -> must still be grammar-checked.
    with pytest.raises(SkillLoadValidationError):
        canonicalize_skill_id(bad, {})


def test_build_records_well_formed() -> None:
    records = build_skill_load_records(
        "plan:0001-x",
        [{"id": "driver-selection", "reason": "selection modeling"}],
        aliases={},
    )
    assert [(r.plan_id, r.canonical_skill_id, r.reason) for r in records] == [
        ("plan:0001-x", "driver-selection", "selection modeling")
    ]


def test_build_records_canonicalizes_via_alias() -> None:
    records = build_skill_load_records(
        "plan:0001-x",
        [{"id": "old-name", "reason": "r"}],
        aliases={"old-name": "driver-selection"},
    )
    assert records[0].canonical_skill_id == "driver-selection"


@pytest.mark.parametrize(
    "value",
    [
        "not-a-list",
        ["not-a-mapping"],
        [{"reason": "missing id"}],
        [{"id": "driver-selection"}],
        [{"id": 5, "reason": "non-string id"}],
        [{"id": "driver-selection", "reason": 5}],
        [{"id": "driver-selection", "reason": ""}],
        [{"id": "driver-selection", "reason": "   "}],
    ],
)
def test_build_records_rejects_malformed_shape(value: object) -> None:
    with pytest.raises(SkillLoadValidationError):
        build_skill_load_records("plan:0001-x", value, aliases={})


def test_build_records_rejects_literal_duplicate() -> None:
    with pytest.raises(SkillLoadValidationError, match="duplicate canonical"):
        build_skill_load_records(
            "plan:0001-x",
            [
                {"id": "driver-selection", "reason": "a"},
                {"id": "driver-selection", "reason": "b"},
            ],
            aliases={},
        )


def test_build_records_rejects_converging_aliases() -> None:
    # Two distinct raw ids that resolve to one canonical id collide.
    with pytest.raises(SkillLoadValidationError, match="duplicate canonical"):
        build_skill_load_records(
            "plan:0001-x",
            [
                {"id": "old-name", "reason": "a"},
                {"id": "driver-selection", "reason": "b"},
            ],
            aliases={"old-name": "driver-selection"},
        )


# Sentinel so `_plan()` (field ABSENT) is distinct from `_plan(None)` (field present, value null).
_ABSENT = object()


def _plan(skills_loaded: object = _ABSENT) -> Entity:
    extra = {} if skills_loaded is _ABSENT else {"skills_loaded": skills_loaded}
    return Entity(
        id="plan:0001-x",
        canonical_id="plan:0001-x",
        kind="plan",
        type=EntityType.PLAN,
        title="Plan",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/plans/0001-x.md",
        **extra,
    )


def test_collect_gen3_plan_with_skills_loaded() -> None:
    entity = _plan([{"id": "driver-selection", "reason": "r"}])
    records = collect_skill_loads([entity], generation=3, aliases={})
    assert [r.canonical_skill_id for r in records] == ["driver-selection"]


def test_collect_gen2_ignores_skills_loaded() -> None:
    entity = _plan([{"id": "driver-selection", "reason": "r"}])
    assert collect_skill_loads([entity], generation=2, aliases={}) == []
    assert collect_skill_loads([entity], generation=None, aliases={}) == []


def test_collect_gen3_rejects_explicit_null_skills_loaded() -> None:
    # An authored `skills_loaded: null` is PRESENT-but-malformed, not absent: it must hard-fail,
    # not be silently skipped. (getattr cannot see this; only model_extra membership can.)
    entity = _plan(None)
    with pytest.raises(SkillLoadValidationError):
        collect_skill_loads([entity], generation=3, aliases={})


def test_collect_ignores_non_plan_and_plans_without_field() -> None:
    plan_without = _plan()
    dataset = Entity(
        id="dataset:d1",
        canonical_id="dataset:d1",
        kind="dataset",
        type=EntityType.DATASET,
        title="D",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/datasets/d1.md",
        skills_loaded=[{"id": "driver-selection", "reason": "r"}],
    )
    assert collect_skill_loads([plan_without, dataset], generation=3, aliases={}) == []


def _source_project(tmp_path: Path, *, generation: int | None, skills_loaded: object) -> Path:
    seed_project(tmp_path)
    if generation is not None:
        science_yaml = tmp_path / "science.yaml"
        science_yaml.write_text(
            science_yaml.read_text(encoding="utf-8")
            + f"entity_schema_version: {generation}\n",
            encoding="utf-8",
        )
    write_markdown_entity(
        tmp_path,
        "entities/plans/0001-skills.md",
        {
            "id": "plan:0001-skills",
            "kind": "plan",
            "title": "Skill plan",
            "status": "draft",
            "skills_loaded": skills_loaded,
        },
        "Body.",
    )
    return tmp_path


def test_load_project_sources_collects_gen3_plan_skills_loaded(tmp_path: Path) -> None:
    project = _source_project(
        tmp_path,
        generation=3,
        skills_loaded=[{"id": "driver-selection", "reason": "model selection"}],
    )

    sources = load_project_sources(project, include_commons=False)

    assert [(record.plan_id, record.canonical_skill_id, record.reason) for record in sources.skill_loads] == [
        ("plan:0001-skills", "driver-selection", "model selection")
    ]


@pytest.mark.parametrize("generation", [2, None])
def test_load_project_sources_ignores_raw_malformed_skills_loaded_before_gen3(
    tmp_path: Path, generation: int | None
) -> None:
    project = _source_project(tmp_path, generation=generation, skills_loaded=None)

    sources = load_project_sources(project, include_commons=False)

    plan = next(entity for entity in sources.entities if entity.canonical_id == "plan:0001-skills")
    assert plan.model_extra is not None
    assert plan.model_extra["skills_loaded"] is None
    assert sources.skill_loads == []


def test_load_project_sources_rejects_gen3_null_skills_loaded(tmp_path: Path) -> None:
    project = _source_project(tmp_path, generation=3, skills_loaded=None)

    with pytest.raises(SkillLoadValidationError, match="skills_loaded must be a list"):
        load_project_sources(project, include_commons=False)
