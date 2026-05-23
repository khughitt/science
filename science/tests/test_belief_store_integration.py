"""Integration: _claim_summary_data derives belief via independence-aware aggregation."""

from __future__ import annotations

from pathlib import Path


def _write(tmp_path: Path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _project_with_one_support_one_diagnostic_dispute(tmp_path: Path) -> Path:
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")

    _write(
        tmp_path,
        "doc/propositions/p.md",
        """---
id: proposition:p
kind: proposition
title: "Proposition P"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
---
""",
    )

    # ONE clean supporting evidence-line.
    _write(
        tmp_path,
        "doc/evidence-lines/sup.md",
        """---
id: evidence-line:sup
kind: evidence-line
title: "Sup supports P"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
stance: supports
target: proposition:p
evidence_role: direct_test
strength: strong
independence: independent
independence_group: g1
---
""",
    )

    # ONE diagnostic disputing evidence-line (model_criticism + scoped) -> contested but not capping.
    _write(
        tmp_path,
        "doc/evidence-lines/dis.md",
        """---
id: evidence-line:dis
kind: evidence-line
title: "Dis disputes P"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
stance: disputes
target: proposition:p
evidence_role: model_criticism
dispute_scope: generalization
---
""",
    )

    return tmp_path


def test_claim_summary_reports_fragile_contested(tmp_path):
    from rdflib import Dataset, URIRef

    from science_tool.graph.materialize import materialize_graph
    from science_tool.graph.store import PROJECT_NS, _claim_summary_data

    project = _project_with_one_support_one_diagnostic_dispute(tmp_path)
    trig_path = materialize_graph(project)
    ds = Dataset()
    ds.parse(source=str(trig_path), format="trig")
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])

    claim = URIRef(PROJECT_NS["proposition/p"])
    data = _claim_summary_data(knowledge, provenance, claim)
    assert data is not None
    assert data["belief_state"] == "fragile"  # magnitude only (1 clean support => fragile)
    assert data["contested"] is True  # diagnostic dispute present
    assert data["belief_display"] == "fragile (contested)"
