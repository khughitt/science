"""Task 6 — end-to-end workbench round-trip on a fixture patch (the capstone).

Ties together every prior epistemic-edges task on a tiny inline fixture, with NO
MM30 data. This is the exact seam the deferred MM30 migration plugs into:

    compile  ->  materialize  ->  belief (on proposition IRIs)
             ->  derived_edge_status  ->  `dag workbench --check`  ->  channel-driven render

The fixture has two relational propositions:

  1. ``gene:PHF19 --affects--> construct:proliferation`` (polarity=positive,
     claim_layer=causal_effect) with a LITERATURE evidence stub (supports) — the
     compiled evidence-line is belief-eligible and genuinely contributes belief.
  2. ``construct:proliferation --is_proxy_for--> outcome:relapse``
     (sign-less predicate → polarity must be ``not_applicable``,
     claim_layer=structural_claim) with a STAGED empirical stub
     (``empirical_data_evidence`` and NO ``dataset_usage``) — the compiled
     evidence-line is ``belief_eligible=False`` and is genuinely EXCLUDED from
     belief.

Every assertion is non-vacuous: the staged line is provably absent from belief
AND the literature line provably present; the derived statuses are asserted; the
``--check`` gate is asserted green; the channel-driven hue is asserted.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from rdflib import Dataset

from science_tool.dag.proposition_edges import edges_from_propositions
from science_tool.dag.render import POLARITY_HUES, style_for_edge
from science_tool.dag.workbench import (
    WorkbenchFile,
    compile_workbench,
    serialize_canonical,
)
from science_tool.graph.belief import aggregate_belief, collect_evidence_units
from science_tool.graph.derived_status import derived_edge_status
from science_tool.graph.io import PROJECT_NS
from science_tool.graph.materialize import _entity_uri, materialize_graph

# ---------------------------------------------------------------------------
# The fixture patch (inline — simpler than a tests/fixtures/ file).
# ---------------------------------------------------------------------------

_FIXTURE_WORKBENCH = """\
patch: e2e
rows:
  - subject: gene:PHF19
    predicate: affects
    object: construct:proliferation
    patch: e2e
    polarity: positive
    claim_layer: causal_effect
    evidence:
      - evidence_type: literature
        stance: supports
        source: "doi:10.1234/phf19-proliferation"
  - subject: construct:proliferation
    predicate: is_proxy_for
    object: outcome:relapse
    patch: e2e
    polarity: not_applicable
    claim_layer: structural_claim
    evidence:
      - evidence_type: empirical_data_evidence
        stance: supports
