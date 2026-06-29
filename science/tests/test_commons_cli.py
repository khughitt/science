"""Tests for science_tool.commons.cli."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.cli import commons_group


def test_init_creates_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "commons"))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "commons" / "datasets").is_dir()
    assert (tmp_path / "commons" / ".git").is_dir()


def test_init_force_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "commons"
    root.mkdir()
    (root / "stray.txt").write_text("hi")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["init", "--force"])
    assert result.exit_code == 0, result.output
    assert (root / "datasets").is_dir()


def test_index_rebuild_with_valid_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild"])
    assert result.exit_code == 0, result.output
    assert "indexed 5" in result.output
    assert (root / "registry.sqlite").is_file()


def test_index_rebuild_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["entities_indexed"] == 5
    assert payload["errors"] == []
    assert payload["duration_ms"] >= 0


def test_list_outputs_all_indexed_entities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    rebuild = runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["list", "--format", "json"])

    assert rebuild.exit_code == 0, rebuild.output
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [row["id"] for row in payload["rows"]] == [
        "dataset:cath-domains",
        "dataset:rnaseq-example",
        "paper:Adams2025",
        "theme:research-hygiene",
        "topic:single-cell-foundation-models",
    ]


def test_index_rebuild_exit_1_when_entity_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    # Drop in a bad paper. bibkey "bad-name" (hyphen) violates the paper-mixin
    # bibkey regex while filename/id/type stay mutually consistent.
    (root / "papers" / "badname.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:badname"\n'
        'type: "paper"\n'
        'title: "Bad"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "bad-name"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild"])
    assert result.exit_code == 1


def test_missing_store_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild"])
    assert result.exit_code == 1
    assert "commons store not found" in result.output


def _seeded_store(tmp_path: Path) -> Path:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    return root


def test_commons_inventory_to_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["inventory"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "2"
    assert payload["project_id"] == "commons"
    assert {e["id"] for e in payload["entities"]} == {
        "dataset:cath-domains",
        "dataset:rnaseq-example",
        "paper:Adams2025",
        "topic:single-cell-foundation-models",
        "theme:research-hygiene",
    }


def test_commons_inventory_to_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    output = tmp_path / "commons-inventory.json"
    runner = CliRunner()
    result = runner.invoke(commons_group, ["inventory", "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert result.output == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project_id"] == "commons"


def test_commons_inventory_missing_root_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["inventory"])
    assert result.exit_code == 1
    assert "commons store not found" in result.output


def test_show_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["show", "paper:Adams2025"])
    assert result.exit_code == 0, result.output
    assert "paper:Adams2025" in result.output
    assert "Adams, A." in result.output  # author from frontmatter


def test_show_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["show", "paper:Adams2025", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["canonical_id"] == "paper:Adams2025"
    assert payload["frontmatter"]["bibkey"] == "Adams2025"
    assert "commons_metadata" in payload


def test_show_missing_entity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["show", "paper:DoesNotExist"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower() or "failed" in result.output.lower()


def _write_reference_graph_member_commons(root: Path, data_root: Path) -> None:
    parent = root / "datasets" / "mondo-v1"
    parent.mkdir(parents=True)
    (parent / "entity.md").write_text(
        "---\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0\n"
        "id: dataset:mondo-v1\n"
        "type: dataset\n"
        "title: MONDO\n"
        "version: 1.0.0\n"
        "status: active\n"
        "created: '2026-05-31'\n"
        "updated: '2026-05-31'\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "source_class: reference\n"
        "access: {level: public, verified: true}\n"
        "graph_resource: graph\n"
        "graph_format: obograph_json\n"
        "member_key_space: {kind: curie, prefixes: [MONDO], resolution_status: resolved}\n"
        "node_index_resource: nodes\n"
        "edge_resource: edges\n"
        "member_count: 1\n"
        "edge_count: 1\n"
        "---\n",
        encoding="utf-8",
    )
    data_dir = data_root / "mondo-v1"
    data_dir.mkdir(parents=True)
    graph_text = '{"graphs":[]}\n'
    nodes_text = (
        "member_key,member_kind,label,status,replaced_by,dataset_usage\n"
        'MONDO:0005148,term,multiple myeloma,active,,"[]"\n'
    )
    edges_text = "subject,predicate,object,evidence,dataset_usage\n" 'MONDO:0005148,is_a,MONDO:0000001,,"[]"\n'
    (data_dir / "mondo.json").write_text(graph_text, encoding="utf-8")
    (data_dir / "nodes.csv").write_text(nodes_text, encoding="utf-8")
    (data_dir / "edges.csv").write_text(edges_text, encoding="utf-8")
    (parent / "datapackage.yaml").write_text(
        "resources:\n"
        "  - name: graph\n"
        "    path: mondo.json\n"
        f"    hash: sha256:{hashlib.sha256(graph_text.encode('utf-8')).hexdigest()}\n"
        "  - name: nodes\n"
        "    path: nodes.csv\n"
        f"    hash: sha256:{hashlib.sha256(nodes_text.encode('utf-8')).hexdigest()}\n"
        "  - name: edges\n"
        "    path: edges.csv\n"
        f"    hash: sha256:{hashlib.sha256(edges_text.encode('utf-8')).hexdigest()}\n",
        encoding="utf-8",
    )

    member = root / "datasets" / "mondo-0005148"
    member.mkdir(parents=True)
    (member / "entity.md").write_text(
        "---\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0\n"
        "id: dataset:mondo-0005148\n"
        "type: dataset\n"
        "title: MONDO 0005148\n"
        "version: 1.0.0\n"
        "status: active\n"
        "created: '2026-05-31'\n"
        "updated: '2026-05-31'\n"
        "origin: derived\n"
        "tier: use-now\n"
        "datapackage: virtual:member-of\n"
        "parent_dataset: dataset:mondo-v1\n"
        "derivation:\n"
        "  kind: member_of\n"
        "  parent_dataset: dataset:mondo-v1\n"
        "  member_key: MONDO:0005148\n"
        "member_kind: term\n"
        "label: multiple myeloma\n"
        "---\n",
        encoding="utf-8",
    )
    (member / "datapackage.yaml").write_text("resources: []\n", encoding="utf-8")


def test_member_payload_json_resolves_reference_graph_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "commons"
    data_root = tmp_path / "data"
    _write_reference_graph_member_commons(root, data_root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(data_root))

    runner = CliRunner()
    result = runner.invoke(commons_group, ["member-payload", "dataset:mondo-0005148", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["member_id"] == "dataset:mondo-0005148"
    assert payload["parent_dataset"] == "dataset:mondo-v1"
    assert payload["member_key"] == "MONDO:0005148"
    assert payload["payload_kind"] == "bio.reference_graph.member"
    assert payload["payload"]["node"]["label"] == "multiple myeloma"
    assert payload["payload"]["incident_edges"][0]["predicate"] == "is_a"


def test_reference_graph_scaffold_member_json_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "commons"
    data_root = tmp_path / "data"
    _write_reference_graph_member_commons(root, data_root)
    target = root / "datasets" / "mondo-0005148-scaffold" / "entity.md"
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(data_root))

    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        [
            "reference-graph",
            "scaffold-member",
            "dataset:mondo-v1",
            "MONDO:0005148",
            "--slug",
            "mondo-0005148-scaffold",
            "--date",
            "2026-06-28",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not target.exists()
    payload = json.loads(result.output)
    assert payload["applied"] is False
    assert payload["canonical_id"] == "dataset:mondo-0005148-scaffold"
    assert payload["entity_path"] == "datasets/mondo-0005148-scaffold/entity.md"
    frontmatter = payload["frontmatter"]
    assert frontmatter == {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        "id": "dataset:mondo-0005148-scaffold",
        "type": "dataset",
        "title": "multiple myeloma",
        "version": "1.0.0",
        "status": "active",
        "created": "2026-06-28",
        "updated": "2026-06-28",
        "origin": "derived",
        "tier": "use-now",
        "source_class": "reference",
        "parent_dataset": "dataset:mondo-v1",
        "datapackage": "virtual:member-of",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:mondo-v1",
            "member_key": "MONDO:0005148",
        },
        "member_kind": "term",
        "label": "multiple myeloma",
    }


def test_reference_graph_scaffold_member_apply_writes_valid_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "commons"
    data_root = tmp_path / "data"
    _write_reference_graph_member_commons(root, data_root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(data_root))

    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        [
            "reference-graph",
            "scaffold-member",
            "dataset:mondo-v1",
            "MONDO:0005148",
            "--slug",
            "mondo-0005148-scaffold",
            "--date",
            "2026-06-28",
            "--apply",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] is True
    member_dir = root / "datasets" / "mondo-0005148-scaffold"
    entity_text = (member_dir / "entity.md").read_text(encoding="utf-8")
    assert "schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0" in entity_text
    assert yaml.safe_load((member_dir / "datapackage.yaml").read_text(encoding="utf-8")) == {"resources": []}

    record = CommonsEntityAdapter(root).load("dataset:mondo-0005148-scaffold")
    assert record.frontmatter["derivation"]["member_key"] == "MONDO:0005148"
    resolved = runner.invoke(commons_group, ["member-payload", "dataset:mondo-0005148-scaffold", "--json"])
    assert resolved.exit_code == 0, resolved.output
    resolved_payload = json.loads(resolved.output)
    assert resolved_payload["payload"]["node"]["label"] == "multiple myeloma"


def test_reference_graph_resolve_member_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "commons"
    data_root = tmp_path / "data"
    _write_reference_graph_member_commons(root, data_root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(data_root))

    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        ["reference-graph", "resolve-member", "dataset:mondo-v1", "MONDO:0005148", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["registry_id"] == "dataset:mondo-v1"
    assert payload["member_key"] == "MONDO:0005148"
    assert payload["status"] == "active"
    assert payload["label"] == "multiple myeloma"
    assert payload["replaced_by"] == []


def test_find_default_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["find", "dataset"])
    assert result.exit_code == 0
    assert "dataset:cath-domains" in result.output
    assert "dataset:rnaseq-example" in result.output


def test_find_with_tag_and(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(
        commons_group, ["find", "dataset", "--tag", "rnaseq", "--tag", "bulk"]
    )
    assert result.exit_code == 0
    assert "dataset:rnaseq-example" in result.output
    assert "dataset:cath-domains" not in result.output


def test_find_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["find", "paper", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert payload[0]["canonical_id"] == "paper:Adams2025"


@pytest.mark.parametrize("entity_type", ["dataset", "paper", "topic", "theme"])
def test_find_warns_on_stale_registry_for_all_entity_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entity_type: str
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.delenv("SCIENCE_COMMONS_QUIET_STALE", raising=False)
    runner = CliRunner()
    rebuild = runner.invoke(commons_group, ["index", "rebuild"])
    assert rebuild.exit_code == 0, rebuild.output

    (root / "papers" / "Brown2026.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:Brown2026"\n'
        'type: "paper"\n'
        'title: "A second representative paper"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-06-29"\n'
        'updated: "2026-06-29"\n'
        'bibkey: "Brown2026"\n'
        'authors: ["Brown, B."]\n'
        "year: 2026\n"
        'journal: "Example Journal"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\n"
        "\n"
        "# A second representative paper\n",
        encoding="utf-8",
    )

    result = runner.invoke(commons_group, ["find", entity_type])

    assert result.exit_code == 0, result.output
    assert "warning: commons registry is stale" in result.stderr


def test_find_year_filter_only_for_papers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(
        commons_group, ["find", "dataset", "--year-from", "2020"]
    )
    assert result.exit_code != 0


def test_show_before_rebuild_exits_1_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Show must surface CommonsRegistryError as a clean exit-1 message,
    not a raw sqlite3.OperationalError traceback."""
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    # Note: no `index rebuild` invocation — registry.sqlite is absent.
    runner = CliRunner()
    result = runner.invoke(commons_group, ["show", "paper:Adams2025"])
    assert result.exit_code == 1
    assert "OperationalError" not in result.output
    assert (
        "registry" in result.output.lower()
        or "index rebuild" in result.output
    )


