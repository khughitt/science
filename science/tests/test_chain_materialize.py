"""Tests for chain-related triple emission during materialize."""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(tmp_path: Path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _load_dataset(project: Path) -> Dataset:
    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    return dataset


def _minimal_project(tmp_path: Path) -> Path:
    """Materialize a project with three mechanism entities + one chain + one chain-audit."""
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")
    for slug in ("a", "b", "c"):
        _write(
            tmp_path,
            f"doc/mechanisms/{slug}.md",
            f"""---
id: mechanism:{slug}
kind: mechanism
title: "Mechanism {slug}"
project: test
summary: "Mechanism {slug} summary."
ontology_terms: []
related: []
source_refs: []
participants:
  - meta:participant-1
  - meta:participant-2
propositions:
  - meta:proposition
created: 2026-05-01
updated: 2026-05-01
---
""",
        )
    _write(
        tmp_path,
        "doc/chains/abc.md",
        """---
id: chain:abc
kind: structural-chain
title: "A to B to C chain"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
chain:
  - mechanism:a
  - mechanism:b
  - mechanism:c
---
""",
    )
    _write(
        tmp_path,
        "doc/audits/abc-2026-05.md",
        """---
id: chain-audit:abc-2026-05
kind: chain-audit
title: "ABC audit"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
audits: chain:abc
proposition_refs: []
bayes_factor_evidence:
  hypothesis_ref: hypothesis:abc-coupling
  null_baseline: "uniform"
  interpretation: evidence-against
verdict:
  composite: "[-]"
  rule: single-claim
  claims:
    - id: claim:abc
      polarity: "[-]"
---
""",
    )
    return tmp_path


def test_has_link_triples_emitted(tmp_path: Path) -> None:
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    chain_uri = URIRef(PROJECT_NS["chain/abc"])
    targets = {str(o) for _, _, o in knowledge.triples((chain_uri, SCI_NS.hasLink, None))}
    assert len(targets) == 3
    assert str(PROJECT_NS["mechanism/a"]) in targets
    assert str(PROJECT_NS["mechanism/b"]) in targets
    assert str(PROJECT_NS["mechanism/c"]) in targets


def test_link_sequence_rdf_list_emitted(tmp_path: Path) -> None:
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    chain_uri = URIRef(PROJECT_NS["chain/abc"])
    head_triples = list(knowledge.triples((chain_uri, SCI_NS.linkSequence, None)))
    assert len(head_triples) == 1, "exactly one linkSequence triple per chain"
    head = head_triples[0][2]

    ordered = []
    cur = head
    while cur != RDF.nil:
        first = next(knowledge.triples((cur, RDF.first, None)))[2]
        ordered.append(str(first))
        cur = next(knowledge.triples((cur, RDF.rest, None)))[2]

    assert ordered == [
        str(PROJECT_NS["mechanism/a"]),
        str(PROJECT_NS["mechanism/b"]),
        str(PROJECT_NS["mechanism/c"]),
    ]


def test_audits_triple_emitted(tmp_path: Path) -> None:
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    audit_uri = URIRef(PROJECT_NS["chain-audit/abc-2026-05"])
    chain_uri = URIRef(PROJECT_NS["chain/abc"])
    assert (audit_uri, SCI_NS.audits, chain_uri) in knowledge


def test_chain_rejects_disallowed_link_kind(tmp_path: Path) -> None:
    project = _minimal_project(tmp_path)
    _write(
        project,
        "doc/tasks/t1.md",
        """---
id: task:t1
kind: task
title: "Invalid chain link task"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
---
""",
    )
    _write(
        project,
        "doc/chains/abc.md",
        """---
id: chain:abc
kind: structural-chain
title: "A to invalid task chain"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
chain:
  - mechanism:a
  - task:t1
  - mechanism:c
---
""",
    )

    with pytest.raises(ValueError, match="has_link|sci:hasLink"):
        materialize_graph(project)


def test_chain_audit_rejects_non_chain_audits_target(tmp_path: Path) -> None:
    project = _minimal_project(tmp_path)
    _write(
        project,
        "doc/audits/abc-2026-05.md",
        """---
id: chain-audit:abc-2026-05
kind: chain-audit
title: "ABC audit"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
audits: mechanism:a
proposition_refs: []
bayes_factor_evidence:
  hypothesis_ref: hypothesis:abc-coupling
  null_baseline: "uniform"
  interpretation: evidence-against
verdict:
  composite: "[-]"
  rule: single-claim
  claims:
    - id: claim:abc
      polarity: "[-]"
---
""",
    )

    with pytest.raises(ValueError, match="audits|sci:audits"):
        materialize_graph(project)
