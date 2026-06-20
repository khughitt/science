"""Task 3b: belief_eligible=False evidence-lines are excluded from cito/belief materialization.

A staged line (belief_eligible=False) must emit no cito:supports/disputes edge and must
be invisible to collect_evidence_units.  An eligible line (belief_eligible=True, default)
is materialized normally.
"""
from __future__ import annotations

from rdflib import RDF, Graph, Literal, URIRef
from science_model.entities import EntityType, EvidenceLineEntity, ProjectEntity, QuantitativeResult
from science_model.reasoning import EvidenceStance

from science_tool.graph.belief import EVIDENCE_LINE_CLASS, collect_evidence_units
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.materialize import _add_evidence_line_metadata, _add_evidence_line_relations

# ---------------------------------------------------------------------------
# Shared URIs
# ---------------------------------------------------------------------------
CLAIM = URIRef(PROJECT_NS["proposition/p"])
LINE_A = URIRef(PROJECT_NS["evidence-line/a"])   # belief_eligible=True (default)
LINE_B = URIRef(PROJECT_NS["evidence-line/b"])   # belief_eligible=False (staged)


# ---------------------------------------------------------------------------
# Minimal entity factories
# ---------------------------------------------------------------------------

def _make_line(slug: str, *, eligible: bool, quant: QuantitativeResult | None = None) -> EvidenceLineEntity:
    return EvidenceLineEntity(
        id=f"evidence-line:{slug}",
        title=f"line {slug}",
        kind="evidence-line",
        type=EntityType.EVIDENCE_LINE,
        project="test",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path=f"entities/evidence-lines/{slug}.md",
        stance=EvidenceStance.SUPPORTS,
        target="proposition:p",
        strength=None,
        independence=None,
        belief_eligible=eligible,
        quantitative_result=quant,
    )


# ---------------------------------------------------------------------------
# Graph-builder harness — mirrors the style of test_belief_scalar_quant_result.py
# ---------------------------------------------------------------------------

def _build_graphs(
    eligible_quant: QuantitativeResult | None = None,
    staged_quant: QuantitativeResult | None = None,
) -> tuple[Graph, Graph]:
    """Materialise line A (eligible) and line B (staged) into fresh knowledge/provenance graphs.

    Uses the same low-level helpers that materialize_graph calls, so this is an
    exact unit test of the gate logic rather than a full project round-trip.
    """
    knowledge, provenance = Graph(), Graph()

    entity_a = _make_line("a", eligible=True, quant=eligible_quant)
    entity_b = _make_line("b", eligible=False, quant=staged_quant)

    # Register both lines as rdf:type EvidenceLine so collect_evidence_units can
    # find them (materialize_graph emits this unconditionally for all entities).
    knowledge.add((LINE_A, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE_B, RDF.type, EVIDENCE_LINE_CLASS))

    # Minimal resolver / entity_index stubs for _add_evidence_line_relations.
    class _Resolution:
        status = "unresolved"
        canonical_id = None

    class _Resolver:
        def resolve(self, *args, **kwargs):
            if "proposition:p" in args or kwargs.get("ref") == "proposition:p":
                return _Resolution()
            return _Resolution()

    # For _add_evidence_line_relations we need the target in the entity_index.
    # We pass an empty index here; the cito edge won't be emitted (target not found),
    # but that's irrelevant to the staged-line gate — we just need to confirm line B
    # skips the call entirely.  Use a real resolver stub that resolves the target so
    # line A DOES emit its cito edge.

    class _Hit:
        status = "resolved"
        canonical_id = "proposition:p"

    class _Resolver2:
        def resolve(self, ref, **kwargs):
            if "proposition" in ref:
                return _Hit()
            return _Resolution()

    prop = ProjectEntity(
        id="proposition:p",
        title="P",
        kind="proposition",
        type=EntityType.PROPOSITION,
        project="test",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/propositions/p.md",
    )
    entity_index = {"proposition:p": prop}
    resolver = _Resolver2()

    # --- Line A (eligible=True) ---
    _add_evidence_line_relations(
        line_uri=LINE_A,
        entity=entity_a,
        entity_index=entity_index,
        resolver=resolver,
        knowledge=knowledge,
        provenance=provenance,
        ext_prefixes=frozenset(),
    )
    _add_evidence_line_metadata(uri=LINE_A, provenance=provenance, entity=entity_a)

    # --- Line B (staged, eligible=False) ---
    _add_evidence_line_relations(
        line_uri=LINE_B,
        entity=entity_b,
        entity_index=entity_index,
        resolver=resolver,
        knowledge=knowledge,
        provenance=provenance,
        ext_prefixes=frozenset(),
    )
    _add_evidence_line_metadata(uri=LINE_B, provenance=provenance, entity=entity_b)

    return knowledge, provenance


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStagedLineCitoExclusion:
    """Line B (belief_eligible=False) emits no cito stance edge."""

    def test_staged_line_no_cito_supports(self):
        knowledge, _ = _build_graphs()
        assert (LINE_B, CITO_NS.supports, CLAIM) not in knowledge

    def test_staged_line_no_cito_disputes(self):
        knowledge, _ = _build_graphs()
        assert (LINE_B, CITO_NS.disputes, CLAIM) not in knowledge

    def test_staged_line_no_cito_any_target(self):
        """No cito:supports or cito:disputes triple with LINE_B as subject at all."""
        knowledge, _ = _build_graphs()
        cito_subjects = {
            str(s)
            for pred in (CITO_NS.supports, CITO_NS.disputes)
            for s, _, _ in knowledge.triples((None, pred, None))
        }
        assert str(LINE_B) not in cito_subjects