"""


def _scratch_project(root: Path) -> Path:
    """Write the minimal manifest a project root needs for compile + materialize."""
    (root / "science.yaml").write_text(
        "name: epistemic-edges-e2e\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )
    return root


def _prop_by_subject(propositions, subject: str):
    matches = [p for p in propositions if p.subject == subject]
    assert len(matches) == 1, f"expected exactly one proposition with subject {subject!r}"
    return matches[0]


# ---------------------------------------------------------------------------
# The capstone test — the whole loop on one fixture.
# ---------------------------------------------------------------------------


def test_epistemic_edges_end_to_end_roundtrip(tmp_path: Path) -> None:
    project_root = _scratch_project(tmp_path)
    wb = WorkbenchFile.model_validate(yaml.safe_load(_FIXTURE_WORKBENCH))

    # --- 1. COMPILE -------------------------------------------------------
    result = compile_workbench(wb, project_root=project_root)

    # Two PropositionEntity files were written under entities/propositions/.
    prop_dir = project_root / "entities" / "propositions"
    written = sorted(p.name for p in prop_dir.glob("*.md"))
    assert len(written) == 2, f"expected 2 proposition files, got {written}"
    assert len(result.propositions) == 2

    prop_lit = _prop_by_subject(result.propositions, "gene:PHF19")
    prop_staged = _prop_by_subject(result.propositions, "construct:proliferation")

    # The proposition files exist on disk (round-trip is file-backed).
    for prop in (prop_lit, prop_staged):
        slug = prop.id.split(":", 1)[1]
        assert (prop_dir / f"{slug}.md").exists(), f"missing entity file for {prop.id}"

    # Sign-aptitude held by the model validator: affects (sign-meaningful) kept
    # polarity=positive; is_proxy_for (sign-less) kept polarity=not_applicable.
    assert prop_lit.polarity is not None and prop_lit.polarity.value == "positive"
    assert prop_staged.polarity is not None and prop_staged.polarity.value == "not_applicable"

    # Two evidence-lines were lifted; eligibility split as designed.
    assert len(result.evidence_lines) == 2
    line_lit = next(le for le in result.evidence_lines if le.target == prop_lit.id)
    line_staged = next(le for le in result.evidence_lines if le.target == prop_staged.id)

    assert line_lit.belief_eligible is True, (
        "literature stub must lift to a belief-eligible evidence-line"
    )
    assert line_staged.belief_eligible is False, (
        "empirical stub with NO dataset_usage must lift to a STAGED "
        "(belief_eligible=False) evidence-line"
    )

    # --- 2. MATERIALIZE ---------------------------------------------------
    # materialize_graph reads exactly the entity files compile just wrote.
    trig_path = materialize_graph(project_root, strict=False)
    ds = Dataset()
    ds.parse(source=str(trig_path), format="trig")
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])

    iri_lit = _entity_uri(prop_lit.id)
    iri_staged = _entity_uri(prop_staged.id)

    # --- 3. BELIEF DERIVES ON THE PROPOSITION IRIs ------------------------
    units_lit = collect_evidence_units(knowledge, provenance, [iri_lit])
    units_staged = collect_evidence_units(knowledge, provenance, [iri_staged])

    lit_line_iri = str(_entity_uri(line_lit.id))
    staged_line_iri = str(_entity_uri(line_staged.id))

    # Non-vacuous PRESENCE: the literature line genuinely contributes a unit to
    # proposition 1, keyed on proposition 1's IRI.
    lit_unit_iris = {u.line_uri for u in units_lit}
    assert lit_line_iri in lit_unit_iris, (
        f"literature evidence-line {lit_line_iri} must be a belief unit for prop 1; "
        f"got {lit_unit_iris}"
    )
    assert len(units_lit) == 1, f"prop 1 should collect exactly its one support unit, got {units_lit}"
    assert units_lit[0].stance == "supports"

    # Non-vacuous EXCLUSION: the staged empirical line contributes NO unit to
    # proposition 2 (its only support is staged), so prop 2 has zero belief units.
    staged_unit_iris = {u.line_uri for u in units_staged}
    assert staged_line_iri not in staged_unit_iris, (
        f"staged empirical evidence-line {staged_line_iri} must be EXCLUDED from belief; "
        f"got units {staged_unit_iris}"
    )
    assert units_staged == [], (
        f"prop 2 has only a staged line → it must collect zero belief units, got {units_staged}"
    )

    # And the staged line emits NO cito edge at all (Task 3b gate), proving the
    # exclusion is at materialization, not just at collection.
    from science_tool.graph.io import CITO_NS

    staged_line_uri = _entity_uri(line_staged.id)
    cito_subjects = {
        str(s)
        for pred in (CITO_NS.supports, CITO_NS.disputes)
        for s, _, _ in knowledge.triples((None, pred, None))
    }
    assert str(staged_line_uri) not in cito_subjects, (
        "staged line must emit no cito:supports/disputes edge"
    )
    assert lit_line_iri in cito_subjects, "literature line must emit a cito edge"

    # Aggregated belief reflects this: prop 1 has one clean support → fragile
    # (a single support unit is fragile by design); prop 2 has none → speculative.
    belief_lit = aggregate_belief(units_lit)
    belief_staged = aggregate_belief(units_staged)
    assert belief_lit.magnitude.value == "fragile", (
        f"prop 1 (one literature support) → fragile; got {belief_lit.magnitude.value}"
    )
    assert belief_staged.magnitude.value == "speculative", (
        f"prop 2 (no eligible support) → speculative; got {belief_staged.magnitude.value}"
    )

    # --- 4. derived_edge_status PROJECTION --------------------------------
    # Proposition 2: a structural claim with NO grounding evidence (its only
    # support was staged) → the ordered projection returns "unknown" (the
    # no-grounding band is ordered BEFORE the structural band).
    des_staged = derived_edge_status(
        belief_magnitude=belief_staged.magnitude.value,
        refuted=False,
        claim_layer="structural_claim",
        has_grounding_evidence=bool(units_staged),
    )
    assert des_staged.status == "unknown", (
        f"grounding-less structural claim must project to unknown; got {des_staged.status}"
    )

    # Proposition 1: a causal_effect claim WITH grounding (its literature unit).
    # At fragile magnitude (not in the supported band) the ordered projection
    # returns the "tentative" fallback.
    des_lit = derived_edge_status(
        belief_magnitude=belief_lit.magnitude.value,
        refuted=False,
        claim_layer="causal_effect",
        has_grounding_evidence=bool(units_lit),
    )
    assert des_lit.status == "tentative", (
        f"grounded fragile causal claim must project to tentative; got {des_lit.status}"
    )
    # And cranking its magnitude into the supported band flips it to supported —
    # proves the projection is genuinely reading belief_magnitude, not constant.
    des_lit_strong = derived_edge_status(
        belief_magnitude="well_supported",
        refuted=False,
        claim_layer="causal_effect",
        has_grounding_evidence=True,
    )
    assert des_lit_strong.status == "supported"

    # --- 5. `dag workbench --check` PASSES on the canonical form -----------
    canonical_text = serialize_canonical(result)
    wb_path = project_root / "e2e.workbench.yaml"
    wb_path.write_text(canonical_text, encoding="utf-8")

    proc = subprocess.run(
        ["uv", "run", "--frozen", "science", "dag", "workbench", "--check", str(wb_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"dag workbench --check must pass on canonical text; rc={proc.returncode} "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert "OK (canonical)" in proc.stdout

    # --- 6. RENDERER STYLES FROM CHANNELS ---------------------------------
    edges = edges_from_propositions(result.propositions)
    assert len(edges) == 2, "both relational propositions project to channel-mode edges"

    edge_lit = next(e for e in edges if e["source"] == "gene:PHF19")
    edge_staged = next(e for e in edges if e["source"] == "construct:proliferation")

    # Channel mode is selected by the presence of channel fields; edge_status is
    # never authored on the edge dict — it is DERIVED inside style_for_edge.
    assert "polarity" in edge_lit and "edge_status" not in edge_lit
    assert edge_lit["polarity"] == "positive"
    assert edge_staged["polarity"] == "not_applicable"

    attrs_lit = style_for_edge(edge_lit)
    attrs_staged = style_for_edge(edge_staged)

    # Hue is channel-driven (polarity), distinct per sign.
    assert attrs_lit["color"] == f'"{POLARITY_HUES["positive"]}"', (
        f"positive polarity must drive the positive hue; got {attrs_lit['color']}"
    )
    assert attrs_staged["color"] == f'"{POLARITY_HUES["not_applicable"]}"', (
        f"not_applicable polarity must drive the not_applicable hue; got {attrs_staged['color']}"
    )
    assert attrs_lit["color"] != attrs_staged["color"], (
        "the two polarities must produce different channel-driven hues"
    )

    # edge_status surfaced by the renderer is DERIVED (the propositions carry no
    # grounding belief at this projection stage → unknown), not authored.
    assert attrs_lit["derived_edge_status"] == "unknown"
    assert attrs_staged["derived_edge_status"] == "unknown"
