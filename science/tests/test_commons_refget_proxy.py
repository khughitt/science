from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.refget_proxy import RefgetProxy
from science_tool.commons.sequence_store import open_store, refget_digest

_SEQ = "ACGTACGTACGTACGTTTTTGGGGCCCC"


def _proxy(tmp_path: Path) -> tuple[RefgetProxy, str]:
    digest = refget_digest(_SEQ)
    (tmp_path / digest).write_text(_SEQ, encoding="ascii")
    return RefgetProxy(store=open_store(tmp_path)), digest


def test_get_sequence_by_ga4gh_and_bare_digest(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    assert proxy.get_sequence(f"ga4gh:{digest}", 0, 4) == "ACGT"
    assert proxy.get_sequence(digest, 0, 4) == "ACGT"


def test_get_metadata_exposes_ga4gh_alias_and_length(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    meta = proxy.get_metadata(f"ga4gh:{digest}")
    assert meta["length"] == len(_SEQ)
    assert f"ga4gh:{digest}" in meta["aliases"]


def test_missing_identifier_fails_loud_no_network(tmp_path: Path) -> None:
    proxy = RefgetProxy(store=open_store(tmp_path))
    with pytest.raises(LookupError):
        proxy.get_sequence("ga4gh:SQ.absent", 0, 1)


def test_derive_refget_accession_validates_and_returns_bare_digest(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    assert proxy.derive_refget_accession(digest) == digest
    assert proxy.derive_refget_accession(f"ga4gh:{digest}") == digest

    with pytest.raises(LookupError):
        proxy.derive_refget_accession("ga4gh:SQ.absent")
