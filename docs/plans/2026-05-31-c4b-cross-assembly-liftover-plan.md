# C4b Cross-Assembly Liftover & Seqcol Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add pinned cross-assembly coordinate liftover and seqcol compatibility relations so assembly-mismatch validation can distinguish unresolved mismatches from explicitly lifted, provenance-bearing re-identifications.

**Implementation status:** Implemented in `~/d/science` on branch `feature/c4b-liftover` and in
`~/d/science-commons` via `dataset:assembly-liftover-grch37-grch38`. The first pass supports pinned UCSC
GRCh37→GRCh38 same-strand chain-block liftover, explicit unliftable/multi-mapping/strand-ambiguous
defects, lifted target-assembly VRS reminting, and provenance-verified validation remedies. Reverse-strand
allele reminting, broad interval/BED liftover, rsID, transcript HGVS, and protein projection remain out of
C4b scope.

**Architecture:** C4b is a remedy layer over C1/C4a, not a rewrite. It keeps seqcol digest equality as identity, stores cross-assembly relations as a separate reference dataset, parses pinned UCSC chain files into a pure resolver, and records lifted variants as distinct target-assembly VRS identities linked to their source with liftover provenance.

**Tech Stack:** Python stdlib (`csv`, `gzip`, `hashlib`, `urllib.request`), existing commons resolver/datapackage helpers, existing C4a `variant.vrs_id`, pytest, `science validate`.

---

## Audit Snapshot

- C1/C4a already implemented the assembly registry, `identity_context.assembly`, `contigs.csv`,
  `contig_aliases.csv`, row-level VRS minting, and detect-only `identity.cross-dataset-assembly-mismatch`.
- `science/src/science_tool/commons/variant.py` already mints VRS ids on the declared source assembly; C4b must mint a new target-assembly id after liftover, never mutate the source id.
- `science/src/science_tool/commons/contigs.py` already resolves aliases inside a declared seqcol assembly and detects accession/assembly mismatch; C4b should consume it for chain contig validation.
- `science/src/science_tool/validate/checks/identity_context.py` already has `evaluate_cross_dataset_assembly`; C4b should extend that check with a narrow "mismatch has declared liftover provenance" pass condition.
- `~/d/science-commons/datasets/assembly-registry` and `sequence-store-grch38-grch37` are still placeholder-built in the local commons store. C4b tests must stay hermetic with fixtures; real-data promotion can remain a separate operator step.

## Source Pinning Decision

Use UCSC liftOver chain files as the first pinned source:

- `https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz`
- Optional reverse / explicit target opt-in:
  `https://hgdownload.soe.ucsc.edu/goldenPath/hg38/liftOver/hg38ToHg19.over.chain.gz`

The UCSC index exposes the hg19-to-hg38 chain as a stable file under `goldenPath/hg19/liftOver/`, and
UCSC documents the chain format in its Genome Browser chain-format page. The recipe must lock sha256 and
bytes; the URL alone is not the reproducibility handle.

**Direction contract:** UCSC chain headers are
`chain score tName tSize tStrand tStart tEnd qName qSize qStrand qStart qEnd id`. For
`hg19ToHg38.over.chain.gz`, the `t*` side is the source/from assembly (`hg19` / GRCh37) and the `q*`
side is the target/to assembly (`hg38` / GRCh38). C4b therefore parses `tName/tStart/tEnd` as
`source_*` and `qName/qStart/qEnd` as `target_*`. This is load-bearing: swapping these fields silently
performs hg38-to-hg19 while labeling the result as GRCh38.

## File Map

**Science repo (`~/d/science`):**

- Create: `science/src/science_tool/commons/liftover.py`
  - Pure UCSC chain parser and coordinate resolver.
- Create: `science/tests/test_commons_liftover.py`
  - Unit tests for chain parsing, same-strand mapping, strand-ambiguous defects, unliftable spans, multi-mapping, and invalid chains.
- Create: `science/src/science_tool/commons/assembly_compatibility.py`
  - Resolver over compatibility relation rows.
- Create: `science/tests/test_commons_assembly_compatibility.py`
  - Unit tests for relation parsing and exact relation lookup.
- Modify: `science/src/science_tool/commons/variant.py`
  - Add `lifted_vrs_id(...)` wrapper that lifts the source span then remints target VRS id.
- Modify: `science/tests/test_commons_variant.py`
  - Add tests for lifted variant success and defect paths.
- Modify: `science/src/science_tool/validate/checks/identity_context.py`
  - Extend cross-dataset assembly mismatch to honor explicit liftover provenance.
- Modify: `science/tests/validate/test_checks_identity_context.py`
  - Add mismatch-remedy tests.
