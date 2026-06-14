from science_model.templates import MIGRATED_KINDS


def test_inquiry_is_no_longer_a_migrated_kind():
    assert "inquiry" not in MIGRATED_KINDS