def test_validate_clean_store_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate"])
    assert result.exit_code == 0, result.output
    assert "checked 5 entities" in result.output


def test_validate_reports_per_entity_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    # bibkey "bad-name" (hyphen) violates the paper-mixin bibkey regex.
    (root / "papers" / "badname.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:badname"\n'
        'type: "paper"\n'
        'title: "Bad"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "bad-name"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate"])
    assert result.exit_code == 1
    assert "badname.md" in result.output


def test_validate_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["checked"] == 5
    assert payload["errors"] == []


def test_find_before_rebuild_exits_1_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["find", "paper"])
    assert result.exit_code == 1
    assert "OperationalError" not in result.output
    assert (
        "registry" in result.output.lower()
        or "index rebuild" in result.output
    )


def _seeded_store_with_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_name: str, fixture: str
) -> Path:
    """Seed the commons store + registry, register one overlay project, return root."""
    import shutil

    import yaml

    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder

    src = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(src, root)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()

    overlay_root = Path(__file__).parent / "fixtures" / "overlays" / fixture
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump(
            {
                "projects": [
                    {
                        "path": str(overlay_root),
                        "name": project_name,
                        "registered": "2026-05-14",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    return root


def test_show_project_human_merges_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["show", "paper:Adams2025", "--project", "proj-alpha"]
    )
    assert result.exit_code == 0, result.output
    assert "overlay:" in result.output
    assert "proj-alpha" in result.output
    assert "Project-Specific Notes" in result.output


def test_show_project_json_includes_overlay_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        ["show", "paper:Adams2025", "--project", "proj-alpha", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["canonical_id"] == "paper:Adams2025"
    assert payload["merged_frontmatter"]["hypothesis_links"] == ["H2", "H4"]
    assert payload["overlay"]["project"] == "proj-alpha"
    assert payload["overlay"]["overlay_path"] == "overlays/papers/Adams2025.md"
    assert payload["field_sources"]["tags"] == "canonical+overlay"


def test_show_project_with_no_overlay_for_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        ["show", "theme:research-hygiene", "--project", "proj-alpha", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["overlay"] is None


def test_show_unknown_project_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["show", "paper:Adams2025", "--project", "ghost"]
    )
    assert result.exit_code == 1
    assert "ghost" in result.output


def test_show_project_warns_on_inactive_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Add a pin_version to the proj-alpha paper overlay copy.
    import shutil

    import yaml

    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder

    src = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(src, root)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()

    proj = tmp_path / "proj-pinned"
    (proj / "overlays" / "papers").mkdir(parents=True)
    (proj / "overlays" / "papers" / "Adams2025.md").write_text(
        '---\nid: "paper:Adams2025"\noverlay_of: "paper:Adams2025"\n'
        'pin_version: "1.2.0"\nrelevance: "pinned"\n---\n\n## Notes\n',
        encoding="utf-8",
    )
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump(
            {
                "projects": [
                    {
                        "path": str(proj),
                        "name": "proj-pinned",
                        "registered": "2026-05-14",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["show", "paper:Adams2025", "--project", "proj-pinned"]
    )
    assert result.exit_code == 0, result.output
    assert "pin_version" in result.stderr
    assert "Phase E" in result.stderr


def test_validate_project_clean_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate", "--project", "proj-alpha"])
    assert result.exit_code == 0, result.output
    assert "checked 2" in result.output


def test_validate_project_broken_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-broken", "proj-broken")
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate", "--project", "proj-broken"])
    assert result.exit_code == 1
    assert "error" in result.output


def test_validate_project_with_type_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        ["validate", "--project", "proj-alpha", "--type", "paper"],
    )
    assert result.exit_code == 2
    assert "--project cannot be combined with --type" in result.output


_NO_DP_ENTITY = (
    "---\n"
    'schema_profile: "science-entity-base/1.0+dataset/1.0"\n'
    'id: "dataset:no-dp"\n'
    'type: "dataset"\n'
    'title: "No datapackage"\n'
    'version: "1.0.0"\n'
    'status: "active"\n'
    'created: "2026-05-13"\n'
    'updated: "2026-05-13"\n'
    'datapackage: "datapackage.yaml"\n'
    'origin: "external"\n'
    'tier: "use-now"\n'
    "access:\n"
    '  level: "public"\n'
    "  verified: true\n"
    '  source_url: "https://example.org"\n'
    "ontology_terms: []\n"
    "tags: []\n"
    "---\nbody\n"
)


def test_index_rebuild_reports_missing_datapackage_as_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    no_dp = root / "datasets" / "no-dp"
    no_dp.mkdir()
    (no_dp / "entity.md").write_text(_NO_DP_ENTITY, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["entities_indexed"] == 5
    assert any("no-dp" in err["path"] for err in payload["errors"])


def test_validate_reports_missing_datapackage_as_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    no_dp = root / "datasets" / "no-dp"
    no_dp.mkdir()
    (no_dp / "entity.md").write_text(_NO_DP_ENTITY, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert any("no-dp" in err["path"] for err in payload["errors"])
