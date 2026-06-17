# science/tests/test_text_source_adapter.py
from science_tool.annotation.text_source_adapter import LocatorRegime


def test_locator_regime_values():
    assert {r.value for r in LocatorRegime} == {
        "offset_anchored",
        "regenerable",
        "none",
    }


# append to science/tests/test_text_source_adapter.py
from pathlib import Path
import pytest
from science_tool.annotation.text_source_adapter import TextSourceAdapter, LocatorRegime


class _DummyAdapter(TextSourceAdapter):
    name = "dummy"
    locator_regime = LocatorRegime.NONE

    def handles(self, source_md: Path) -> bool:
        return source_md.name == "dummy.md"

    def source_ref(self, source_md: Path) -> str:
        return "doc:dummy"


def test_capability_defaults_are_false():
    a = _DummyAdapter()
    assert a.can_fetch is False
    assert a.can_seed is False
    assert a.name == "dummy"
    assert a.locator_regime is LocatorRegime.NONE


def test_handles_and_source_ref_dispatch():
    a = _DummyAdapter()
    assert a.handles(Path("dummy.md")) is True
    assert a.handles(Path("other.md")) is False
    assert a.source_ref(Path("dummy.md")) == "doc:dummy"


def test_base_extract_raises_not_implemented():
    a = _DummyAdapter()
    with pytest.raises(NotImplementedError, match="does not implement extract"):
        a.extract(
            source_md=Path("dummy.md"),
            model="m",
            candidates=[],
            now=None,
            actor="t",
        )
