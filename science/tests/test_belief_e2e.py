"""End-to-end belief test: the decisive-refutation cap on COMPUTED belief.

  PART 1 — a decisive whole-claim refutation caps the computed magnitude to `fragile`.
  PART 2 — a diagnostic/scoped dispute does not trigger that cap; support stands.

Both tests previously had a second half asserting the `belief.refutation-masked` /
`belief.inflated` / `belief.single-source-ceiling` rules, which compared an AUTHORED magnitude
against the computed one. **Belief is no longer authored** (D5 / design rev 8), so those rules
have no input and were removed with it. The cap itself is computed and is unchanged.
"""

from __future__ import annotations

import json
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
    _write(root, "entities/propositions/p.md", _prop("well_supported"))
    _write(root, "entities/evidence-lines/sup1.md", _supporting_line("sup1", "g1"))
    _write(root, "entities/evidence-lines/sup2.md", _supporting_line("sup2", "g2"))
    _write(root, "entities/evidence-lines/dis.md", dispute_fn())


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


# ---------------------------------------------------------------------------
# PART 1 — decisive refutation caps the COMPUTED magnitude to fragile
#
# This test used to have a second half asserting that an authored `well_supported` then fired
# `belief.refutation-masked` (ERROR). Belief is no longer authored (D5 / design rev 8), so that
# rule and its input are gone. The invariant that actually matters — the aggregator itself caps a
# claim to `fragile` in the face of a decisive whole-claim refutation — is computed, and is
# unchanged. It is asserted below.
#
# The DELETED half guarded a real thing: an author asserting >= supported while an unresolved
# decisive refutation stands. That invariant now belongs on the `verdict` axis, where the claim is
# actually authored.
# ---------------------------------------------------------------------------

def test_e2e_decisive_refutation_caps_computed_magnitude_to_fragile(tmp_path: Path) -> None:
    """Two clean independent direct_test supports (would be well_supported) + one decisive
    whole_claim dispute → the aggregator caps the computed magnitude to fragile."""
    _scaffold(tmp_path, _decisive_dispute_line)

    from science_tool.graph.store import _claim_summary_data

    knowledge, provenance, claim = _build_and_load(tmp_path)
    data = _claim_summary_data(knowledge, provenance, claim)
    assert data is not None, "_claim_summary_data returned None"

    assert data["belief_state"] == "fragile", (
        f"expected fragile (decisive refutation cap), got {data['belief_state']!r}"
    )
    assert data["contested"] is True, "expected contested=True with a dispute present"


# ---------------------------------------------------------------------------
# PART 2 — a diagnostic/scoped dispute does NOT trigger the decisive cap
# ---------------------------------------------------------------------------

def test_e2e_diagnostic_dispute_does_not_cap_computed_support(tmp_path: Path) -> None:
    """Switch the dispute to model_criticism + generalization (diagnostic/scoped). The decisive
    cap no longer applies, so two clean independent direct_test supports still compute
    well_supported — while `contested` stays True, because any dispute marks contested."""
    _scaffold(tmp_path, _diagnostic_dispute_line)

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


# ---------------------------------------------------------------------------
# Dataset-QA ceiling — end-to-end through materialize (Task 8)
#
# Wires emit_dataset_qa_layer into the materialize pipeline and exercises the
# full seam: dataset declares a qa_report.json → QA layer stamps qaFailedDataset
# on the empirical line resting on the failed dependence dataset → belief applies
# the dataset-QA ceiling.
# ---------------------------------------------------------------------------


def _dataset_with_qa_report(slug: str, *, qa_report_rel: str) -> str:
    """A minimal external dataset datapackage declaring a project-root-relative qa_report."""
    return (
        "profiles: [science-pkg-entity-1.0]\n"
        f"id: dataset:{slug}\n"
        "kind: dataset\n"
        f"title: {slug}\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        f"qa_report: {qa_report_rel}\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
    )


def _supporting_line_on_dataset(eid: str, group: str, dataset_ref: str) -> str:
    """Empirical, independent, strong direct_test support that ANALYZED `dataset_ref`
    (a DEPENDENCE role) — so it can be stamped qaFailedDataset when that dataset fails QA."""
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
        "dataset_usage:\n"
        f"  - ref: {dataset_ref}\n"
        "    role: analyzed\n"
        "    overlap: full\n"
        "---\n"
    )


def _write_qa_report(root: Path, rel: str, *, structural_failed: bool) -> None:
    _write(
        root,
        rel,
        json.dumps(
            {
                "package": "dataset:mmrf",
                "package_structural_failed": structural_failed,
                "resources": (
                    [{"resource": "expression", "status": "fail"}] if structural_failed else []
                ),
            }
        ),
    )


def _belief_for_p(root: Path):
    """Same belief path _claim_summary_data uses, but returns the full BeliefResult so the
    dataset-QA ceiling flags (magnitude + qa_dataset_capped) are observable end-to-end."""
    from science_tool.graph.belief import aggregate_belief, collect_evidence_units
    from science_tool.graph.store import _evidence_targets_for_uri

    knowledge, provenance, claim = _build_and_load(root)
    units = collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, claim))
    return aggregate_belief(units)


def test_dataset_qa_ceiling_end_to_end(tmp_path: Path) -> None:
    """Two independent strong direct_test EMPIRICAL supports reach well_supported on clean
    data. One support ANALYZED dataset:mmrf, which declares a qa_report.json.

    Failed report  → mmrf is structurally failed → QA layer stamps qaFailedDataset on the
                     line resting on it. The QA-clean remainder is a single support (fragile),
                     which cannot stand at well_supported, so belief is capped to FRAGILE and
                     qa_dataset_capped is True.
    Clean report   → nothing is stamped → both supports count cleanly → WELL_SUPPORTED and
                     qa_dataset_capped is False (belief RISES above fragile).
    """
    qa_rel = "data/mmrf/qa_report.json"
    _manifest(tmp_path)
    _write(
        tmp_path,
        "data/mmrf/datapackage.yaml",
        _dataset_with_qa_report("mmrf", qa_report_rel=qa_rel),
    )
    _write(tmp_path, "entities/propositions/p.md", _prop("well_supported"))
    # sup1 rests on the failed-QA dataset; sup2 is QA-clean (no dataset usage).
    _write(
        tmp_path,
        "entities/evidence-lines/sup1.md",
        _supporting_line_on_dataset("sup1", "g1", "dataset:mmrf"),
    )
    _write(tmp_path, "entities/evidence-lines/sup2.md", _supporting_line("sup2", "g2"))

    # --- Failed report → capped to fragile ---
    _write_qa_report(tmp_path, qa_rel, structural_failed=True)
    failed = _belief_for_p(tmp_path)
    assert failed.magnitude.value == "fragile", (
        f"expected fragile (dataset-QA ceiling: clean remainder is a single support), "
        f"got {failed.magnitude.value!r}"
    )
    assert failed.qa_dataset_capped is True, "expected qa_dataset_capped=True with failed QA report"

    # --- Clean report → not capped, belief rises ---
    _write_qa_report(tmp_path, qa_rel, structural_failed=False)
    clean = _belief_for_p(tmp_path)
    assert clean.magnitude.value == "well_supported", (
        f"expected well_supported (two clean direct_test supports, no QA cap), "
        f"got {clean.magnitude.value!r}"
    )
    assert clean.qa_dataset_capped is False, "expected qa_dataset_capped=False with clean QA report"
