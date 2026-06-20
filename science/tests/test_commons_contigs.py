from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.contigs import (
    _ALIAS_COLUMNS,
    _CONTIG_COLUMNS,
    ALIASES_RESOURCE,
    CONTIGS_RESOURCE,
    AccessionAssemblyMismatch,
    AmbiguousContig,
    ContigError,
    ContigMatch,
    _AliasRow,
    _ContigRow,
    _parse_alias_rows,
    _parse_contig_rows,
    _validate_alias_contig_refs,
    _validate_header,
    resolve_contig,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "commons"


def _kw() -> dict[str, Path]:
    return {
        "commons_root": _FIXTURES / "assembly-c4a",
        "data_root": _FIXTURES / "assembly-c4a-data",
    }


def test_resolve_by_refseq_accession() -> None:
    match = resolve_contig("NC_000001.11", seqcol_digest="DIGEST38", **_kw())

    assert match == ContigMatch(
        refget_digest="SQ.chr1_38",
        name="1",
        length=248956422,
        alias_kind="refseq_accession",
    )


def test_resolve_by_ucsc_and_bare_label() -> None:
    assert resolve_contig("chr1", seqcol_digest="DIGEST38", **_kw()) == ContigMatch(
        refget_digest="SQ.chr1_38",
        name="1",
        length=248956422,
        alias_kind="ucsc",
    )
    assert resolve_contig("1", seqcol_digest="DIGEST38", **_kw()) == ContigMatch(
        refget_digest="SQ.chr1_38",
        name="1",
        length=248956422,
        alias_kind="seqcol_name",
    )


def test_unknown_alias_is_error() -> None:
    with pytest.raises(ContigError, match="unknown contig"):
        resolve_contig("chrZ", seqcol_digest="DIGEST38", **_kw())


def test_accession_from_wrong_assembly_is_mismatch() -> None:
    result = resolve_contig("NC_000001.10", seqcol_digest="DIGEST38", **_kw())

    assert result == AccessionAssemblyMismatch(
        query="NC_000001.10",
        found_seqcol_digest="DIGEST37",
    )


def test_non_accession_alias_outside_assembly_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons import contigs

    def load_fixture(resource, expected_columns, parser, *, registry_id, commons_root, data_root):
        del expected_columns, registry_id, commons_root, data_root
        rows_by_resource = {
            CONTIGS_RESOURCE: [
                {
                    "seqcol_digest": "DIGEST37",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.chr1_37",
                    "length": "249250621",
                },
                {
                    "seqcol_digest": "DIGEST36",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.chr1_36",
                    "length": "247249719",
                },
            ],
            ALIASES_RESOURCE: [
                {
                    "seqcol_digest": "DIGEST37",
                    "refget_digest": "SQ.chr1_37",
                    "alias": "chr1",
                    "alias_kind": "ucsc",
                    "sequence_accession": "",
                },
                {
                    "seqcol_digest": "DIGEST36",
                    "refget_digest": "SQ.chr1_36",
                    "alias": "chr1",
                    "alias_kind": "ucsc",
                    "sequence_accession": "",
                },
            ],
        }
        return parser(rows_by_resource[resource])

    monkeypatch.setattr(contigs, "_load", load_fixture)

    with pytest.raises(ContigError, match="unknown contig"):
        resolve_contig("chr1", seqcol_digest="DIGEST38")


def test_accession_outside_multiple_assemblies_is_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons import contigs

    def load_fixture(resource, expected_columns, parser, *, registry_id, commons_root, data_root):
        del expected_columns, registry_id, commons_root, data_root
        rows_by_resource = {
            CONTIGS_RESOURCE: [
                {
                    "seqcol_digest": "DIGEST37",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.chr1_37",
                    "length": "249250621",
                },
                {
                    "seqcol_digest": "DIGEST36",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.chr1_36",
                    "length": "247249719",
                },
            ],
            ALIASES_RESOURCE: [
                {
                    "seqcol_digest": "DIGEST37",
                    "refget_digest": "SQ.chr1_37",
                    "alias": "ACCN",
                    "alias_kind": "refseq_accession",
                    "sequence_accession": "ACCN",
                },
                {
                    "seqcol_digest": "DIGEST36",
                    "refget_digest": "SQ.chr1_36",
                    "alias": "ACCN",
                    "alias_kind": "genbank_accession",
                    "sequence_accession": "ACCN",
                },
            ],
        }
        return parser(rows_by_resource[resource])

    monkeypatch.setattr(contigs, "_load", load_fixture)

    assert resolve_contig("ACCN", seqcol_digest="DIGEST38") == AmbiguousContig(
        query="ACCN",
        candidates=("DIGEST36:SQ.chr1_36", "DIGEST37:SQ.chr1_37"),
    )


def test_alias_ambiguous_within_assembly_is_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons import contigs

    contig_rows = [
        _ContigRow(
            seqcol_digest="DIGEST38",
            sequence_index=0,
            name="1",
            refget_digest="SQ.chr1_38",
            length=248956422,
        ),
        _ContigRow(
            seqcol_digest="DIGEST38",
            sequence_index=1,
            name="1_alt",
            refget_digest="SQ.chr1_alt_38",
            length=1000,
        ),
    ]
    alias_rows = [
        _AliasRow(
            seqcol_digest="DIGEST38",
            refget_digest="SQ.chr1_38",
            alias="chr1",
            alias_kind="ucsc",
            sequence_accession="",
        ),
        _AliasRow(
            seqcol_digest="DIGEST38",
            refget_digest="SQ.chr1_alt_38",
            alias="chr1",
            alias_kind="ucsc",
            sequence_accession="",
        ),
    ]

    def load_fixture(resource, expected_columns, parser, *, registry_id, commons_root, data_root):
        del expected_columns, parser, registry_id, commons_root, data_root
        if resource == CONTIGS_RESOURCE:
            return contig_rows
        if resource == ALIASES_RESOURCE:
            return alias_rows
        raise AssertionError(f"unexpected resource {resource!r}")

    monkeypatch.setattr(contigs, "_load", load_fixture)

    assert resolve_contig("chr1", seqcol_digest="DIGEST38") == AmbiguousContig(
        query="chr1",
        candidates=("SQ.chr1_38", "SQ.chr1_alt_38"),
    )


def test_contig_parser_rejects_malformed_surplus_columns() -> None:
    with pytest.raises(ContigError, match="surplus columns"):
        _parse_contig_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.a",
                    "length": "248956422",
                    None: ["extra"],
                }
            ]
        )


