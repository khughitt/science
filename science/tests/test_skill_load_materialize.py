from __future__ import annotations

from rdflib.namespace import RDF

from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.materialize import build_dataset_from_sources
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write_gen3_project(root, *, skills_block: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\nentity_schema_version: 3\n",
        encoding="utf-8",
    )
    plans = root / "entities" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    (plans / "0001-demo.md").write_text(
        "---\n"
        "id: plan:0001-demo\n"
        "kind: plan\n"
        "title: Demo analysis plan\n"
        "status: active\n"
        f"{skills_block}"
        "---\n\nBody.\n",
        encoding="utf-8",
    )


_SKILLS = "skills_loaded:\n  - id: driver-selection\n    reason: selection modeling\n"


def _provenance(root):
    sources = load_project_sources(root)
    dataset = build_dataset_from_sources(sources)
    return sources, dataset.graph(PROJECT_NS["graph/provenance"])


def test_gen3_plan_materializes_skill_load_record(tmp_path) -> None:
    _write_gen3_project(tmp_path, skills_block=_SKILLS)
    _, provenance = _provenance(tmp_path)
    plan = project_entity_uri("plan:0001-demo")
    loads = list(provenance.objects(plan, SCI_NS.hasSkillLoad))
    assert len(loads) == 1
    node = loads[0]
    assert (node, RDF.type, SCI_NS.SkillLoad) in provenance
    assert (node, SCI_NS.skill, SCI_NS["skill/driver-selection"]) in provenance


def test_materialization_is_idempotent(tmp_path) -> None:
    _write_gen3_project(tmp_path, skills_block=_SKILLS)
    sources, first = _provenance(tmp_path)
    second = build_dataset_from_sources(sources).graph(PROJECT_NS["graph/provenance"])
    assert set(first) == set(second)


def test_gen2_plan_emits_no_skill_load(tmp_path) -> None:
    _write_gen3_project(tmp_path, skills_block=_SKILLS)
    sci = tmp_path / "science.yaml"
    sci.write_text(
        sci.read_text(encoding="utf-8").replace("entity_schema_version: 3", "entity_schema_version: 2"),
        encoding="utf-8",
    )
    sources, provenance = _provenance(tmp_path)
    assert sources.skill_loads == []
    assert not list(provenance.subjects(SCI_NS.hasSkillLoad, None))
