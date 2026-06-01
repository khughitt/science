# MONDO Reference Graph Commons Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest a pinned MONDO release into `~/d/science-commons` as the first real `bio.reference_graph` commons dataset.

**Architecture:** Extend RG1's graph format vocabulary with `obograph_json`, then build a MONDO recipe that treats the pinned MONDO OBO Graph JSON release asset as the canonical graph artifact. The recipe writes RG1 projections: `nodes.csv` contains addressable `MONDO:` terms, including deprecated terms and `IAO:0100001` replacements; `edges.csv` contains directly incident MONDO edges and xref relations without collapsing them into identity.

**Tech Stack:** Python stdlib (`csv`, `hashlib`, `json`, `urllib.request`), `pyyaml`, existing `science_tool.commons` datapackage/resolver helpers, existing `bio.reference_graph` parser/validator/payload resolver.

---

## Source Decision

Current upstream state checked on 2026-05-31:

- Latest MONDO GitHub release is `v2026-05-05`, published 2026-05-05.
- Release assets include:
  - `mondo.json` (`103231823` bytes; `sha256:4b6ece0b965528fadbd578b98ac95f268e833f18f1827ec58d380b2ac652e95d`)
  - `mondo_nodes.tsv` (`sha256:38657fb00390b366612fa830daf486f39f627fede32a7a3cfe4b389eee91fc76`)
  - `mondo_edges.tsv` (`sha256:245109d54ebb9b89d35c0e3b7ff2d95580fa894635c70861cf9fb2b8b4c5b364`)
- `mondo.json` preserves deprecated-term replacement metadata in node `meta.basicPropertyValues` using `IAO:0100001`.
- `mondo_nodes.tsv` exposes `deprecated` but not replacement targets, so it is not sufficient for the RG1 node lifecycle contract.
- The `mondo.json` byte count and SHA-256 above were verified against the downloaded release asset before writing the lockfile recipe.
- A local preflight of the pinned `mondo.json` found 31,960 MONDO-prefixed nodes, no duplicate MONDO ids, 74 deprecated CLASS nodes with blank labels, and 2 MONDO-prefixed PROPERTY nodes. The recipe therefore filters to `type == "CLASS"`, hard-fails duplicate MONDO ids and blank active labels, and uses the member key as an explicit counted label fallback only for deprecated blank-label terms.
- BioOntologies remains useful as a future comparison path. Its current PyPI version is `0.7.4`, and its README describes converting OWL/OBO/Bioregistry inputs to OBO Graph JSON through ROBOT. Because MONDO already publishes OBO Graph JSON as a release asset, this plan does not add BioOntologies or a ROBOT/JVM dependency to the production recipe.

Primary source: `https://github.com/monarch-initiative/mondo/releases/download/v2026-05-05/mondo.json`.

## File Map

- Modify: `science/model/src/science_model/schemas/extension-bio-reference_graph-1.0.json`
  - Accept `graph_format: obograph_json`.
- Modify: `science/model/tests/test_bio_extension_reference_graph.py`
  - Cover `obograph_json` as a valid collection graph format.
- Modify: `science/src/science_tool/commons/reference_graph.py`
  - Add `obograph_json` to `REFERENCE_GRAPH_FORMATS`.
- Modify: `science/tests/test_commons_reference_graph.py`
  - Cover parser/constant support for `obograph_json`.
- Modify: `science/tests/validate/test_checks_reference_graphs.py`
  - Cover validation acceptance for `obograph_json`.
- Create: `~/d/science-commons/datasets/mondo/entity.md`
  - Canonical commons dataset record for `dataset:mondo`.
- Create: `~/d/science-commons/datasets/mondo/datapackage.yaml`
  - Hash-pinned resource descriptor.
- Create: `~/d/science-commons/datasets/mondo/recipe/fetch.py`
  - Fetch and verify pinned MONDO release assets.
- Create: `~/d/science-commons/datasets/mondo/recipe/build.py`
  - Build `nodes.csv`, `edges.csv`, and `build-summary.yaml` from `mondo.json`.
- Create: `~/d/science-commons/datasets/mondo/recipe/build_datapackage.py`
  - Render the commons datapackage with hashes and byte counts.
- Create: `~/d/science-commons/datasets/mondo/recipe/lockfile.yaml`
  - Pin `mondo.json` URL, digest, byte count, release tag, and release page.
- Create: `~/d/science-commons/datasets/mondo/recipe/README.md`
  - Operator rebuild instructions and source-path decision.
- Create: `~/d/science-commons/datasets/mondo/recipe/test_mondo_recipe.py`
  - Hermetic tests for extraction behavior.
- Modify: `docs/plans/2026-05-31-bio-reference-graph-design.md`
  - Mark RG4 as planned by this MONDO ingestion and mention `obograph_json`.
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`
  - Mark the real MONDO recipe as underway/implemented after the recipe lands.

## Task 1: Add `obograph_json` Graph Format Support

**Files:**
- Modify: `science/model/src/science_model/schemas/extension-bio-reference_graph-1.0.json`
- Modify: `science/model/tests/test_bio_extension_reference_graph.py`
- Modify: `science/src/science_tool/commons/reference_graph.py`
- Modify: `science/tests/test_commons_reference_graph.py`
- Modify: `science/tests/validate/test_checks_reference_graphs.py`

- [ ] **Step 1: Write failing schema and validator tests**

In `science/model/tests/test_bio_extension_reference_graph.py`, add:

```python
def test_reference_graph_accepts_obograph_json_format() -> None:
    EntityValidator().validate(_base_collection(graph_format="obograph_json"))
```

In `science/tests/test_commons_reference_graph.py`, add:

```python
from science_tool.commons.reference_graph import REFERENCE_GRAPH_FORMATS


def test_reference_graph_formats_include_obograph_json() -> None:
    assert "obograph_json" in REFERENCE_GRAPH_FORMATS
