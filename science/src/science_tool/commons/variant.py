"""Public small-allele variant resolver for C4a commons."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.commons.contigs import (
    AccessionAssemblyMismatch,
    AmbiguousContig,
    ContigError,
    ContigMatch,
    resolve_contig as _resolve_contig,
)
from science_tool.commons.errors import CommonsError
from science_tool.commons.refget_proxy import RefgetProxy
from science_tool.commons.resolver import resolve
from science_tool.commons.sequence_store import SequenceStoreError, open_store
from science_tool.commons.vrs import compute_vrs_id

_SEQUENCE_STORE_DATASET = "dataset:sequence-store-grch38-grch37"
_MANIFEST_RESOURCE = "manifest.csv"
_SUPPORTED_FORMATS = frozenset({"spdi", "vcf", "hgvs"})
_BREAKEND_CHARS = frozenset("[]")
_DNA_LITERAL_CHARS = frozenset("ACGTN")
_HGVS_G_SUBSTITUTION = re.compile(r"^g\.([1-9][0-9]*)([ACGTN]+)>([ACGTN]+)$")


@dataclass(frozen=True, slots=True)
class VariantMatch:
    vrs_id: str
    refget_digest: str


@dataclass(frozen=True, slots=True)
class VariantDefect:
    query: str
    reason: str
    detail: str


class VariantStoreUnavailable(RuntimeError):
    """The default commons sequence store resource cannot be opened."""


def _unsupported(detail: str) -> tuple[None, str]:
    return None, detail


def _is_symbolic(value: str) -> bool:
    return value.startswith("<") and value.endswith(">")


def _has_breakend(value: str) -> bool:
    return any(char in value for char in _BREAKEND_CHARS)


def _is_dna_literal(value: str) -> bool:
    return all(char in _DNA_LITERAL_CHARS for char in value)


def _parse_spdi(expr: str) -> tuple[tuple[str, int, str, str] | None, str]:
    parts = expr.rsplit(":", 3)
    if len(parts) != 4:
        return _unsupported("malformed-spdi")

    contig, pos_text, ref, alt = parts
    if not contig:
        return _unsupported("missing-contig")
    if not pos_text.isdecimal():
        return _unsupported("invalid-position")
    if ref == "." or alt == "." or (not ref and not alt):
        return _unsupported("empty-ref-alt")
    if "," in ref or "," in alt:
        return _unsupported("multiallelic")
    if _is_symbolic(ref) or _is_symbolic(alt) or _has_breakend(ref) or _has_breakend(alt):
        return _unsupported("symbolic-or-imprecise")
    if not _is_dna_literal(ref) or not _is_dna_literal(alt):
        return _unsupported("invalid-dna-literal")

    return (contig, int(pos_text), ref, alt), ""


def _parse_vcf(expr: str) -> tuple[tuple[str, int, str, str] | None, str]:
    parts = expr.split("-")
    if len(parts) != 4:
        return _unsupported("malformed-vcf")

    contig, pos_text, ref, alt = parts
    if not contig:
        return _unsupported("missing-contig")
    if not pos_text.isdecimal():
        return _unsupported("invalid-position")
    pos1 = int(pos_text)
    if pos1 <= 0:
        return _unsupported("invalid-position")
    if ref == "." or alt == "." or not ref or not alt:
        return _unsupported("empty-ref-alt")
    if "," in alt:
        return _unsupported("multiallelic")
    if _is_symbolic(ref) or _is_symbolic(alt) or _has_breakend(ref) or _has_breakend(alt):
        return _unsupported("symbolic-or-imprecise")
    if not _is_dna_literal(ref) or not _is_dna_literal(alt):
        return _unsupported("invalid-dna-literal")

    return (contig, pos1 - 1, ref, alt), ""


def _parse_hgvs(expr: str) -> tuple[tuple[str, int, str, str] | None, str]:
    if ":" not in expr:
        return _unsupported("malformed-hgvs")
    contig, description = expr.split(":", 1)
    if not contig or not description:
        return _unsupported("malformed-hgvs")
    match = _HGVS_G_SUBSTITUTION.fullmatch(description)
    if match is None:
        return _unsupported("malformed-hgvs")
    pos1, ref, alt = match.groups()
    return (contig, int(pos1) - 1, ref, alt), ""


def _parse_with_detail(expr: str, fmt: str) -> tuple[tuple[str, int, str, str] | None, str]:
    fmt = fmt.lower()
    if fmt not in _SUPPORTED_FORMATS:
        return _unsupported(f"unsupported fmt {fmt!r}")
    if fmt == "spdi":
        return _parse_spdi(expr)
    if fmt == "vcf":
        return _parse_vcf(expr)
    return _parse_hgvs(expr)


def _open_proxy(
    *,
    commons_root: Path | str | None,
    data_root: Path | str | None,
    store_root: Path | str | None = None,
) -> RefgetProxy:
    if store_root is not None:
        return RefgetProxy(open_store(Path(store_root)))

    try:
        manifest = resolve(
            _SEQUENCE_STORE_DATASET,
            _MANIFEST_RESOURCE,
            commons_root=None if commons_root is None else Path(commons_root),
            data_root=None if data_root is None else Path(data_root),
        )
    except CommonsError as error:
        raise VariantStoreUnavailable(str(error)) from error

    return RefgetProxy(open_store(manifest.path.parent))


def _parse(expr: str, fmt: str) -> tuple[str, int, str, str] | None:
    parsed, _ = _parse_with_detail(expr, fmt)
    return parsed


def _contig_defect(expr: str, resolution: AmbiguousContig | AccessionAssemblyMismatch) -> VariantDefect:
    if isinstance(resolution, AmbiguousContig):
        return VariantDefect(expr, "ambiguous-contig", ",".join(resolution.candidates))
    return VariantDefect(expr, "accession-assembly-mismatch", resolution.found_seqcol_digest)


def _validate_reference(
    expr: str,
    proxy: RefgetProxy,
    match: ContigMatch,
    *,
    pos0: int,
    ref: str,
) -> VariantDefect | None:
    span_end = pos0 + len(ref)
    if pos0 < 0 or span_end > match.length:
        return VariantDefect(expr, "out-of-bounds", f"span {pos0}:{span_end} outside contig length {match.length}")

    if not ref:
        return None

    actual = proxy.get_sequence(match.refget_digest, pos0, span_end)
    if actual != ref:
        return VariantDefect(expr, "ref-mismatch", f"expected {actual!r} at {match.name}:{pos0}, got {ref!r}")

    return None


def vrs_id(
    expr: str,
    *,
    fmt: str,
    assembly_seqcol: str,
    commons_root: Path | str | None = None,
    data_root: Path | str | None = None,
    store_root: Path | str | None = None,
) -> VariantMatch | VariantDefect:
    fmt = fmt.lower()
    parsed, detail = _parse_with_detail(expr, fmt)
    if parsed is None:
        return VariantDefect(expr, "unsupported-allele", detail)
    contig, pos0, ref, alt = parsed

    try:
        resolution = _resolve_contig(
            query=contig,
            seqcol_digest=assembly_seqcol,
            commons_root=None if commons_root is None else Path(commons_root),
            data_root=None if data_root is None else Path(data_root),
        )
    except ContigError as error:
        return VariantDefect(expr, "unknown-contig", str(error))

    if not isinstance(resolution, ContigMatch):
        return _contig_defect(expr, resolution)

    proxy = _open_proxy(commons_root=commons_root, data_root=data_root, store_root=store_root)

    defect = _validate_reference(expr, proxy, resolution, pos0=pos0, ref=ref)
    if defect is not None:
        return defect
    spdi_expr = f"ga4gh:{resolution.refget_digest}:{pos0}:{ref}:{alt}"
    try:
        return VariantMatch(compute_vrs_id(proxy, fmt="spdi", expr=spdi_expr), resolution.refget_digest)
    except (SequenceStoreError, VariantStoreUnavailable):
        raise
    except Exception as error:
        return VariantDefect(expr, "unsupported-allele", f"translator-rejected: {error}")
