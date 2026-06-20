from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, cast

LiftoverStatus = Literal["lifted", "unliftable", "multi_mapping", "strand_ambiguous"]
ChainStrand = Literal["+", "-"]


class ChainFormatError(ValueError):
    """Raised when UCSC chain text is malformed."""


@dataclass(frozen=True, slots=True)
class ChainBlock:
    size: int
    dt: int
    dq: int


@dataclass(frozen=True, slots=True)
class Chain:
    score: int
    target_name: str
    target_size: int
    target_strand: ChainStrand
    target_start: int
    target_end: int
    source_name: str
    source_size: int
    source_strand: ChainStrand
    source_start: int
    source_end: int
    chain_id: int
    blocks: tuple[ChainBlock, ...]


@dataclass(frozen=True, slots=True)
class LiftedInterval:
    source_seqcol_digest: str
    target_seqcol_digest: str
    source_contig: str
    target_contig: str
    source_start: int
    source_end: int
    target_start: int
    target_end: int
    target_strand: ChainStrand
    chain_id: int


@dataclass(frozen=True, slots=True)
class LiftoverDefect:
    status: Literal["unliftable", "multi_mapping", "strand_ambiguous"]
    detail: str


def parse_chain_text(text: str) -> list[Chain]:
    chains: list[Chain] = []
    current: Chain | None = None
    blocks: list[ChainBlock] = []
    terminal_block_seen = False
    last_line_number = 0

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        last_line_number = line_number
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        fields = line.split()
        if fields[0] == "chain":
            if current is not None:
                chains.append(_close_chain(current, blocks, line_number))
            current = _parse_header(fields, line_number)
            blocks = []
            terminal_block_seen = False
            continue

        if current is None:
            raise ChainFormatError(f"block before chain header on line {line_number}")
        if terminal_block_seen:
            raise ChainFormatError(f"block after terminal block on line {line_number}")

        block = _parse_block(fields, line_number)
        blocks.append(block)
        terminal_block_seen = len(fields) == 1

    if current is not None:
        chains.append(_close_chain(current, blocks, last_line_number + 1))

    return chains


def _parse_header(fields: list[str], line_number: int) -> Chain:
    if len(fields) != 13:
        raise ChainFormatError(f"chain header on line {line_number} must have 13 fields")

    (
        _chain,
        score_text,
        t_name,
        t_size_text,
        t_strand,
        t_start_text,
        t_end_text,
        q_name,
        q_size_text,
        q_strand,
        q_start_text,
        q_end_text,
        chain_id_text,
    ) = fields

    if t_strand not in {"+", "-"}:
        raise ChainFormatError(f"invalid source strand on line {line_number}: {t_strand}")
    if q_strand not in {"+", "-"}:
        raise ChainFormatError(f"invalid target strand on line {line_number}: {q_strand}")
    source_strand = cast(ChainStrand, t_strand)
    target_strand = cast(ChainStrand, q_strand)

    score = _parse_non_negative_int(score_text, "score", line_number)
    t_size = _parse_non_negative_int(t_size_text, "source size", line_number)
    t_start = _parse_non_negative_int(t_start_text, "source start", line_number)
    t_end = _parse_non_negative_int(t_end_text, "source end", line_number)
    q_size = _parse_non_negative_int(q_size_text, "target size", line_number)
    q_start = _parse_non_negative_int(q_start_text, "target start", line_number)
    q_end = _parse_non_negative_int(q_end_text, "target end", line_number)
    chain_id = _parse_non_negative_int(chain_id_text, "chain id", line_number)

    return Chain(
        score=score,
        target_name=q_name,
        target_size=q_size,
        target_strand=target_strand,
        target_start=q_start,
        target_end=q_end,
        source_name=t_name,
        source_size=t_size,
        source_strand=source_strand,
        source_start=t_start,
        source_end=t_end,
        chain_id=chain_id,
        blocks=(),
    )


