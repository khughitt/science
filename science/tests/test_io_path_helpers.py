"""sidecar_for_markdown / markdown_for_sidecar are explicit and fail loudly."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.annotation.io import (
    markdown_for_sidecar,
    sidecar_for_markdown,
)


def test_sidecar_for_markdown_simple() -> None:
    assert sidecar_for_markdown(Path("foo.md")) == Path("foo.anno.trig")


def test_sidecar_for_markdown_multi_dotted() -> None:
    assert (
        sidecar_for_markdown(Path("paper.v1.md"))
        == Path("paper.v1.anno.trig")
    )


def test_sidecar_for_markdown_keeps_parent() -> None:
    assert (
        sidecar_for_markdown(Path("notes/foo.md"))
        == Path("notes/foo.anno.trig")
    )


def test_sidecar_for_markdown_rejects_non_md() -> None:
    with pytest.raises(ValueError):
        sidecar_for_markdown(Path("foo.txt"))


def test_sidecar_for_markdown_rejects_no_extension() -> None:
    with pytest.raises(ValueError):
        sidecar_for_markdown(Path("README"))


def test_markdown_for_sidecar_simple() -> None:
    assert (
        markdown_for_sidecar(Path("foo.anno.trig"))
        == Path("foo.md")
    )


def test_markdown_for_sidecar_multi_dotted() -> None:
    assert (
        markdown_for_sidecar(Path("paper.v1.anno.trig"))
        == Path("paper.v1.md")
    )


def test_markdown_for_sidecar_keeps_parent() -> None:
    assert (
        markdown_for_sidecar(Path("notes/foo.anno.trig"))
        == Path("notes/foo.md")
    )


def test_markdown_for_sidecar_rejects_wrong_suffix() -> None:
    with pytest.raises(ValueError):
        markdown_for_sidecar(Path("foo.trig"))


def test_round_trip_simple() -> None:
    p = Path("foo.md")
    assert markdown_for_sidecar(sidecar_for_markdown(p)) == p


def test_round_trip_multi_dotted() -> None:
    p = Path("paper.v1.md")
    assert markdown_for_sidecar(sidecar_for_markdown(p)) == p