def test_contig_parser_rejects_unexpected_named_column() -> None:
    with pytest.raises(ContigError, match="unexpected columns"):
        _parse_contig_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.a",
                    "length": "248956422",
                    "extra": "unexpected",
                }
            ]
        )


@pytest.mark.parametrize("column", ["seqcol_digest", "sequence_index", "name", "refget_digest", "length"])
def test_contig_parser_rejects_blank_required_fields(column: str) -> None:
    row = {
        "seqcol_digest": "DIGEST38",
        "sequence_index": "0",
        "name": "1",
        "refget_digest": "SQ.a",
        "length": "248956422",
    }
    row[column] = ""

    with pytest.raises(ContigError, match=f"blank {column}|invalid {column}"):
        _parse_contig_rows([row])


@pytest.mark.parametrize("length", ["0", "-1", "1.5", "abc"])
def test_contig_parser_rejects_invalid_length_values(length: str) -> None:
    with pytest.raises(ContigError, match="invalid length"):
        _parse_contig_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.a",
                    "length": length,
                }
            ]
        )


def test_alias_parser_rejects_malformed_surplus_columns() -> None:
    with pytest.raises(ContigError, match="surplus columns"):
        _parse_alias_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "refget_digest": "SQ.a",
                    "alias": "chr1",
                    "alias_kind": "ucsc",
                    "sequence_accession": "",
                    None: ["extra"],
                }
            ]
        )


def test_alias_parser_rejects_unexpected_named_column() -> None:
    with pytest.raises(ContigError, match="unexpected columns"):
        _parse_alias_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "refget_digest": "SQ.a",
                    "alias": "chr1",
                    "alias_kind": "ucsc",
                    "sequence_accession": "",
                    "extra": "unexpected",
                }
            ]
        )


