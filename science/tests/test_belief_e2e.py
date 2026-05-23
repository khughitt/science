"""End-to-end belief test: decisive-refutation cap + belief checks (Phase 1).

Exercises the full pipeline for BOTH halves of the decisive-refutation
cap behavior:

  PART 1 — decisive refutation caps magnitude + `belief.refutation-masked` fires.
  PART 2 — switch dispute to diagnostic/scoped → ERROR clears, support stands.
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _manifest(root: Path) -> None:
    _write(root, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")


def _prop(belief_state: str) -> str:
    return (
        "---\n"
        "id: proposition:p\n"
        "kind: proposition\n"
        'title: "Proposition P"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        f"belief_state: {belief_state}\n"
        "---\n"
    )


def _supporting_line(eid: str, group: str) -> str:
    return (
        "---\n"
        f"id: evidence-line:{eid}\n"
        "kind: evidence-line\n"
        f'title: "{eid}"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        "stance: supports\n"
        "target: proposition:p\n"
        "evidence_role: direct_test\n"
        "strength: strong\n"
        "independence: independent\n"
        f"independence_group: {group}\n"
        "evidence_type: empirical_data_evidence\n"
        "---\n"
    )


def _decisive_dispute_line() -> str:
    """Decisive: independent + strong + direct_test + whole_claim."""
    return (
        "---\n"
        "id: evidence-line:dis\n"
        "kind: evidence-line\n"
        'title: "dis"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        "stance: disputes\n"
        "target: proposition:p\n"
        "evidence_role: direct_test\n"
        "strength: strong\n"
        "independence: independent\n"
        "independence_group: g3\n"
        "dispute_scope: whole_claim\n"
        "---\n"
    )


def _diagnostic_dispute_line() -> str:
    """Diagnostic: model_criticism + generalization — never decisive."""
    return (
        "---\n"
        "id: evidence-line:dis\n"
        "kind: evidence-line\n"
        'title: "dis"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        "stance: disputes\n"
        "target: proposition:p\n"
        "evidence_role: model_criticism\n"
        "strength: strong\n"
        "independence: independent\n"
        "independence_group: g3\n"
        "dispute_scope: generalization\n"
        "---\n"
    )


def _scaffold(root: Path, dispute_fn) -> None:
    _manifest(root)
    _write(root, "doc/propositions/p.md", _prop("well_supported"))
    _write(root, "doc/evidence-lines/sup1.md", _supporting_line("sup1", "g1"))
    _write(root, "doc/evidence-lines/sup2.md", _supporting_line("sup2", "g2"))
    _write(root, "doc/evidence-lines/dis.md", dispute_fn())


def _build_and_load(root: Path):
    """Materialize graph; return (knowledge, provenance, claim_uri)."""
    from rdflib import Dataset, URIRef
    from science_tool.graph.materialize import materialize_graph
    from science_tool.graph.store import PROJECT_NS

    trig_path = materialize_graph(root)
    ds = Dataset()
    ds.parse(source=str(trig_path), format="trig")
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])
    claim = URIRef(PROJECT_NS["proposition/p"])
    return knowledge, provenance, claim


def _run_belief_checks(root: Path) -> set[str]:
    from science_tool.validate import ValidateContext
    from science_tool.validate.checks.evidence_lines import check_belief_authoring

    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return {r.rule for r in check_belief_authoring(ctx)}


# ---------------------------------------------------------------------------
# PART 1 — decisive refutation caps magnitude to fragile; refutation-masked fires
# ---------------------------------------------------------------------------

def test_e2e_decisive_refutation_caps_to_fragile_and_check_fires(tmp_path: Path) -> None:
    """Two clean independent direct_test supports (would be well_supported) + one
    decisive whole_claim dispute → aggregator caps magnitude to fragile; authored
    well_supported triggers belief.refutation-masked ERROR."""
    _scaffold(tmp_path, _decisive_dispute_line)

    # Half 1: computed belief via _claim_summary_data
    from science_tool.graph.store import _claim_summary_data

    knowledge, provenance, claim = _build_and_load(tmp_path)
    data = _claim_summary_data(knowledge, provenance, claim)
    assert data is not None, "_claim_summary_data returned None"

    assert data["belief_state"] == "fragile", (
        f"expected fragile (decisive refutation cap), got {data['belief_state']!r}"
    )
    assert data["contested"] is True, "expected contested=True with a dispute present"

    # Half 2: belief authoring check fires refutation-masked
    rules = _run_belief_checks(tmp_path)
    assert "belief.refutation-masked" in rules, (
        f"expected belief.refutation-masked in check results; got rules={rules}"
    )


# ---------------------------------------------------------------------------
# PART 2 — diagnostic/scoped dispute → ERROR clears; well_supported stands
# ---------------------------------------------------------------------------

def test_e2e_diagnostic_dispute_clears_error_support_stands(tmp_path: Path) -> None:
    """Switch the dispute to model_criticism + generalization (diagnostic/scoped).
    The decisive cap no longer applies; two clean independent direct_test supports
    → computed well_supported; belief.refutation-masked does NOT fire; contested
    is True (any dispute sets contested); belief.inflated does NOT fire because
    authored == computed."""
    _scaffold(tmp_path, _diagnostic_dispute_line)

    # Half 1: computed belief
    from science_tool.graph.store import _claim_summary_data

    knowledge, provenance, claim = _build_and_load(tmp_path)
    data = _claim_summary_data(knowledge, provenance, claim)
    assert data is not None, "_claim_summary_data returned None"

    assert data["belief_state"] == "well_supported", (
        f"expected well_supported (two clean direct_test supports, no decisive cap), "
        f"got {data['belief_state']!r}"
    )
    assert data["contested"] is True, (
        "expected contested=True — diagnostic dispute still marks contested"
    )

    # Half 2: belief.refutation-masked must NOT fire; belief.inflated must NOT fire
    rules = _run_belief_checks(tmp_path)
    assert "belief.refutation-masked" not in rules, (
        f"belief.refutation-masked should not fire for diagnostic/scoped dispute; rules={rules}"
    )
    assert "belief.inflated" not in rules, (
        f"belief.inflated should not fire when authored == computed (both well_supported); "
        f"rules={rules}"
    )
    # The single-source-ceiling must also not fire (two independent groups present).
    assert "belief.single-source-ceiling" not in rules, (
        f"belief.single-source-ceiling should not fire with two independent support units; "
        f"rules={rules}"
    )
