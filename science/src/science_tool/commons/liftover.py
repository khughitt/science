from __future__ import annotations

from dataclasses import dataclass, replace


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
    target_strand: str
    target_start: int
    target_end: int
    source_name: str
    source_size: int
    source_strand: str
    source_start: int
    source_end: int
    chain_id: int
    blocks: tuple[ChainBlock, ...]


def parse_chain_text(text: str) -> list[Chain]:
    chains: list[Chain] = []
    current: Chain | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        fields = line.split()
        if fields[0] == "chain":
            if current is not None:
                chains.append(current)
            current = _parse_header(fields, line_number)
            continue

        if current is None:
            raise ChainFormatError(f"block before chain header on line {line_number}")

        block = _parse_block(fields, line_number)
        current = replace(current, blocks=(*current.blocks, block))

    if current is not None:
        chains.append(current)

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
        target_strand=q_strand,
        target_start=q_start,
        target_end=q_end,
        source_name=t_name,
        source_size=t_size,
        source_strand=t_strand,
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


def _parse_non_negative_int(value: str, field_name: str, line_number: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ChainFormatError(f"{field_name} on line {line_number} must be a non-negative integer") from exc

    if parsed < 0:
        raise ChainFormatError(f"{field_name} on line {line_number} must be a non-negative integer")
    return parsed
