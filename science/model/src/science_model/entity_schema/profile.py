"""Parse and render schema_profile strings.

Format: <base>/<ver>(+<mixin>/<ver>)?(+<ext>/<ver>)*

Examples:
  "science-entity-base/1.0"
  "science-entity-base/1.0+dataset/1.0"
  "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.scrna/1.0"
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_NAME = "science-entity-base"
TYPE_MIXIN_NAMES = frozenset({"dataset", "paper", "topic", "theme"})


class ProfileParseError(ValueError):
    """Raised when a schema_profile string is malformed."""


@dataclass(frozen=True, slots=True)
class ProfileComponent:
    name: str
    version: str

    def render(self) -> str:
        return f"{self.name}/{self.version}"


@dataclass(frozen=True, slots=True)
class ProfileString:
    base: ProfileComponent
    mixin: ProfileComponent | None
    extensions: tuple[ProfileComponent, ...]

    def render(self) -> str:
        parts = [self.base.render()]
        if self.mixin is not None:
            parts.append(self.mixin.render())
        parts.extend(ext.render() for ext in self.extensions)
        return "+".join(parts)


def parse_profile(raw: str) -> ProfileString:
    if not raw:
        raise ProfileParseError("schema_profile is empty")
    components = [_parse_component(token) for token in raw.split("+")]
    base = components[0]
    if base.name != BASE_NAME:
        raise ProfileParseError(
            f"schema_profile must start with science-entity-base, got {base.name!r}"
        )
    if len(components) == 1:
        return ProfileString(base=base, mixin=None, extensions=())
    mixin = components[1]
    if mixin.name not in TYPE_MIXIN_NAMES:
        raise ProfileParseError(
            f"schema_profile mixin must be one of {sorted(TYPE_MIXIN_NAMES)!r}, "
            f"got {mixin.name!r}"
        )
    return ProfileString(base=base, mixin=mixin, extensions=tuple(components[2:]))


def _parse_component(token: str) -> ProfileComponent:
    if "/" not in token:
        raise ProfileParseError(f"profile component {token!r} missing version (expected 'name/version')")
    name, version = token.split("/", 1)
    if not name or not version:
        raise ProfileParseError(f"profile component {token!r} has empty name or version")
    return ProfileComponent(name=name, version=version)
