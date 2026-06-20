"""Task 5f: edges.yaml retired as epistemic source-of-truth.

The DAG becomes a VIEW over compiled relational propositions:

1. ``edges_from_propositions`` SOURCES edges from compiled
   ``PropositionEntity`` records — each proposition → an edge dict carrying the
   orthogonal *authored* channel fields (polarity / claim_layer /
   identification) so ``style_for_edge`` runs in CHANNEL mode and DERIVES
   ``edge_status`` via ``derived_edge_status`` (never read from an authored
   ``edge_status``).

2. ``EdgesYamlFile`` is demoted to a LEGACY-IMPORT ADAPTER: it can still be
   READ via ``load_legacy_edges_yaml`` (so existing edges.yaml inputs load) but
   doing so emits a DEPRECATION warning, and its authored ``edge_status`` is
   NEVER consumed as the epistemic status — the derived status from the
   channels wins.
"""

from __future__ import annotations

import warnings

import pytest
from science_model.propositions import PropositionEntity

from science_tool.dag.proposition_edges import edges_from_propositions
from science_tool.dag.render import style_for_edge
from science_tool.dag.schema import EdgesYamlFile, load_legacy_edges_yaml

# ---------------------------------------------------------------------------
# 1. Propositions are the epistemic source-of-truth for edges.
# ---------------------------------------------------------------------------


def _proposition(
    *,
    subject: str,
    obj: str,
    predicate: str,
    polarity: str | None,
    claim_layer: str | None = None,
    identification_strength: str | None = None,
) -> PropositionEntity:
    return PropositionEntity(
        id=f"proposition:{subject}-{predicate}-{obj}",
        subject=subject,
        object=obj,
        predicate=predicate,
        polarity=polarity,
        claim_layer=claim_layer,
        identification_strength=identification_strength,
    )


class TestEdgesSourcedFromPropositions:
    def test_proposition_becomes_edge_with_subject_object_endpoints(self) -> None:
        prop = _proposition(
            subject="a", obj="b", predicate="affects", polarity="positive"
        )
        edges = edges_from_propositions([prop])
        assert len(edges) == 1
        edge = edges[0]
        assert edge["source"] == "a"
        assert edge["target"] == "b"
        # The proposition's polarity rides on the hue channel.
        assert edge["polarity"] == "positive"

    def test_edge_runs_in_channel_mode_and_derives_status(self) -> None:
        # Ungrounded proposition (no belief/grounding wired) → derived "unknown".
        prop = _proposition(
            subject="a", obj="b", predicate="affects", polarity="positive"
        )
        edge = edges_from_propositions([prop])[0]
        attrs = style_for_edge(edge)
        # edge_status is DERIVED, not authored — no edge_status key on the edge.
        assert "edge_status" not in edge
        assert attrs["derived_edge_status"] == "unknown"

    def test_structural_claim_polarity_drives_channels_not_authored_status(self) -> None:
        # Two propositions with DIFFERENT polarity must produce DIFFERENT hues,
        # proving styling is channel-driven (Task 4b) off the proposition axes.
        pos = _proposition(
            subject="a", obj="b", predicate="affects", polarity="positive"
        )
        neg = _proposition(
            subject="c", obj="d", predicate="affects", polarity="negative"
        )
        pos_attrs = style_for_edge(edges_from_propositions([pos])[0])
        neg_attrs = style_for_edge(edges_from_propositions([neg])[0])
        assert pos_attrs["color"] != neg_attrs["color"]

    def test_identification_strength_rides_the_line_style_channel(self) -> None:
        prop = _proposition(
            subject="a",
            obj="b",
            predicate="is_proxy_for",
            polarity=None,
            claim_layer="structural_claim",
            identification_strength="interventional",
        )
        edge = edges_from_propositions([prop])[0]
        attrs = style_for_edge(edge)
        assert attrs["arrowhead"] == "diamond"


# ---------------------------------------------------------------------------
# 2. edges.yaml is a deprecated legacy-import adapter — never a status SoT.
# ---------------------------------------------------------------------------

_LEGACY_YAML = """\
dag: legacy
source_dot: doc/figures/dags/legacy.dot
edges:
- id: 1
  source: a
  target: b
  edge_status: supported
  identification: observational
  description: legacy authored edge
"""


class TestEdgesYamlDeprecatedAdapter:
    def test_loading_edges_yaml_emits_deprecation(self) -> None:
        with pytest.warns(DeprecationWarning, match="epistemic source-of-truth"):
            model = load_legacy_edges_yaml(_LEGACY_YAML)
        assert isinstance(model, EdgesYamlFile)
        assert model.dag == "legacy"

    def test_model_validate_alone_also_warns(self) -> None:
        import yaml

        with pytest.warns(DeprecationWarning):
            EdgesYamlFile.model_validate(yaml.safe_load(_LEGACY_YAML))

    def test_authored_edge_status_is_not_the_epistemic_status_sot(self) -> None:
        # The authored edge_status says "supported", but when the same edge is
        # sourced through the channel-driven path WITHOUT grounding evidence,
        # the DERIVED status is "unknown" — authored status is not consulted.
        channel_edge = {
            "source": "a",
            "target": "b",
            "polarity": "positive",
            "identification": "observational",
            # No belief_magnitude/has_grounding_evidence → ungrounded.
        }
        attrs = style_for_edge(channel_edge)
        assert attrs["derived_edge_status"] == "unknown"
        assert attrs["derived_edge_status"] != "supported"


def test_no_deprecation_warning_for_proposition_sourced_edges() -> None:
    """Sourcing from propositions must NOT trip the edges.yaml deprecation."""
    prop = _proposition(subject="a", obj="b", predicate="affects", polarity="positive")
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        edges = edges_from_propositions([prop])
        style_for_edge(edges[0])
    assert edges
