from __future__ import annotations

from pathlib import Path

from science_tool.commons.assembly_compatibility import (
    AssemblyCompatibilityError,
    CompatibilityRelation,
    load_compatibility_relations,
    parse_compatibility_rows,
    relation_for,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_LIFTOVER_COMMONS_ROOT = _FIXTURES / "liftover"
_LIFTOVER_DATA_ROOT = _FIXTURES / "liftover-data"
_GRCH37_DIGEST = "XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA"
_GRCH38_DIGEST = "XemD97fxYMS4q-FBm_n5CHQgmzh1_67a"
_LIFTOVER_DATASET = "dataset:assembly-liftover-grch37-grch38"


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


def test_load_compatibility_relations_from_commons_fixture() -> None:
    relations = load_compatibility_relations(
        dataset_id=_LIFTOVER_DATASET,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )

    assert relations == [
        CompatibilityRelation(
            source_seqcol_digest=_GRCH37_DIGEST,
            target_seqcol_digest=_GRCH38_DIGEST,
            relation="liftover_possible",
            method="ucsc_chain",
            chain_resource="chains/hg19ToHg38.over.chain.gz",
            direction="forward",
            source_label="GRCh37",
            target_label="GRCh38",
            source_url="https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz",
            chain_sha256="sha256:5ec7528c49d2a189294a4a342022420cd3f364ae7d1b202858af4a6a16dc78f3",
        )
    ]
    assert (
        relation_for(
            relations,
            source_seqcol_digest=_GRCH37_DIGEST,
            target_seqcol_digest=_GRCH38_DIGEST,
        )
        is not None
    )
    assert (
        relation_for(
            relations,
            source_seqcol_digest=_GRCH38_DIGEST,
            target_seqcol_digest=_GRCH37_DIGEST,
        )
        is None
    )