```

In `science/tests/validate/test_checks_reference_graphs.py`, add:

```python
def test_obograph_json_format_is_validated_as_supported_graph_artifact() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph(graph_format="obograph_json")],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={
                "dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]
            },
            edge_rows_by_dataset_id={"dataset:mondo": [_edge()]},
            member_datasets=[],
        )
    )

    assert results == []
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run --frozen --project science pytest \
  science/model/tests/test_bio_extension_reference_graph.py::test_reference_graph_accepts_obograph_json_format \
  science/tests/test_commons_reference_graph.py::test_reference_graph_formats_include_obograph_json \
  science/tests/validate/test_checks_reference_graphs.py::test_obograph_json_format_is_validated_as_supported_graph_artifact \
  -q
```

Expected: FAIL because `obograph_json` is not in the schema enum or `REFERENCE_GRAPH_FORMATS`.

- [ ] **Step 3: Implement format support**

In `science/model/src/science_model/schemas/extension-bio-reference_graph-1.0.json`, change:

```json
"graph_format": {"enum": ["rdf_turtle", "rdf_ntriples", "jsonl_edges"]},
```

to:

```json
"graph_format": {"enum": ["rdf_turtle", "rdf_ntriples", "jsonl_edges", "obograph_json"]},
```

In `science/src/science_tool/commons/reference_graph.py`, change:

```python
REFERENCE_GRAPH_FORMATS = frozenset({"rdf_turtle", "rdf_ntriples", "jsonl_edges"})
```

to:

```python
REFERENCE_GRAPH_FORMATS = frozenset({"rdf_turtle", "rdf_ntriples", "jsonl_edges", "obograph_json"})
```

- [ ] **Step 4: Run tests and confirm pass**

Run:

```bash
uv run --frozen --project science pytest \
  science/model/tests/test_bio_extension_reference_graph.py::test_reference_graph_accepts_obograph_json_format \
  science/tests/test_commons_reference_graph.py::test_reference_graph_formats_include_obograph_json \
  science/tests/validate/test_checks_reference_graphs.py::test_obograph_json_format_is_validated_as_supported_graph_artifact \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add \
  science/model/src/science_model/schemas/extension-bio-reference_graph-1.0.json \
  science/model/tests/test_bio_extension_reference_graph.py \
  science/src/science_tool/commons/reference_graph.py \
  science/tests/test_commons_reference_graph.py \
  science/tests/validate/test_checks_reference_graphs.py
git commit -m "feat(reference-graph): support OBO Graph JSON artifacts"
```

## Task 2: Create MONDO Recipe Tests

**Files:**
- Create: `~/d/science-commons/datasets/mondo/recipe/test_mondo_recipe.py`

- [ ] **Step 1: Create hermetic fixture tests**

Create `~/d/science-commons/datasets/mondo/recipe/test_mondo_recipe.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from build import (
    OBO_REPLACED_BY,
    build_mondo_tables,
    curie_or_iri,
    load_obograph,
)


def _fixture_graph() -> dict[str, object]:
    return {
        "graphs": [
            {
                "nodes": [
                    {
                        "id": "http://purl.obolibrary.org/obo/MONDO_0000001",
                        "lbl": "disease",
                        "type": "CLASS",
                    },
                    {
                        "id": "http://purl.obolibrary.org/obo/MONDO_0005148",
                        "lbl": "type 2 diabetes mellitus",
                        "type": "CLASS",
                        "meta": {
                            "xrefs": [{"val": "OMIM:125853"}, {"val": "NCIT:C26747"}],
                        },
                    },
                    {
                        "id": "http://purl.obolibrary.org/obo/MONDO_0008549",
                        "lbl": "obsolete thoracic dysostosis, isolated",
                        "type": "CLASS",
                        "meta": {
                            "deprecated": True,
                            "basicPropertyValues": [
                                {
                                    "pred": OBO_REPLACED_BY,
                                    "val": "http://purl.obolibrary.org/obo/MONDO_0979242",
                                }
                            ],
                        },
                    },
                    {
                        "id": "http://purl.obolibrary.org/obo/HP_0000001",
                        "lbl": "external phenotype",
                        "type": "CLASS",
                    },
                ],
                "edges": [
                    {
                        "sub": "http://purl.obolibrary.org/obo/MONDO_0005148",
                        "pred": "is_a",
                        "obj": "http://purl.obolibrary.org/obo/MONDO_0000001",
                    },
                    {
                        "sub": "http://purl.obolibrary.org/obo/MONDO_0005148",
                        "pred": "http://purl.obolibrary.org/obo/RO_0004024",
                        "obj": "http://purl.obolibrary.org/obo/GO_0034651",
                    },
                    {
                        "sub": "http://purl.obolibrary.org/obo/HP_0000001",
                        "pred": "is_a",
                        "obj": "http://purl.obolibrary.org/obo/MONDO_0000001",
                    },
                ],
            }
        ]
    }


def test_curie_or_iri_normalizes_obo_purls_only() -> None:
    assert curie_or_iri("http://purl.obolibrary.org/obo/MONDO_0005148") == "MONDO:0005148"
    assert curie_or_iri("http://purl.obolibrary.org/obo/RO_0004024") == "RO:0004024"
    assert curie_or_iri("http://identifiers.org/hgnc/10001") == "http://identifiers.org/hgnc/10001"


def test_load_obograph_requires_single_graph(tmp_path: Path) -> None:
    path = tmp_path / "mondo.json"
    path.write_text(json.dumps(_fixture_graph()), encoding="utf-8")

    graph = load_obograph(path)

    assert len(graph["nodes"]) == 4
    assert len(graph["edges"]) == 3


