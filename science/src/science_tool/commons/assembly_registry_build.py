"""No-FASTA build helpers for the seqcol-keyed assembly registry (C-D2).

The canonical seqcol digest is computed over the inherent attributes
``names`` + ``sequences`` only (GA4GH seqcol v1.0.0); ``lengths`` is carried in
the level-2 record but is not part of the collection identity. Per-contig
``SQ.`` digests come from a refget seqcol server's level-2 record, so no FASTA
is ever fetched. ``refget`` is imported lazily — only building the registry
needs it; resolving/validating it does not. See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D2).
"""

from __future__ import annotations

from typing import Any

_SEQCOL_SERVER = "https://seqcolapi.databio.org"


_INHERENT_ATTRS = ["names", "sequences"]  # GA4GH seqcol v1.0.0; lengths is NOT inherent


def compute_seqcol_digest(level2: dict[str, Any]) -> str:
    """Canonical seqcol digest from a level-2 record {names, lengths, sequences}.

    The canonical identity is over the inherent attributes ``names`` +
    ``sequences`` only; ``lengths`` is carried in the level-2 record but is NOT
    part of the collection identity (GA4GH seqcol v1.0.0). We therefore (1) pass
    only the inherent payload and (2) pass ``inherent_attrs`` explicitly, so the
    digest is correct regardless of the library's default — it never depends on
    refget silently dropping ``lengths``. ``refget.utils.seqcol_digest`` applies
    the spec's canonical-JSON + sha512t24u rollup over exactly these attributes.
    """
    from refget.utils import seqcol_digest  # lazy: recipe-only dependency

    return seqcol_digest(
        {"names": list(level2["names"]), "sequences": list(level2["sequences"])},
        inherent_attrs=_INHERENT_ATTRS,
    )


def build_registry_row(
    *, level2: dict[str, Any], label: str, accession: str, server_digest: str, source_url: str
) -> dict[str, Any]:
    """Build one registry row, asserting the recomputed digest matches the server.

    The recompute-and-assert is the integrity gate: it proves the pinned
    level-2 record reproduces the canonical identifier with zero FASTA.
    """
    computed = compute_seqcol_digest(level2)
    if computed != server_digest:
        raise ValueError(f"seqcol digest mismatch for {label!r}: server={server_digest!r} computed={computed!r}")
    return {
        "seqcol_digest": server_digest,
        "label": label,
        "accession": accession,
        "n_sequences": len(level2["names"]),
        "source_url": source_url,
    }


def build_contig_rows(*, level2: dict[str, Any], seqcol_digest: str) -> list[dict[str, Any]]:
    """Materialize level-2 names, SQ digests, and lengths into contig rows.

    The seqcol digest identifies the aligned names and SQ digests; lengths are
    persisted from the same level-2 record for validation and lookup metadata.
    ``sequence_index`` makes that alignment auditable.
    """
    names, lengths, sequences = level2["names"], level2["lengths"], level2["sequences"]
    if not (len(names) == len(lengths) == len(sequences)):
        raise ValueError(
            f"ragged level-2 record for {seqcol_digest!r}: "
            f"{len(names)} names / {len(lengths)} lengths / {len(sequences)} sequences"
        )

    out: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for i, (name, length, refget_digest) in enumerate(zip(names, lengths, sequences, strict=True)):
        if not isinstance(name, str):
            raise ValueError(f"invalid contig name {name!r} at index {i} for {seqcol_digest!r}")
        if not name.strip():
            raise ValueError(f"blank contig name at index {i} for {seqcol_digest!r}")
        if name != name.strip():
            raise ValueError(f"invalid contig name {name!r} at index {i} for {seqcol_digest!r}")
        if not isinstance(refget_digest, str):
            raise ValueError(f"invalid refget digest {refget_digest!r} at index {i} for {seqcol_digest!r}")
        if not refget_digest.strip():
            raise ValueError(f"blank refget digest at index {i} for {seqcol_digest!r}")
        if refget_digest != refget_digest.strip():
            raise ValueError(f"invalid refget digest {refget_digest!r} at index {i} for {seqcol_digest!r}")
        if name in seen_names:
            raise ValueError(f"duplicate contig name {name!r} in {seqcol_digest!r}")
        seen_names.add(name)
        if not isinstance(length, int) or isinstance(length, bool):
            raise ValueError(f"invalid length {length!r} for contig {name!r}")
        length_i = length
        if length_i <= 0:
            raise ValueError(f"invalid length {length!r} for contig {name!r}")
        out.append(
            {
                "seqcol_digest": seqcol_digest,
                "sequence_index": i,
                "name": name,
                "refget_digest": refget_digest,
                "length": length_i,
            }
        )
    return out


def fetch_seqcol_level2(digest: str, *, base_url: str = _SEQCOL_SERVER) -> dict[str, Any]:
    """Fetch a level-2 seqcol record from a refget seqcol server (build-time only).

    Network call — used only when (re)building the registry, never at resolve
    time. The level-2 response carries {names, lengths, sequences[SQ...]}.
    """
    import httpx

    resp = httpx.get(f"{base_url}/collection/{digest}", params={"level": 2}, timeout=30.0)
    resp.raise_for_status()
    return resp.json()
