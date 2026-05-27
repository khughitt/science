from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.gene_crosswalk import (
    AmbiguousGeneMatch,
    GeneCrosswalkError,
    ResolvedGeneMatch,
    available_gene_keys,
    to_canonical,
)

_FIX = Path(__file__).parent / "fixtures" / "commons" / "gene-crosswalk"
_DATA = Path(__file__).parent / "fixtures" / "commons" / "gene-crosswalk-data"


def _kw() -> dict:
    return {"commons_root": _FIX, "data_root": _DATA}


def test_available_keys_are_the_gene_keys() -> None:
    keys = available_gene_keys(**_kw())
    assert keys == {
        "9606|hgnc|HGNC:5",
        "9606|hgnc|HGNC:37133",
        "9606|hgnc|HGNC:99991",
        "9606|hgnc|HGNC:99992",
    }


def test_resolve_by_hgnc_id_exact() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_id", gene_id="HGNC:5", **_kw())
    assert isinstance(m, ResolvedGeneMatch)
    assert m.gene_key == "9606|hgnc|HGNC:5"
    assert m.symbol == "A1BG"
    assert m.entrez_id == "1"
    assert m.ensembl_gene_id == "ENSG00000121410"
    assert m.match_type == "exact"
    assert m.status == "approved"
    assert m.replacement_gene_key is None


def test_resolve_by_current_symbol() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="A1BG", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:5"
    assert m.match_type == "exact"


def test_resolve_by_prev_symbol() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="A1BGAS", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:37133"
    assert m.match_type == "prev_symbol"


def test_resolve_by_unique_alias() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="FLJ23569", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:37133"
    assert m.match_type == "alias_symbol"


def test_shared_alias_is_ambiguous_with_no_gene_key() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="XYZ", **_kw())
    assert isinstance(m, AmbiguousGeneMatch)
    assert set(m.candidates) == {"9606|hgnc|HGNC:5", "9606|hgnc|HGNC:37133"}
    assert not hasattr(m, "gene_key")


def test_resolve_by_entrez() -> None:
    m = to_canonical(taxon=9606, namespace="entrez", gene_id="503538", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:37133"


def test_resolve_by_ensembl() -> None:
    m = to_canonical(taxon=9606, namespace="ensembl", gene_id="ENSG00000121410", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:5"


def test_merged_id_surfaces_status_and_forward_pointer_not_auto_followed() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_id", gene_id="HGNC:99991", **_kw())
    assert isinstance(m, ResolvedGeneMatch)
    assert m.gene_key == "9606|hgnc|HGNC:99991"  # the matched (merged) row, NOT the target
    assert m.status == "merged"
    assert m.replacement_gene_key == "9606|hgnc|HGNC:5"


def test_split_id_is_ambiguous_over_forward_targets() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_id", gene_id="HGNC:99992", **_kw())
    assert isinstance(m, AmbiguousGeneMatch)
    assert set(m.candidates) == {"9606|hgnc|HGNC:5", "9606|hgnc|HGNC:37133"}


def test_unknown_id_returns_none() -> None:
    assert to_canonical(taxon=9606, namespace="hgnc_id", gene_id="HGNC:00000", **_kw()) is None


def test_other_taxon_returns_none() -> None:
    # v1 crosswalk is human-only; a non-human taxon resolves nothing (and the
    # resolver does NOT parse the taxon out of the opaque gene_key).
    assert to_canonical(taxon=10090, namespace="hgnc_id", gene_id="HGNC:5", **_kw()) is None


def test_unsupported_namespace_raises() -> None:
    with pytest.raises(GeneCrosswalkError, match="unsupported gene namespace"):
        to_canonical(taxon=9606, namespace="refseq", gene_id="NM_000014", **_kw())


# --- pure row validation (no I/O) ---


def test_parse_rejects_duplicate_member_key() -> None:
    from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows

    rows = [
        {"gene_key": "9606|hgnc|HGNC:5", "status": "approved"},
        {"gene_key": "9606|hgnc|HGNC:5", "status": "approved"},
    ]
    with pytest.raises(GeneCrosswalkError, match="duplicate member key"):
        _parse_crosswalk_rows(rows)


def test_parse_rejects_blank_key() -> None:
    from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows

    with pytest.raises(GeneCrosswalkError, match="blank gene_key"):
        _parse_crosswalk_rows([{"gene_key": "  ", "status": "approved"}])


def test_parse_rejects_missing_column() -> None:
    from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows

    with pytest.raises(GeneCrosswalkError, match="missing required column"):
        _parse_crosswalk_rows([{"symbol": "A1BG", "status": "approved"}])


def test_parse_rejects_unknown_status() -> None:
    from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows

    with pytest.raises(GeneCrosswalkError, match="invalid status"):
        _parse_crosswalk_rows([{"gene_key": "9606|hgnc|HGNC:5", "status": "bogus"}])


def test_make_gene_key_is_pipe_delimited_opaque_composite() -> None:
    from science_tool.commons.gene_crosswalk import make_gene_key

    assert make_gene_key(9606, "HGNC:5") == "9606|hgnc|HGNC:5"