def test_build_mondo_tables_extracts_nodes_edges_xrefs_and_replacements() -> None:
    graph = _fixture_graph()["graphs"][0]

    tables = build_mondo_tables(graph)

    assert tables.nodes == [
        {
            "member_key": "MONDO:0000001",
            "member_kind": "term",
            "label": "disease",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        },
        {
            "member_key": "MONDO:0005148",
            "member_kind": "term",
            "label": "type 2 diabetes mellitus",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        },
        {
            "member_key": "MONDO:0008549",
            "member_kind": "term",
            "label": "obsolete thoracic dysostosis, isolated",
            "status": "deprecated",
            "replaced_by": "MONDO:0979242",
            "dataset_usage": "[]",
        },
    ]
    assert {
        (row["subject"], row["predicate"], row["object"])
        for row in tables.edges
    } == {
        ("MONDO:0005148", "is_a", "MONDO:0000001"),
        ("MONDO:0005148", "RO:0004024", "GO:0034651"),
        ("HP:0000001", "is_a", "MONDO:0000001"),
        ("MONDO:0005148", "xref", "OMIM:125853"),
        ("MONDO:0005148", "xref", "NCIT:C26747"),
    }
    assert tables.summary["member_count"] == 3
    assert tables.summary["status_counts"] == {"active": 2, "deprecated": 1, "withdrawn": 0}
    assert tables.summary["label_fallback_count"] == 0
    assert tables.summary["skipped_non_class_mondo_count"] == 0
    assert tables.summary["edge_count"] == 5


def test_build_mondo_tables_rejects_blank_active_mondo_label() -> None:
    graph = _fixture_graph()["graphs"][0]
    graph["nodes"][0]["lbl"] = ""

    with pytest.raises(ValueError, match="blank label"):
        build_mondo_tables(graph)


def test_build_mondo_tables_uses_counted_member_key_label_for_blank_deprecated_terms() -> None:
    graph = _fixture_graph()["graphs"][0]
    graph["nodes"][2]["lbl"] = ""

    tables = build_mondo_tables(graph)

    deprecated = [row for row in tables.nodes if row["member_key"] == "MONDO:0008549"][0]
    assert deprecated["label"] == "MONDO:0008549"
    assert tables.summary["label_fallback_count"] == 1


def test_build_mondo_tables_rejects_duplicate_mondo_ids() -> None:
    graph = _fixture_graph()["graphs"][0]
    graph["nodes"].append(dict(graph["nodes"][1]))

    with pytest.raises(ValueError, match="duplicate MONDO node"):
        build_mondo_tables(graph)


def test_build_mondo_tables_skips_mondo_non_class_nodes() -> None:
    graph = _fixture_graph()["graphs"][0]
    graph["nodes"].append(
        {
            "id": "http://purl.obolibrary.org/obo/MONDO_0100332",
            "lbl": "disease has primary infectious agent",
            "type": "PROPERTY",
        }
    )

    tables = build_mondo_tables(graph)

    assert "MONDO:0100332" not in {row["member_key"] for row in tables.nodes}
    assert tables.summary["skipped_non_class_mondo_count"] == 1
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd ~/d/science-commons/datasets/mondo/recipe
uv run --frozen --project ~/d/science/science pytest test_mondo_recipe.py -q
```

Expected: FAIL because `build.py` does not exist yet.

- [ ] **Step 3: Commit failing tests**

Run:

```bash
cd ~/d/science-commons
git add datasets/mondo/recipe/test_mondo_recipe.py
git commit -m "test(mondo): specify reference graph extraction"
```

## Task 3: Implement MONDO Build Logic

**Files:**
- Create: `~/d/science-commons/datasets/mondo/recipe/build.py`
- Modify: `~/d/science-commons/datasets/mondo/recipe/test_mondo_recipe.py`

- [ ] **Step 1: Create build implementation**

Create `~/d/science-commons/datasets/mondo/recipe/build.py`:

```python
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.config import resolve_commons_data_root

# science:code
# status: exploratory
# science:end

OBO_REPLACED_BY = "http://purl.obolibrary.org/obo/IAO_0100001"
_OBO_PURL = re.compile(r"^http://purl\.obolibrary\.org/obo/([A-Za-z][A-Za-z0-9]*)_(.+)$")


@dataclass(frozen=True, slots=True)
class MondoTables:
    nodes: list[dict[str, str]]
    edges: list[dict[str, str]]
    summary: dict[str, Any]


def curie_or_iri(value: object) -> str:
    text = str(value or "").strip()
    match = _OBO_PURL.fullmatch(text)
    if match is None:
        return text
    return f"{match.group(1)}:{match.group(2)}"


def load_obograph(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    graphs = raw.get("graphs") if isinstance(raw, dict) else None
    if not isinstance(graphs, list) or len(graphs) != 1 or not isinstance(graphs[0], dict):
        raise ValueError(f"{path}: expected OBO Graph JSON with exactly one graph")
    graph = graphs[0]
    if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        raise ValueError(f"{path}: expected graph.nodes and graph.edges lists")
    return graph


def _is_mondo_curie(value: str) -> bool:
    return value.startswith("MONDO:")


def _replacement_values(meta: dict[str, Any]) -> tuple[str, ...]:
    raw = meta.get("basicPropertyValues", [])
    if not isinstance(raw, list):
        return ()
    out: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict) or entry.get("pred") != OBO_REPLACED_BY:
            continue
        replacement = curie_or_iri(entry.get("val"))
        if replacement:
            out.append(replacement)
    return tuple(dict.fromkeys(out))


def _xref_values(meta: dict[str, Any]) -> tuple[str, ...]:
    raw = meta.get("xrefs", [])
    if not isinstance(raw, list):
        return ()
    out: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        val = str(entry.get("val") or "").strip()
        if val:
            out.append(val)
    return tuple(dict.fromkeys(out))