- Modify: `docs/plans/2026-05-28-c4-variant-identity-design.md`
  - Mark C4b plan drafted/implemented after work lands.
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`
  - Update status after C4b lands.

**Commons repo (`~/d/science-commons`):**

- Create: `datasets/assembly-liftover-grch37-grch38/entity.md`
- Create: `datasets/assembly-liftover-grch37-grch38/datapackage.yaml`
- Create: `datasets/assembly-liftover-grch37-grch38/recipe/fetch.py`
- Create: `datasets/assembly-liftover-grch37-grch38/recipe/build.py`
- Create: `datasets/assembly-liftover-grch37-grch38/recipe/README.md`
- Create after build: bulk-data files under `$SCIENCE_COMMONS_DATA_ROOT/assembly-liftover-grch37-grch38/`
  - `chains/hg19ToHg38.over.chain.gz`
  - optional `chains/hg38ToHg19.over.chain.gz`
  - `compatibility_relations.csv`

## Data Contracts

### `compatibility_relations.csv`

```csv
source_seqcol_digest,target_seqcol_digest,relation,method,chain_resource,direction,source_label,target_label,source_url,chain_sha256
5K4odB173rjao1Cnbk5BnvLt9V7aPAa2,g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp,liftover_possible,ucsc_chain,chains/hg19ToHg38.over.chain.gz,forward,GRCh37,GRCh38,https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz,sha256:<digest>
```

Rules:

- `source_seqcol_digest != target_seqcol_digest`; compatibility is not identity.
- `relation` initially supports `liftover_possible`.
- `method` initially supports `ucsc_chain`.
- `chain_resource` must name a resource in the liftover datapackage.
- `direction` is `forward` for the chain as published; reverse use is represented by a separate relation only when explicitly pinned.
- The validation remedy must verify that the declared liftover dataset has a pinned
  `liftover_possible` relation for the exact `(source_seqcol_digest, target_seqcol_digest)` pair. A
  frontmatter assertion alone is not enough to suppress an assembly-mismatch warning.

### Liftover Result Types

```python
from dataclasses import dataclass
from typing import Literal

LiftoverStatus = Literal["lifted", "unliftable", "multi_mapping", "strand_ambiguous"]

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
    target_strand: Literal["+", "-"]
    chain_id: int

@dataclass(frozen=True, slots=True)
class LiftoverDefect:
    status: Literal["unliftable", "multi_mapping", "strand_ambiguous"]
    detail: str
```

## Task 1: Pure Liftover Chain Parser

**Files:**
- Create: `science/src/science_tool/commons/liftover.py`
- Create: `science/tests/test_commons_liftover.py`

- [x] **Step 1: Write failing parser tests**

Create `science/tests/test_commons_liftover.py`:

```python
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
```

- [x] **Step 2: Run parser tests and confirm failure**

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_liftover.py -q
```

Expected: FAIL because `science_tool.commons.liftover` does not exist.

- [x] **Step 3: Implement minimal parser**

Create `science/src/science_tool/commons/liftover.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


class ChainFormatError(ValueError):
    """A UCSC chain file violates the subset C4b accepts."""


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
    target_strand: Literal["+", "-"]
    target_start: int
    target_end: int
    source_name: str
    source_size: int
    source_strand: Literal["+", "-"]
    source_start: int
    source_end: int
    chain_id: int
    blocks: tuple[ChainBlock, ...]


def _int(text: str, *, field: str) -> int:
    if not text.isdecimal():
        raise ChainFormatError(f"{field} must be a non-negative integer, got {text!r}")
    return int(text)


def _parse_header(line: str) -> Chain:
    parts = line.split()
    if len(parts) != 13 or parts[0] != "chain":
        raise ChainFormatError(f"malformed chain header {line!r}")
    source_strand = parts[4]
    target_strand = parts[9]
    if source_strand not in {"+", "-"} or target_strand not in {"+", "-"}:
        raise ChainFormatError(f"unsupported chain strand in {line!r}")
    return Chain(
        score=_int(parts[1], field="score"),
        source_name=parts[2],
        source_size=_int(parts[3], field="source_size"),
        source_strand=source_strand,  # type: ignore[arg-type]
        source_start=_int(parts[5], field="source_start"),
        source_end=_int(parts[6], field="source_end"),
        target_name=parts[7],
        target_size=_int(parts[8], field="target_size"),
        target_strand=target_strand,  # type: ignore[arg-type]
        target_start=_int(parts[10], field="target_start"),
        target_end=_int(parts[11], field="target_end"),
        chain_id=_int(parts[12], field="chain_id"),
        blocks=(),
    )


def parse_chain_text(text: str) -> list[Chain]:
    chains: list[Chain] = []
    current: Chain | None = None
    blocks: list[ChainBlock] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("chain "):
            if current is not None:
                chains.append(replace(current, blocks=tuple(blocks)))
            current = _parse_header(line)
            blocks = []
            continue
        if current is None:
            raise ChainFormatError(f"line {line_number}: block before chain header")
        parts = line.split()
        if len(parts) == 1:
            blocks.append(ChainBlock(size=_int(parts[0], field="block size"), dt=0, dq=0))
        elif len(parts) == 3:
            blocks.append(
                ChainBlock(
                    size=_int(parts[0], field="block size"),
                    dt=_int(parts[1], field="block dt"),
                    dq=_int(parts[2], field="block dq"),
                )
            )
        else:
            raise ChainFormatError(f"line {line_number}: malformed block row {line!r}")
    if current is not None:
        chains.append(replace(current, blocks=tuple(blocks)))
    return chains
```

