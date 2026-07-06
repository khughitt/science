"""Task 4b: channel-driven edge styling.

Tests verify:
1. Proposition channel fields map to a 5-value derived edge status via
   derived_edge_status at the render/style boundary.
2. Axis-specific styling is driven by orthogonal channels INDEPENDENTLY of
   edge_status: two edges with the SAME derived edge_status but DIFFERENT polarity
   produce DIFFERENT hues, proving styling is channel-driven.
3. identification → line-style (arrowhead already covered in existing tests).
4. belief_magnitude → intensity (penwidth/opacity).
5. contested → overlay (style suffix).
"""

from __future__ import annotations

import pytest

from science_tool.dag.render import style_for_edge

# ---------------------------------------------------------------------------
# Helpers — construct minimal edge dicts using the new channel fields
# ---------------------------------------------------------------------------


def _channel_edge(
    *,
    polarity: str = "unsigned",
    identification: str = "observational",
    belief_magnitude: str = "speculative",
    claim_layer: str = "causal_effect",
    refuted: bool = False,
    has_grounding_evidence: bool = False,
    contested: bool = False,
    beta: float | None = None,
    hdi_low: float | None = None,
    hdi_high: float | None = None,
    **extra: object,
) -> dict:  # type: ignore[type-arg]
    """Build a minimal edge record using the new orthogonal channel fields."""
    edge: dict = {  # type: ignore[type-arg]
        "source": "a",
        "target": "b",
        "polarity": polarity,
        "identification": identification,
        "belief_magnitude": belief_magnitude,
        "claim_layer": claim_layer,
        "refuted": refuted,
        "has_grounding_evidence": has_grounding_evidence,
        "contested": contested,
    }
    if beta is not None or hdi_low is not None or hdi_high is not None:
        post: dict = {}  # type: ignore[type-arg]
        if beta is not None:
            post["beta"] = beta
        if hdi_low is not None:
            post["hdi_low"] = hdi_low
        if hdi_high is not None:
            post["hdi_high"] = hdi_high
        edge["posterior"] = post
    edge.update(extra)
    return edge


# ===========================================================================
# 1. derived_edge_status is called at the style boundary.
# ===========================================================================


class TestDerivedStatus:
    """edge_status is derived via derived_edge_status from channel fields."""

    def test_refuted_yields_eliminated(self) -> None:
        edge = _channel_edge(refuted=True, has_grounding_evidence=True)
        attrs = style_for_edge(edge)
        assert attrs["derived_edge_status"] == "eliminated"

    def test_no_grounding_yields_unknown(self) -> None:
        edge = _channel_edge(refuted=False, has_grounding_evidence=False)
        attrs = style_for_edge(edge)
        assert attrs["derived_edge_status"] == "unknown"

    def test_structural_claim_with_grounding_yields_structural(self) -> None:
        edge = _channel_edge(
            refuted=False,
            has_grounding_evidence=True,
            claim_layer="structural_claim",
        )
        attrs = style_for_edge(edge)
        assert attrs["derived_edge_status"] == "structural"

    def test_supported_magnitude_yields_supported(self) -> None:
        edge = _channel_edge(
            refuted=False,
            has_grounding_evidence=True,
            claim_layer="causal_effect",
            belief_magnitude="supported",
        )
        attrs = style_for_edge(edge)
        assert attrs["derived_edge_status"] == "supported"

    def test_well_supported_magnitude_yields_supported(self) -> None:
        edge = _channel_edge(
            refuted=False,
            has_grounding_evidence=True,
            claim_layer="causal_effect",
            belief_magnitude="well_supported",
        )
        attrs = style_for_edge(edge)
        assert attrs["derived_edge_status"] == "supported"

    def test_non_supported_magnitude_with_grounding_yields_tentative(self) -> None:
        edge = _channel_edge(
            refuted=False,
            has_grounding_evidence=True,
            claim_layer="causal_effect",
            belief_magnitude="fragile",
        )
        attrs = style_for_edge(edge)
        assert attrs["derived_edge_status"] == "tentative"


# ===========================================================================
# 2. Channel-driven hue: same edge_status, different polarity → different hue
# ===========================================================================


