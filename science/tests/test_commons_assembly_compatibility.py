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


def test_parse_rejects_extra_named_columns() -> None:
    try:
        parse_compatibility_rows([_row(unexpected_column="extra")])
    except AssemblyCompatibilityError as exc:
        assert "unexpected columns" in str(exc)
    else:
        raise AssertionError("expected AssemblyCompatibilityError")