def build_mondo_tables(graph: dict[str, Any]) -> MondoTables:
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    status_counts = {"active": 0, "deprecated": 0, "withdrawn": 0}
    mondo_keys: set[str] = set()
    label_fallback_count = 0
    skipped_non_class_mondo_count = 0

    for node in graph["nodes"]:
        if not isinstance(node, dict):
            raise ValueError("node entry is not an object")
        member_key = curie_or_iri(node.get("id"))
        if not _is_mondo_curie(member_key):
            continue
        if node.get("type") != "CLASS":
            skipped_non_class_mondo_count += 1
            continue
        if member_key in mondo_keys:
            raise ValueError(f"duplicate MONDO node {member_key}")
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        status = "deprecated" if meta.get("deprecated") is True else "active"
        label = str(node.get("lbl") or "").strip()
        if not label:
            if status != "deprecated":
                raise ValueError(f"{member_key}: blank label")
            label = member_key
            label_fallback_count += 1
        replaced_by = _replacement_values(meta)
        nodes.append(
            {
                "member_key": member_key,
                "member_kind": "term",
                "label": label,
                "status": status,
                "replaced_by": ";".join(replaced_by),
                "dataset_usage": "[]",
            }
        )
        status_counts[status] += 1
        mondo_keys.add(member_key)
        for xref in _xref_values(meta):
            edges.append(
                {
                    "subject": member_key,
                    "predicate": "xref",
                    "object": xref,
                    "evidence": "",
                    "dataset_usage": "[]",
                }
            )

    for edge in graph["edges"]:
        if not isinstance(edge, dict):
            raise ValueError("edge entry is not an object")
        subject = curie_or_iri(edge.get("sub") or edge.get("subj"))
        predicate = curie_or_iri(edge.get("pred"))
        object_ = curie_or_iri(edge.get("obj"))
        if not subject or not predicate or not object_:
            raise ValueError("edge has blank subject, predicate, or object")
        if subject not in mondo_keys and object_ not in mondo_keys:
            continue
        edges.append(
            {
                "subject": subject,
                "predicate": predicate,
                "object": object_,
                "evidence": "",
                "dataset_usage": "[]",
            }
        )

    nodes.sort(key=lambda row: row["member_key"])
    edges.sort(key=lambda row: (row["subject"], row["predicate"], row["object"]))
    summary = {
        "member_count": len(nodes),
        "edge_count": len(edges),
        "status_counts": status_counts,
        "label_fallback_count": label_fallback_count,
        "skipped_non_class_mondo_count": skipped_non_class_mondo_count,
    }
    return MondoTables(nodes=nodes, edges=edges, summary=summary)


