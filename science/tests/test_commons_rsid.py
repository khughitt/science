from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from pathlib import Path

import science_tool.commons.rsid as rsid_module
from science_tool.commons.rsid import RsidDefect, RsidMatch, resolve_rsid


def _sqlite(path: Path) -> Path:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE metadata (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE rsid_alleles (
              rsid TEXT NOT NULL,
              seqcol_digest TEXT NOT NULL,
              contig TEXT NOT NULL,
              pos0 INTEGER NOT NULL,
              ref TEXT NOT NULL,
              alt TEXT NOT NULL,
              source_vcf TEXT NOT NULL,
              allele_index INTEGER NOT NULL,
              PRIMARY KEY (rsid, seqcol_digest, contig, pos0, ref, alt, source_vcf, allele_index)
            );
            CREATE INDEX rsid_alleles_lookup
            ON rsid_alleles (rsid, seqcol_digest);
            """
        )
        conn.executemany(
            """
            INSERT INTO rsid_alleles
            (rsid, seqcol_digest, contig, pos0, ref, alt, source_vcf, allele_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("rs1", "GRCH38", "NC_000001.11", 10, "A", "G", "GCF_000001405.40.gz", 1),
                ("rs2", "GRCH38", "NC_000001.11", 20, "C", "T", "GCF_000001405.40.gz", 1),
                ("rs2", "GRCH38", "NC_000001.11", 20, "C", "A", "GCF_000001405.40.gz", 2),
                ("rs2", "GRCH37", "NC_000001.10", 19, "C", "T", "GCF_000001405.25.gz", 1),
            ],
        )
    return path


def test_resolve_rsid_returns_unique_match(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("RS1", assembly_seqcol="GRCH38", sqlite_path=path)

    assert result == RsidMatch(
        rsid="rs1",
        seqcol_digest="GRCH38",
        contig="NC_000001.11",
        pos0=10,
        ref="A",
        alt="G",
        source_vcf="GCF_000001405.40.gz",
        allele_index=1,
    )


def test_resolve_rsid_filters_by_ref_alt(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("rs2", assembly_seqcol="GRCH38", sqlite_path=path, ref="C", alt="A")

    assert result == RsidMatch(
        rsid="rs2",
        seqcol_digest="GRCH38",
        contig="NC_000001.11",
        pos0=20,
        ref="C",
        alt="A",
        source_vcf="GCF_000001405.40.gz",
        allele_index=2,
    )


def test_resolve_rsid_filters_by_ref_only(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("rs1", assembly_seqcol="GRCH38", sqlite_path=path, ref="A")

    assert result == RsidMatch(
        rsid="rs1",
        seqcol_digest="GRCH38",
        contig="NC_000001.11",
        pos0=10,
        ref="A",
        alt="G",
        source_vcf="GCF_000001405.40.gz",
        allele_index=1,
    )


def test_resolve_rsid_filters_by_alt_only(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("rs2", assembly_seqcol="GRCH38", sqlite_path=path, alt="A")

    assert result == RsidMatch(
        rsid="rs2",
        seqcol_digest="GRCH38",
        contig="NC_000001.11",
        pos0=20,
        ref="C",
        alt="A",
        source_vcf="GCF_000001405.40.gz",
        allele_index=2,
    )


def test_resolve_rsid_reports_ambiguity_without_allele_filter(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("rs2", assembly_seqcol="GRCH38", sqlite_path=path)

    assert result == RsidDefect("rs2", "ambiguous-rsid", "2 candidate alleles for GRCH38")


def test_resolve_rsid_reports_unknown_after_assembly_filter(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("rs1", assembly_seqcol="GRCH37", sqlite_path=path)

    assert result == RsidDefect("rs1", "rsid-assembly-mismatch", "no allele for declared assembly GRCH37")


def test_resolve_rsid_rejects_malformed_label(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite"

    result = resolve_rsid("1", assembly_seqcol="GRCH38", sqlite_path=path)

    assert result == RsidDefect("1", "malformed-rsid", "expected rs followed by digits")


def test_resolve_rsid_rejects_whitespace_padded_labels(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    assert resolve_rsid(" RS1 ", assembly_seqcol="GRCH38", sqlite_path=path) == RsidDefect(
        " RS1 ",
        "malformed-rsid",
        "expected rs followed by digits",
    )
    assert resolve_rsid("rs1\n", assembly_seqcol="GRCH38", sqlite_path=path) == RsidDefect(
        "rs1\n",
        "malformed-rsid",
        "expected rs followed by digits",
    )


def test_resolve_rsid_uses_registry_only_without_explicit_sqlite_path(tmp_path: Path, monkeypatch) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")
    calls = []

    def fake_resolve(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(path=path)

    monkeypatch.setattr(rsid_module, "resolve", fake_resolve)

    explicit_result = resolve_rsid("rs1", assembly_seqcol="GRCH38", sqlite_path=path)

    assert isinstance(explicit_result, RsidMatch)
    assert calls == []

    registry_result = resolve_rsid(
        "rs1",
        assembly_seqcol="GRCH38",
        registry="dataset:test-rsid",
        commons_root=tmp_path / "commons",
        data_root=tmp_path / "data",
    )

    assert isinstance(registry_result, RsidMatch)
    assert calls == [
        (
            ("dataset:test-rsid", "rsid_mappings.sqlite"),
            {"commons_root": tmp_path / "commons", "data_root": tmp_path / "data"},
        )
    ]
