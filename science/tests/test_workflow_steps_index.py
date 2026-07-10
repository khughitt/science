from __future__ import annotations

from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import load_project_sources
from science_tool.workflow_steps_index import steps_and_methods_for_workflow


def _write(project_root, rel, frontmatter):
    p = project_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{frontmatter}\n---\n\nbody\n", encoding="utf-8")
    return p


def test_pairs_each_workflow_step_with_its_method(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "id: project:x\nname: X\nprofile: software\n", encoding="utf-8"
    )
    _write(tmp_path, "entities/workflows/wf.md", 'id: "workflow:wf"\nkind: "workflow"\ntitle: "WF"')
    _write(
        tmp_path,
        "entities/methods/cluster.md",
        'id: "method:cluster"\nkind: "method"\ntitle: "Cluster"\n'
        'stochasticity: "seedable"\nseed_params: ["random_state"]',
    )
    _write(
        tmp_path,
        "entities/workflow-steps/s1.md",
        'id: "workflow-step:s1"\nkind: "workflow-step"\ntitle: "S1"\n'
        'workflow: "workflow:wf"\nmethod: "method:cluster"',
    )
    _write(
        tmp_path,
        "entities/workflow-steps/s2.md",
        'id: "workflow-step:s2"\nkind: "workflow-step"\ntitle: "S2"\n'
        'workflow: "workflow:wf"\nmethod: "method:missing"',
    )

    sources = load_project_sources(tmp_path, strict_core_schema=False)
    resolver = ReferenceResolver.from_entities(
        sources.entities, manual_aliases=sources.manual_aliases
    )
    pairs = steps_and_methods_for_workflow(sources, resolver, "workflow:wf")

    assert [s.id for s, _m in pairs] == ["workflow-step:s1", "workflow-step:s2"]
    assert pairs[0][1] is not None and pairs[0][1].id == "method:cluster"
    assert pairs[1][1] is None  # method:missing does not resolve
