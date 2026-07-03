"""No-FASTA build helpers for the seqcol-keyed assembly registry (C-D2).

The canonical seqcol digest is computed over the inherent attributes
``names`` + ``sequences`` only (GA4GH seqcol v1.0.0); ``lengths`` is carried in
the level-2 record but is not part of the collection identity. Per-contig
``SQ.`` digests come from a refget seqcol server's level-2 record, so no FASTA
is ever fetched. ``refget`` is imported lazily — only building the registry
needs it; resolving/validating it does not. See
docs/plans/historical/2026-05-26-bio-identity-and-reference-genome-design.md (C-D2).
"""

from __future__ import annotations

from typing import Any

_SEQCOL_SERVER = "https://seqcolapi.databio.org"


_INHERENT_ATTRS = ["names", "sequences"]  # GA4GH seqcol v1.0.0; lengths is NOT inherent
_ALIAS_SEPARATOR = "|"


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
    from refget.utils import seqcol_digest  # pyright: ignore[reportMissingImports]  # lazy: recipe-only dependency

    return seqcol_digest(
        {"names": list(level2["names"]), "sequences": list(level2["sequences"])},
        inherent_attrs=_INHERENT_ATTRS,
    )


def _clean_required_text(value: Any, *, field: str, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid {field} for {label!r}: expected string, got {type(value).__name__}")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"blank {field} for {label!r}")
    if cleaned != value:
        raise ValueError(f"invalid {field} for {label!r}: leading/trailing whitespace in {value!r}")
    return cleaned


def _clean_aliases(aliases: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    if not isinstance(aliases, (tuple, list)):
        raise ValueError(f"invalid aliases for 'assembly': expected tuple or list, got {type(aliases).__name__}")

    out: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        cleaned = _clean_required_text(alias, field="alias", label="assembly")
        if _ALIAS_SEPARATOR in cleaned:
            raise ValueError(f"invalid alias for 'assembly': contains {_ALIAS_SEPARATOR!r}: {cleaned!r}")
        if cleaned in seen:
            raise ValueError(f"duplicate assembly alias {cleaned!r}")
        seen.add(cleaned)
        out.append(cleaned)
    return tuple(out)


def validate_registry_label_bindings(rows: list[dict[str, Any]]) -> None:
    labels_by_token: dict[str, int] = {}
    aliases_by_token: dict[str, int] = {}

    for row_index, row in enumerate(rows):
        label = _clean_required_text(row.get("label"), field="label", label="assembly")
        aliases_raw = row.get("aliases", "")
        if not isinstance(aliases_raw, str):
            raise ValueError(
                f"invalid aliases for assembly {label!r} at row {row_index}: "
                f"expected string, got {type(aliases_raw).__name__}"
            )
        aliases = () if aliases_raw == "" else tuple(aliases_raw.split(_ALIAS_SEPARATOR))
        aliases = _clean_aliases(list(aliases))

        if label in aliases:
            raise ValueError(f"duplicate assembly label or alias {label!r}")

        if label in labels_by_token:
            raise ValueError(f"duplicate assembly label {label!r}")
        labels_by_token[label] = row_index

        for alias in aliases:
            if alias in aliases_by_token:
                raise ValueError(f"duplicate assembly alias {alias!r}")
            aliases_by_token[alias] = row_index

    collisions = set(labels_by_token) & set(aliases_by_token)
    for token in sorted(collisions):
        if labels_by_token[token] != aliases_by_token[token]:
            raise ValueError(f"duplicate assembly label or alias {token!r}")


def build_registry_row(
    *,
    level2: dict[str, Any],
    label: str,
    aliases: tuple[str, ...] | list[str] = (),
    accession: str,
    naming: str,
    server_digest: str,
    source_collection_url: str,
    source_url: str,
) -> dict[str, Any]:
    """Build one registry row, asserting the recomputed digest matches the server.

    The recompute-and-assert is the integrity gate: it proves the pinned
    level-2 record reproduces the canonical identifier with zero FASTA.
    """
    label = _clean_required_text(label, field="label", label="assembly")
    aliases_clean = _clean_aliases(aliases)
    accession = _clean_required_text(accession, field="accession", label=label)
    naming = _clean_required_text(naming, field="naming", label=label)
    server_digest = _clean_required_text(server_digest, field="server_digest", label=label)
    source_collection_url = _clean_required_text(source_collection_url, field="source_collection_url", label=label)
    source_url = _clean_required_text(source_url, field="source_url", label=label)

    computed = compute_seqcol_digest(level2)
    if computed != server_digest:
        raise ValueError(f"seqcol digest mismatch for {label!r}: server={server_digest!r} computed={computed!r}")
    return {
        "seqcol_digest": server_digest,
        "label": label,
        "aliases": _ALIAS_SEPARATOR.join(aliases_clean),
        "accession": accession,
        "n_sequences": len(level2["names"]),
        "naming": naming,
        "source_collection_url": source_collection_url,
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
