"""End-to-end test: chain-link change propagates to chain-audit freshness."""

from __future__ import annotations

from pathlib import Path

from rdflib import Dataset, URIRef

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


def _project_with_chain_audit(tmp_path: Path, *, fp_updated: str, audit_reviewed: str) -> Path:
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")
    for slug, updated in (("a", "2026-05-01"), ("b", fp_updated), ("c", "2026-05-01")):
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
updated: {updated}
---
""",
        )
    _write(
        tmp_path,
        "doc/chains/abc.md",
        """---
id: chain:abc
kind: structural-chain
title: "ABC chain"
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
        f"""---
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
review_state:
  last_reviewed: {audit_reviewed}
bayes_factor_evidence:
  hypothesis_ref: hypothesis:abc
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


def _freshness_state(dataset: Dataset, audit_uri: URIRef) -> str | None:
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    triples = list(knowledge.triples((audit_uri, SCI_NS.freshnessState, None)))
    if not triples:
        return None
    return str(triples[0][2])


def test_audit_fresh_when_links_unchanged_since_review(tmp_path: Path) -> None:
    project = _project_with_chain_audit(tmp_path, fp_updated="2026-05-01", audit_reviewed="2026-05-02")
    dataset = _load_dataset(project)
    audit_uri = URIRef(PROJECT_NS["chain-audit/abc-2026-05"])
    assert _freshness_state(dataset, audit_uri) == "fresh"


def test_audit_needs_review_when_link_updates_after_review(tmp_path: Path) -> None:
    """Mechanism B updated 2026-05-10, audit reviewed 2026-05-02 -> needs-review."""
    project = _project_with_chain_audit(tmp_path, fp_updated="2026-05-10", audit_reviewed="2026-05-02")
    dataset = _load_dataset(project)
    audit_uri = URIRef(PROJECT_NS["chain-audit/abc-2026-05"])
    assert _freshness_state(dataset, audit_uri) == "needs-review"

    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    triggered_uris = {str(o) for _, _, o in knowledge.triples((audit_uri, SCI_NS.triggeredBy, None))}
    assert str(PROJECT_NS["mechanism/b"]) in triggered_uris