def write_tables(tables: MondoTables, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        output_dir / "nodes.csv",
        ["member_key", "member_kind", "label", "status", "replaced_by", "dataset_usage"],
        tables.nodes,
    )
    _write_csv(
        output_dir / "edges.csv",
        ["subject", "predicate", "object", "evidence", "dataset_usage"],
        tables.edges,
    )
    (output_dir / "build-summary.yaml").write_text(
        yaml.safe_dump(tables.summary, sort_keys=False),
        encoding="utf-8",
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def verify_entity(entity_path: Path, summary_path: Path) -> None:
    text = entity_path.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    entity = yaml.safe_load(frontmatter)
    summary = yaml.safe_load(summary_path.read_text(encoding="utf-8"))
    for key in ("member_count", "edge_count"):
        if entity.get(key) != summary.get(key):
            raise ValueError(f"{entity_path}: {key}={entity.get(key)!r} does not match build summary {summary.get(key)!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MONDO RG1 projections from OBO Graph JSON.")
    parser.add_argument("--source-json", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--verify-entity", type=Path)
    args = parser.parse_args()

    output_dir = args.output_dir or resolve_commons_data_root() / "mondo"
    source_json = args.source_json or output_dir / "_src" / "mondo.json"
    tables = build_mondo_tables(load_obograph(source_json))
    write_tables(tables, output_dir)
    if args.verify_entity is not None:
        verify_entity(args.verify_entity, output_dir / "build-summary.yaml")
    print(f"wrote {tables.summary['member_count']} MONDO nodes and {tables.summary['edge_count']} edges to {output_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run recipe tests and confirm pass**

Run:

```bash
cd ~/d/science-commons/datasets/mondo/recipe
uv run --frozen --project ~/d/science/science pytest test_mondo_recipe.py -q
```

Expected: PASS.

- [ ] **Step 3: Run RG parser tests against recipe output shape**

Run:

```bash
cd ~/d/science
uv run --frozen --project science pytest science/tests/test_commons_reference_graph.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
cd ~/d/science-commons
git add datasets/mondo/recipe/build.py datasets/mondo/recipe/test_mondo_recipe.py
git commit -m "feat(mondo): build reference graph projections"
```

## Task 4: Implement Pinned Fetch And Datapackage Rendering

**Files:**
- Create: `~/d/science-commons/datasets/mondo/recipe/fetch.py`
- Create: `~/d/science-commons/datasets/mondo/recipe/build_datapackage.py`
- Create: `~/d/science-commons/datasets/mondo/recipe/lockfile.yaml`
- Create: `~/d/science-commons/datasets/mondo/recipe/README.md`

- [ ] **Step 1: Create fetch script**

Create `~/d/science-commons/datasets/mondo/recipe/fetch.py`:

```python
from __future__ import annotations

import argparse
import hashlib
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml
from science_tool.commons.config import resolve_commons_data_root

# science:code
# status: exploratory
# science:end

LOCKFILE = {
    "mondo_release": "v2026-05-05",
    "release_page": "https://github.com/monarch-initiative/mondo/releases/tag/v2026-05-05",
    "files": {
        "mondo.json": {
            "url": "https://github.com/monarch-initiative/mondo/releases/download/v2026-05-05/mondo.json",
            "sha256": "sha256:4b6ece0b965528fadbd578b98ac95f268e833f18f1827ec58d380b2ac652e95d",
            "bytes": 103231823,
        }
    },
}


def fetch_sources(*, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = Path(__file__).with_name("lockfile.yaml")
    if not lock_path.exists():
        lock_path.write_text(yaml.safe_dump(LOCKFILE, sort_keys=False), encoding="utf-8")
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    for filename, entry in lock["files"].items():
        url = str(entry["url"])
        _reject_mutable_url(url)
        path = output_dir / filename
        if not path.exists():
            _download(url, path)
        digest, byte_count = _hash_file(path)
        if digest != entry["sha256"] or byte_count != entry["bytes"]:
            raise ValueError(f"{path}: hash/bytes mismatch against lockfile")
    return lock


def _reject_mutable_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError(f"MONDO source URL must be an https://github.com release asset, got {url!r}")
    if "/releases/latest/" in parsed.path or "/raw/" in parsed.path or "/refs/heads/" in parsed.path:
        raise ValueError(f"MONDO source URL is mutable; pin a release tag asset, got {url!r}")
    if "/releases/download/v" not in parsed.path:
        raise ValueError(f"MONDO source URL must use a versioned /releases/download/v.../ asset, got {url!r}")


def _download(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with urllib.request.urlopen(url) as response, tmp_path.open("wb") as fh:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            fh.write(chunk)
    tmp_path.replace(output_path)


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
            byte_count += len(chunk)
    return f"sha256:{digest.hexdigest()}", byte_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch pinned MONDO source artifacts.")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir or resolve_commons_data_root() / "mondo" / "_src"
    lock = fetch_sources(output_dir=output_dir)
    print(f"MONDO {lock['mondo_release']} sources verified in {output_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create datapackage renderer**

Create `~/d/science-commons/datasets/mondo/recipe/build_datapackage.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.config import resolve_commons_data_root
from science_tool.commons.datapackage import OUTPUT_ROOT_TOKEN, stream_sha256_and_bytes

# science:code
# status: exploratory
# science:end

RESOURCE_FILES = {
    "graph": "_src/mondo.json",
    "nodes": "nodes.csv",
    "edges": "edges.csv",
    "build_summary": "build-summary.yaml",
}


def build_datapackage_doc(data_dir: Path) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    for name, filename in RESOURCE_FILES.items():
        path = data_dir / filename
        sha256, byte_count = stream_sha256_and_bytes(path)
        resources.append(
            {
                "name": name,
                "path": filename,
                "format": "json" if filename.endswith(".json") else ("yaml" if filename.endswith(".yaml") else "csv"),
                "mediatype": _mediatype(filename),
                "source": {
                    "type": "local",
                    "ref": f"{OUTPUT_ROOT_TOKEN}/mondo/{filename}",
                },
                "hash": sha256,
                "bytes": byte_count,
            }
        )
    return {"name": "mondo", "resources": resources}


def _mediatype(filename: str) -> str:
    if filename.endswith(".json"):
        return "application/json"
    if filename.endswith(".yaml"):
        return "application/yaml"
    return "text/csv"


def render_datapackage_text(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render MONDO datapackage.yaml.")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output-path", type=Path)
    args = parser.parse_args()
    data_dir = args.data_dir or resolve_commons_data_root() / "mondo"
    output_path = args.output_path or Path(__file__).parent.parent / "datapackage.yaml"
    output_path.write_text(render_datapackage_text(build_datapackage_doc(data_dir)), encoding="utf-8")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create README**

Create `~/d/science-commons/datasets/mondo/recipe/README.md`:

```markdown
# MONDO Commons Recipe

This recipe builds `dataset:mondo`, the first real `bio.reference_graph` commons dataset.

The pinned source is MONDO release `v2026-05-05`:

`https://github.com/monarch-initiative/mondo/releases/download/v2026-05-05/mondo.json`

The production recipe uses the upstream OBO Graph JSON asset directly. BioOntologies is not a production dependency in this pass because MONDO already publishes OBO Graph JSON and the recipe needs release-pinned, hash-verified bytes without introducing a ROBOT/JVM conversion step.

The recipe defaults use `resolve_commons_data_root()`, which is `/data/science-commons` unless configured. The commands below pass `~/d/science-commons-data/mondo` explicitly so the build lands in durable local storage. Alternatively, set `SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data` before running the scripts without flags.

Run:

```bash
cd ~/d/science-commons/datasets/mondo
uv run --frozen --project ~/d/science/science python recipe/fetch.py --output-dir ~/d/science-commons-data/mondo/_src
uv run --frozen --project ~/d/science/science python recipe/build.py --source-json ~/d/science-commons-data/mondo/_src/mondo.json --output-dir ~/d/science-commons-data/mondo
uv run --frozen --project ~/d/science/science python recipe/build_datapackage.py --data-dir ~/d/science-commons-data/mondo --output-path datapackage.yaml
uv run --frozen --project ~/d/science/science python recipe/build.py --source-json ~/d/science-commons-data/mondo/_src/mondo.json --output-dir ~/d/science-commons-data/mondo --verify-entity entity.md
```

The node index includes active and deprecated MONDO terms. Deprecated terms remain addressable members; replacement targets from `IAO:0100001` are recorded in `nodes.csv.replaced_by` and are not auto-applied.

The edge table includes direct edges where either endpoint is a MONDO term plus node xrefs as `predicate=xref`. Xrefs are relations, not identity rewrites.
```

- [ ] **Step 4: Run fetch/build/datapackage smoke**

Run:

```bash
cd ~/d/science-commons/datasets/mondo
uv run --frozen --project ~/d/science/science python recipe/fetch.py --output-dir ~/d/science-commons-data/mondo/_src
uv run --frozen --project ~/d/science/science python recipe/build.py --source-json ~/d/science-commons-data/mondo/_src/mondo.json --output-dir ~/d/science-commons-data/mondo
uv run --frozen --project ~/d/science/science python recipe/build_datapackage.py --data-dir ~/d/science-commons-data/mondo --output-path datapackage.yaml
```

Expected:

- `~/d/science-commons-data/mondo/_src/mondo.json` exists and hash-verifies.
- `~/d/science-commons-data/mondo/nodes.csv` exists.
- `~/d/science-commons-data/mondo/edges.csv` exists.
- `~/d/science-commons-data/mondo/build-summary.yaml` has positive `member_count` and `edge_count`, plus `label_fallback_count: 74` and `skipped_non_class_mondo_count: 2` for the pinned release.
- `datapackage.yaml` has `graph`, `nodes`, `edges`, and `build_summary` resources with hashes and byte counts.
- The `graph` resource path is `_src/mondo.json`, so the commons data resolver checks the pinned source bytes in place.

- [ ] **Step 5: Commit**

Run:

```bash
cd ~/d/science-commons
git add \
  datasets/mondo/recipe/fetch.py \
  datasets/mondo/recipe/build_datapackage.py \
  datasets/mondo/recipe/lockfile.yaml \
  datasets/mondo/recipe/README.md \
  datasets/mondo/datapackage.yaml
git commit -m "feat(mondo): fetch pinned MONDO release"
```

## Task 5: Add Canonical `dataset:mondo` Commons Record

**Files:**
- Create: `~/d/science-commons/datasets/mondo/entity.md`
- Modify: `~/d/science-commons/datasets/mondo/datapackage.yaml`

- [ ] **Step 1: Read build summary values**

Run:

```bash
cd ~/d/science-commons
cat ~/d/science-commons-data/mondo/build-summary.yaml
```

Expected: the file contains integer `member_count` and `edge_count` keys plus
`status_counts.active`, `status_counts.deprecated`, and `status_counts.withdrawn`.
The exact counts are release-derived and must be copied mechanically into the
entity by the next step. For the pinned release, the summary also records the
expected non-fatal data-shape counts `label_fallback_count: 74` and
`skipped_non_class_mondo_count: 2`.

- [ ] **Step 2: Create entity frontmatter with exact counts**

Create `~/d/science-commons/datasets/mondo/entity.md` from the build summary:

```bash
cd ~/d/science-commons/datasets/mondo
uv run --frozen --project ~/d/science/science python -c '
from pathlib import Path
import yaml

summary = yaml.safe_load(Path("~/d/science-commons-data/mondo/build-summary.yaml").expanduser().read_text(encoding="utf-8"))
entity = f"""---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0
id: dataset:mondo
type: dataset
title: MONDO disease ontology reference graph
version: "1.0.0"
created: "2026-05-31"
updated: "2026-05-31"
tags: []
access:
  level: public
  availability: available
  verified: true
  verification_method: retrieved
datapackage: datapackage.yaml
graph_resource: graph
graph_format: obograph_json
member_key_space:
  kind: curie
  prefixes: [MONDO]
  resolution_status: resolved
node_index_resource: nodes
edge_resource: edges
member_count: {summary["member_count"]}
edge_count: {summary["edge_count"]}
license: CC-BY-4.0
origin: external
source_class: reference
status: active
tier: use-now
---
# MONDO disease ontology reference graph

Pinned MONDO release `v2026-05-05`, represented as a `bio.reference_graph`
commons dataset. The canonical graph artifact is the upstream OBO Graph JSON
release asset; `nodes.csv` and `edges.csv` are build-derived projections used
for fast validation and virtual member payload resolution.

The member surface is restricted to addressable `MONDO:` terms. Deprecated
MONDO terms remain addressable members and count toward `member_count`; when
MONDO declares a replacement with `IAO:0100001`, the replacement is recorded in
`nodes.csv.replaced_by` and is not auto-applied.

The edge projection includes direct graph edges where either endpoint is a
MONDO term plus MONDO node xrefs as `predicate=xref`. Xrefs and related external
terms are retained as relations, not identity rewrites.
"""
Path("entity.md").write_text(entity, encoding="utf-8")
'
```

- [ ] **Step 3: Verify entity counts match build summary**

Run:

```bash
cd ~/d/science-commons/datasets/mondo
uv run --frozen --project ~/d/science/science python recipe/build.py \
  --source-json ~/d/science-commons-data/mondo/_src/mondo.json \
  --output-dir ~/d/science-commons-data/mondo \
  --verify-entity entity.md
```

Expected: command exits 0.

- [ ] **Step 4: Configure per-machine data override if needed**

Run:

```bash
uv run --frozen --project ~/d/science/science science commons data resolve dataset:mondo nodes
```

Expected if the data root already resolves: prints an absolute path under `~/d/science-commons-data/mondo/nodes.csv`.

If it fails because the machine default data root is different, add or update `~/.config/science/data.yaml` with:

```yaml
mondo: ~/d/science-commons-data/mondo
```

Then rerun the resolve command. The final command must print a hash-verified absolute path.

- [ ] **Step 5: Run commons validation**

Run:

```bash
cd ~/d/science
uv run --frozen --project science science commons validate
```

Expected: no `dataset:mondo` schema or datapackage defects.

- [ ] **Step 6: Run real RG1 row-contract validation**

Run:

```bash
cd ~/d/science
uv run --frozen --project science python - <<'PY'
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.reference_graph import parse_edge_rows, parse_node_index_rows
from science_tool.commons.reference_graph_resources import read_commons_edge_rows, read_commons_node_rows

record = CommonsEntityAdapter(resolve_commons_root()).load("dataset:mondo")
node_rows = read_commons_node_rows(record.frontmatter)
edge_rows = read_commons_edge_rows(record.frontmatter)
if isinstance(node_rows, Exception):
    raise node_rows
if isinstance(edge_rows, Exception):
    raise edge_rows
if node_rows is None:
    raise SystemExit("node rows unavailable")
if edge_rows is None:
    raise SystemExit("edge rows unavailable")
nodes = parse_node_index_rows(node_rows)
edges = parse_edge_rows(edge_rows)
if len(nodes) != record.frontmatter["member_count"]:
    raise SystemExit(f"member_count mismatch: {len(nodes)} != {record.frontmatter['member_count']}")
if len(edges) != record.frontmatter["edge_count"]:
    raise SystemExit(f"edge_count mismatch: {len(edges)} != {record.frontmatter['edge_count']}")
print(f"validated {len(nodes)} MONDO nodes and {len(edges)} edges")
PY
```

Expected: prints a validated MONDO node/edge count line. This is the real-data RG1 check; `science commons validate` only validates entity schema.

- [ ] **Step 7: Commit**

Run:

```bash
cd ~/d/science-commons
git add datasets/mondo/entity.md datasets/mondo/datapackage.yaml
git commit -m "data(mondo): add MONDO reference graph dataset"
```

## Task 6: Add Validation And Payload Smoke Tests

**Files:**
- Modify: `science/tests/validate/test_checks_reference_graphs.py`
- Modify: `science/tests/test_commons_reference_graph_payload.py`

- [ ] **Step 1: Add fixture tests for MONDO-style data**

In `science/tests/validate/test_checks_reference_graphs.py`, add:

```python
def test_reference_graph_accepts_mondo_style_replacement_and_xref_edges() -> None:
    rows = [
        _node(member_key="MONDO:0005148", label="type 2 diabetes mellitus"),
        _node(
            member_key="MONDO:0008549",
            label="obsolete thoracic dysostosis, isolated",
            status="deprecated",
            replaced_by="MONDO:0979242",
        ),
    ]
    edges = [
        _edge(subject="MONDO:0005148", predicate="is_a", object="MONDO:0000001"),
        _edge(subject="MONDO:0005148", predicate="xref", object="OMIM:125853"),
    ]

    results = list(
        evaluate_reference_graphs(
            [_reference_graph(graph_format="obograph_json", member_count=2, edge_count=2)],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": rows},
            edge_rows_by_dataset_id={"dataset:mondo": edges},
            member_datasets=[],
        )
    )

    assert results == []
```

In `science/tests/test_commons_reference_graph_payload.py`, extend `_write_reference_graph_commons` so the parent node/edge files include a deprecated MONDO node and an xref edge:

```python
    node_rows = [
        {
            "member_key": "MONDO:0005148",
            "member_kind": "term",
            "label": "multiple myeloma",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": _dataset_usage("dataset:ordo"),
        },
        {
            "member_key": "MONDO:0000001",
            "member_kind": "term",
            "label": "disease",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        },
        {
            "member_key": "MONDO:0008549",
            "member_kind": "term",
            "label": "obsolete thoracic dysostosis, isolated",
            "status": "deprecated",
            "replaced_by": "MONDO:0979242",
            "dataset_usage": "[]",
        },
        {
            "member_key": "MONDO:9999999",
            "member_kind": "term",
            "label": "unrelated disease",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        },
    ]
```

Add this edge to `edge_rows`:

```python
        {
            "subject": "MONDO:0008549",
            "predicate": "xref",
            "object": "OMIM:example",
            "evidence": "",
            "dataset_usage": "[]",
        },
```

Then update the fixture frontmatter counts:

```python
        "member_count": 4,
```

and:

```python
        parent_fm["edge_count"] = 4
```

Finally add this test:

```python
def test_resolve_virtual_reference_graph_member_payload_returns_deprecated_node_and_xref_edges(
    tmp_path: Path,
) -> None:
    commons_root, data_root = _write_reference_graph_commons(tmp_path, member_key="MONDO:0008549")

    payload = resolve_virtual_member_payload(
        "dataset:mondo-0005148",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert isinstance(payload, VirtualMemberPayload)
    assert payload.member_key == "MONDO:0008549"
    assert payload.payload["node"]["status"] == "deprecated"
    assert payload.payload["node"]["replaced_by"] == ["MONDO:0979242"]
    assert ("MONDO:0008549", "xref", "OMIM:example") in {
        (edge["subject"], edge["predicate"], edge["object"])
        for edge in payload.payload["incident_edges"]
    }
```

- [ ] **Step 2: Run tests and confirm pass**

Run:

```bash
cd ~/d/science
uv run --frozen --project science pytest \
  science/tests/validate/test_checks_reference_graphs.py \
  science/tests/test_commons_reference_graph_payload.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run real MONDO resolver smoke**

Run:

```bash
cd ~/d/science
uv run --frozen --project science science commons data resolve dataset:mondo graph
uv run --frozen --project science science commons data resolve dataset:mondo nodes
uv run --frozen --project science science commons data resolve dataset:mondo edges
```

Expected: all three commands print hash-verified absolute paths.

- [ ] **Step 4: Commit**

Run:

```bash
cd ~/d/science
git add science/tests/validate/test_checks_reference_graphs.py science/tests/test_commons_reference_graph_payload.py
git commit -m "test(reference-graph): cover MONDO-style graph payloads"
```

## Task 7: Update Status Docs

**Files:**
- Modify: `docs/plans/2026-05-31-bio-reference-graph-design.md`
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`
- Modify: `meta/doc/background/papers/Vasilevsky2022.md`

- [ ] **Step 1: Update reference-graph phase table**

In `docs/plans/2026-05-31-bio-reference-graph-design.md`, change the RG4 row from:

```markdown
| RG4 | First real commons recipe, likely MONDO or GO, with pinned release artifacts | pending |
```

to:

```markdown
| RG4 | First real commons recipe: `dataset:mondo` from pinned MONDO OBO Graph JSON, with node/edge projections | implemented locally |
```

Also replace:

```markdown
RG1 and RG2 are implemented locally. Next, plan RG3/RG4 follow-ups: broader graph-member promotion
workflows, unpromoted-member B materialization, and the first real MONDO or GO commons recipe with
pinned release artifacts.
```

with:

```markdown
RG1, RG2, and RG4 are implemented locally. Remaining follow-ups are broader graph-member promotion
workflows, unpromoted-member B materialization, additional real graph recipes such as GO and Open
Targets, and non-molecular identity resolvers.
```

- [ ] **Step 2: Update umbrella status header**

In the top `Status:` line of `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`, replace:

```markdown
non-tabular reference modeling is partly resolved by `bio.reference_graph` RG1/RG2 with real MONDO/GO/Open Targets recipes and RG3+ workflows pending
```

with:

```markdown
non-tabular reference modeling is partly resolved by `bio.reference_graph` RG1/RG2/RG4 with `dataset:mondo` implemented locally and GO/Open Targets recipes plus RG3+ workflows pending
```

- [ ] **Step 3: Update umbrella non-tabular paragraphs**

In `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`, update the open-item paragraph and the §8 status paragraph so both state this content, adapted to the surrounding sentence:

```markdown
`bio.reference_graph` RG1, RG2, and RG4 are implemented locally: RG1 validates node indexes, RG2
resolves promoted graph-member virtual payloads, and RG4 adds `dataset:mondo` as the first real pinned
reference graph recipe. GO/Open Targets recipes, broader graph-member promotion workflows,
unpromoted-member B materialization, and non-molecular identity resolvers remain follow-up work.
```

- [ ] **Step 4: Update the paper note**

In `meta/doc/background/papers/Vasilevsky2022.md`, replace the follow-up sentence:

```markdown
Draft the MONDO commons ingestion plan around a pinned release, not the paper's 2022 counts.
```

with:

```markdown
The MONDO commons ingestion path now targets pinned MONDO release `v2026-05-05` and derives counts from
the built `nodes.csv`/`edges.csv`, not from the paper's 2022 release statistics.
```

- [ ] **Step 5: Verify stale status text is gone**

Run:

```bash
rg -n "RG2\\+ pending|real MONDO/GO/Open Targets recipes|first real MONDO or GO commons recipe|RG4 .* pending|Draft the MONDO commons ingestion plan" \
  docs/plans/2026-05-31-bio-reference-graph-design.md \
  docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md \
  meta/doc/background/papers/Vasilevsky2022.md
```

Expected: no output.

- [ ] **Step 6: Commit**

Run:

```bash
cd ~/d/science
git add \
  docs/plans/2026-05-31-bio-reference-graph-design.md \
  docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md \
  meta/doc/background/papers/Vasilevsky2022.md
git commit -m "docs(reference-graph): update MONDO ingestion status"
```

## Task 8: Final Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run focused science tests**

Run:

```bash
cd ~/d/science
uv run --frozen --project science pytest \
  science/model/tests/test_bio_extension_reference_graph.py \
  science/tests/test_commons_reference_graph.py \
  science/tests/test_commons_reference_graph_resources.py \
  science/tests/test_commons_reference_graph_payload.py \
  science/tests/validate/test_checks_reference_graphs.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run MONDO recipe tests**

Run:

```bash
cd ~/d/science-commons/datasets/mondo/recipe
uv run --frozen --project ~/d/science/science pytest test_mondo_recipe.py -q
```

Expected: PASS.

- [ ] **Step 3: Run formatting and type checks for touched science files**

Run:

```bash
cd ~/d/science
uv run --frozen --project science ruff check \
  science/src/science_tool/commons/reference_graph.py \
  science/tests/test_commons_reference_graph.py \
  science/tests/test_commons_reference_graph_payload.py \
  science/tests/validate/test_checks_reference_graphs.py \
  science/model/tests/test_bio_extension_reference_graph.py
uv run --frozen --project science pyright \
  science/src/science_tool/commons/reference_graph.py
```

Expected: both commands pass.

- [ ] **Step 4: Run commons data resolution smoke**

Run:

```bash
cd ~/d/science
uv run --frozen --project science science commons data resolve dataset:mondo graph
uv run --frozen --project science science commons data resolve dataset:mondo nodes
uv run --frozen --project science science commons data resolve dataset:mondo edges
```

Expected: all three commands print hash-verified absolute paths. The `graph` path is
`~/d/science-commons-data/mondo/_src/mondo.json`; `nodes` and `edges` are under
`~/d/science-commons-data/mondo/`.

- [ ] **Step 5: Run real reference graph row validation**

Run:

```bash
cd ~/d/science
uv run --frozen --project science python - <<'PY'
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.reference_graph import parse_edge_rows, parse_node_index_rows
from science_tool.commons.reference_graph_resources import read_commons_edge_rows, read_commons_node_rows

record = CommonsEntityAdapter(resolve_commons_root()).load("dataset:mondo")
node_rows = read_commons_node_rows(record.frontmatter)
edge_rows = read_commons_edge_rows(record.frontmatter)
if isinstance(node_rows, Exception):
    raise node_rows
if isinstance(edge_rows, Exception):
    raise edge_rows
if node_rows is None:
    raise SystemExit("node rows unavailable")
if edge_rows is None:
    raise SystemExit("edge rows unavailable")
nodes = parse_node_index_rows(node_rows)
edges = parse_edge_rows(edge_rows)
assert len(nodes) == record.frontmatter["member_count"]
assert len(edges) == record.frontmatter["edge_count"]
print(f"validated {len(nodes)} MONDO nodes and {len(edges)} edges")
PY
```

Expected: prints a validated MONDO node/edge count line. Do not use the project-root validator as the acceptance check for `dataset:mondo`; the dataset lives in the commons repo, not in the `~/d/science` project root.

- [ ] **Step 6: Check whitespace**

Run:

```bash
cd ~/d/science
rtk git diff --check
cd ~/d/science-commons
rtk git diff --check
```

Expected: both commands produce no output.

## Self-Review

- Spec coverage: The plan implements RG4 by adding the missing OBO Graph JSON format, creating a pinned MONDO recipe, producing RG1 node/edge projections, preserving deprecated/replacement semantics, retaining xrefs as edges, and exercising RG2 payload resolution behavior.
- Source-path decision: Direct `mondo.json` is the production input because it is release-pinned and preserves replacements. BioOntologies is documented as a future comparison path, not added as an unnecessary dependency.
- No silent fallbacks: Fetch refuses mutable URLs and verifies hash/bytes. Build rejects malformed graph shape, duplicate MONDO ids, blank active labels, and malformed edge endpoints. Deprecated blank-label terms are explicitly counted and labeled by member key because the pinned release contains 74 such addressable deprecated classes.
- Type consistency: `graph_format` is `obograph_json` in schema, parser constants, entity frontmatter, and validation tests. Node and edge CSV columns match the implemented RG1 parsers.
