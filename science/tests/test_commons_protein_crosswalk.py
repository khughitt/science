from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.protein_crosswalk import (
    AmbiguousProteinMatch,
    ProteinCrosswalkError,
    ResolvedProteinMatch,
    available_protein_keys,
    to_canonical,
)

_FIX = Path(__file__).parent / "fixtures" / "commons" / "protein-crosswalk"
_DATA = Path(__file__).parent / "fixtures" / "commons" / "protein-crosswalk-data"


def _kw() -> dict:
    return {"commons_root": _FIX, "data_root": _DATA}


def test_available_keys_are_the_protein_keys() -> None:
    keys = available_protein_keys(**_kw())
    assert keys == {
        "9606|uniprot|P04217",
        "9606|uniprot|P31946",
        "9606|uniprot|Q9NQ94",
        "9606|uniprot|P99999",
    }


def test_resolve_by_uniprot_accession_exact() -> None:
    m = to_canonical(taxon=9606, namespace="uniprot", protein_id="P04217", **_kw())
    assert isinstance(m, ResolvedProteinMatch)
    assert m.protein_key == "9606|uniprot|P04217"
    assert m.entry_name == "A1BG_HUMAN"
    assert m.gene_key == ("9606|hgnc|HGNC:5",)
    assert m.match_type == "exact"
    assert m.isoform is None
    assert m.status == "approved"
    assert m.replacement_protein_key is None


def test_resolve_by_entry_name() -> None:
    m = to_canonical(taxon=9606, namespace="uniprot_entry_name", protein_id="1433B_HUMAN", **_kw())
    assert isinstance(m, ResolvedProteinMatch) and m.protein_key == "9606|uniprot|P31946"
    assert m.match_type == "entry_name"


def test_resolve_by_ensembl_protein() -> None:
    m = to_canonical(taxon=9606, namespace="ensembl_protein", protein_id="ENSP00000300161", **_kw())
    assert isinstance(m, ResolvedProteinMatch) and m.protein_key == "9606|uniprot|P31946"
    assert m.match_type == "ensembl_protein"


def test_resolve_by_refseq_protein() -> None:
    m = to_canonical(taxon=9606, namespace="refseq_protein", protein_id="NP_055521", **_kw())
    assert isinstance(m, ResolvedProteinMatch) and m.protein_key == "9606|uniprot|Q9NQ94"
    assert m.match_type == "refseq_protein"


def test_isoform_input_surfaces_canonical_not_collapsed() -> None:
    m = to_canonical(taxon=9606, namespace="uniprot", protein_id="P31946-2", **_kw())
    assert isinstance(m, ResolvedProteinMatch)
    assert m.protein_key == "9606|uniprot|P31946"  # the canonical member row
    assert m.match_type == "isoform"
    assert m.isoform == "P31946-2"  # the queried isoform preserved, not collapsed


def test_shared_ensembl_protein_is_ambiguous_with_no_protein_key() -> None:
    m = to_canonical(taxon=9606, namespace="ensembl_protein", protein_id="ENSPSHARED", **_kw())
    assert isinstance(m, AmbiguousProteinMatch)
    assert set(m.candidates) == {"9606|uniprot|P04217", "9606|uniprot|Q9NQ94"}
    assert not hasattr(m, "protein_key")


def test_merged_accession_surfaces_status_and_forward_pointer_not_auto_followed() -> None:
    m = to_canonical(taxon=9606, namespace="uniprot", protein_id="P99999", **_kw())
    assert isinstance(m, ResolvedProteinMatch)
    assert m.protein_key == "9606|uniprot|P99999"  # the matched (merged) row, NOT the target
    assert m.status == "merged"
    assert m.replacement_protein_key == "9606|uniprot|P04217"


def test_unknown_id_returns_none() -> None:
    assert to_canonical(taxon=9606, namespace="uniprot", protein_id="P00000", **_kw()) is None


def test_other_taxon_returns_none() -> None:
    # v1 crosswalk is human-only; a non-human taxon resolves nothing (and the
    # resolver does NOT parse the taxon out of the opaque protein_key).
    assert to_canonical(taxon=10090, namespace="uniprot", protein_id="P04217", **_kw()) is None


def test_unsupported_namespace_raises() -> None:
    with pytest.raises(ProteinCrosswalkError, match="unsupported protein namespace"):
        to_canonical(taxon=9606, namespace="entrez", protein_id="1", **_kw())


# --- pure row validation (no I/O) ---


def test_parse_rejects_duplicate_member_key() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    rows = [
        {"protein_key": "9606|uniprot|P04217", "status": "approved"},
        {"protein_key": "9606|uniprot|P04217", "status": "approved"},
    ]
    with pytest.raises(ProteinCrosswalkError, match="duplicate member key"):
        _parse_crosswalk_rows(rows)


def test_parse_rejects_blank_key() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    with pytest.raises(ProteinCrosswalkError, match="blank protein_key"):
        _parse_crosswalk_rows([{"protein_key": "  ", "status": "approved"}])


def test_parse_rejects_missing_column() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    with pytest.raises(ProteinCrosswalkError, match="missing required column"):
        _parse_crosswalk_rows([{"entry_name": "A1BG_HUMAN", "status": "approved"}])


def test_parse_rejects_unknown_status() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    with pytest.raises(ProteinCrosswalkError, match="invalid status"):
        _parse_crosswalk_rows([{"protein_key": "9606|uniprot|P04217", "status": "bogus"}])


def test_parse_rejects_merged_with_wrong_replacement_count() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    with pytest.raises(ProteinCrosswalkError, match="merged.*requires"):
        _parse_crosswalk_rows([{"protein_key": "9606|uniprot|P99999", "status": "merged", "replacement_protein_keys": ""}])


def test_make_protein_key_is_pipe_delimited_opaque_composite() -> None:
    from science_tool.commons.protein_crosswalk import make_protein_key

    assert make_protein_key(9606, "P04217") == "9606|uniprot|P04217"
