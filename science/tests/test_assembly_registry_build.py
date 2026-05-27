from __future__ import annotations

import pytest

# Import the module unconditionally: it must import cleanly WITHOUT refget
# (refget is imported lazily inside the digest functions). Only the assertions
# that actually compute a digest skip when refget is absent.
from science_tool.commons.assembly_registry_build import (
    build_registry_row,
    compute_seqcol_digest,
    fetch_seqcol_level2,
)

_L2 = {
    "names": ["chr1", "chr2"],
    "lengths": [10, 20],
    "sequences": ["SQ.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "SQ.bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
}


def test_module_imports_without_refget() -> None:
    # The lazy-import contract: importing the module does not require refget.
    assert callable(compute_seqcol_digest)
    assert callable(build_registry_row)
    assert callable(fetch_seqcol_level2)


def test_lengths_are_not_inherent() -> None:
    pytest.importorskip("refget")
    # Same names+sequences, different lengths -> identical digest. The helper
    # passes ONLY the inherent payload (names + sequences) with an explicit
    # inherent_attrs, so lengths cannot leak into the canonical id.
    other = {**_L2, "lengths": [999, 999]}
    assert compute_seqcol_digest(_L2) == compute_seqcol_digest(other)


def test_sequences_change_the_digest() -> None:
    pytest.importorskip("refget")
    other = {**_L2, "sequences": ["SQ.cccccccccccccccccccccccccccccccc", _L2["sequences"][1]]}
    assert compute_seqcol_digest(_L2) != compute_seqcol_digest(other)


def test_build_row_round_trips_when_digest_matches() -> None:
    pytest.importorskip("refget")
    digest = compute_seqcol_digest(_L2)
    row = build_registry_row(
        level2=_L2, label="TEST", accession="GCA_TEST.1", server_digest=digest, source_url="https://x"
    )
    assert row["seqcol_digest"] == digest
    assert row["label"] == "TEST"
    assert row["accession"] == "GCA_TEST.1"
    assert row["n_sequences"] == 2


def test_build_row_raises_on_digest_mismatch() -> None:
    pytest.importorskip("refget")
    with pytest.raises(ValueError, match="digest mismatch"):
        build_registry_row(
            level2=_L2,
            label="TEST",
            accession="GCA_TEST.1",
            server_digest="not-the-real-digest",
            source_url="https://x",
        )


def test_compute_forwards_only_inherent_payload_without_lengths(monkeypatch) -> None:
    # CI-running guard (no real refget): compute_seqcol_digest must forward ONLY
    # names+sequences and an explicit inherent_attrs, so lengths can never leak
    # into the canonical identity even if refget's default changed.
    import sys
    import types

    captured: dict = {}

    def _fake_seqcol_digest(payload, inherent_attrs=None):
        captured["payload"] = payload
        captured["inherent_attrs"] = inherent_attrs
        return "FAKE_DIGEST"

    fake_utils = types.ModuleType("refget.utils")
    fake_utils.seqcol_digest = _fake_seqcol_digest
    fake_refget = types.ModuleType("refget")
    fake_refget.utils = fake_utils
    monkeypatch.setitem(sys.modules, "refget", fake_refget)
    monkeypatch.setitem(sys.modules, "refget.utils", fake_utils)

    assert compute_seqcol_digest(_L2) == "FAKE_DIGEST"
    assert set(captured["payload"].keys()) == {"names", "sequences"}
    assert "lengths" not in captured["payload"]
    assert captured["inherent_attrs"] == ["names", "sequences"]
