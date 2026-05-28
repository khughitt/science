from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.refget_proxy import RefgetProxy
from science_tool.commons.sequence_store import open_store, refget_digest
from science_tool.commons.vrs import compute_vrs_id

_SEQ = "CGTACGTACGTACGTACGTACGTACGTACGTACGTACGTA"

# GOLDEN: captured once from compute_vrs_id(... ) against pinned ga4gh.vrs;
# regenerate + re-review only on deliberate version bump.
_GOLDEN_SNV = "ga4gh:VA._uAlNwdTfBSPBnzSA68-6sKBm8brTU2K"


def _proxy(tmp_path: Path) -> tuple[RefgetProxy, str]:
    digest = refget_digest(_SEQ)
    (tmp_path / digest).write_text(_SEQ, encoding="ascii")
    return RefgetProxy(store=open_store(tmp_path)), digest


def test_compute_vrs_id_from_spdi_is_deterministic(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    expr = f"ga4gh:{digest}:5:G:T"
    vid = compute_vrs_id(proxy, fmt="spdi", expr=expr)
    assert vid.startswith("ga4gh:VA.")
    assert compute_vrs_id(proxy, fmt="spdi", expr=expr) == vid


def test_spdi_snv_matches_pinned_golden(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    assert compute_vrs_id(proxy, fmt="spdi", expr=f"ga4gh:{digest}:5:G:T") == _GOLDEN_SNV


def test_same_change_on_a_different_sequence_is_a_different_id(tmp_path: Path) -> None:
    other = "TTTTCGTACGTACGTACGTACGTACGTACGTACGTACGTA"
    od = refget_digest(other)
    (tmp_path / od).write_text(other, encoding="ascii")
    proxy = RefgetProxy(store=open_store(tmp_path))
    base, _ = _proxy(tmp_path)
    a = compute_vrs_id(base, fmt="spdi", expr=f"ga4gh:{refget_digest(_SEQ)}:5:G:T")
    b = compute_vrs_id(proxy, fmt="spdi", expr=f"ga4gh:{od}:5:G:T")
    assert a != b


def test_compute_vrs_id_rejects_uncovered_formats(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    with pytest.raises(ValueError, match="unsupported variant fmt 'gnomad'"):
        compute_vrs_id(proxy, fmt="gnomad", expr=f"ga4gh:{digest}:5:G:T")
