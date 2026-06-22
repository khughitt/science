# tests/test_dataset_prioritize.py
from __future__ import annotations

from science_tool.dataset_prioritize import readiness_for, readiness_weight


def _ext(level: str, verified: bool, availability: str = "available") -> dict:
    return {
        "id": "dataset:x", "type": "dataset", "title": "X", "status": "candidate",
        "origin": "external", "tier": "track",
        "access": {"level": level, "availability": availability, "verified": verified},
        "ontology_terms": [], "related": [],
    }


def test_readiness_for_reuses_canonical_states() -> None:
    assert readiness_for(_ext("public", False)).state == "public, unverified"
    assert readiness_for(_ext("controlled", True)).state == "available"
    assert readiness_for(_ext("public", False, availability="embargoed")).state == "embargoed"


def test_readiness_weight_ordering_and_flagged_default() -> None:
    # available > unverified-public > unverified-controlled > embargoed
    w_avail, f_avail = readiness_weight(_ext("controlled", True))
    w_pub, _ = readiness_weight(_ext("public", False))
    w_ctrl, _ = readiness_weight(_ext("controlled", False))
    w_emb, _ = readiness_weight(_ext("public", False, availability="embargoed"))
    assert w_avail == 1.0
    assert w_avail > w_pub > w_ctrl > w_emb
    assert f_avail == []
    # an unparseable / unknown-origin entity flags rather than silently bucketing
    w_unk, f_unk = readiness_weight({"id": "dataset:b", "type": "dataset", "title": "B"})
    assert w_unk == 0.1
    assert "readiness-unresolved" in f_unk
