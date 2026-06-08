from __future__ import annotations

from pathlib import Path

import yaml
from rdflib import Literal, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.graph.io import DCAT_NS, DCTERMS_NS
from science_tool.graph.materialize import _build_dataset_from_sources, _entity_uri
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS

_GOOD_HASH = "sha256:" + "a" * 64


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: proj\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def _datapackage(root: Path, slug: str, ident: str, *, with_url: bool) -> None:
    # MUST carry profiles: [science-pkg-entity-1.0] + id/type/title or DatapackageAdapter
    # never discovers it (storage_adapters/datapackage.py:74).
    pkg = root / "data" / slug
    pkg.mkdir(parents=True, exist_ok=True)
    resource: dict = {
        "name": "counts",
        "path": "counts.parquet",
        "hash": _GOOD_HASH,
        "bytes": 12345678,
        "format": "parquet",
    }
    if with_url:
        resource["source"] = {"type": "url", "ref": "https://example.org/counts.parquet"}
    doc = {
        "profiles": ["science-pkg-entity-1.0"],
        "name": slug,
        "id": ident,
        "type": "dataset",
        "title": ident,
        "origin": "external",
        "access": {"level": "public", "verified": False},
        "resources": [resource],
    }
    (pkg / "datapackage.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _datasets_graph(root: Path):
    sources = load_project_sources(root, include_commons=False)
    ds = _build_dataset_from_sources(sources)
    return ds.graph(PROJECT_NS["graph/datasets"])


def test_orphan_datapackage_resources_materialize_as_dcat(tmp_path: Path) -> None:
    _seed(tmp_path)
    _datapackage(tmp_path, "ds1", "dataset:ds1", with_url=True)
    g = _datasets_graph(tmp_path)

    dataset_uri = _entity_uri("dataset:ds1")
    distributions = list(g.objects(dataset_uri, DCAT_NS.distribution))
    assert len(distributions) == 1
    r = distributions[0]
    assert (r, RDF.type, DCAT_NS.Distribution) in g
    assert (r, RDF.type, PROV.Entity) in g
    assert (r, DCTERMS_NS.identifier, Literal("counts")) in g
    assert (r, DCTERMS_NS["format"], Literal("parquet")) in g
    assert (r, SCI_NS.resourceHash, Literal(_GOOD_HASH)) in g
    assert (r, DCAT_NS.downloadURL, URIRef("https://example.org/counts.parquet")) in g
    # dcat:byteSize present as an integer literal
    assert any(int(o) == 12345678 for o in g.objects(r, DCAT_NS.byteSize))


def test_deferred_owner_datapackage_resources_materialize(tmp_path: Path) -> None:
    # a real markdown owner + a sibling datapackage that DEFERS to it (Phase 1.5):
    # resources still materialize about the dataset entity.
    _seed(tmp_path)
    md = tmp_path / "entities" / "datasets" / "ds1.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(
        '---\nid: "dataset:ds1"\ntype: "dataset"\ntitle: "DS1"\norigin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    _datapackage(tmp_path, "ds1", "dataset:ds1", with_url=False)
    g = _datasets_graph(tmp_path)

    dataset_uri = _entity_uri("dataset:ds1")
    distributions = list(g.objects(dataset_uri, DCAT_NS.distribution))
    assert len(distributions) == 1
    assert (distributions[0], DCTERMS_NS.identifier, Literal("counts")) in g


def test_dataset_without_datapackage_has_no_distribution(tmp_path: Path) -> None:
    _seed(tmp_path)
    md = tmp_path / "entities" / "datasets" / "ds2.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(
        '---\nid: "dataset:ds2"\ntype: "dataset"\ntitle: "DS2"\norigin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    g = _datasets_graph(tmp_path)
    assert list(g.objects(_entity_uri("dataset:ds2"), DCAT_NS.distribution)) == []
