"""YAML loader for the managed-artifact registry."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from science_tool.project_artifacts.registry_schema import Registry


class RegistryLoadError(Exception):
    """Raised when the registry cannot be loaded or fails schema validation."""


def load_registry(path: Path) -> Registry:
    """Parse and schema-validate the registry at *path*.

    Surfaces YAML errors as ``RegistryLoadError("YAML parse error: ...")``
    and pydantic violations with the YAML path of the offending field.
    """
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(path.read_text(encoding="utf-8"))
    except YAMLError as exc:
        raise RegistryLoadError(f"YAML parse error in {path}: {exc}") from exc

    if data is None:
        data = {"artifacts": []}

    try:
        return Registry.model_validate(data)
    except ValidationError as exc:
        # Render each error as 'registry.yaml: <yaml-path>: <message>'.
        lines = [f"{path.name}: schema validation failed:"]
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            lines.append(f"  artifacts.{loc}: {err['msg']}")
        raise RegistryLoadError("\n".join(lines)) from exc


def load_packaged_registry() -> Registry:
    """Load the registry.yaml shipped inside the package."""
    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / "registry.yaml") as p:
        return load_registry(p)