- [x] **Step 4: Run parser tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_liftover.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/commons/liftover.py science/tests/test_commons_liftover.py
rtk git commit -m "feat: parse UCSC liftover chains"
```

## Task 2: Pure Coordinate Liftover

**Files:**
- Modify: `science/src/science_tool/commons/liftover.py`
- Modify: `science/tests/test_commons_liftover.py`

- [x] **Step 1: Add failing coordinate tests**

Append to `science/tests/test_commons_liftover.py`:

```python
from science_tool.commons.liftover import LiftoverDefect, LiftedInterval, lift_interval


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
```

- [x] **Step 2: Run coordinate tests and confirm failure**

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_liftover.py -q
```

Expected: FAIL because `lift_interval` and result types do not exist.

- [x] **Step 3: Implement same-strand interval liftover**

Add the result dataclasses from the "Data Contracts" section to `liftover.py`, plus:

```python
def _block_ranges(chain: Chain) -> list[tuple[int, int, int, int]]:
    source_pos = chain.source_start
    target_pos = chain.target_start
    ranges: list[tuple[int, int, int, int]] = []
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
        return LiftoverDefect(status="unliftable", detail=f"invalid interval {start}:{end}")
    matches: list[LiftedInterval] = []
    strand_skips = 0
    for chain in chains:
        if chain.source_name != source_contig:
            continue
        lifted = _lift_with_chain(chain, start, end)
        if lifted is None:
            if chain.source_strand != "+" or chain.target_strand != "+":
                strand_skips += 1
            continue
        target_start, target_end = lifted
        matches.append(
            LiftedInterval(
                source_seqcol_digest=source_seqcol_digest,
                target_seqcol_digest=target_seqcol_digest,
                source_contig=chain.source_name,
                target_contig=chain.target_name,
                source_start=start,
                source_end=end,
                target_start=target_start,
                target_end=target_end,
                target_strand=chain.target_strand,
                chain_id=chain.chain_id,
            )
        )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return LiftoverDefect(status="multi_mapping", detail=f"{len(matches)} mappings")
    if strand_skips:
        return LiftoverDefect(status="strand_ambiguous", detail="reverse-strand chain support deferred")
    return LiftoverDefect(status="unliftable", detail=f"no chain block covers {source_contig}:{start}-{end}")
```

- [x] **Step 4: Run coordinate tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_liftover.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/commons/liftover.py science/tests/test_commons_liftover.py
rtk git commit -m "feat: lift coordinates through pinned chain blocks"
```

## Task 3: Compatibility Relation Resolver

**Files:**
- Create: `science/src/science_tool/commons/assembly_compatibility.py`
- Create: `science/tests/test_commons_assembly_compatibility.py`

- [x] **Step 1: Write failing relation tests**

Create `science/tests/test_commons_assembly_compatibility.py`:

```python
from __future__ import annotations

from science_tool.commons.assembly_compatibility import (
    AssemblyCompatibilityError,
    CompatibilityRelation,
    parse_compatibility_rows,
    relation_for,
)


def _row(**extra: str) -> dict[str, str]:
    return {
        "source_seqcol_digest": "SRC",
        "target_seqcol_digest": "TGT",
        "relation": "liftover_possible",
        "method": "ucsc_chain",
        "chain_resource": "chains/srcToTgt.over.chain.gz",
        "direction": "forward",
        "source_label": "GRCh37",
        "target_label": "GRCh38",
        "source_url": "https://example.test/srcToTgt.over.chain.gz",
        "chain_sha256": "sha256:" + "a" * 64,
        **extra,
    }


def test_parse_compatibility_rows() -> None:
    rows = parse_compatibility_rows([_row()])
    assert rows == [
        CompatibilityRelation(
            source_seqcol_digest="SRC",
            target_seqcol_digest="TGT",
            relation="liftover_possible",
            method="ucsc_chain",
            chain_resource="chains/srcToTgt.over.chain.gz",
            direction="forward",
            source_label="GRCh37",
            target_label="GRCh38",
            source_url="https://example.test/srcToTgt.over.chain.gz",
            chain_sha256="sha256:" + "a" * 64,
        )
    ]


