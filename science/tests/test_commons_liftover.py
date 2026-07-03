from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.assembly_compatibility import load_compatibility_relations, relation_for
from science_tool.commons.liftover import (
    ChainFormatError,
    LiftedInterval,
    LiftoverDefect,
    lift_interval,
    load_chain,
    parse_chain_text,
)

CHAIN = """\
chain 1000 chr1 1000 + 500 630 chr1 2000 + 1000 1140 7
50 10 20
70
"""

_FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_LIFTOVER_COMMONS_ROOT = _FIXTURES / "liftover"
_LIFTOVER_DATA_ROOT = _FIXTURES / "liftover-data"
_GRCH37_DIGEST = "XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA"
_GRCH38_DIGEST = "XemD97fxYMS4q-FBm_n5CHQgmzh1_67a"
_LIFTOVER_DATASET = "dataset:assembly-liftover-grch37-grch38"


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


def test_load_chain_reads_gzipped_commons_resource() -> None:
    relations = load_compatibility_relations(
        dataset_id=_LIFTOVER_DATASET,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )
    relation = relation_for(relations, source_seqcol_digest=_GRCH37_DIGEST, target_seqcol_digest=_GRCH38_DIGEST)
    assert relation is not None

    chains = load_chain(
        dataset_id=_LIFTOVER_DATASET,
        chain_resource=relation.chain_resource,
        expected_sha256=relation.chain_sha256,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )

    assert len(chains) == 1
    assert chains[0].source_name == "chr1"
    assert chains[0].target_name == "chr1"
    assert chains[0].chain_id == 7


def test_loaded_chain_lifts_interval_offline() -> None:
    relations = load_compatibility_relations(
        dataset_id=_LIFTOVER_DATASET,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )
    relation = relation_for(relations, source_seqcol_digest=_GRCH37_DIGEST, target_seqcol_digest=_GRCH38_DIGEST)
    assert relation is not None
    chains = load_chain(
        dataset_id=_LIFTOVER_DATASET,
        chain_resource=relation.chain_resource,
        expected_sha256=relation.chain_sha256,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )

    result = lift_interval(
        chains,
        source_seqcol_digest=_GRCH37_DIGEST,
        target_seqcol_digest=_GRCH38_DIGEST,
        source_contig="chr1",
        start=510,
        end=511,
    )

    assert result == LiftedInterval(
        source_seqcol_digest=_GRCH37_DIGEST,
        target_seqcol_digest=_GRCH38_DIGEST,
        source_contig="chr1",
        target_contig="chr1",
        source_start=510,
        source_end=511,
        target_start=1010,
        target_end=1011,
        target_strand="+",
        chain_id=7,
    )


def test_load_chain_rejects_relation_hash_mismatch() -> None:
    relations = load_compatibility_relations(
        dataset_id=_LIFTOVER_DATASET,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )
    relation = relation_for(relations, source_seqcol_digest=_GRCH37_DIGEST, target_seqcol_digest=_GRCH38_DIGEST)
    assert relation is not None

    with pytest.raises(ChainFormatError, match="does not match compatibility chain_sha256"):
        load_chain(
            dataset_id=_LIFTOVER_DATASET,
            chain_resource=relation.chain_resource,
            expected_sha256="sha256:" + "a" * 64,
            commons_root=_LIFTOVER_COMMONS_ROOT,
            data_root=_LIFTOVER_DATA_ROOT,
        )
