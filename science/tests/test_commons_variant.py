from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.contigs import AccessionAssemblyMismatch, AmbiguousContig, ContigError, ContigMatch
from science_tool.commons.refget_proxy import RefgetProxy
from science_tool.commons.sequence_store import open_store, refget_digest
from science_tool.commons import variant as V
from science_tool.commons.vrs import compute_vrs_id

_SEQ = "CGTACGTACGTACGTACGTACGTACGTACGTACGTACGTA"

# GOLDEN: captured once from compute_vrs_id(... ) against pinned ga4gh.vrs;
# regenerate + re-review only on deliberate version bump.
_GOLDEN_SNV = "ga4gh:VA._uAlNwdTfBSPBnzSA68-6sKBm8brTU2K"


def _proxy(tmp_path: Path) -> tuple[RefgetProxy, str]:
    digest = refget_digest(_SEQ)
    (tmp_path / digest).write_text(_SEQ, encoding="ascii")
    return RefgetProxy(store=open_store(tmp_path)), digest


def test_compute_vrs_id_from_spdi_is_deterministic(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    expr = f"ga4gh:{digest}:5:G:T"
    vid = compute_vrs_id(proxy, fmt="spdi", expr=expr)
    assert vid.startswith("ga4gh:VA.")
    assert compute_vrs_id(proxy, fmt="spdi", expr=expr) == vid


def test_spdi_snv_matches_pinned_golden(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    assert compute_vrs_id(proxy, fmt="spdi", expr=f"ga4gh:{digest}:5:G:T") == _GOLDEN_SNV


def test_same_change_on_a_different_sequence_is_a_different_id(tmp_path: Path) -> None:
    other = "TTTTCGTACGTACGTACGTACGTACGTACGTACGTACGTA"
    od = refget_digest(other)
    (tmp_path / od).write_text(other, encoding="ascii")
    proxy = RefgetProxy(store=open_store(tmp_path))
    base, _ = _proxy(tmp_path)
    a = compute_vrs_id(base, fmt="spdi", expr=f"ga4gh:{refget_digest(_SEQ)}:5:G:T")
    b = compute_vrs_id(proxy, fmt="spdi", expr=f"ga4gh:{od}:5:G:T")
    assert a != b


def test_compute_vrs_id_rejects_uncovered_formats(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    with pytest.raises(ValueError, match="unsupported variant fmt 'gnomad'"):
        compute_vrs_id(proxy, fmt="gnomad", expr=f"ga4gh:{digest}:5:G:T")


def test_vrs_id_from_vcf_against_declared_assembly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    monkeypatch.setattr(V, "_resolve_contig", lambda **_: ContigMatch(digest, "1", len(_SEQ), "seqcol_name"))
    monkeypatch.setattr(V, "_open_proxy", lambda **_: proxy)

    match = V.vrs_id(
        "1-6-G-T",
        fmt="vcf",
        assembly_seqcol="DIGEST38",
        commons_root=tmp_path,
        data_root=tmp_path,
    )

    assert isinstance(match, V.VariantMatch)
    assert match.vrs_id.startswith("ga4gh:VA.")
    assert match.refget_digest == digest


def test_ref_mismatch_is_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    monkeypatch.setattr(V, "_resolve_contig", lambda **_: ContigMatch(digest, "1", len(_SEQ), "seqcol_name"))
    monkeypatch.setattr(V, "_open_proxy", lambda **_: proxy)

    defect = V.vrs_id("1-6-A-T", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "ref-mismatch"


def test_symbolic_allele_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id("1-6-G-<DEL>", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_accession_assembly_mismatch_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        V,
        "_resolve_contig",
        lambda **kwargs: AccessionAssemblyMismatch(kwargs["query"], "DIGEST37"),
    )

    defect = V.vrs_id(
        "NC_000001.10:5:G:T",
        fmt="spdi",
        assembly_seqcol="DIGEST38",
        commons_root=tmp_path,
        data_root=tmp_path,
    )

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "accession-assembly-mismatch"


def test_vrs_id_can_use_explicit_store_root_for_fixtures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    digest = refget_digest(_SEQ)
    (tmp_path / digest).write_text(_SEQ, encoding="ascii")
    monkeypatch.setattr(V, "_resolve_contig", lambda **_: ContigMatch(digest, "1", len(_SEQ), "seqcol_name"))

    match = V.vrs_id(
        "1-6-G-T",
        fmt="vcf",
        assembly_seqcol="DIGEST38",
        commons_root=tmp_path,
        data_root=tmp_path,
        store_root=tmp_path,
    )

    assert isinstance(match, V.VariantMatch)
    assert match.vrs_id.startswith("ga4gh:VA.")
    assert match.refget_digest == digest


def test_multiallelic_vcf_alt_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id("1-6-G-A,C", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_vcf_alt_with_separator_is_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id("1-6-G-T-extra", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_vcf_invalid_base_is_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id("1-6-G-Z", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_vcf_lowercase_base_is_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id("1-6-G-t", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_out_of_bounds_reference_span_is_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    monkeypatch.setattr(V, "_resolve_contig", lambda **_: ContigMatch(digest, "1", len(_SEQ), "seqcol_name"))
    monkeypatch.setattr(V, "_open_proxy", lambda **_: proxy)

    defect = V.vrs_id(
        "1-100-G-T",
        fmt="vcf",
        assembly_seqcol="DIGEST38",
        commons_root=tmp_path,
        data_root=tmp_path,
    )

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "out-of-bounds"


def test_out_of_bounds_empty_ref_spdi_insertion_is_flagged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proxy, digest = _proxy(tmp_path)
    monkeypatch.setattr(V, "_resolve_contig", lambda **_: ContigMatch(digest, "1", len(_SEQ), "seqcol_name"))
    monkeypatch.setattr(V, "_open_proxy", lambda **_: proxy)

    defect = V.vrs_id(
        "1:100::T",
        fmt="spdi",
        assembly_seqcol="DIGEST38",
        commons_root=tmp_path,
        data_root=tmp_path,
    )

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "out-of-bounds"


def test_empty_ref_spdi_insertion_at_contig_end_is_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proxy, digest = _proxy(tmp_path)
    monkeypatch.setattr(V, "_resolve_contig", lambda **_: ContigMatch(digest, "1", len(_SEQ), "seqcol_name"))
    monkeypatch.setattr(V, "_open_proxy", lambda **_: proxy)
    monkeypatch.setattr(
        V,
        "compute_vrs_id",
        lambda proxy, *, fmt, expr: "ga4gh:VA.end_insertion",
    )

    match = V.vrs_id(
        f"1:{len(_SEQ)}::T",
        fmt="spdi",
        assembly_seqcol="DIGEST38",
        commons_root=tmp_path,
        data_root=tmp_path,
    )

    assert isinstance(match, V.VariantMatch)
    assert match.vrs_id == "ga4gh:VA.end_insertion"
    assert match.refget_digest == digest


def test_ambiguous_contig_result_is_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(V, "_resolve_contig", lambda **_: AmbiguousContig("1", ("SQ.a", "SQ.b")))

    defect = V.vrs_id("1-6-G-T", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "ambiguous-contig"


def test_unknown_contig_exception_is_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def raise_unknown(**_: object) -> None:
        raise ContigError("unknown contig")

    monkeypatch.setattr(V, "_resolve_contig", raise_unknown)

    defect = V.vrs_id("9-6-G-T", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unknown-contig"


def test_spdi_parser_splits_from_right_for_colon_contigs() -> None:
    assert V._parse("ref:with:colon:5:G:T", "spdi") == ("ref:with:colon", 5, "G", "T")


def test_spdi_dot_ref_is_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id("1:5:.:T", fmt="spdi", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_spdi_dot_alt_is_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id("1:5:G:.", fmt="spdi", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_spdi_invalid_base_is_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id("1:5:G:Z", fmt="spdi", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_spdi_lowercase_base_is_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id("1:5:G:t", fmt="spdi", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_hgvs_g_accession_returns_typed_unsupported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, digest = _proxy(tmp_path)
    monkeypatch.setattr(V, "_resolve_contig", lambda **_: ContigMatch(digest, "1", len(_SEQ), "refseq_accession"))

    def fail_open_proxy(**_: object) -> None:
        raise AssertionError("HGVS_g unsupported result should not open the sequence store")

    monkeypatch.setattr(V, "_open_proxy", fail_open_proxy)

    defect = V.vrs_id(
        "NC_000001.11:g.6G>T",
        fmt="hgvs",
        assembly_seqcol="DIGEST38",
        commons_root=tmp_path,
        data_root=tmp_path,
    )

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"
    assert "hgvs-needs-accession" in defect.detail


@pytest.mark.parametrize(
    "expr",
    [
        "NC_000001.11:g.?",
        "NC_000001.11:g.(6G>T)",
        "NC_000001.11:g.6g>T",
        "NC_000001.11:g.6G>t",
        "NC_000001.11:g.6G>.",
        "NC_000001.11:g.6G>Z",
        "NC_000001.11:g.0G>T",
    ],
)
def test_malformed_hgvs_g_is_rejected(expr: str, tmp_path: Path) -> None:
    defect = V.vrs_id(expr, fmt="hgvs", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"


def test_non_genomic_hgvs_is_rejected(tmp_path: Path) -> None:
    defect = V.vrs_id(
        "NM_000000.1:c.6G>T",
        fmt="hgvs",
        assembly_seqcol="DIGEST38",
        commons_root=tmp_path,
        data_root=tmp_path,
    )

    assert isinstance(defect, V.VariantDefect)
    assert defect.reason == "unsupported-allele"
