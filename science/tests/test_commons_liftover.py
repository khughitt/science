from __future__ import annotations

import pytest

from science_tool.commons.liftover import ChainFormatError, parse_chain_text


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