def test_relation_for_exact_source_target() -> None:
    rows = parse_compatibility_rows([_row(), _row(source_seqcol_digest="OTHER")])
    assert relation_for(rows, source_seqcol_digest="SRC", target_seqcol_digest="TGT") is not None
    assert relation_for(rows, source_seqcol_digest="TGT", target_seqcol_digest="SRC") is None


def test_parse_rejects_identity_relation() -> None:
    try:
        parse_compatibility_rows([_row(source_seqcol_digest="SRC", target_seqcol_digest="SRC")])
    except AssemblyCompatibilityError as exc:
        assert "must differ" in str(exc)
    else:
        raise AssertionError("expected AssemblyCompatibilityError")
```

- [x] **Step 2: Run relation tests and confirm failure**

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_assembly_compatibility.py -q
```

Expected: FAIL because `assembly_compatibility.py` does not exist.

- [x] **Step 3: Implement relation parser**

Implement `assembly_compatibility.py` with:

```python
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from science_tool.commons.resolver import resolve

RelationKind = Literal["liftover_possible"]
RelationMethod = Literal["ucsc_chain"]
RelationDirection = Literal["forward"]
COMPATIBILITY_RESOURCE = "compatibility_relations"

_COLUMNS = (
    "source_seqcol_digest",
    "target_seqcol_digest",
    "relation",
    "method",
    "chain_resource",
    "direction",
    "source_label",
    "target_label",
    "source_url",
    "chain_sha256",
)


class AssemblyCompatibilityError(ValueError):
    """Compatibility relation rows violate C4b invariants."""


@dataclass(frozen=True, slots=True)
class CompatibilityRelation:
    source_seqcol_digest: str
    target_seqcol_digest: str
    relation: RelationKind
    method: RelationMethod
    chain_resource: str
    direction: RelationDirection
    source_label: str
    target_label: str
    source_url: str
    chain_sha256: str


def _required(row: dict[str, str], row_number: int, column: str) -> str:
    value = row.get(column)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise AssemblyCompatibilityError(f"row {row_number}: invalid {column}")
    return value


def parse_compatibility_rows(rows: list[dict[str, str]]) -> list[CompatibilityRelation]:
    out: list[CompatibilityRelation] = []
    seen: set[tuple[str, str, str]] = set()
    for row_number, row in enumerate(rows, start=1):
        missing = [column for column in _COLUMNS if column not in row]
        if missing:
            raise AssemblyCompatibilityError(f"row {row_number}: missing columns {missing}")
        source = _required(row, row_number, "source_seqcol_digest")
        target = _required(row, row_number, "target_seqcol_digest")
        if source == target:
            raise AssemblyCompatibilityError(f"row {row_number}: source and target seqcol digests must differ")
        relation = _required(row, row_number, "relation")
        if relation != "liftover_possible":
            raise AssemblyCompatibilityError(f"row {row_number}: unsupported relation {relation!r}")
        method = _required(row, row_number, "method")
        if method != "ucsc_chain":
            raise AssemblyCompatibilityError(f"row {row_number}: unsupported method {method!r}")
        direction = _required(row, row_number, "direction")
        if direction != "forward":
            raise AssemblyCompatibilityError(f"row {row_number}: unsupported direction {direction!r}")
        key = (source, target, relation)
        if key in seen:
            raise AssemblyCompatibilityError(f"row {row_number}: duplicate relation {key!r}")
        seen.add(key)
        chain_sha256 = _required(row, row_number, "chain_sha256")
        if not chain_sha256.startswith("sha256:") or len(chain_sha256) != len("sha256:") + 64:
            raise AssemblyCompatibilityError(f"row {row_number}: invalid chain_sha256")
        out.append(
            CompatibilityRelation(
                source_seqcol_digest=source,
                target_seqcol_digest=target,
                relation=relation,  # type: ignore[arg-type]
                method=method,  # type: ignore[arg-type]
                chain_resource=_required(row, row_number, "chain_resource"),
                direction=direction,  # type: ignore[arg-type]
                source_label=_required(row, row_number, "source_label"),
                target_label=_required(row, row_number, "target_label"),
                source_url=_required(row, row_number, "source_url"),
                chain_sha256=chain_sha256,
            )
        )
    return out


def relation_for(
    relations: list[CompatibilityRelation], *, source_seqcol_digest: str, target_seqcol_digest: str
) -> CompatibilityRelation | None:
    matches = [
        relation
        for relation in relations
        if relation.source_seqcol_digest == source_seqcol_digest
        and relation.target_seqcol_digest == target_seqcol_digest
        and relation.relation == "liftover_possible"
    ]
    if len(matches) > 1:
        raise AssemblyCompatibilityError("duplicate liftover_possible relations")
    return matches[0] if matches else None


def load_compatibility_relations(
    *,
    dataset_id: str,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[CompatibilityRelation]:
    resolved = resolve(dataset_id, COMPATIBILITY_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as handle:
        return parse_compatibility_rows(list(csv.DictReader(handle)))
```

