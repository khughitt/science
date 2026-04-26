"""YAML loader for the managed-artifact registry."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

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
    # Round-trip mode preserves node styles so we can enforce that bash
    # `check`/`apply` scripts are written as block scalars (| or >) rather
    # than plain flow values that would silently be re-flowed.
    yaml = YAML(typ="rt")
    try:
        data = yaml.load(path.read_text(encoding="utf-8"))
    except YAMLError as exc:
        raise RegistryLoadError(f"YAML parse error in {path}: {exc}") from exc

    if data is None:
        data = {"artifacts": []}

    _enforce_block_scalars(data, path)

    try:
        # Convert ruamel's CommentedMap/CommentedSeq into plain dict/list for pydantic.
        plain = _to_plain(data)
        return Registry.model_validate(plain)
    except ValidationError as exc:
        # Render each error as 'registry.yaml: <yaml-path>: <message>'.
        lines = [f"{path.name}: schema validation failed:"]
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            lines.append(f"  artifacts.{loc}: {err['msg']}")
        raise RegistryLoadError("\n".join(lines)) from exc


def _to_plain(node: Any) -> Any:
    """Recursively convert ruamel CommentedMap/CommentedSeq to plain dict/list."""
    if hasattr(node, "items"):
        return {k: _to_plain(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_to_plain(v) for v in node]
    return node


def _enforce_block_scalars(data: Any, path: Path) -> None:
    """For every bash migration step's check/apply, require block-scalar style."""
    if not hasattr(data, "get"):
        return
    for art_idx, art in enumerate(data.get("artifacts", []) or []):
        for mig_idx, mig in enumerate(art.get("migrations", []) or []):
            for step_idx, step in enumerate(mig.get("steps", []) or []):
                impl = step.get("impl") or {}
                if impl.get("kind") != "bash":
                    continue
                for field in ("check", "apply"):
                    val = impl.get(field)
                    if val is None:
                        continue
                    style = getattr(val, "style", None)
                    if style not in ("|", ">"):
                        raise RegistryLoadError(
                            f"{path.name}: artifacts[{art_idx}].migrations[{mig_idx}]."
                            f"steps[{step_idx}].impl.{field} must be a YAML block scalar "
                            f"(| or >), not plain flow"
                        )


def load_packaged_registry() -> Registry:
    """Load the registry.yaml shipped inside the package."""
    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / "registry.yaml") as p:
        return load_registry(p)
