"""Pin reader/writer: round-trip preserves science.yaml unrelated keys + comments."""

from pathlib import Path

import pytest

from science_tool.project_artifacts.pin import (
    PinAlreadyExists,
    PinNotFound,
    add_pin,
    read_pins,
    remove_pin,
)
from science_tool.project_artifacts.registry_schema import Pin


def _write_science_yaml(p: Path, content: str) -> None:
    (p / "science.yaml").write_text(content, encoding="utf-8")


def test_read_pins_empty(tmp_path: Path) -> None:
    _write_science_yaml(tmp_path, "name: x\n")
    assert read_pins(tmp_path) == []


def test_add_pin_writes_entry(tmp_path: Path) -> None:
    _write_science_yaml(tmp_path, "name: x\n# top comment\n")
    pin = Pin(
        name="validate.sh",
        pinned_to="2026.04.25",
        pinned_hash="a" * 64,
        rationale="r",
        revisit_by="2026-06-01",
    )
    add_pin(tmp_path, pin)
    contents = (tmp_path / "science.yaml").read_text(encoding="utf-8")
    assert "managed_artifacts" in contents
    assert "validate.sh" in contents
    assert "name: x" in contents  # preserved
    assert "top comment" in contents  # preserved


def test_add_pin_duplicate_refuses(tmp_path: Path) -> None:
    _write_science_yaml(tmp_path, "name: x\n")
    pin = Pin(
        name="validate.sh",
        pinned_to="2026.04.25",
        pinned_hash="a" * 64,
        rationale="r",
        revisit_by="2026-06-01",
    )
    add_pin(tmp_path, pin)
    with pytest.raises(PinAlreadyExists, match="validate.sh"):
        add_pin(tmp_path, pin)


def test_remove_pin(tmp_path: Path) -> None:
    _write_science_yaml(tmp_path, "name: x\n")
    pin = Pin(
        name="validate.sh",
        pinned_to="2026.04.25",
        pinned_hash="a" * 64,
        rationale="r",
        revisit_by="2026-06-01",
    )
    add_pin(tmp_path, pin)
    remove_pin(tmp_path, "validate.sh")
    assert read_pins(tmp_path) == []


def test_remove_pin_not_found(tmp_path: Path) -> None:
    _write_science_yaml(tmp_path, "name: x\n")
    with pytest.raises(PinNotFound):
        remove_pin(tmp_path, "validate.sh")