@pytest.mark.parametrize(
    ("resource", "expected_columns", "fieldnames"),
    [
        (
            CONTIGS_RESOURCE,
            _CONTIG_COLUMNS,
            ["seqcol_digest", "sequence_index", "name", "refget_digest", "length", "length"],
        ),
        (
            ALIASES_RESOURCE,
            _ALIAS_COLUMNS,
            ["seqcol_digest", "refget_digest", "alias", "alias_kind", "sequence_accession", "alias"],
        ),
    ],
)
def test_header_validation_rejects_duplicate_columns(
    resource: str, expected_columns: frozenset[str], fieldnames: list[str]
) -> None:
    with pytest.raises(ContigError, match=f"{resource}: duplicate columns"):
        _validate_header(resource, fieldnames, expected_columns)


def test_header_validation_rejects_missing_header() -> None:
    with pytest.raises(ContigError, match=f"{CONTIGS_RESOURCE}: missing CSV header"):
        _validate_header(CONTIGS_RESOURCE, None, _CONTIG_COLUMNS)


def test_header_validation_rejects_column_set_mismatch() -> None:
    with pytest.raises(ContigError, match=f"{ALIASES_RESOURCE}: malformed CSV header"):
        _validate_header(
            ALIASES_RESOURCE,
            ["seqcol_digest", "refget_digest", "alias", "alias_kind", "extra"],
            _ALIAS_COLUMNS,
        )


@pytest.mark.parametrize("column", ["seqcol_digest", "refget_digest", "alias", "alias_kind"])
def test_alias_parser_rejects_blank_required_fields(column: str) -> None:
    row = {
        "seqcol_digest": "DIGEST38",
        "refget_digest": "SQ.a",
        "alias": "chr1",
        "alias_kind": "ucsc",
        "sequence_accession": "",
    }
    row[column] = ""

    with pytest.raises(ContigError, match=f"blank {column}"):
        _parse_alias_rows([row])


def test_alias_parser_rejects_invalid_alias_kind() -> None:
    with pytest.raises(ContigError, match="invalid alias_kind"):
        _parse_alias_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "refget_digest": "SQ.a",
                    "alias": "chr1",
                    "alias_kind": "bogus",
                    "sequence_accession": "",
                }
            ]
        )


def test_parser_rejects_duplicate_alias() -> None:
    with pytest.raises(ContigError, match="duplicate alias"):
        _parse_alias_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "refget_digest": "SQ.a",
                    "alias": "chr1",
                    "alias_kind": "ucsc",
                    "sequence_accession": "",
                },
                {
                    "seqcol_digest": "DIGEST38",
                    "refget_digest": "SQ.b",
                    "alias": "chr1",
                    "alias_kind": "ucsc",
                    "sequence_accession": "",
                },
            ]
        )


def test_parser_rejects_duplicate_contig_name() -> None:
    with pytest.raises(ContigError, match="duplicate contig name"):
        _parse_contig_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.a",
                    "length": "248956422",
                },
                {
                    "seqcol_digest": "DIGEST38",
                    "sequence_index": "1",
                    "name": "1",
                    "refget_digest": "SQ.b",
                    "length": "248956422",
                },
            ]
        )


def test_parser_rejects_duplicate_sequence_index() -> None:
    with pytest.raises(ContigError, match="duplicate sequence_index"):
        _parse_contig_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.a",
                    "length": "248956422",
                },
                {
                    "seqcol_digest": "DIGEST38",
                    "sequence_index": "0",
                    "name": "2",
                    "refget_digest": "SQ.b",
                    "length": "242193529",
                },
            ]
        )


def test_alias_referencing_missing_contig_key_is_rejected() -> None:
    contigs = {
        ("DIGEST38", "SQ.a"): _parse_contig_rows(
            [
                {
                    "seqcol_digest": "DIGEST38",
                    "sequence_index": "0",
                    "name": "1",
                    "refget_digest": "SQ.a",
                    "length": "248956422",
                }
            ]
        )[0]
    }
    aliases = _parse_alias_rows(
        [
            {
                "seqcol_digest": "DIGEST38",
                "refget_digest": "SQ.missing",
                "alias": "chr1",
                "alias_kind": "ucsc",
                "sequence_accession": "",
            }
        ]
    )

    with pytest.raises(ContigError, match="references missing contig"):
        _validate_alias_contig_refs(aliases, contigs)
