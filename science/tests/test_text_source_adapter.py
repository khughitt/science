# science/tests/test_text_source_adapter.py
from datetime import datetime, timezone

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

from science_tool.annotation.text_source_adapter import TextSourceAdapter


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


# append to science/tests/test_text_source_adapter.py
from science_tool.annotation.text_source_adapter import PaperSourceAdapter


def test_paper_adapter_capabilities():
    a = PaperSourceAdapter()
    assert a.name == "paper"
    assert a.locator_regime is LocatorRegime.OFFSET_ANCHORED
    assert a.can_fetch is True
    assert a.can_seed is True


def test_paper_adapter_handles_source_md():
    a = PaperSourceAdapter()
    assert a.handles(Path("/x/smith2020.source.md")) is True
    assert a.handles(Path("/x/smith2020.v1.source.md")) is True
    assert a.handles(Path("/x/notes.md")) is False


def test_paper_adapter_source_ref_strips_source_suffix():
    a = PaperSourceAdapter()
    assert a.source_ref(Path("/x/smith2020.source.md")) == "paper:smith2020"
    assert a.source_ref(Path("/x/smith2020.v1.source.md")) == "paper:smith2020.v1"


def test_paper_adapter_source_ref_rejects_non_source_md():
    a = PaperSourceAdapter()
    with pytest.raises(ValueError, match=r"expects a \.source\.md path"):
        a.source_ref(Path("/x/plain.md"))


# append to science/tests/test_text_source_adapter.py
from science_tool.annotation.text_source_adapter import (
    TEXT_SOURCE_ADAPTERS,
    TextSourceAdapterError,
    resolve_adapter,
)


def test_registry_contains_paper_adapter():
    assert any(isinstance(a, PaperSourceAdapter) for a in TEXT_SOURCE_ADAPTERS)


def test_resolve_adapter_returns_paper_for_source_md():
    adapter = resolve_adapter(Path("/x/smith2020.source.md"))
    assert isinstance(adapter, PaperSourceAdapter)


def test_resolve_adapter_fails_loud_when_unhandled():
    with pytest.raises(TextSourceAdapterError, match="no text source adapter handles"):
        resolve_adapter(Path("/x/unknown.txt"))


def test_paper_adapter_extract_delegates(monkeypatch):
    import science_tool.annotation.statement_extract as se

    captured = {}

    def fake_extract_candidates(*, source_md, model, candidates, now, actor):
        captured.update(
            source_md=source_md, model=model, candidates=candidates, now=now, actor=actor
        )
        return "SENTINEL_REPORT"

    monkeypatch.setattr(se, "extract_candidates", fake_extract_candidates)

    now = datetime.now(timezone.utc)
    out = PaperSourceAdapter().extract(
        source_md=Path("/x/p.source.md"), model="m", candidates=[], now=now, actor="paper-annotate"
    )
    assert out == "SENTINEL_REPORT"
    assert captured == {
        "source_md": Path("/x/p.source.md"),
        "model": "m",
        "candidates": [],
        "now": now,
        "actor": "paper-annotate",
    }
