from __future__ import annotations

import pytest

from science_tool.commons.liftover import (
    ChainFormatError,
    LiftedInterval,
    LiftoverDefect,
    lift_interval,
    parse_chain_text,
)

CHAIN = """\
chain 1000 chr1 1000 + 500 630 chr1 2000 + 1000 1140 7
50 10 20
70
"""


def test_parse_chain_text_reads_blocks() -> None:
    chains = parse_chain_text(CHAIN)
    assert len(chains) == 1
    chain = chains[0]
    assert chain.chain_id == 7
    # UCSC t* fields are the source/from side for hg19ToHg38.
    assert chain.source_name == "chr1"
    assert chain.source_start == 500
    assert chain.source_end == 630
    # UCSC q* fields are the target/to side.
    assert chain.target_name == "chr1"
    assert chain.target_start == 1000
    assert chain.target_end == 1140
    assert [(b.size, b.dt, b.dq) for b in chain.blocks] == [(50, 10, 20), (70, 0, 0)]


def test_hg19_to_hg38_direction_uses_t_as_source_and_q_as_target() -> None:
    chains = parse_chain_text(CHAIN)
    chain = chains[0]
    assert chain.source_start == 500
    assert chain.target_start == 1000


def test_parse_chain_text_rejects_ragged_block() -> None:
    with pytest.raises(ChainFormatError, match="block"):
        parse_chain_text("chain 1 chr1 100 + 0 10 chr1 100 + 0 10 1\n50 1\n")


def test_parse_chain_text_rejects_header_only_chain() -> None:
    with pytest.raises(ChainFormatError, match="block"):
        parse_chain_text("chain 1 chr1 100 + 0 10 chr1 100 + 0 10 1\n")


def test_parse_chain_text_rejects_chain_without_terminal_block() -> None:
    with pytest.raises(ChainFormatError, match="terminal"):
        parse_chain_text("chain 1 chr1 100 + 0 10 chr1 100 + 0 10 1\n5 1 1\n")


def test_parse_chain_text_rejects_new_header_after_nonterminal_block() -> None:
    text = """\
chain 1 chr1 100 + 0 10 chr1 100 + 0 10 1
5 1 1
chain 2 chr2 100 + 0 10 chr2 100 + 0 10 2
5
"""
    with pytest.raises(ChainFormatError, match="terminal"):
        parse_chain_text(text)


def test_parse_chain_text_rejects_block_after_terminal_block() -> None:
    with pytest.raises(ChainFormatError, match="terminal"):
        parse_chain_text("chain 1 chr1 100 + 0 10 chr1 100 + 0 10 1\n5\n1\n")


def test_parse_chain_text_rejects_non_decimal_integer_token() -> None:
    with pytest.raises(ChainFormatError, match="integer"):
        parse_chain_text("chain +1 chr1 100 + 0 10 chr1 100 + 0 10 1\n5\n")


def test_lift_interval_maps_plus_strand_inside_one_block() -> None:
    result = lift_interval(
        parse_chain_text(CHAIN),
        source_seqcol_digest="SRC",
        target_seqcol_digest="TGT",
        source_contig="chr1",
        start=510,
        end=511,
    )
    assert result == LiftedInterval(
        source_seqcol_digest="SRC",
        target_seqcol_digest="TGT",
        source_contig="chr1",
        target_contig="chr1",
        source_start=510,
        source_end=511,
        target_start=1010,
        target_end=1011,
        target_strand="+",
        chain_id=7,
    )


def test_lift_interval_rejects_gap_spanning_interval() -> None:
    result = lift_interval(
        parse_chain_text(CHAIN),
        source_seqcol_digest="SRC",
        target_seqcol_digest="TGT",
        source_contig="chr1",
        start=545,
        end=565,
    )
    assert isinstance(result, LiftoverDefect)
    assert result.status == "unliftable"


def test_lift_interval_reports_multi_mapping() -> None:
    duplicate = CHAIN + "\n" + CHAIN.replace(" 7\n", " 8\n")
    result = lift_interval(
        parse_chain_text(duplicate),
        source_seqcol_digest="SRC",
        target_seqcol_digest="TGT",
        source_contig="chr1",
        start=510,
        end=511,
    )
    assert isinstance(result, LiftoverDefect)
    assert result.status == "multi_mapping"


def test_lift_interval_ignores_unsupported_strand_chain_outside_interval() -> None:
    reverse_chain = CHAIN.replace(" + 500 630 ", " - 500 630 ")
    result = lift_interval(
        parse_chain_text(reverse_chain),
        source_seqcol_digest="SRC",
        target_seqcol_digest="TGT",
        source_contig="chr1",
        start=700,
        end=701,
    )
    assert isinstance(result, LiftoverDefect)
    assert result.status == "unliftable"


def test_lift_interval_reports_strand_ambiguous_for_unsupported_strand_covering_interval() -> None:
    reverse_chain = CHAIN.replace(" + 500 630 ", " - 500 630 ")
    result = lift_interval(
        parse_chain_text(reverse_chain),
        source_seqcol_digest="SRC",
        target_seqcol_digest="TGT",
        source_contig="chr1",
        start=510,
        end=511,
    )
    assert isinstance(result, LiftoverDefect)
    assert result.status == "strand_ambiguous"