- [x] **Step 4: Run relation tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_assembly_compatibility.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/commons/assembly_compatibility.py science/tests/test_commons_assembly_compatibility.py
rtk git commit -m "feat: model assembly compatibility relations"
```

## Task 4: Commons Liftover Dataset Recipe

**Files:**
- Create: `~/d/science-commons/datasets/assembly-liftover-grch37-grch38/entity.md`
- Create: `~/d/science-commons/datasets/assembly-liftover-grch37-grch38/datapackage.yaml`
- Create: `~/d/science-commons/datasets/assembly-liftover-grch37-grch38/recipe/fetch.py`
- Create: `~/d/science-commons/datasets/assembly-liftover-grch37-grch38/recipe/build.py`
- Create: `~/d/science-commons/datasets/assembly-liftover-grch37-grch38/recipe/README.md`

- [x] **Step 1: Create placeholder entity and datapackage**

Use this entity frontmatter:

```yaml
---
schema_profile: science-entity-base/1.0+dataset/1.0
id: dataset:assembly-liftover-grch37-grch38
type: dataset
title: GRCh37 to GRCh38 assembly liftover chains
version: "1.0.0"
created: "2026-05-31"
updated: "2026-05-31"
status: active
origin: external
source_class: reference
tier: use-now
access:
  level: public
  availability: available
  verified: true
  verification_method: retrieved
datapackage: datapackage.yaml
---
```

Initial datapackage:

```yaml
name: assembly-liftover-grch37-grch38
profile: data-package
resources:
  - name: compatibility_relations
    path: compatibility_relations.csv
    format: csv
    mediatype: text/csv
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 0
  - name: hg19ToHg38_chain
    path: chains/hg19ToHg38.over.chain.gz
    format: chain.gz
    mediatype: application/gzip
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 0
```

- [x] **Step 2: Implement `fetch.py`**

`fetch.py` downloads only from explicit URLs and writes `lockfile.yaml` with URL, sha256, and bytes. It must reject URLs containing `latest`, `current`, or `download/test`.

- [x] **Step 3: Implement `build.py`**

`build.py` reads `lockfile.yaml`, writes `compatibility_relations.csv`, computes resource hashes/bytes, and rewrites `datapackage.yaml`. It should accept explicit seqcol digests:

```bash
rtk uv run --frozen --project ~/d/science/science python recipe/build.py \
  --source-seqcol <GRCh37 seqcol digest> \
  --target-seqcol <GRCh38 seqcol digest>
```

- [x] **Step 4: Commit commons dataset scaffold**

```bash
cd ~/d/science-commons
rtk git add datasets/assembly-liftover-grch37-grch38
rtk git commit -m "data: add assembly liftover recipe"
```

## Task 5: Lifted Variant Resolver

**Files:**
- Modify: `science/src/science_tool/commons/variant.py`
- Modify: `science/tests/test_commons_variant.py`

**Gate:** This task's unit tests monkeypatch the reminting boundary and do not require the real
`sequence-store-grch38-grch37` data. Full end-to-end reminting against real GRCh37/GRCh38 sequence bytes
is blocked until that sequence-store dataset is built locally; until then, real-data verification should
be reported as skipped rather than inferred.

- [x] **Step 1: Write failing lifted variant tests**

Add tests that monkeypatch `variant.vrs_id` for the target reminting boundary and call a new function:

```python
from science_tool.commons.liftover import LiftedInterval
from science_tool.commons.variant import LiftedVariantMatch, lifted_vrs_id