def _parse_block(fields: list[str], line_number: int) -> ChainBlock:
    if len(fields) not in {1, 3}:
        raise ChainFormatError(f"chain block on line {line_number} must have 1 or 3 fields")

    size = _parse_non_negative_int(fields[0], "block size", line_number)
    if len(fields) == 1:
        return ChainBlock(size=size, dt=0, dq=0)

    dt = _parse_non_negative_int(fields[1], "block dt", line_number)
    dq = _parse_non_negative_int(fields[2], "block dq", line_number)
    return ChainBlock(size=size, dt=dt, dq=dq)


def _close_chain(chain: Chain, blocks: list[ChainBlock], line_number: int) -> Chain:
    if not blocks:
        raise ChainFormatError(f"chain block missing before line {line_number}")
    if blocks[-1].dt != 0 or blocks[-1].dq != 0:
        raise ChainFormatError(f"chain missing terminal block before line {line_number}")
    return replace(chain, blocks=tuple(blocks))


def _parse_non_negative_int(value: str, field_name: str, line_number: int) -> int:
    if not value.isdecimal():
        raise ChainFormatError(f"{field_name} on line {line_number} must be a non-negative integer")
    return int(value)


def _block_ranges(chain: Chain) -> list[tuple[int, int, int, int]]:
    ranges: list[tuple[int, int, int, int]] = []
    source_pos = chain.source_start
    target_pos = chain.target_start

    for block in chain.blocks:
        ranges.append((source_pos, source_pos + block.size, target_pos, target_pos + block.size))
        source_pos += block.size + block.dt
        target_pos += block.size + block.dq

    return ranges


def _lift_with_chain(chain: Chain, start: int, end: int) -> tuple[int, int] | None:
    if chain.source_strand != "+" or chain.target_strand != "+":
        return None

    for source_start, source_end, target_start, _target_end in _block_ranges(chain):
        if source_start <= start and end <= source_end:
            offset_start = start - source_start
            offset_end = end - source_start
            return target_start + offset_start, target_start + offset_end

    return None


def _source_blocks_cover_interval(chain: Chain, start: int, end: int) -> bool:
    return any(source_start <= start and end <= source_end for source_start, source_end, _target_start, _target_end in _block_ranges(chain))


def lift_interval(
    chains: list[Chain],
    *,
    source_seqcol_digest: str,
    target_seqcol_digest: str,
    source_contig: str,
    start: int,
    end: int,
) -> LiftedInterval | LiftoverDefect:
    if start < 0 or end <= start:
        return LiftoverDefect(status="unliftable", detail="invalid interval")

    lifted: list[tuple[Chain, int, int]] = []
    strand_ambiguous = False
    for chain in chains:
        if chain.source_name != source_contig:
            continue
        if chain.source_strand != "+" or chain.target_strand != "+":
            if _source_blocks_cover_interval(chain, start, end):
                strand_ambiguous = True
            continue

        mapped_interval = _lift_with_chain(chain, start, end)
        if mapped_interval is not None:
            target_start, target_end = mapped_interval
            lifted.append((chain, target_start, target_end))

    if len(lifted) > 1:
        return LiftoverDefect(status="multi_mapping", detail="interval maps through multiple chains")
    if len(lifted) == 1:
        chain, target_start, target_end = lifted[0]
        return LiftedInterval(
            source_seqcol_digest=source_seqcol_digest,
            target_seqcol_digest=target_seqcol_digest,
            source_contig=source_contig,
            target_contig=chain.target_name,
            source_start=start,
            source_end=end,
            target_start=target_start,
            target_end=target_end,
            target_strand=chain.target_strand,
            chain_id=chain.chain_id,
        )
    if strand_ambiguous:
        return LiftoverDefect(status="strand_ambiguous", detail="reverse-strand chain support is not implemented")
    return LiftoverDefect(status="unliftable", detail="interval does not map through a single chain block")