class TestPolarityDrivesHue:
    """Polarity drives hue INDEPENDENT of derived edge_status."""

    @pytest.fixture
    def base_kwargs(self) -> dict:  # type: ignore[type-arg]
        # Both edges will have the same derived_edge_status = "tentative"
        return {
            "refuted": False,
            "has_grounding_evidence": True,
            "claim_layer": "causal_effect",
            "belief_magnitude": "fragile",
        }

    def test_positive_vs_negative_different_hue(self, base_kwargs: dict) -> None:  # type: ignore[type-arg]
        pos_edge = _channel_edge(polarity="positive", **base_kwargs)
        neg_edge = _channel_edge(polarity="negative", **base_kwargs)
        pos_attrs = style_for_edge(pos_edge)
        neg_attrs = style_for_edge(neg_edge)
        # Same derived status
        assert pos_attrs["derived_edge_status"] == neg_attrs["derived_edge_status"] == "tentative"
        # Different hues
        assert pos_attrs["color"] != neg_attrs["color"], (
            f"positive ({pos_attrs['color']}) and negative ({neg_attrs['color']}) "
            "polarity must produce different hues"
        )

    def test_positive_vs_unsigned_different_hue(self, base_kwargs: dict) -> None:  # type: ignore[type-arg]
        pos_edge = _channel_edge(polarity="positive", **base_kwargs)
        uns_edge = _channel_edge(polarity="unsigned", **base_kwargs)
        pos_attrs = style_for_edge(pos_edge)
        uns_attrs = style_for_edge(uns_edge)
        assert pos_attrs["derived_edge_status"] == uns_attrs["derived_edge_status"]
        assert pos_attrs["color"] != uns_attrs["color"]

    def test_unsigned_vs_not_applicable_different_hue(self, base_kwargs: dict) -> None:  # type: ignore[type-arg]
        uns_edge = _channel_edge(polarity="unsigned", **base_kwargs)
        na_edge = _channel_edge(polarity="not_applicable", **base_kwargs)
        uns_attrs = style_for_edge(uns_edge)
        na_attrs = style_for_edge(na_edge)
        assert uns_attrs["color"] != na_attrs["color"]


# ===========================================================================
# 3. Identification → line-style (structural identification → dotted)
# ===========================================================================


class TestIdentificationDrivesStyle:
    def test_structural_identification_yields_dotted(self) -> None:
        edge = _channel_edge(
            identification="structural",
            has_grounding_evidence=True,
            claim_layer="structural_claim",
        )
        attrs = style_for_edge(edge)
        assert attrs["style"] == '"dotted"'

    def test_interventional_yields_diamond_arrowhead(self) -> None:
        edge = _channel_edge(
            identification="interventional",
            has_grounding_evidence=True,
            belief_magnitude="supported",
        )
        attrs = style_for_edge(edge)
        assert attrs["arrowhead"] == "diamond"

    def test_longitudinal_yields_odot_arrowhead(self) -> None:
        edge = _channel_edge(
            identification="longitudinal",
            has_grounding_evidence=True,
            belief_magnitude="supported",
        )
        attrs = style_for_edge(edge)
        assert attrs["arrowhead"] == "odot"

    def test_observational_yields_normal_arrowhead(self) -> None:
        edge = _channel_edge(identification="observational", has_grounding_evidence=True)
        attrs = style_for_edge(edge)
        assert attrs["arrowhead"] == "normal"


# ===========================================================================
# 4. belief_magnitude → intensity (penwidth / color intensity)
# ===========================================================================


class TestBeliefMagnitudeDrivesIntensity:
    """well_supported/supported edges carry stronger visual weight than fragile/speculative."""

    def test_well_supported_penwidth_ge_supported(self) -> None:
        ws = style_for_edge(
            _channel_edge(has_grounding_evidence=True, belief_magnitude="well_supported")
        )
        s = style_for_edge(
            _channel_edge(has_grounding_evidence=True, belief_magnitude="supported")
        )
        # Both should have penwidth >= the default for weaker magnitudes
        fragile = style_for_edge(
            _channel_edge(has_grounding_evidence=True, belief_magnitude="fragile")
        )
        ws_pw = float(ws["penwidth"])
        s_pw = float(s["penwidth"])
        f_pw = float(fragile["penwidth"])
        assert ws_pw >= s_pw, "well_supported should not be narrower than supported"
        assert s_pw >= f_pw, "supported should not be narrower than fragile"


# ===========================================================================
# 5. contested → overlay (style includes dashed or label marker)
# ===========================================================================


class TestContestedOverlay:
    def test_contested_adds_dashed_style_or_label_marker(self) -> None:
        contested_edge = _channel_edge(
            has_grounding_evidence=True,
            belief_magnitude="supported",
            contested=True,
        )
        uncontested_edge = _channel_edge(
            has_grounding_evidence=True,
            belief_magnitude="supported",
            contested=False,
        )
        c_attrs = style_for_edge(contested_edge)
        u_attrs = style_for_edge(uncontested_edge)
        # contested must produce a visually distinct output (either different
        # style, a [?] label marker, or a different fontcolor/color)
        differs = (
            c_attrs.get("style") != u_attrs.get("style")
            or c_attrs.get("label") != u_attrs.get("label")
            or c_attrs.get("fontcolor") != u_attrs.get("fontcolor")
        )
        assert differs, (
            "contested=True must produce some visual difference vs contested=False: "
            f"contested={c_attrs}, uncontested={u_attrs}"
        )


# ===========================================================================
# 6. Channel fields are required.
# ===========================================================================


def test_edge_without_channels_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing channel field"):
        style_for_edge({"source": "a", "target": "b", "edge_status": "supported"})
