"""Permanent spike contract for the future ``commons/vrs.py`` adapter.

These tests pin the installed ga4gh.vrs API surface needed to normalize
alleles and compute VRS identifiers through an injected in-memory DataProxy.
They intentionally avoid SeqRepo and network access so later production code
can preserve that dependency boundary.
"""

import pytest

pytest.importorskip("ga4gh.vrs")

from ga4gh.core import ga4gh_identify, sha512t24u
from ga4gh.vrs.extras.translator import AlleleTranslator


_SEQ = "CGTACGTACGTACGTACGTACGTACGTACGTACGTACGTA"
_REPEAT_SEQ = "CCCCAAAAAGGGGTTTTCCCC"


def _refget_digest(seq: str) -> str:
    return "SQ." + sha512t24u(seq.encode("ascii"))


class _MemoryProxy:
    def __init__(self, seq: str) -> None:
        self._seq = seq
        self._sq = _refget_digest(seq)
        self._identifiers = {self._sq, f"ga4gh:{self._sq}"}

    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str:
        if identifier not in self._identifiers:
            raise KeyError(identifier)
        return self._seq[start:end]

    def get_metadata(self, identifier: str) -> dict[str, object]:
        if identifier not in self._identifiers:
            raise KeyError(identifier)
        return {
            "length": len(self._seq),
            "aliases": [f"ga4gh:{self._sq}"],
            "alphabet": "ACGT",
        }

    def derive_refget_accession(self, identifier: str) -> str | None:
        if identifier not in self._identifiers:
            raise KeyError(identifier)
        return self._sq


def test_vrs_identifies_an_snv_through_custom_proxy_offline() -> None:
    proxy = _MemoryProxy(_SEQ)
    sq = _refget_digest(_SEQ)
    tlr = AlleleTranslator(data_proxy=proxy)

    allele_id = ga4gh_identify(tlr.translate_from(f"{sq}:5:G:T", fmt="spdi"))
    repeated_id = ga4gh_identify(tlr.translate_from(f"{sq}:5:G:T", fmt="spdi"))

    assert allele_id.startswith("ga4gh:VA.")
    assert repeated_id == allele_id


def test_equivalent_indel_representations_share_one_id() -> None:
    proxy = _MemoryProxy(_REPEAT_SEQ)
    sq = _refget_digest(_REPEAT_SEQ)
    tlr = AlleleTranslator(data_proxy=proxy)

    a = ga4gh_identify(tlr.translate_from(f"{sq}:4:A:", fmt="spdi", do_normalize=True))
    b = ga4gh_identify(tlr.translate_from(f"{sq}:5:A:", fmt="spdi", do_normalize=True))

    assert a == b