def test_lifted_vrs_id_links_source_and_target_ids(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_vrs_id(expr: str, *, fmt: str, assembly_seqcol: str, **kwargs):
        calls.append((expr, fmt, assembly_seqcol))
        if assembly_seqcol == "SRC":
            return VariantMatch(vrs_id="ga4gh:VA.source", refget_digest="SQ.src")
        return VariantMatch(vrs_id="ga4gh:VA.target", refget_digest="SQ.tgt")

    monkeypatch.setattr("science_tool.commons.variant.vrs_id", fake_vrs_id)
    monkeypatch.setattr(
        "science_tool.commons.variant.lift_interval",
        lambda *args, **kwargs: LiftedInterval(
            source_seqcol_digest="SRC",
            target_seqcol_digest="TGT",
            source_contig="chr1",
            target_contig="chr1",
            source_start=9,
            source_end=10,
            target_start=99,
            target_end=100,
            target_strand="+",
            chain_id=1,
        ),
    )

    result = lifted_vrs_id("chr1-10-A-T", fmt="vcf", source_seqcol="SRC", target_seqcol="TGT", chains=[])

    assert result == LiftedVariantMatch(
        source_vrs_id="ga4gh:VA.source",
        target_vrs_id="ga4gh:VA.target",
        source_seqcol_digest="SRC",
        target_seqcol_digest="TGT",
        chain_id=1,
    )
```

- [x] **Step 2: Implement `LiftedVariantMatch` and `lifted_vrs_id`**

`lifted_vrs_id` must:

1. Parse the source expression using the existing `_parse_with_detail`.
2. Mint the source VRS id with existing `vrs_id`.
3. Lift `[pos0, pos0 + len(ref))` through `liftover.lift_interval`.
4. Reject reverse-strand / multi-mapping / unliftable as
   `VariantDefect(expr, f"liftover-{status}", detail)`.
5. Remint the target VRS id using SPDI over the target contig and the same `ref`/`alt` only for `target_strand == "+"`.

This deliberately supports same-strand small alleles first; reverse-complement allele reminting is
deferred until a concrete dataset needs it. Expect real UCSC chains to yield many `strand_ambiguous`
defects under this first-pass scope; that miss rate must be reported in any real dataset lift, not hidden.

- [x] **Step 3: Run variant tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_variant.py -q
```

Expected: PASS.

- [x] **Step 4: Commit**

```bash
rtk git add science/src/science_tool/commons/variant.py science/tests/test_commons_variant.py
rtk git commit -m "feat: remint lifted variant identities"
```

## Task 6: Assembly Mismatch Remedy In Validation

**Files:**
- Modify: `science/src/science_tool/validate/checks/identity_context.py`
- Modify: `science/tests/validate/test_checks_identity_context.py`

- [x] **Step 1: Add failing validation tests**

Add this import near the top of `science/tests/validate/test_checks_identity_context.py`:

```python
from science_tool.commons.assembly_compatibility import CompatibilityRelation
```

Append tests:

```python
_LIFTOVER_DATASET = "dataset:assembly-liftover-grch37-grch38"


def _relation(source: str, target: str) -> CompatibilityRelation:
    return CompatibilityRelation(
        source_seqcol_digest=source,
        target_seqcol_digest=target,
        relation="liftover_possible",
        method="ucsc_chain",
        chain_resource="chains/srcToTgt.over.chain.gz",
        direction="forward",
        source_label="source",
        target_label="target",
        source_url="https://example.test/srcToTgt.over.chain.gz",
        chain_sha256="sha256:" + "a" * 64,
    )


def test_cross_dataset_mismatch_with_declared_liftover_passes() -> None:
    a = _with_assembly("dataset:a", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )
    assert (
        list(
            evaluate_cross_dataset_assembly(
                [a, derived],
                compatibility_relations_by_dataset_id={_LIFTOVER_DATASET: [_relation("DIGEST_37", "DIGEST_38")]},
            )
        )
        == []
    )


def test_cross_dataset_mismatch_with_frontmatter_only_still_warns() -> None:
    a = _with_assembly("dataset:a", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )
    warns = [
        r
        for r in evaluate_cross_dataset_assembly(
            [a, derived], compatibility_relations_by_dataset_id={_LIFTOVER_DATASET: []}
        )
        if r.rule == "identity.cross-dataset-assembly-mismatch"
    ]
    assert len(warns) == 1


def test_cross_dataset_mismatch_with_wrong_liftover_target_warns() -> None:
    a = _with_assembly("dataset:a", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "OTHER",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )
    warns = [
        r
        for r in evaluate_cross_dataset_assembly([a, derived])
        if r.rule == "identity.cross-dataset-assembly-mismatch"
    ]
    assert len(warns) == 1


def test_cross_dataset_mismatch_with_multiple_lifted_parents_passes() -> None:
    a = _with_assembly("dataset:a", "DIGEST_37")
    b = _with_assembly("dataset:b", "DIGEST_36")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a", "dataset:b"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                },
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_36",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                },
            ],
        },
    )
    assert (
        list(
            evaluate_cross_dataset_assembly(
                [a, b, derived],
                compatibility_relations_by_dataset_id={
                    _LIFTOVER_DATASET: [
                        _relation("DIGEST_37", "DIGEST_38"),
                        _relation("DIGEST_36", "DIGEST_38"),
                    ]
                },
            )
        )
        == []
    )


def test_load_relations_fallback_keeps_warning_when_dataset_unresolvable() -> None:
    """The IO wrapper's catch path: an unresolvable liftover dataset maps to None,
    and None must NOT suppress the assembly-mismatch warning."""
    from science_tool.commons.errors import CommonsError
    from science_tool.validate.checks.identity_context import _load_relations_for_datasets

    def boom(*, dataset_id: str, commons_root=None, data_root=None):
        raise CommonsError(f"{dataset_id} is not built locally")

    a = _with_assembly("dataset:a", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )
    relations = _load_relations_for_datasets([a, derived], loader=boom)
    assert relations == {_LIFTOVER_DATASET: None}

    warns = [
        r
        for r in evaluate_cross_dataset_assembly(
            [a, derived], compatibility_relations_by_dataset_id=relations
        )
        if r.rule == "identity.cross-dataset-assembly-mismatch"
    ]
    assert len(warns) == 1
```

- [x] **Step 2: Implement narrow liftover provenance check**

Change the pure function signature so tests can inject parsed relations:

```python
from science_tool.commons.assembly_compatibility import CompatibilityRelation, relation_for


def evaluate_cross_dataset_assembly(
    datasets: Iterable[dict[str, Any]],
    *,
    compatibility_relations_by_dataset_id: dict[str, list[CompatibilityRelation] | None] | None = None,
) -> Iterator[Result]:
    ...
```

Add helper:

```python
def _has_liftover_remedy(
    derivation: dict[str, Any],
    *,
    from_digest: str,
    to_digest: str,
    compatibility_relations_by_dataset_id: dict[str, list[CompatibilityRelation] | None],
) -> bool:
    transformations = derivation.get("transformations")
    if not isinstance(transformations, list):
        return False
    for entry in transformations:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "liftover":
            continue
        if entry.get("from_seqcol_digest") != from_digest or entry.get("to_seqcol_digest") != to_digest:
            continue
        if entry.get("method") != "ucsc_chain":
            continue
        dataset = entry.get("dataset")
        if not isinstance(dataset, str) or not dataset.startswith("dataset:"):
            continue
        relations = compatibility_relations_by_dataset_id.get(dataset)
        if relations is None:
            continue
        if relation_for(relations, source_seqcol_digest=from_digest, target_seqcol_digest=to_digest) is not None:
            return True
    return False
```

Then restructure `evaluate_cross_dataset_assembly` from a flat set check to pairwise parent checks:

```python
def evaluate_cross_dataset_assembly(
    datasets: Iterable[dict[str, Any]],
    *,
    compatibility_relations_by_dataset_id: dict[str, list[CompatibilityRelation] | None] | None = None,
) -> Iterator[Result]:
    compatibility_relations_by_dataset_id = compatibility_relations_by_dataset_id or {}
    by_id = {fm.get("id"): fm for fm in datasets if fm.get("id")}
    for fm in datasets:
        derivation = fm.get("derivation") or {}
        inputs = derivation.get("inputs") if isinstance(derivation, dict) else None
        if not inputs:
            continue
        own_digest = _declared_digest(fm)
        parent_pairs: list[tuple[str, str]] = []
        observed_digests: set[str] = set()
        if own_digest:
            observed_digests.add(own_digest)
        for input_id in inputs:
            parent = by_id.get(input_id)
            if parent is None:
                continue
            parent_digest = _declared_digest(parent)
            if parent_digest:
                observed_digests.add(parent_digest)
            if own_digest and parent_digest and parent_digest != own_digest:
                parent_pairs.append((parent_digest, own_digest))

        if not parent_pairs:
            if len(observed_digests) >= 2:
                yield _result(
                    Severity.WARN,
                    fm.get("_path"),
                    f"{fm.get('id', '?')}: derivation inputs span distinct assemblies {sorted(observed_digests)} "
                    f"with no target assembly for liftover remedy",
                    "identity.cross-dataset-assembly-mismatch",
                )
            continue

        unresolved_pairs = [
            (from_digest, to_digest)
            for from_digest, to_digest in parent_pairs
            if not _has_liftover_remedy(
                derivation,
                from_digest=from_digest,
                to_digest=to_digest,
                compatibility_relations_by_dataset_id=compatibility_relations_by_dataset_id,
            )
        ]
        if unresolved_pairs:
            yield _result(
                Severity.WARN,
                fm.get("_path"),
                f"{fm.get('id', '?')}: derivation inputs span distinct assemblies {sorted(observed_digests)} "
                f"without pinned liftover remedies for {unresolved_pairs}",
                "identity.cross-dataset-assembly-mismatch",
            )
```

> **Note:** `relation_for` raises `AssemblyCompatibilityError` on duplicate `(source, target)` pairs, and
> `_has_liftover_remedy` does not catch it. This is safe because `parse_compatibility_rows` already rejects
> duplicates at parse time, so any list reaching the pure function via the loader is duplicate-free. The pure
> function deliberately trusts its input is parse-validated; only hand-built lists could trip the raise.

Update `check_cross_dataset_assembly(ctx)` to load the relation rows for every liftover dataset named in
`derivation.transformations` before calling the pure function. Factor the load-and-catch into an injectable
helper so the "declared but unverifiable → `None`" fallback is unit-testable without a `ValidateContext`:

```python
from collections.abc import Callable
from pathlib import Path  # if not already imported

from science_tool.commons.assembly_compatibility import (
    AssemblyCompatibilityError,
    CompatibilityRelation,
    load_compatibility_relations,
)
from science_tool.commons.errors import CommonsError


def _declared_liftover_datasets(datasets: Iterable[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for fm in datasets:
        derivation = fm.get("derivation") or {}
        transformations = derivation.get("transformations") if isinstance(derivation, dict) else None
        if not isinstance(transformations, list):
            continue
        for entry in transformations:
            if isinstance(entry, dict) and entry.get("type") == "liftover":
                dataset = entry.get("dataset")
                if isinstance(dataset, str) and dataset.startswith("dataset:"):
                    out.add(dataset)
    return out


def _load_relations_for_datasets(
    datasets: Iterable[dict[str, Any]],
    *,
    loader: Callable[..., list[CompatibilityRelation]] = load_compatibility_relations,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> dict[str, list[CompatibilityRelation] | None]:
    out: dict[str, list[CompatibilityRelation] | None] = {}
    for dataset_id in _declared_liftover_datasets(datasets):
        try:
            out[dataset_id] = loader(dataset_id=dataset_id, commons_root=commons_root, data_root=data_root)
        except (CommonsError, AssemblyCompatibilityError):
            out[dataset_id] = None  # declared, but not verifiable -> does NOT suppress the warning
    return out
```

`check_cross_dataset_assembly` must materialize the frontmatters once (they are consumed twice — by the
loader and by the pure check) and pass the resolved relations through:

```python
@Check(section="assembly identity", order=26)
def check_cross_dataset_assembly(ctx: ValidateContext) -> Iterator[Result]:
    datasets = list(dataset_frontmatters(ctx))
    relations = _load_relations_for_datasets(datasets)
    yield from evaluate_cross_dataset_assembly(datasets, compatibility_relations_by_dataset_id=relations)
```

- [x] **Step 3: Run validation tests**

```bash
rtk uv run --frozen --project science pytest science/tests/validate/test_checks_identity_context.py -q
```

Expected: PASS.

- [x] **Step 4: Commit**

```bash
rtk git add science/src/science_tool/validate/checks/identity_context.py science/tests/validate/test_checks_identity_context.py
rtk git commit -m "feat: honor declared liftover provenance in assembly checks"
```

## Task 7: Documentation Status And Verification

**Files:**
- Modify: `docs/plans/2026-05-28-c4-variant-identity-design.md`
- Modify: `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md`
- Modify after implementation: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`

- [x] **Step 1: Update C4 design status**

Change C4b status from remaining to implementation-ready, and link this plan. After implementation, change it to implemented.

- [x] **Step 2: Run targeted verification**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_commons_liftover.py \
  science/tests/test_commons_assembly_compatibility.py \
  science/tests/test_commons_variant.py \
  science/tests/validate/test_checks_identity_context.py \
  science/tests/validate/test_checks_variant_identity.py \
  -q

rtk uv run --frozen --project science ruff check \
  science/src/science_tool/commons/liftover.py \
  science/src/science_tool/commons/assembly_compatibility.py \
  science/src/science_tool/commons/variant.py \
  science/src/science_tool/validate/checks/identity_context.py \
  science/tests/test_commons_liftover.py \
  science/tests/test_commons_assembly_compatibility.py \
  science/tests/test_commons_variant.py \
  science/tests/validate/test_checks_identity_context.py

rtk git diff --check
```

Expected: all tests pass, ruff passes, no whitespace errors.

- [x] **Step 3: Commit docs**

```bash
rtk git add docs/plans/2026-05-28-c4-variant-identity-design.md docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
rtk git commit -m "docs: mark C4b liftover implemented"
```

## Self-Review Checklist

- [x] **Spec coverage:** C4b has pinned chain data, compatibility relation rows, pure liftover, lifted VRS reminting, and a C1 check-3 remedy.
- [x] **No silent collapse:** seqcol equality remains identity; compatibility/liftover only relates distinct digests.
- [x] **Direction checked:** `hg19ToHg38` parses UCSC `t*` fields as source/from and `q*` fields as
  target/to, with a test that asserts this direction explicitly.
- [x] **No silent drops:** unliftable, multi-mapping, and strand-ambiguous results are explicit defects.
- [x] **Verified relation remedy:** assembly-mismatch validation suppresses a warning only when the declared
  liftover dataset contains a pinned `liftover_possible` relation for the exact source/target digests.
- [x] **Tested IO fallback:** the `_load_relations_for_datasets` catch path is unit-tested — an unresolvable
  liftover dataset maps to `None` and still warns (the "verified, not honor-system" guarantee lives here, not
  in the pure function).
- [x] **No live runtime calls:** fetch is recipe-only; resolvers read pinned local files via commons.
- [x] **No overreach:** reverse-strand allele reminting, broad interval/BED liftover, rsID, transcript HGVS, and protein projection remain out of C4b unless a concrete dataset demands them.
