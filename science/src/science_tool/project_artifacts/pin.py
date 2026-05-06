"""Pin reader/writer: round-trips science.yaml's managed_artifacts.pins."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from science_tool.project_artifacts.registry_schema import Pin


class PinAlreadyExists(Exception):
    """Raised when adding a pin for a name that is already pinned."""


class PinNotFound(Exception):
    """Raised when removing a pin for a name that is not pinned."""


def _load(project_root: Path) -> tuple[YAML, Any]:
    """Return (yaml-instance, parsed-data) for science.yaml."""
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    text = (project_root / "science.yaml").read_text(encoding="utf-8")
    return yaml, yaml.load(text) or {}


def _save(project_root: Path, yaml: YAML, data: Any) -> None:
    with (project_root / "science.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(data, f)


def read_pins(project_root: Path) -> list[Pin]:
    """Read managed_artifacts.pins as a list of Pin objects."""
    _, data = _load(project_root)
    raw = (data.get("managed_artifacts") or {}).get("pins") or []
    return [Pin.model_validate(dict(p)) for p in raw]


def add_pin(project_root: Path, pin: Pin) -> None:
    """Append a pin entry; raises PinAlreadyExists if name is already pinned."""
    yaml, data = _load(project_root)
    ma = data.setdefault("managed_artifacts", {})
    pins = ma.setdefault("pins", [])
    for existing in pins:
        if existing.get("name") == pin.name:
            raise PinAlreadyExists(f"pin already exists for {pin.name!r}")
    pins.append(pin.model_dump())
    _save(project_root, yaml, data)


def remove_pin(project_root: Path, name: str) -> None:
    """Remove the pin entry for NAME; raises PinNotFound if absent."""
    yaml, data = _load(project_root)
    pins = (data.get("managed_artifacts") or {}).get("pins") or []
    new_pins = [p for p in pins if p.get("name") != name]
    if len(new_pins) == len(pins):
        raise PinNotFound(f"no pin found for {name!r}")
    data["managed_artifacts"]["pins"] = new_pins
    _save(project_root, yaml, data)
