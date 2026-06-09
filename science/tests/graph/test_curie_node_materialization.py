# tests/graph/test_curie_node_materialization.py
from __future__ import annotations

from pathlib import Path

import yaml
from rdflib import Literal, URIRef
from rdflib.namespace import PROV, RDF, SKOS

# Mirror tests/graph/test_paper_node_metadata.py (4b): build with
# _build_dataset_from_sources and read the named knowledge graph. NOTE:
# materialize_graph(project_root) takes a path and RETURNS a path (it writes the
# .trig), so it is NOT what these triple assertions want.
from science_tool.graph.materialize import PROJECT_NS, _build_dataset_from_sources, _entity_uri
from science_tool.graph.sources import load_project_sources

# `ontologies: [biology]` registers the `protein` kind (biolink:Protein, name=protein)
# AND declares its curie prefix `UniProtKB`, so (a) the row is not skipped as an
# unknown kind and (b) is_external_reference recognizes the curie -> the same_as
# edge materializes. A literal inline catalog does NOT work: _read_project_config
# coerces `ontologies` entries to strings (sources.py), so only NAMED catalogs load.
_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\nontologies:\n  - biology\n"


def _project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    src.joinpath("external_refs.yaml").write_text(
        yaml.safe_dump(
            {
                "references": [
                    {
                        "id": "protein:BCMA",
                        "type": "protein",
                        "title": "BCMA",
                        "primary_external_id": {
                            "source": "UniProtKB",
                            "id": "Q02223",
                            "curie": "UniProtKB:Q02223",
                            "provenance": "manual",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_curie_node_is_prov_entity_with_exactmatch_uriref(tmp_path: Path) -> None:
    _project(tmp_path)
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    ds = _build_dataset_from_sources(sources)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    bridge = ds.graph(PROJECT_NS["graph/bridge"])  # same_as external-term edges land here
    uri = _entity_uri("protein:BCMA")
    # (a) prov:Entity marking via the participation gate
    assert (uri, RDF.type, PROV.Entity) in knowledge
    # (b) curie cross-reference: skos:exactMatch to a URIRef (NOT a Literal)
    objs = list(bridge.objects(uri, SKOS.exactMatch))
    assert objs, "no skos:exactMatch emitted for the curie"
    assert all(isinstance(o, URIRef) for o in objs)
    assert not any(isinstance(o, Literal) for o in objs)


def test_owned_entity_with_curie_is_not_external_ref_but_still_exactmatches(tmp_path: Path) -> None:
    # An OWNED entity carrying the same-shaped curie must NOT get the external-ref
    # prov:Entity marking, yet its curie still materializes via same_as. Use a
    # `concept` owner: it has a markdown slug policy (entities/concepts), whereas
    # `protein` has no _BUILTIN_MARKDOWN_POLICIES entry so cannot be a markdown owner.
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    owners = tmp_path / "entities" / "concepts"
    owners.mkdir(parents=True, exist_ok=True)
    (owners / "bcma-marker.md").write_text(
        "---\nid: concept:bcma-marker\ntype: concept\ntitle: BCMA marker\n"
        "same_as: [UniProtKB:Q02223]\n---\n\nOwned concept that asserts a curie equivalence.\n",
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    ds = _build_dataset_from_sources(sources)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    bridge = ds.graph(PROJECT_NS["graph/bridge"])
    uri = _entity_uri("concept:bcma-marker")
    assert (uri, RDF.type, PROV.Entity) not in knowledge  # owned -> no external-ref marking
    assert list(bridge.objects(uri, SKOS.exactMatch))  # curie still emitted via same_as