class TestEligibleLineCitoPresent:
    """Line A (belief_eligible=True, default) emits its cito edge normally."""

    def test_eligible_line_cito_supports(self):
        knowledge, _ = _build_graphs()
        assert (LINE_A, CITO_NS.supports, CLAIM) in knowledge


class TestStagedLineQuantExclusion:
    """Line B (staged) emits no quant scalar predicates that feed belief."""

    def test_staged_line_no_quant_beta(self):
        quant = QuantitativeResult(beta=1.5, prob_sign=0.95)
        _, provenance = _build_graphs(staged_quant=quant)
        assert (LINE_B, SCI_NS.quantBeta, Literal(1.5)) not in provenance

    def test_staged_line_no_quant_prob_sign(self):
        quant = QuantitativeResult(beta=1.5, prob_sign=0.95)
        _, provenance = _build_graphs(staged_quant=quant)
        assert (LINE_B, SCI_NS.quantProbSign, Literal(0.95)) not in provenance

    def test_staged_line_no_quant_hdi(self):
        quant = QuantitativeResult(beta=1.5, prob_sign=0.95, hdi=[0.2, 2.8])
        _, provenance = _build_graphs(staged_quant=quant)
        assert (LINE_B, SCI_NS.quantHdiLow, Literal(0.2)) not in provenance
        assert (LINE_B, SCI_NS.quantHdiHigh, Literal(2.8)) not in provenance


class TestBeliefVisibility:
    """collect_evidence_units must not include staged line B; must include eligible line A."""

    def test_eligible_line_visible_to_belief(self):
        knowledge, provenance = _build_graphs()
        # Add minimal ordinal metadata so line A produces a full unit.
        provenance.add((LINE_A, SCI_NS.evidenceStrength, Literal("strong")))
        provenance.add((LINE_A, SCI_NS.evidenceRole, Literal("direct_test")))
        provenance.add((LINE_A, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
        provenance.add((LINE_A, SCI_NS.independenceGroup, Literal("g1")))
        provenance.add((LINE_A, SCI_NS.evidenceIndependence, Literal("independent")))
        units = collect_evidence_units(knowledge, provenance, [CLAIM])
        line_uris = {u.line_uri for u in units}
        assert str(LINE_A) in line_uris

    def test_staged_line_invisible_to_belief(self):
        knowledge, provenance = _build_graphs()
        # Add metadata for line B too (even if staged, metadata presence must not matter).
        provenance.add((LINE_B, SCI_NS.evidenceStrength, Literal("strong")))
        provenance.add((LINE_B, SCI_NS.evidenceRole, Literal("direct_test")))
        provenance.add((LINE_B, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
        provenance.add((LINE_B, SCI_NS.independenceGroup, Literal("g1")))
        provenance.add((LINE_B, SCI_NS.evidenceIndependence, Literal("independent")))
        units = collect_evidence_units(knowledge, provenance, [CLAIM])
        line_uris = {u.line_uri for u in units}
        assert str(LINE_B) not in line_uris

    def test_only_eligible_lines_in_belief_units(self):
        knowledge, provenance = _build_graphs()
        # Full metadata on both lines.
        for line in (LINE_A, LINE_B):
            provenance.add((line, SCI_NS.evidenceStrength, Literal("strong")))
            provenance.add((line, SCI_NS.evidenceRole, Literal("direct_test")))
            provenance.add((line, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
            provenance.add((line, SCI_NS.independenceGroup, Literal("g1")))
            provenance.add((line, SCI_NS.evidenceIndependence, Literal("independent")))
        units = collect_evidence_units(knowledge, provenance, [CLAIM])
        line_uris = {u.line_uri for u in units}
        # Exactly line A (not line B).
        assert str(LINE_A) in line_uris
        assert str(LINE_B) not in line_uris
        assert len(line_uris) == 1
