from science_model.ids import CanonicalId, normalize_alias


def test_canonical_id_roundtrip() -> None:
    cid = CanonicalId.parse("hypothesis:h01-raw-feature-embedding-informativeness")
    assert cid.kind == "hypothesis"
    assert cid.slug == "h01-raw-feature-embedding-informativeness"
    assert str(cid) == "hypothesis:h01-raw-feature-embedding-informativeness"


def test_alias_normalization_handles_legacy_short_forms() -> None:
    aliases = {
        "H01": "hypothesis:h01-raw-feature-embedding-informativeness",
        "h01": "hypothesis:h01-raw-feature-embedding-informativeness",
    }
    assert normalize_alias("H01", aliases) == "hypothesis:h01-raw-feature-embedding-informativeness"
    assert normalize_alias("h01", aliases) == "hypothesis:h01-raw-feature-embedding-informativeness"
