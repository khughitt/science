from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest

from science_tool import labnote_export as labnote_export_module
from science_tool.references import UnresolvedSemanticRefError
from science_tool.labnote_export import (
    _content_prose_semantic_records,
    _graph_semantic_records,
    _view_config_for_type,
    export_labnote_package,
)
from science_tool.labnote_view_contract import (
    PRODUCER_VIEW_SURFACES,
    VIEW_ID_RE,
    descriptor_errors,
    route_for_view,
)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(text).strip() + "\n", encoding="utf-8")


def write_minimal_project(root: Path) -> None:
    write_text(
        root / "science.yaml",
        """
        name: Post-Acute Infection Syndromes
        id: post-acute-infection
        last_modified: 2026-06-28
        labnote:
          label: PAIS
        """,
    )
    write_text(
        root / "papers" / "references.bib",
        """
        @article{Smith2020,
          author = {Smith, Jane and Doe, John},
          title = {Example immune persistence paper},
          journal = {Example Journal},
          year = {2020},
          doi = {10.1000/example}
        }
        """,
    )
    write_text(
        root / "entities" / "propositions" / "0001-example-proposition.md",
        """
        ---
        id: proposition:0001-example-proposition
        kind: proposition
        title: Example proposition
        status: active
        confidence: supported
        sensitivity: public
        discusses:
          - frame: synthesis:0001-example-synthesis
            role: mechanism
        ---
        # Story

        This public proposition cites [@Smith2020].

        # Evidence

        Evidence prose is preserved as a second section.
        """,
    )
    write_text(
        root / "entities" / "synthesis" / "0001-example-synthesis.md",
        """
        ---
        id: synthesis:0001-example-synthesis
        kind: synthesis
        title: Example synthesis
        status: active
        sensitivity: public
        ---
        Synthesis body text.
        """,
    )
    write_text(
        root / "entities" / "papers" / "internal-paper.md",
        """
        ---
        id: paper:internal-paper
        kind: paper
        title: Internal paper
        sensitivity: internal
        ---
        This record must not enter the public package.
        """,
    )
    write_text(
        root / "entities" / "papers" / "Smith2020.md",
        """
        ---
        id: paper:Smith2020
        kind: paper
        title: Example immune persistence paper
        sensitivity: public
        source_refs:
          - cite: Smith2020
        ---
        Public paper notes are citation-only in the Labnote v1 package.
        """,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_content_prose_semantic_records_harvest_entity_ref_records(tmp_path: Path) -> None:
    project_root = tmp_path / "natural-systems"
    write_text(
        project_root / "content" / "prose" / "primitives" / "diffusion.yml",
        """
        entityRef: prim:diffusion
        title: Diffusion
        summary: Spatial smoothing process.
        """,
    )
    write_text(
        project_root / "content" / "prose" / "parameters" / "pattern-wavelength.yaml",
        """
        entityRef: param:pattern-wavelength
        name: Pattern wavelength
        """,
    )

    records = _content_prose_semantic_records(project_root)

    assert records["prim:diffusion"].entity_type == "prim"
    assert records["prim:diffusion"].label == "Diffusion"
    assert records["prim:diffusion"].source_path == "content/prose/primitives/diffusion.yml"
    assert records["param:pattern-wavelength"].entity_type == "param"
    assert records["param:pattern-wavelength"].label == "Pattern wavelength"


def test_graph_semantic_records_harvest_canonical_graph_nodes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "natural-systems"
    write_text(project_root / "knowledge" / "graph.trig", "")
    monkeypatch.setattr(
        labnote_export_module,
        "export_graph_payload",
        lambda _path, overlays=None: SimpleNamespace(
            nodes=[
                SimpleNamespace(
                    id="https://science.local/entity/model/gray-scott",
                    label="Gray-Scott model",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        labnote_export_module,
        "canonical_id_from_entity_uri",
        lambda uri: "model:gray-scott" if uri.endswith("/model/gray-scott") else None,
    )

    records = _graph_semantic_records(project_root)

    assert records["model:gray-scott"].entity_type == "model"
    assert records["model:gray-scott"].label == "Gray-Scott model"
    assert records["model:gray-scott"].source_path == "knowledge/graph.trig"
    assert records["model:gray-scott"].is_public is False


def test_export_resolves_content_prose_entity_ref_with_dynamic_namespace(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "content" / "prose" / "genes" / "rbl1.yml",
        """
        entityRef: gene:RBL1
        title: RBL1
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-gene.md",
        """
        ---
        id: question:0001-gene
        kind: question
        title: Gene question
        sensitivity: public
        ---
        This points to [@gene:RBL1].
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")
    detail = prose["entities"]["question:0001-gene"]["sections"][0]["source_ref_details"][0]
    assert detail["id"] == "gene:RBL1"
    assert detail["entity_type"] == "gene"
    assert detail["resolution"] == "known_source_entity_not_exported"


def test_data_version_and_semantic_refs_hash_change_when_public_detail_changes(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    first_out = tmp_path / "first"
    second_out = tmp_path / "second"
    write_minimal_project(project_root)
    prose_path = project_root / "content" / "prose" / "primitives" / "diffusion.yml"
    write_text(
        prose_path,
        """
        entityRef: prim:diffusion
        title: Diffusion
        summary: Spatial smoothing process.
        family: transport
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-patterns.md",
        """
        ---
        id: question:0001-patterns
        kind: question
        title: Pattern formation
        sensitivity: public
        ---
        Pattern formation uses [@prim:diffusion].
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=first_out)
    first_project = read_json(first_out / "project.json")
    first_manifest = read_json(first_out / "manifest.json")
    first_resource = {item["name"]: item for item in first_manifest["resources"]}["semantic_refs"]

    write_text(
        prose_path,
        """
        entityRef: prim:diffusion
        title: Diffusion
        summary: Cross-gradient public transport process.
        family: patterning
        """,
    )
    export_labnote_package(project_root=project_root, out_dir=second_out)
    second_project = read_json(second_out / "project.json")
    second_manifest = read_json(second_out / "manifest.json")
    second_resource = {item["name"]: item for item in second_manifest["resources"]}["semantic_refs"]

    assert first_project["package"]["data_version"] != second_project["package"]["data_version"]
    assert first_resource["sha256"] != second_resource["sha256"]


def test_unreferenced_source_semantic_record_does_not_change_data_version_or_emit_bundle(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    first_out = tmp_path / "first"
    second_out = tmp_path / "second"
    write_minimal_project(project_root)
    prose_path = project_root / "content" / "prose" / "primitives" / "reaction.yml"
    write_text(
        prose_path,
        """
        entityRef: prim:reaction
        title: Reaction
        summary: Initial unreferenced detail.
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=first_out)
    write_text(
        prose_path,
        """
        entityRef: prim:reaction
        title: Reaction
        summary: Edited unreferenced detail.
        """,
    )
    export_labnote_package(project_root=project_root, out_dir=second_out)

    first_manifest = read_json(first_out / "manifest.json")
    second_manifest = read_json(second_out / "manifest.json")
    assert first_manifest["data_version"] == second_manifest["data_version"]
    assert not (first_out / "semantic_refs" / "index.json").exists()
    assert not (second_out / "semantic_refs" / "index.json").exists()
    assert "semantic_refs" not in {item["name"] for item in first_manifest["resources"]}
    assert "semantic_refs" not in {item["name"] for item in second_manifest["resources"]}


def test_unreferenced_graph_semantic_record_does_not_change_data_version_or_emit_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    first_out = tmp_path / "first"
    second_out = tmp_path / "second"
    graph_path = project_root / "knowledge" / "graph.trig"
    write_minimal_project(project_root)
    write_text(
        graph_path,
        """
        @prefix sci: <http://example.org/science/vocab/> .
        # initial graph-backed semantic label
        """,
    )
    monkeypatch.setattr(
        labnote_export_module,
        "export_graph_payload",
        lambda path, overlays=None: SimpleNamespace(
            nodes=[
                SimpleNamespace(
                    id="https://science.local/entity/model/unreferenced",
                    label="Edited model" if "edited" in path.read_text(encoding="utf-8") else "Initial model",
                )
            ],
            edges=[],
        ),
    )
    monkeypatch.setattr(
        labnote_export_module,
        "canonical_id_from_entity_uri",
        lambda uri: "model:unreferenced" if uri.endswith("/model/unreferenced") else None,
    )

    export_labnote_package(project_root=project_root, out_dir=first_out)
    write_text(
        graph_path,
        """
        @prefix sci: <http://example.org/science/vocab/> .
        # edited graph-backed semantic label
        """,
    )
    export_labnote_package(project_root=project_root, out_dir=second_out)

    first_manifest = read_json(first_out / "manifest.json")
    second_manifest = read_json(second_out / "manifest.json")
    assert first_manifest["data_version"] == second_manifest["data_version"]
    assert not (first_out / "semantic_refs" / "index.json").exists()
    assert not (second_out / "semantic_refs" / "index.json").exists()
    assert "semantic_refs" not in {item["name"] for item in first_manifest["resources"]}
    assert "semantic_refs" not in {item["name"] for item in second_manifest["resources"]}


def test_export_omits_semantic_refs_bundle_when_only_exported_semantic_refs_are_referenced(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "questions" / "0001-source.md",
        """
        ---
        id: question:0001-source
        kind: question
        title: Source question
        sensitivity: public
        ---
        This points to [@synthesis:0001-example-synthesis].
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    manifest = read_json(out / "manifest.json")
    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")
    assert not (out / "semantic_refs" / "index.json").exists()
    assert "semantic_refs" not in {item["name"] for item in manifest["resources"]}
    assert "features" not in prose


def test_export_omits_semantic_ref_feature_when_no_semantic_index_is_exported(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)

    export_labnote_package(project_root=project_root, out_dir=out)

    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")
    manifest = read_json(out / "manifest.json")
    assert not (out / "semantic_refs" / "index.json").exists()
    assert "semantic_refs" not in {item["name"] for item in manifest["resources"]}
    assert "features" not in prose


def test_export_resolves_content_prose_entity_ref_as_known_not_exported(tmp_path: Path) -> None:
    project_root = tmp_path / "natural-systems"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "content" / "prose" / "primitives" / "diffusion.yml",
        """
        entityRef: prim:diffusion
        title: Diffusion
        summary: Spatial smoothing process.
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-patterns.md",
        """
        ---
        id: question:0001-patterns
        kind: question
        title: Pattern formation
        sensitivity: public
        ---
        Pattern formation uses [@prim:diffusion].
        """,
    )

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")
    section = prose["entities"]["question:0001-patterns"]["sections"][0]
    assert prose["features"] == {"semantic_refs": "1"}
    assert section["semantic_refs"] == ["prim:diffusion"]
    assert section["source_refs"] == ["prim:diffusion"]
    assert section["source_ref_details"] == [
        {
            "id": "prim:diffusion",
            "kind": "semantic_ref",
            "label": "Diffusion",
            "entity_id": "prim:diffusion",
            "entity_type": "prim",
            "resolution": "known_source_entity_not_exported",
        }
    ]
    assert diagnostics["semantic_refs"]["known_source_entity_not_exported"] == 1
    assert diagnostics["semantic_refs"]["unknown_semantic_ref"] == 0


def test_export_fails_when_public_prose_references_graph_only_semantic_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(project_root / "knowledge" / "graph.trig", "")
    write_text(
        project_root / "entities" / "questions" / "0001-patterns.md",
        """
        ---
        id: question:0001-patterns
        kind: question
        title: Pattern formation
        sensitivity: public
        ---
        Pattern formation uses [@model:gray-scott].
        """,
    )
    monkeypatch.setattr(
        labnote_export_module,
        "export_graph_payload",
        lambda _path, overlays=None: SimpleNamespace(
            nodes=[
                SimpleNamespace(
                    id="https://science.local/entity/model/gray-scott",
                    label="Gray-Scott model",
                )
            ],
            edges=[],
        ),
    )
    monkeypatch.setattr(
        labnote_export_module,
        "canonical_id_from_entity_uri",
        lambda uri: "model:gray-scott" if uri.endswith("/model/gray-scott") else None,
    )

    with pytest.raises(ValueError, match="non-public semantic ref in exported prose: model:gray-scott"):
        export_labnote_package(project_root=project_root, out_dir=out)

    assert not (out / "semantic_refs" / "index.json").exists()


def test_content_prose_semantic_record_overrides_graph_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(project_root / "knowledge" / "graph.trig", "")
    write_text(
        project_root / "content" / "prose" / "models" / "gray-scott.yml",
        """
        entityRef: model:gray-scott
        title: Gray-Scott content model
        summary: Public content prose record.
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-patterns.md",
        """
        ---
        id: question:0001-patterns
        kind: question
        title: Pattern formation
        sensitivity: public
        ---
        Pattern formation uses [@model:gray-scott].
        """,
    )
    monkeypatch.setattr(
        labnote_export_module,
        "export_graph_payload",
        lambda _path, overlays=None: SimpleNamespace(
            nodes=[
                SimpleNamespace(
                    id="https://science.local/entity/model/gray-scott",
                    label="Gray-Scott graph model",
                )
            ],
            edges=[],
        ),
    )
    monkeypatch.setattr(
        labnote_export_module,
        "canonical_id_from_entity_uri",
        lambda uri: "model:gray-scott" if uri.endswith("/model/gray-scott") else None,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    detail = read_json(out / "semantic_refs" / "index.json")["semantic_refs"]["model:gray-scott"]
    assert detail["label"] == "Gray-Scott content model"
    assert detail["source_path"] == "content/prose/models/gray-scott.yml"


def test_export_writes_referenced_semantic_refs_bundle(tmp_path: Path) -> None:
    project_root = tmp_path / "natural-systems"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "content" / "prose" / "primitives" / "diffusion.yml",
        """
        entityRef: prim:diffusion
        title: Diffusion
        summary: Spatial smoothing process.
        aliases:
          - diffusive transport
        family: transport
        route: /internal/diffusion
        diagnostic: trace payload
        debug: enabled
        prompt: summarize diffusion
        owner: lab
        notes: internal notes
        private_note: do not export
        internal_detail: hidden
        sensitivity: public
        access:
          level: public
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-patterns.md",
        """
        ---
        id: question:0001-patterns
        kind: question
        title: Pattern formation
        sensitivity: public
        ---
        Pattern formation uses [@prim:diffusion].
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    bundle = read_json(out / "semantic_refs" / "index.json")
    manifest = read_json(out / "manifest.json")
    project = read_json(out / "project.json")
    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")
    detail = bundle["semantic_refs"]["prim:diffusion"]
    source_detail = prose["entities"]["question:0001-patterns"]["sections"][0]["source_ref_details"][0]
    resource = {item["name"]: item for item in manifest["resources"]}["semantic_refs"]

    assert bundle["contract"] == "science.semantic_refs"
    assert bundle["schema_version"] == "1"
    assert bundle["data_version"] == manifest["data_version"] == project["package"]["data_version"]
    assert detail == {
        "id": "prim:diffusion",
        "kind": "semantic_ref",
        "label": "Diffusion",
        "entity_type": "prim",
        "summary": "Spatial smoothing process.",
        "source_path": "content/prose/primitives/diffusion.yml",
        "resolution": "known_source_entity_not_exported",
        "aliases": ["diffusive transport"],
        "metadata": {"family": "transport"},
    }
    # Private metadata fields are not part of the public semantic ref contract.
    assert "private_note" not in detail
    for key in (
        "route",
        "diagnostic",
        "debug",
        "prompt",
        "owner",
        "notes",
        "private_note",
        "internal_detail",
        "sensitivity",
        "access",
    ):
        assert key not in detail["metadata"]
    assert "route" not in detail
    assert "route" not in source_detail
    assert resource["path"] == "semantic_refs/index.json"
    assert resource["kind"] == "bundle"
    assert resource["sensitivity"] == "public"
    assert isinstance(resource["bytes"], int) and resource["bytes"] > 0
    assert len(resource["sha256"]) == 64
    assert resource["media_type"] == "application/json"


@pytest.mark.parametrize(
    "record_metadata",
    [
        "sensitivity: internal",
        "access:\n  level: controlled",
    ],
)
def test_export_fails_when_public_prose_references_non_public_semantic_record(
    tmp_path: Path,
    record_metadata: str,
) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    indented_record_metadata = "\n".join(f"        {line}" for line in record_metadata.splitlines())
    write_minimal_project(project_root)
    write_text(
        project_root / "content" / "prose" / "primitives" / "diffusion.yml",
        f"""
        entityRef: prim:diffusion
        title: Diffusion
        summary: Internal spatial smoothing process.
{indented_record_metadata}
        internal_detail: restricted mechanism note
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-patterns.md",
        """
        ---
        id: question:0001-patterns
        kind: question
        title: Pattern formation
        sensitivity: public
        ---
        Pattern formation uses [@prim:diffusion].
        """,
    )

    with pytest.raises(ValueError, match="non-public semantic ref in exported prose: prim:diffusion"):
        export_labnote_package(project_root=project_root, out_dir=out)

    assert not (out / "semantic_refs" / "index.json").exists()


def test_failed_rerun_clears_stale_semantic_refs_bundle_when_record_becomes_non_public(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    prose_path = project_root / "content" / "prose" / "primitives" / "diffusion.yml"
    write_minimal_project(project_root)
    write_text(
        prose_path,
        """
        entityRef: prim:diffusion
        title: Diffusion
        summary: Spatial smoothing process.
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-patterns.md",
        """
        ---
        id: question:0001-patterns
        kind: question
        title: Pattern formation
        sensitivity: public
        ---
        Pattern formation uses [@prim:diffusion].
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)
    semantic_refs_path = out / "semantic_refs" / "index.json"
    assert semantic_refs_path.exists()

    write_text(
        prose_path,
        """
        entityRef: prim:diffusion
        title: Diffusion
        summary: Internal spatial smoothing process.
        sensitivity: internal
        """,
    )

    with pytest.raises(ValueError, match="non-public semantic ref in exported prose: prim:diffusion"):
        export_labnote_package(project_root=project_root, out_dir=out)

    assert not semantic_refs_path.exists()


def test_semantic_refs_bundle_excludes_exported_entities_and_unreferenced_records(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "content" / "prose" / "primitives" / "diffusion.yml",
        """
        entityRef: prim:diffusion
        title: Diffusion
        """,
    )
    write_text(
        project_root / "content" / "prose" / "primitives" / "reaction.yml",
        """
        entityRef: prim:reaction
        title: Reaction
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-source.md",
        """
        ---
        id: question:0001-source
        kind: question
        title: Source question
        sensitivity: public
        ---
        This points to [@prim:diffusion] and [@question:9999-later].
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "9999-later.md",
        """
        ---
        id: question:9999-later
        kind: question
        title: Later question
        sensitivity: public
        ---
        Later entity body.
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    bundle = read_json(out / "semantic_refs" / "index.json")
    assert set(bundle["semantic_refs"]) == {"prim:diffusion"}


def test_semantic_refs_bundle_scrubs_internal_paths_from_detail_fields(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "content" / "prose" / "primitives" / "diffusion.yml",
        """
        entityRef: prim:diffusion
        title: Diffusion /data/proj/private/label.txt
        summary: Private project path /data/proj/private/summary.txt.
        description: Derived project path ~/.claude/projects/private/note.md.
        source_hint: /data/proj/private/input.tsv
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-patterns.md",
        """
        ---
        id: question:0001-patterns
        kind: question
        title: Pattern formation
        sensitivity: public
        ---
        Pattern formation uses [@prim:diffusion].
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    bundle_text = (out / "semantic_refs" / "index.json").read_text(encoding="utf-8")
    detail = read_json(out / "semantic_refs" / "index.json")["semantic_refs"]["prim:diffusion"]
    assert "/data/proj" not in bundle_text
    assert "~/.claude/projects" not in bundle_text
    assert detail["label"] == "Diffusion [private path removed]"
    assert "[private path removed]" in detail["summary"]
    assert "[private path removed]" in detail["description"]
    assert detail["metadata"]["source_hint"] == "[private path removed]"


def test_semantic_refs_bundle_rejects_non_finite_public_metadata(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "content" / "prose" / "primitives" / "diffusion.yml",
        """
        entityRef: prim:diffusion
        title: Diffusion
        source_hint: .nan
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "0001-patterns.md",
        """
        ---
        id: question:0001-patterns
        kind: question
        title: Pattern formation
        sensitivity: public
        ---
        Pattern formation uses [@prim:diffusion].
        """,
    )

    with pytest.raises(ValueError, match="non-finite semantic ref metadata value"):
        export_labnote_package(project_root=project_root, out_dir=out)


def test_semantic_ref_to_later_discovered_entity_with_graph_record_gets_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(project_root / "knowledge" / "graph.trig", "")
    write_text(
        project_root / "entities" / "questions" / "0001-source.md",
        """
        ---
        id: question:0001-source
        kind: question
        title: Source question
        sensitivity: public
        ---
        This points to [@question:9999-later].
        """,
    )
    write_text(
        project_root / "entities" / "questions" / "9999-later.md",
        """
        ---
        id: question:9999-later
        kind: question
        title: Later question
        sensitivity: public
        ---
        Later entity body.
        """,
    )
    monkeypatch.setattr(
        labnote_export_module,
        "export_graph_payload",
        lambda _path, overlays=None: SimpleNamespace(
            nodes=[
                SimpleNamespace(
                    id="https://science.local/entity/question/9999-later",
                    label="Later question graph node",
                )
            ],
            edges=[],
        ),
    )
    monkeypatch.setattr(
        labnote_export_module,
        "canonical_id_from_entity_uri",
        lambda uri: "question:9999-later" if uri.endswith("/question/9999-later") else None,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")
    detail = prose["entities"]["question:0001-source"]["sections"][0]["source_ref_details"][0]
    assert detail == {
        "id": "question:9999-later",
        "kind": "semantic_ref",
        "label": "Later question",
        "entity_id": "question:9999-later",
        "entity_type": "question",
        "resolution": "resolved_exported_entity",
        "route": "/explore/question?id=question%3A9999-later",
    }


def test_export_fails_unknown_semantic_ref(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "questions" / "0001-source.md",
        """
        ---
        id: question:0001-source
        kind: question
        title: Source question
        sensitivity: public
        ---
        This points to [@prim:not-in-source-index].
        """,
    )

    with pytest.raises(UnresolvedSemanticRefError) as exc:
        export_labnote_package(project_root=project_root, out_dir=out)

    assert "prim:not-in-source-index" in exc.value.unresolved


def test_inline_paper_prefix_is_not_treated_as_semantic_ref(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "questions" / "0001-source.md",
        """
        ---
        id: question:0001-source
        kind: question
        title: Source question
        sensitivity: public
        ---
        Inline paper refs should use normal citekeys, so [@paper:Smith2020] is unsupported here.
        """,
    )

    with pytest.raises(Exception) as exc:
        export_labnote_package(project_root=project_root, out_dir=out)

    assert "paper:Smith2020" in str(exc.value)


def test_export_labnote_package_writes_public_package_contract(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    project = read_json(out / "project.json")
    manifest = read_json(out / "manifest.json")
    views = read_json(out / "views.json")
    entities = read_json(out / "entities" / "index.json")
    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")
    refs = read_json(out / "references" / "index.json")

    assert diagnostics["errors"] == []
    assert project["schema_version"] == "science-project-package.v1"
    assert project["project"]["id"] == "post-acute-infection"
    assert project["project"]["label"] == "PAIS"
    assert project["package"]["data_version"] == manifest["data_version"]
    assert manifest["data_version"].startswith("2026-06-28+")
    assert project["capabilities"] == {
        "entity_search": True,
        "findings": True,
        "graphs": False,
        "dataset_support": False,
        "quantitative_tables": False,
        "restricted_resources_present": True,
    }

    resource_by_name = {resource["name"]: resource for resource in manifest["resources"]}
    for name in (
        "project.json",
        "views.json",
        "references",
        "entities",
        "entity_prose",
        "entity_links",
        "export_diagnostics",
    ):
        assert name in resource_by_name
        resource = resource_by_name[name]
        assert resource["kind"] in {"bundle", "descriptor"}
        assert resource["sensitivity"] == "public"
        assert isinstance(resource["bytes"], int) and resource["bytes"] > 0
        assert len(resource["sha256"]) == 64
        assert resource["media_type"] == "application/json"

    exported_ids = {entity["id"] for entity in entities["entities"]}
    assert exported_ids == {
        "proposition:0001-example-proposition",
        "synthesis:0001-example-synthesis",
    }
    assert "paper:Smith2020" not in exported_ids
    proposition = next(e for e in entities["entities"] if e["type"] == "proposition")
    assert proposition["class"] == "epistemic"
    assert proposition["display_name"] == "Example proposition"
    assert proposition["route"] is None
    assert proposition["source_path"] == "entities/propositions/0001-example-proposition.md"

    assert prose["contract"] == "science.entity_prose"
    assert prose["schema_version"] == "1"
    sections = prose["entities"]["proposition:0001-example-proposition"]["sections"]
    assert [section["key"] for section in sections] == ["story", "evidence"]
    assert "[@Smith2020]" in sections[0]["markdown"]

    assert refs["contract"] == "science.references"
    assert refs["schema_version"] == "1"
    assert "Smith2020" in refs["references"]

    view_ids = [view["id"] for view in views["views"]]
    assert view_ids == ["proposition", "synthesis"]
    assert "paper" not in view_ids
    assert views["views"][0]["surface"] == "findings"
    assert views["views"][0]["route"] == "/findings/proposition"
    assert views["views"][0]["entity_types"] == ["proposition"]
    assert views["views"][1]["entity_types"] == ["synthesis"]


def test_export_labnote_package_uses_declared_kind_for_root_and_irregular_entity_types(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "research-question.md",
        """
        ---
        id: research-question:post-acute-infection-syndromes
        kind: research-question
        title: Why do some people fail to recover after acute infection?
        sensitivity: public
        ---
        Research question body.
        """,
    )
    write_text(
        project_root / "entities" / "patches" / "immune-state-shift-causal-landscape.md",
        """
        ---
        id: patch-definition:immune-state-shift-causal-landscape
        kind: patch-definition
        title: Immune-state-displacement causal landscape
        sensitivity: public
        ---
        Patch body.
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    entities = read_json(out / "entities" / "index.json")["entities"]
    views = read_json(out / "views.json")["views"]
    by_id = {entity["id"]: entity for entity in entities}
    view_by_id = {view["id"]: view for view in views}

    assert by_id["research-question:post-acute-infection-syndromes"]["type"] == "research_question"
    assert by_id["patch-definition:immune-state-shift-causal-landscape"]["type"] == "patch_definition"
    assert "entitie" not in view_by_id
    assert "patche" not in view_by_id
    assert view_by_id["research_question"]["route"] == "/explore/research-question"
    assert view_by_id["patch_definition"]["route"] == "/explore/patch-definition"


def test_export_labnote_package_requires_kind_for_root_entity_files(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "research-question.md",
        """
        ---
        id: research-question:post-acute-infection-syndromes
        title: Missing kind should fail
        sensitivity: public
        ---
        Body.
        """,
    )

    with pytest.raises(ValueError, match=r"root entity file requires frontmatter kind"):
        export_labnote_package(project_root=project_root, out_dir=out)


def test_export_labnote_package_requires_kind_for_non_public_root_entity_files(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "internal-question.md",
        """
        ---
        id: research-question:internal
        title: Missing kind should fail before public filtering
        sensitivity: internal
        ---
        Body.
        """,
    )

    with pytest.raises(ValueError, match=r"root entity file requires frontmatter kind"):
        export_labnote_package(project_root=project_root, out_dir=out)


def test_export_strips_html_comments_from_prose_bundle(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "propositions" / "0001-example-proposition.md",
        """
        ---
        id: proposition:0001-example-proposition
        kind: proposition
        title: Example proposition
        status: active
        confidence: supported
        sensitivity: public
        discusses:
          - frame: synthesis:0001-example-synthesis
            role: mechanism
        ---
        # Story

        This public proposition cites [@Smith2020].

        <!-- Author note: cite as [@citekey] once the source lands. -->

        Inline HTML stays intact: `<!-- keep -->`.

        Double-backtick HTML stays intact: ``<!-- keep double -->``.

        Multiline inline HTML stays intact: `<!-- keep
        multiline -->`.

        ```html
        <!-- keep fenced -->
        ```

        ````markdown
        ```html
        <!-- keep nested fenced -->
        ```
        ````

        # Evidence

        Evidence prose is preserved as a second section.
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)
    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")["entities"]
    record = prose["proposition:0001-example-proposition"]

    assert "Author note" not in record["markdown"]
    assert "[@citekey]" not in record["markdown"]
    assert "[@Smith2020]" in record["markdown"]
    assert "`<!-- keep -->`" in record["markdown"]
    assert "``<!-- keep double -->``" in record["markdown"]
    assert "`<!-- keep\nmultiline -->`" in record["markdown"]
    assert "<!-- keep fenced -->" in record["markdown"]
    assert "<!-- keep nested fenced -->" in record["markdown"]
    for section in record["sections"]:
        assert "Author note" not in section["markdown"]


def test_export_labnote_package_scrubs_internal_paths_from_public_prose(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + """

        # Internal Handoff

        Private absolute path: `/mnt/ssd/Dropbox/natural-systems/.worktrees/example`.
        Private home path: `/home/keith/d/natural-systems/doc/private.md`.
        Private project path: `/data/proj/mm30/8.0/app_export`.
        Derived Claude project path: `~/.claude/projects/-mnt-ssd-Dropbox-natural-systems/memory/`.
        Dropbox integration is useful when discussing file-sync tools.
        """,
        encoding="utf-8",
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")["entities"]
    markdown = prose["proposition:0001-example-proposition"]["markdown"]
    assert "/mnt/ssd" not in markdown
    assert "/home/keith" not in markdown
    assert "/data/proj" not in markdown
    assert "-mnt-ssd-Dropbox-natural-systems" not in markdown
    assert "Dropbox integration is useful when discussing file-sync tools." in markdown
    assert "[private path removed]" in markdown


def test_export_labnote_package_fails_on_unresolved_public_citation(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("[@Smith2020]", "[@Missing2026]"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved citation"):
        export_labnote_package(project_root=project_root, out_dir=out)


def test_export_labnote_package_filters_non_public_access_levels(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "datasets" / "controlled.md",
        """
        ---
        id: dataset:controlled
        kind: dataset
        title: Controlled dataset
        access:
          level: controlled
        ---
        This dataset is not public.
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    entities = read_json(out / "entities" / "index.json")
    exported_ids = {entity["id"] for entity in entities["entities"]}
    assert "dataset:controlled" not in exported_ids
    assert read_json(out / "project.json")["capabilities"]["restricted_resources_present"] is True


def test_export_labnote_package_data_version_changes_with_exported_frontmatter(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "pais"
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_minimal_project(project_root)

    export_labnote_package(project_root=project_root, out_dir=first)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("title: Example proposition", "title: Renamed proposition"),
        encoding="utf-8",
    )
    export_labnote_package(project_root=project_root, out_dir=second)

    assert read_json(first / "manifest.json")["data_version"] != read_json(second / "manifest.json")["data_version"]


def test_export_labnote_package_fails_on_unresolved_source_ref_citation(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "sensitivity: public",
            "sensitivity: public\nsource_refs:\n  - cite: Missing2026",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved source_refs citation"):
        export_labnote_package(project_root=project_root, out_dir=out)


def test_export_labnote_package_fails_on_unresolved_string_source_ref_citation(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "sensitivity: public",
            "sensitivity: public\nsource_refs:\n  - cite:Missing2026",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved source_refs citation"):
        export_labnote_package(project_root=project_root, out_dir=out)


def test_export_labnote_package_exports_frontmatter_links_and_diagnostics(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    proposition_path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    proposition_path.write_text(
        proposition_path.read_text(encoding="utf-8").replace(
            "discusses:\n  - frame: synthesis:0001-example-synthesis\n    role: mechanism",
            """discusses:
  - synthesis:0001-example-synthesis
  - frame: synthesis:0001-example-synthesis
    role: mechanism
  - frame: dataset:gse-example
    role: unclear_custom_role
related:
  - method:example-method
  - dataset:gse-example
  - paper:internal-paper
  - interpretation:not-exported
relations:
  - predicate: cito:supports
    target: dataset:gse-example""",
        ),
        encoding="utf-8",
    )
    write_text(
        project_root / "entities" / "datasets" / "gse-example.md",
        """
        ---
        id: dataset:gse-example
        kind: dataset
        title: Example dataset
        sensitivity: public
        ---
        Dataset text.
        """,
    )
    write_text(
        project_root / "entities" / "methods" / "example-method.md",
        """
        ---
        id: method:example-method
        kind: method
        title: Example method
        sensitivity: public
        ---
        Method text.
        """,
    )

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)
    links = read_json(out / "links" / "index.json")

    assert links["contract"] == "science.entity_links"
    assert links["schema_version"] == "1"
    rows = {
        (
            row["source"],
            row["target"],
            row["predicate"],
            row["link_role"],
            row["finding_backlink"],
        )
        for row in links["links"]
    }
    assert (
        "proposition:0001-example-proposition",
        "synthesis:0001-example-synthesis",
        "cito:discusses",
        "related",
        True,
    ) in rows
    assert (
        "proposition:0001-example-proposition",
        "synthesis:0001-example-synthesis",
        "cito:discusses",
        "mechanism",
        True,
    ) in rows
    assert (
        "proposition:0001-example-proposition",
        "method:example-method",
        "skos:related",
        "related",
        False,
    ) in rows
    assert (
        "proposition:0001-example-proposition",
        "dataset:gse-example",
        "skos:related",
        "related",
        True,
    ) in rows
    assert (
        "proposition:0001-example-proposition",
        "dataset:gse-example",
        "cito:supports",
        "supports",
        True,
    ) in rows
    assert all(row["target"] != "paper:internal-paper" for row in links["links"])
    assert not any("paper:internal-paper" in warning["message"] for warning in diagnostics["warnings"])
    assert any(
        warning["message"] == "link target omitted because it is not exported" for warning in diagnostics["warnings"]
    )
    assert any("interpretation:not-exported" in warning["message"] for warning in diagnostics["warnings"])
    assert any("unclear_custom_role" in warning["message"] for warning in diagnostics["warnings"])


def test_export_labnote_package_warns_and_omits_links_to_unknown_entities(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "discusses:",
            "related:\n  - dataset:missing\ndiscusses:",
        ),
        encoding="utf-8",
    )

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)
    links = read_json(out / "links" / "index.json")

    assert all(row["target"] != "dataset:missing" for row in links["links"])
    assert any("dataset:missing" in warning["message"] for warning in diagnostics["warnings"])


def test_export_labnote_package_exports_knowledge_graph_links(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "knowledge" / "graph.trig",
        """
        @prefix cito: <http://purl.org/spar/cito/> .
        @prefix sci: <http://example.org/science/vocab/> .

        <http://example.org/project/graph/knowledge> {
          <http://example.org/project/proposition/0001-example-proposition>
            cito:supports
            <http://example.org/project/synthesis/0001-example-synthesis> .
          <http://example.org/project/proposition/0001-example-proposition>
            sci:synthesizes
            <http://example.org/project/synthesis/0001-example-synthesis> .
          <http://example.org/project/proposition/0001-example-proposition>
            sci:implements
            <http://example.org/project/synthesis/0001-example-synthesis> .
          <http://example.org/project/interpretation/not-exported>
            sci:synthesizes
            <http://example.org/project/synthesis/0001-example-synthesis> .
        }
        """,
    )

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)
    links = read_json(out / "links" / "index.json")

    rows = {
        (
            row["source"],
            row["target"],
            row["predicate"],
            row["link_role"],
            row["finding_backlink"],
        )
        for row in links["links"]
    }
    assert (
        "proposition:0001-example-proposition",
        "synthesis:0001-example-synthesis",
        "cito:supports",
        "supports",
        True,
    ) in rows
    assert (
        "proposition:0001-example-proposition",
        "synthesis:0001-example-synthesis",
        "sci:synthesizes",
        "synthesizes",
        True,
    ) in rows
    assert (
        sum(
            1
            for row in links["links"]
            if row["source"] == "proposition:0001-example-proposition"
            and row["target"] == "synthesis:0001-example-synthesis"
            and row["predicate"] == "sci:synthesizes"
            and row["link_role"] == "synthesizes"
        )
        == 1
    )
    assert not any(row["predicate"] == "sci:implements" for row in links["links"])
    skipped = [warning for warning in diagnostics["warnings"] if warning["message"].startswith("graph links skipped:")]
    assert len(skipped) == 1


def test_export_labnote_package_writes_links_in_stable_identity_order(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    synthesis_path = project_root / "entities" / "synthesis" / "0001-example-synthesis.md"
    synthesis_path.write_text(
        synthesis_path.read_text(encoding="utf-8").replace(
            "sensitivity: public",
            "sensitivity: public\ndiscusses:\n  - frame: proposition:0001-example-proposition\n    role: related",
        ),
        encoding="utf-8",
    )
    write_text(
        project_root / "knowledge" / "graph.trig",
        """
        @prefix cito: <http://purl.org/spar/cito/> .

        <http://example.org/project/graph/knowledge> {
          <http://example.org/project/proposition/0001-example-proposition>
            cito:supports
            <http://example.org/project/synthesis/0001-example-synthesis> .
        }
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    links = read_json(out / "links" / "index.json")["links"]
    identities = [(row["source"], row["target"], row["predicate"], row["link_role"]) for row in links]
    assert identities == sorted(identities)


def test_export_labnote_package_clears_stale_output_files(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = project_root / ".labnote" / "app_export"
    write_minimal_project(project_root)
    stale = out / "findings" / "index.json"
    write_text(stale, '{"findings": [{"id": "stale"}]}')

    export_labnote_package(project_root=project_root, out_dir=out)

    assert not stale.exists()
    assert (out / "manifest.json").exists()


def test_export_labnote_package_writes_incremental_export_stamp(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = project_root / ".labnote" / "app_export"
    write_minimal_project(project_root)

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    stamp = read_json(out / "export_stamp.json")
    assert diagnostics["skipped"] is False
    assert stamp["schema_version"] == "science.labnote_export_stamp.v1"
    assert stamp["source"]["strategy"] == "content"
    assert len(stamp["source"]["fingerprint"]) == 64
    assert stamp["exporter"]["name"] == "science.labnote_export"


def test_export_labnote_package_skips_when_incremental_stamp_matches(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = project_root / ".labnote" / "app_export"
    write_minimal_project(project_root)
    export_labnote_package(project_root=project_root, out_dir=out)
    stale = out / "stale.txt"
    write_text(stale, "preserved only when export is skipped")

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    assert diagnostics["skipped"] is True
    assert stale.exists()


def test_export_labnote_package_git_stamp_ignores_untracked_generated_output(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = project_root / ".labnote" / "app_export"
    write_minimal_project(project_root)
    subprocess.run(["git", "init"], cwd=project_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Science Test"], cwd=project_root, check=True)
    subprocess.run(["git", "config", "user.email", "science@example.test"], cwd=project_root, check=True)
    subprocess.run(["git", "add", "science.yaml", "papers", "entities"], cwd=project_root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=project_root, check=True, capture_output=True)

    export_labnote_package(project_root=project_root, out_dir=out)
    first_stamp = read_json(out / "export_stamp.json")
    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    assert first_stamp["source"]["strategy"] == "git"
    assert first_stamp["source"]["head"]
    assert diagnostics["skipped"] is True


def test_export_labnote_package_force_rebuild_ignores_matching_stamp(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = project_root / ".labnote" / "app_export"
    write_minimal_project(project_root)
    export_labnote_package(project_root=project_root, out_dir=out)
    stale = out / "stale.txt"
    write_text(stale, "removed by forced rebuild")

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out, force=True)

    assert diagnostics["skipped"] is False
    assert not stale.exists()


def test_export_labnote_package_rebuilds_when_source_fingerprint_changes(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = project_root / ".labnote" / "app_export"
    write_minimal_project(project_root)
    export_labnote_package(project_root=project_root, out_dir=out)
    first_stamp = read_json(out / "export_stamp.json")
    stale = out / "stale.txt"
    write_text(stale, "removed after source change")
    source = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    source.write_text(source.read_text(encoding="utf-8") + "\nAdditional public prose.\n", encoding="utf-8")

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    second_stamp = read_json(out / "export_stamp.json")
    assert diagnostics["skipped"] is False
    assert first_stamp["source"]["fingerprint"] != second_stamp["source"]["fingerprint"]
    assert not stale.exists()


def test_export_labnote_package_refuses_source_subtree_output_dir(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    write_minimal_project(project_root)
    source_path = project_root / "entities" / "propositions" / "0001-example-proposition.md"

    with pytest.raises(ValueError, match="refusing to clear output directory inside project source tree"):
        export_labnote_package(project_root=project_root, out_dir=project_root / "entities")

    assert source_path.exists()


def test_export_labnote_package_data_version_changes_with_graph_links(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_minimal_project(project_root)

    export_labnote_package(project_root=project_root, out_dir=first)
    write_text(
        project_root / "knowledge" / "graph.trig",
        """
        @prefix sci: <http://example.org/science/vocab/> .

        <http://example.org/project/graph/knowledge> {
          <http://example.org/project/proposition/0001-example-proposition>
            sci:synthesizes
            <http://example.org/project/synthesis/0001-example-synthesis> .
        }
        """,
    )
    export_labnote_package(project_root=project_root, out_dir=second)

    assert read_json(first / "manifest.json")["data_version"] != read_json(second / "manifest.json")["data_version"]


def test_science_labnote_export_cli_writes_package(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)

    result = CliRunner().invoke(
        main,
        ["labnote", "export", "--project-root", str(project_root), "--out", str(out)],
    )

    assert result.exit_code == 0, result.output
    assert (out / "project.json").exists()
    assert (out / "manifest.json").exists()
    assert "Exported Labnote package" in result.output


def test_science_labnote_export_cli_reports_skip_and_supports_force(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    runner = CliRunner()

    first = runner.invoke(main, ["labnote", "export", "--project-root", str(project_root), "--out", str(out)])
    second = runner.invoke(main, ["labnote", "export", "--project-root", str(project_root), "--out", str(out)])
    forced = runner.invoke(
        main,
        ["labnote", "export", "--project-root", str(project_root), "--out", str(out), "--force"],
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert forced.exit_code == 0, forced.output
    assert "already up to date" in second.output
    assert "Exported Labnote package" in forced.output


def test_data_version_is_stable_golden(tmp_path: Path):
    write_minimal_project(tmp_path)
    out = tmp_path / ".labnote" / "app_export"
    export_labnote_package(project_root=tmp_path, out_dir=out)
    project = json.loads((out / "project.json").read_text())
    # Golden: exact digest must survive the project_package.core extraction byte-for-byte.
    # Re-pinned in Phase 1: the hidden-kind signature is now a version input, so this
    # fixture's declared-hidden `paper` moved the digest from 6cd94bebe752 exactly once.
    assert project["package"]["data_version"] == "2026-06-28+2785e828e187"


def test_science_labnote_export_cli_reports_expected_export_errors(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    project_root = tmp_path / "missing-config"
    project_root.mkdir()
    out = tmp_path / "out"

    result = CliRunner().invoke(
        main,
        ["labnote", "export", "--project-root", str(project_root), "--out", str(out)],
    )

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "missing science.yaml" in result.output
    assert "Traceback" not in result.output


PROMOTED_FALLBACK_KINDS = [
    "book",
    "citation",
    "concept",
    "discussion",
    "evidence_line",
    "finding",
    "inquiry",
    "interpretation",
    "meta",
    "observation",
    "paper_review",
    "patch_definition",
    "plan",
    "pre_registration",
    "prose_source",
    "report",
    "research_question",
    "spec",
    "theme",
    "topic",
]

RETAINED_EXPLICIT_KINDS = [
    "hypothesis",
    "proposition",
    "synthesis",
    "question",
    "dataset",
    "method",
    "search",
    "workflow",
    "workflow_run",
    "paper",
]


@pytest.mark.parametrize("entity_type", PROMOTED_FALLBACK_KINDS)
def test_promoted_fallback_kinds_are_permanent_visible_vocabulary(entity_type: str) -> None:
    assert entity_type in labnote_export_module.VIEW_VOCABULARY_BY_TYPE

    config = _view_config_for_type(entity_type, {})

    assert config["surface"] == "explore"
    assert config["label"] == entity_type.replace("_", " ").title()
    assert config["order"] == 500
    assert not config.get("hidden")
    assert route_for_view(entity_type, config["surface"]) == f"/explore/{entity_type.replace('_', '-')}"


@pytest.mark.parametrize(
    ("entity_type", "label", "order"),
    [("mechanism", "Mechanisms", 40), ("lead", "Leads", 50)],
)
def test_additional_finding_kinds_are_declared_on_the_findings_surface(
    entity_type: str, label: str, order: int
) -> None:
    config = _view_config_for_type(entity_type, {})

    assert config["surface"] == "findings"
    assert config["label"] == label
    assert config["order"] == order
    assert not config.get("hidden")
    assert route_for_view(entity_type, config["surface"]) == f"/findings/{entity_type}"


@pytest.mark.parametrize("entity_type", RETAINED_EXPLICIT_KINDS)
def test_existing_explicit_vocabulary_entries_are_retained(entity_type: str) -> None:
    assert entity_type in labnote_export_module.VIEW_VOCABULARY_BY_TYPE


def test_paper_stays_hidden_at_order_100() -> None:
    config = _view_config_for_type("paper", {})

    assert config["surface"] == "explore"
    assert config["label"] == "Papers"
    assert config["order"] == 100
    assert config["hidden"] is True


def test_vocabulary_declares_no_literal_routes() -> None:
    # Routes are derived output; a literal would let the vocabulary drift from the contract.
    for entity_type, entry in labnote_export_module.VIEW_VOCABULARY_BY_TYPE.items():
        assert "route" not in entry, entity_type


def test_vocabulary_ids_and_surfaces_satisfy_the_shared_contract() -> None:
    for entity_type, entry in labnote_export_module.VIEW_VOCABULARY_BY_TYPE.items():
        assert VIEW_ID_RE.match(entity_type), entity_type
        assert entry["surface"] in PRODUCER_VIEW_SURFACES, entity_type


def test_finding_types_include_mechanism_and_lead() -> None:
    assert labnote_export_module.FINDING_TYPES == {
        "hypothesis",
        "proposition",
        "synthesis",
        "mechanism",
        "lead",
    }


@pytest.mark.parametrize("entity_type", ["mechanism", "lead"])
def test_entity_class_map_declares_the_new_finding_kinds_explicitly(entity_type: str) -> None:
    # Explicit entries prevent vocabulary drift even though FINDING_TYPES currently
    # short-circuits these kinds before the class-map lookup.
    assert labnote_export_module.ENTITY_CLASS_BY_TYPE[entity_type] == "epistemic"


@pytest.mark.parametrize("entity_type", ["mechanism", "lead"])
def test_project_with_only_a_new_finding_kind_advertises_findings(
    tmp_path: Path, entity_type: str
) -> None:
    project_root = tmp_path / entity_type
    write_text(
        project_root / "science.yaml",
        f"""
        name: Only {entity_type}
        id: only-{entity_type}
        last_modified: 2026-06-28
        """,
    )
    write_text(
        project_root / "entities" / f"{entity_type}s" / f"0001-example-{entity_type}.md",
        f"""
        ---
        id: {entity_type}:0001-example-{entity_type}
        kind: {entity_type}
        title: Example {entity_type}
        sensitivity: public
        ---
        Body text.
        """,
    )
    out = tmp_path / "out"

    export_labnote_package(project_root=project_root, out_dir=out)

    project = read_json(out / "project.json")
    entities = read_json(out / "entities" / "index.json")["entities"]
    views = read_json(out / "views.json")["views"]

    assert project["capabilities"]["findings"] is True
    assert [record["class"] for record in entities] == ["epistemic"]
    assert [view["route"] for view in views] == [f"/findings/{entity_type}"]


@pytest.mark.parametrize("entity_type", ["mechanism", "lead"])
def test_backlink_classification_treats_new_finding_kinds_as_findings(entity_type: str) -> None:
    type_by_id = {
        "finding:a": entity_type,
        "question:b": "question",
        "workflow:c": "workflow",
    }

    assert labnote_export_module._finding_backlink(
        source_id="question:b", target_id="finding:a", backlink=True, type_by_id=type_by_id
    )
    assert labnote_export_module._finding_backlink(
        source_id="finding:a", target_id="question:b", backlink=True, type_by_id=type_by_id
    )
    assert not labnote_export_module._finding_backlink(
        source_id="finding:a", target_id="workflow:c", backlink=True, type_by_id=type_by_id
    )


def test_project_label_override_still_applies_to_a_known_kind() -> None:
    raw_config = {"labnote": {"views": {"question": {"label": "Open Questions", "order": 5}}}}

    config = _view_config_for_type("question", raw_config)

    assert config["label"] == "Open Questions"
    assert config["order"] == 5
    assert config["surface"] == "explore"


@pytest.mark.parametrize("key", ["surface", "route"])
def test_project_surface_and_route_overrides_are_rejected(key: str) -> None:
    raw_config = {"labnote": {"views": {"question": {key: "findings"}}}}

    with pytest.raises(ValueError, match=key):
        _view_config_for_type("question", raw_config)


def test_unknown_kind_may_only_be_declared_hidden() -> None:
    raw_config = {"labnote": {"views": {"talk": {"hidden": True}}}}

    config = _view_config_for_type("talk", raw_config)

    assert config["hidden"] is True


@pytest.mark.parametrize(
    "override",
    [{"hidden": False}, {"label": "Talks"}, {"order": 10}, {"hidden": True, "label": "Talks"}],
)
def test_unknown_kind_rejects_every_other_override(override: dict) -> None:
    raw_config = {"labnote": {"views": {"talk": override}}}

    with pytest.raises(ValueError, match="talk"):
        _view_config_for_type("talk", raw_config)


def _write_public_entity(project_root: Path, entity_type: str, slug: str, *, sensitivity: str = "public") -> None:
    write_text(
        project_root / "entities" / f"{entity_type}s" / f"{slug}.md",
        f"""
        ---
        id: {entity_type}:{slug}
        kind: {entity_type}
        title: {slug.replace('-', ' ').title()}
        sensitivity: {sensitivity}
        ---
        Body text for {slug}.
        """,
    )


def _hidden_kind_project(tmp_path: Path, name: str, extra_yaml: str = "") -> Path:
    project_root = tmp_path / name
    write_text(
        project_root / "science.yaml",
        f"""
        name: Hidden Kind Fixture
        id: {name}
        last_modified: 2026-06-28
        {extra_yaml}
        """,
    )
    return project_root


def test_unknown_kind_is_hidden_inventoried_and_warned(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(tmp_path, "unknown-kind")
    for index in range(1, 4):
        _write_public_entity(project_root, "talk", f"000{index}-example-talk")
    _write_public_entity(project_root, "question", "0001-example-question")
    out = tmp_path / "out"

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    entities = read_json(out / "entities" / "index.json")["entities"]
    views = read_json(out / "views.json")

    assert [record["type"] for record in entities] == ["question"]
    assert [view["id"] for view in views["views"]] == ["question"]
    assert views["hidden_kinds"] == [
        {"entity_type": "talk", "entity_count": 3, "reason": "fallback_hidden"}
    ]

    talk_warnings = [warning for warning in diagnostics["warnings"] if "talk" in warning["message"]]
    assert len(talk_warnings) == 1
    assert "fallback_hidden" in talk_warnings[0]["message"]
    assert "3" in talk_warnings[0]["message"]


def test_declared_hidden_kinds_are_inventoried_without_a_fallback_warning(tmp_path: Path) -> None:
    project_root = tmp_path / "declared-hidden"
    write_minimal_project(project_root)
    out = tmp_path / "out"

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    views = read_json(out / "views.json")

    assert {"entity_type": "paper", "entity_count": 1, "reason": "declared_hidden"} in views["hidden_kinds"]
    assert all(entry["reason"] != "fallback_hidden" for entry in views["hidden_kinds"])
    assert not [warning for warning in diagnostics["warnings"] if "paper" in warning["message"]]


def test_project_override_hiding_a_known_kind_is_declared_hidden(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(
        tmp_path,
        "override-hidden",
        extra_yaml="labnote:\n          views:\n            question:\n              hidden: true",
    )
    _write_public_entity(project_root, "question", "0001-example-question")
    _write_public_entity(project_root, "synthesis", "0001-example-synthesis")
    out = tmp_path / "out"

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    views = read_json(out / "views.json")

    assert views["hidden_kinds"] == [
        {"entity_type": "question", "entity_count": 1, "reason": "declared_hidden"}
    ]
    assert [view["id"] for view in views["views"]] == ["synthesis"]
    assert not [warning for warning in diagnostics["warnings"] if "question" in warning["message"]]


def test_unknown_kind_declared_hidden_by_the_project_is_not_fallback(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(
        tmp_path,
        "unknown-declared-hidden",
        extra_yaml="labnote:\n          views:\n            talk:\n              hidden: true",
    )
    _write_public_entity(project_root, "talk", "0001-example-talk")
    _write_public_entity(project_root, "question", "0001-example-question")
    out = tmp_path / "out"

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    views = read_json(out / "views.json")

    assert views["hidden_kinds"] == [
        {"entity_type": "talk", "entity_count": 1, "reason": "declared_hidden"}
    ]
    assert not [warning for warning in diagnostics["warnings"] if "talk" in warning["message"]]


def test_hidden_inventory_respects_the_public_boundary(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(tmp_path, "restricted-boundary")
    _write_public_entity(project_root, "talk", "0001-restricted-talk", sensitivity="internal")
    _write_public_entity(project_root, "future_kind", "0001-public-future")
    _write_public_entity(project_root, "future_kind", "0002-restricted-future", sensitivity="internal")
    _write_public_entity(project_root, "question", "0001-example-question")
    out = tmp_path / "out"

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    views = read_json(out / "views.json")
    descriptor_text = (out / "views.json").read_text(encoding="utf-8")
    warning_text = json.dumps(diagnostics["warnings"])

    assert views["hidden_kinds"] == [
        {"entity_type": "future_kind", "entity_count": 1, "reason": "fallback_hidden"}
    ]
    assert "0001-restricted-talk" not in descriptor_text
    assert "0002-restricted-future" not in descriptor_text
    assert "0001-restricted-talk" not in warning_text
    assert "0002-restricted-future" not in warning_text


def test_hidden_kinds_are_sorted_and_unique(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(
        tmp_path,
        "sorted-hidden",
        extra_yaml="labnote:\n          views:\n            zeta_kind:\n              hidden: true",
    )
    for entity_type in ("talk", "alpha_kind", "zeta_kind"):
        _write_public_entity(project_root, entity_type, f"0001-example-{entity_type}")
        _write_public_entity(project_root, entity_type, f"0002-example-{entity_type}")
    _write_public_entity(project_root, "question", "0001-example-question")
    out = tmp_path / "out"

    export_labnote_package(project_root=project_root, out_dir=out)

    hidden = read_json(out / "views.json")["hidden_kinds"]

    assert hidden == [
        {"entity_type": "alpha_kind", "entity_count": 2, "reason": "fallback_hidden"},
        {"entity_type": "talk", "entity_count": 2, "reason": "fallback_hidden"},
        {"entity_type": "zeta_kind", "entity_count": 2, "reason": "declared_hidden"},
    ]
    assert len({entry["entity_type"] for entry in hidden}) == len(hidden)


def test_exported_descriptor_satisfies_the_shared_structural_contract(tmp_path: Path) -> None:
    project_root = tmp_path / "contract-clean"
    write_minimal_project(project_root)
    out = tmp_path / "out"

    export_labnote_package(project_root=project_root, out_dir=out)

    assert descriptor_errors(read_json(out / "views.json")) == []


def test_structurally_invalid_descriptor_fails_the_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "contract-broken"
    write_minimal_project(project_root)
    out = tmp_path / "out"
    monkeypatch.setitem(
        labnote_export_module.VIEW_VOCABULARY_BY_TYPE, "synthesis", {"surface": "analysis", "label": "S", "order": 30}
    )

    with pytest.raises(ValueError, match="surface"):
        export_labnote_package(project_root=project_root, out_dir=out)


def test_filter_hidden_entities_helper_is_gone() -> None:
    assert not hasattr(labnote_export_module, "_filter_hidden_entities")


def _export_data_version(project_root: Path, out: Path) -> str:
    export_labnote_package(project_root=project_root, out_dir=out, force=True)
    return read_json(out / "project.json")["package"]["data_version"]


def test_data_version_changes_when_a_new_hidden_kind_appears(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(tmp_path, "hidden-version-a")
    _write_public_entity(project_root, "question", "0001-example-question")
    _write_public_entity(project_root, "talk", "0001-example-talk")

    first = _export_data_version(project_root, tmp_path / "out-1")
    _write_public_entity(project_root, "future_kind", "0001-example-future")
    second = _export_data_version(project_root, tmp_path / "out-2")

    assert first != second


def test_data_version_ignores_hidden_count_and_content_churn(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(tmp_path, "hidden-version-b")
    _write_public_entity(project_root, "question", "0001-example-question")
    _write_public_entity(project_root, "talk", "0001-example-talk")

    first = _export_data_version(project_root, tmp_path / "out-1")
    write_text(
        project_root / "entities" / "talks" / "0001-example-talk.md",
        """
        ---
        id: talk:0001-example-talk
        kind: talk
        title: Edited talk title
        sensitivity: public
        ---
        Rewritten body text.
        """,
    )
    _write_public_entity(project_root, "talk", "0002-second-talk")
    second = _export_data_version(project_root, tmp_path / "out-2")

    assert first == second


def test_data_version_ignores_restricted_entities_of_a_new_kind(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(tmp_path, "hidden-version-c")
    _write_public_entity(project_root, "question", "0001-example-question")

    first = _export_data_version(project_root, tmp_path / "out-1")
    _write_public_entity(project_root, "talk", "0001-restricted-talk", sensitivity="internal")
    second = _export_data_version(project_root, tmp_path / "out-2")

    assert first == second


def test_data_version_still_changes_when_a_visible_entity_changes(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(tmp_path, "hidden-version-d")
    _write_public_entity(project_root, "question", "0001-example-question")
    _write_public_entity(project_root, "talk", "0001-example-talk")

    first = _export_data_version(project_root, tmp_path / "out-1")
    write_text(
        project_root / "entities" / "questions" / "0001-example-question.md",
        """
        ---
        id: question:0001-example-question
        kind: question
        title: Edited question title
        sensitivity: public
        ---
        Rewritten visible body.
        """,
    )
    second = _export_data_version(project_root, tmp_path / "out-2")

    assert first != second


def test_hidden_kind_signature_hashes_only_type_and_reason(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(tmp_path, "hidden-version-e")
    _write_public_entity(project_root, "question", "0001-example-question")
    _write_public_entity(project_root, "talk", "0001-example-talk")
    export_labnote_package(project_root=project_root, out_dir=tmp_path / "out-1", force=True)

    baseline = read_json(tmp_path / "out-1" / "project.json")["package"]["data_version"]
    raw_config = labnote_export_module._load_raw_project_yaml(project_root)
    entities, _, _ = labnote_export_module._discover_entities(project_root, set())
    partition = labnote_export_module._partition_entities_for_views(entities, raw_config)

    # Same (entity_type, reason) pairs, different counts -> identical version.
    inflated = [dict(entry, entity_count=entry["entity_count"] + 99) for entry in partition.hidden_kinds]
    assert labnote_export_module._data_version(
        project_root,
        raw_config,
        partition.visible_entities,
        None,
        None,
        [(entry["entity_type"], entry["reason"]) for entry in inflated],
    ) == baseline

    # A different reason for the same kind -> different version.
    assert labnote_export_module._data_version(
        project_root,
        raw_config,
        partition.visible_entities,
        None,
        None,
        [(entry["entity_type"], "declared_hidden") for entry in partition.hidden_kinds],
    ) != baseline


def test_exporter_version_is_two() -> None:
    assert labnote_export_module.EXPORTER_VERSION == "2"


def test_export_stamped_by_the_previous_exporter_version_is_rebuilt(tmp_path: Path) -> None:
    # Nothing else in the stamp covers the Phase 1 descriptor change, so without the
    # version bump every existing .labnote/app_export would be skipped and keep
    # pre-Phase-1 output forever.
    project_root = tmp_path / "stale-stamp"
    write_minimal_project(project_root)
    out = tmp_path / ".labnote" / "app_export"
    export_labnote_package(project_root=project_root, out_dir=out)

    stale = read_json(out / "export_stamp.json")
    stale["exporter"]["version"] = "1"
    (out / "export_stamp.json").write_text(json.dumps(stale), encoding="utf-8")
    (out / "views.json").write_text(json.dumps({"views": []}), encoding="utf-8")

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    assert diagnostics["skipped"] is False
    assert read_json(out / "export_stamp.json")["exporter"]["version"] == "2"
    assert "hidden_kinds" in read_json(out / "views.json")


def test_export_stamped_by_the_current_exporter_version_is_skipped(tmp_path: Path) -> None:
    project_root = tmp_path / "current-stamp"
    write_minimal_project(project_root)
    out = tmp_path / ".labnote" / "app_export"
    export_labnote_package(project_root=project_root, out_dir=out)

    assert export_labnote_package(project_root=project_root, out_dir=out)["skipped"] is True


def test_entity_index_scrubs_internal_paths_from_nested_frontmatter(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "interpretations" / "0001-funnel.md",
        """
        ---
        id: interpretation:0001-funnel
        kind: interpretation
        title: Funnel from /data/proj/example/run.json
        summary: Derived from /mnt/ssd/example/summary.tsv in the pilot run.
        sensitivity: public
        aliases:
          - /data/proj/example/alias.md
        input: /data/proj/example/run.json
        tags:
          - /mnt/ssd/example/tag
        source_refs:
          - /home/keith/example/ref.md
        execution_trace:
          pinned_outputs:
            - /data/proj/example/pinned.jsonl
        ---
        Body text with no path.
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    index_path = out / "entities" / "index.json"
    index_text = index_path.read_text(encoding="utf-8")
    assert "/data/proj" not in index_text
    assert "/mnt/ssd" not in index_text
    assert "/home/keith" not in index_text

    row = next(
        entity
        for entity in read_json(index_path)["entities"]
        if entity["id"] == "interpretation:0001-funnel"
    )
    assert row["display_name"] == "Funnel from [private path removed]"
    assert row["summary"] == "Derived from [private path removed] in the pilot run."
    assert row["metadata"]["input"] == "[private path removed]"
    assert row["metadata"]["execution_trace"]["pinned_outputs"] == ["[private path removed]"]
    assert row["aliases"] == ["[private path removed]"]
    assert row["tags"] == ["[private path removed]"]
    assert row["source_refs"] == ["[private path removed]"]


SECTION_SEVEN_PROMOTED_KINDS = [
    ("decision", "Decisions", 110),
    ("analysis_plan", "Analysis Plans", 120),
    ("latent", "Latent Constructs", 130),
    ("paper_synthesis", "Paper Syntheses", 140),
    ("critique", "Critiques", 150),
    ("bias_audit", "Bias Audits", 160),
    ("review", "Reviews", 170),
]


@pytest.mark.parametrize(("entity_type", "label", "order"), SECTION_SEVEN_PROMOTED_KINDS)
def test_section_seven_kinds_are_visible_explore_vocabulary(entity_type: str, label: str, order: int) -> None:
    config = _view_config_for_type(entity_type, {})

    assert config["surface"] == "explore"
    assert config["label"] == label
    assert config["order"] == order
    assert not config.get("hidden")
    assert route_for_view(entity_type, config["surface"]) == (f"/explore/{entity_type.replace('_', '-')}")


@pytest.mark.parametrize(("entity_type", "_label", "_order"), SECTION_SEVEN_PROMOTED_KINDS)
def test_section_seven_kinds_declare_an_explicit_entity_class(entity_type: str, _label: str, _order: int) -> None:
    # Unmapped non-finding kinds fall back to "source" at labnote_export.py:865.
    # That fallback is invisible while a kind is hidden and wrong once promoted.
    assert labnote_export_module.ENTITY_CLASS_BY_TYPE[entity_type] == "epistemic"


@pytest.mark.parametrize(("entity_type", "_label", "_order"), SECTION_SEVEN_PROMOTED_KINDS)
def test_section_seven_kinds_are_not_in_the_fallback_compatibility_group(
    entity_type: str, _label: str, _order: int
) -> None:
    # PROMOTED_FALLBACK_TYPES means "served by the generic fallback before Phase 1"
    # and pins order 500. These kinds were fallback_hidden, which is the opposite.
    assert entity_type not in labnote_export_module.PROMOTED_FALLBACK_TYPES


def test_section_seven_orders_are_unique_and_sit_between_paper_and_the_fallback_block() -> None:
    orders = [order for _, _, order in SECTION_SEVEN_PROMOTED_KINDS]

    assert len(set(orders)) == len(orders)
    assert min(orders) > _view_config_for_type("paper", {})["order"]
    assert max(orders) < 500


def test_promoting_the_section_seven_kinds_empties_the_fallback_inventory(tmp_path: Path) -> None:
    project_root = _hidden_kind_project(tmp_path, "section-seven")
    for entity_type, _label, _order in SECTION_SEVEN_PROMOTED_KINDS:
        _write_public_entity(project_root, entity_type, f"0001-example-{entity_type}")
    out = tmp_path / "out"

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    views = read_json(out / "views.json")
    entities = read_json(out / "entities" / "index.json")["entities"]
    promoted = {entity_type for entity_type, _label, _order in SECTION_SEVEN_PROMOTED_KINDS}

    assert promoted.issubset({view["id"] for view in views["views"]})
    assert promoted.issubset({record["type"] for record in entities})
    assert all(record["class"] == "epistemic" for record in entities if record["type"] in promoted)
    assert [entry for entry in views["hidden_kinds"] if entry["reason"] == "fallback_hidden"] == []
    assert not [warning for warning in diagnostics["warnings"] if "fallback_hidden" in warning["message"]]
