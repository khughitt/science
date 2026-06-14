from pathlib import Path

from click.testing import CliRunner

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.cli import main


def test_init_investigation_scaffolds_markdown_and_writes_no_graph(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["inquiry", "init", "i01-demo", "--label", "Demo", "--target", "hypothesis:h01",
         "--profile", "investigation", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    md = tmp_path / "entities" / "patches" / "i01-demo.md"
    assert md.exists()
    text = md.read_text()
    assert "patch_type: inquiry" in text
    assert "profile: investigation" in text
    assert not (tmp_path / "knowledge" / "graph.trig").exists()


def test_init_causal_requires_estimand(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["inquiry", "init", "i02", "--label", "C", "--target", "hypothesis:h01",
         "--profile", "causal", "--project-root", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "treatment" in result.output.lower() and "outcome" in result.output.lower()


def test_init_causal_scaffold_is_valid_when_estimand_given(tmp_path: Path):
    import yaml
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["inquiry", "init", "i03", "--label", "C", "--target", "hypothesis:h01",
         "--profile", "causal", "--treatment", "concept:drug", "--outcome", "concept:recovery",
         "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    text = (tmp_path / "entities" / "patches" / "i03.md").read_text()
    fm = yaml.safe_load(text.split("---")[1])
    PatchDefinitionEntity(**fm)


def test_add_node_is_retired():
    result = CliRunner().invoke(main, ["inquiry", "add-node", "i01-demo", "concept:x"])
    assert result.exit_code != 0
    assert "retired" in result.output.lower() and "graph build" in result.output.lower()


def test_set_estimand_is_retired():
    result = CliRunner().invoke(
        main, ["inquiry", "set-estimand", "i01", "--treatment", "concept:a", "--outcome", "concept:b"]
    )
    assert result.exit_code != 0 and "retired" in result.output.lower()


def test_import_writes_source_and_refuses_overwrite(tmp_path: Path):
    from rdflib import Dataset
    from science_tool.graph.inquiry_compile import emit_inquiry_views

    ds = Dataset()
    ent = PatchDefinitionEntity(
        id="patch-definition:i09", title="Imported", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={}, patch_type="inquiry",
        project="", ontology_terms=[], related=[], source_refs=[], content_preview="", file_path="entities/patches/i09.md",
        inquiry={"profile": "investigation", "status": "specified",
                 "boundary_roles": [{"ref": "concept:x", "role": "BoundaryIn"}],
                 "flow_edges": [{"subject": "concept:x", "predicate": "feedsInto",
                                 "object": "concept:y", "claim_refs": ["proposition:p1"]}]},
    )
    emit_inquiry_views(ds, [ent])
    graph_dir = tmp_path / "knowledge"
    graph_dir.mkdir(parents=True)
    trig = graph_dir / "graph.trig"
    ds.serialize(destination=str(trig), format="trig")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["inquiry", "import", "i09", "--project-root", str(tmp_path), "--path", str(trig)],
    )
    assert result.exit_code == 0, result.output
    dest = tmp_path / "entities" / "patches" / "i09.md"
    assert dest.exists()
    import yaml
    fm = yaml.safe_load(dest.read_text().split("---")[1])
    loaded = PatchDefinitionEntity(**fm)
    assert loaded.patch_type == "inquiry"
    assert loaded.inquiry.profile == "investigation"
    assert loaded.inquiry.flow_edges[0].claim_refs == ["proposition:p1"]

    again = runner.invoke(main, ["inquiry", "import", "i09", "--project-root", str(tmp_path), "--path", str(trig)])
    assert again.exit_code != 0 and "force" in again.output.lower()
