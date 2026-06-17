# science/tests/test_text_source_adapter.py
from science_tool.annotation.text_source_adapter import LocatorRegime


def test_locator_regime_values():
    assert {r.value for r in LocatorRegime} == {
        "offset_anchored",
        "regenerable",
        "none",
    }
