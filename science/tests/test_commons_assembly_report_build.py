from __future__ import annotations

import pytest

from science_tool.commons.assembly_report_build import parse_assembly_report

_REPORT = (
    "# Assembly name:  GRCh38\n"
    "# Sequence-Name\tSequence-Role\tAssigned-Molecule\tAssigned-Molecule-Location/Type\t"
    "GenBank-Accn\tRelationship\tRefSeq-Accn\tAssembly-Unit\tSequence-Length\tUCSC-style-name\n"
    "1\tassembled-molecule\t1\tChromosome\tCM000663.2\t=\tNC_000001.11\tPrimary Assembly\t248956422\tchr1\n"
    "MT\tassembled-molecule\tMT\tMitochondrion\tJ01415.2\t=\tNC_012920.1\tnon-nuclear\t16569\tchrM\n"
)


_CONTIGS = [
    {
        "seqcol_digest": "DIGEST38",
        "sequence_index": 0,
        "name": "1",
        "refget_digest": "SQ.chr1",
        "length": 248956422,
    },
    {"seqcol_digest": "DIGEST38", "sequence_index": 1, "name": "MT", "refget_digest": "SQ.mt", "length": 16569},
]


def test_parse_assembly_report_emits_alias_rows_per_kind() -> None:
    aliases = parse_assembly_report(_REPORT)
    chr1 = {(a["alias"], a["alias_kind"]) for a in aliases if a["sequence_name"] == "1"}
    assert chr1 == {
        ("1", "seqcol_name"),
        ("CM000663.2", "genbank_accession"),
        ("NC_000001.11", "refseq_accession"),
        ("chr1", "ucsc"),
    }
    nc = next(a for a in aliases if a["alias"] == "NC_000001.11")
    assert nc["sequence_accession"] == "NC_000001.11"
    assert nc["alias_kind"] == "refseq_accession"


def test_build_contig_alias_rows_joins_by_sequence_name_and_rejects_unmatched() -> None:
    from science_tool.commons.assembly_report_build import build_contig_alias_rows, parse_assembly_report

    aliases = build_contig_alias_rows(contig_rows=_CONTIGS, report_rows=parse_assembly_report(_REPORT))
    assert {
        "seqcol_digest": "DIGEST38",
        "refget_digest": "SQ.chr1",
        "alias": "NC_000001.11",
        "alias_kind": "refseq_accession",
        "sequence_accession": "NC_000001.11",
    } in aliases

    with pytest.raises(ValueError, match="assembly-report sequence name"):
        build_contig_alias_rows(contig_rows=_CONTIGS[:1], report_rows=parse_assembly_report(_REPORT))


def test_build_contig_alias_rows_rejects_contig_name_missing_from_report() -> None:
    from science_tool.commons.assembly_report_build import build_contig_alias_rows, parse_assembly_report

    with pytest.raises(ValueError, match="seqcol contig name '2' has no assembly-report row"):
        build_contig_alias_rows(
            contig_rows=[
                *_CONTIGS,
                {
                    "seqcol_digest": "DIGEST38",
                    "sequence_index": 2,
                    "name": "2",
                    "refget_digest": "SQ.chr2",
                    "length": 242193529,
                },
            ],
            report_rows=parse_assembly_report(_REPORT),
        )


def test_parse_assembly_report_rejects_header_missing_required_columns() -> None:
    report = (
        "# Sequence-Name\tSequence-Role\tGenBank-Accn\tRefSeq-Accn\n1\tassembled-molecule\tCM000663.2\tNC_000001.11\n"
    )

    with pytest.raises(ValueError, match="assembly report header missing required columns"):
        parse_assembly_report(report)


def test_build_contig_alias_rows_rejects_duplicate_seqcol_contig_name() -> None:
    from science_tool.commons.assembly_report_build import build_contig_alias_rows, parse_assembly_report

    with pytest.raises(ValueError, match="duplicate seqcol contig name '1'"):
        build_contig_alias_rows(contig_rows=[*_CONTIGS, _CONTIGS[0]], report_rows=parse_assembly_report(_REPORT))
