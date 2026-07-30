"""Parse and render schema_profile strings.

Format: <base>/<ver>(+<mixin>/<ver>)?(+<ext>/<ver>)*

Examples:
  "science-entity-base/1.0"
  "science-entity-base/1.0+dataset/1.0"
  "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.scrna/1.0"
"""

from __future__ import annotations

from dataclasses import dataclass

from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE

BASE_NAME = "science-entity-base"

# Commons type mixins (base 1.0). Shared across repos; versioned; 369 live records.
COMMONS_MIXIN_NAMES = frozenset({"dataset", "paper", "topic", "theme"})

# Project-authored kinds converging onto the same schema system (base 2.0). DERIVED from the
# per-kind `schema_closed` declaration, over the BUILT-IN profiles only -- a project cannot arm
# strictness for itself. This set still gates BOTH schema strictness (`unevaluatedProperties:
# false`) and load enforcement, deliberately: `sources.py` explains that splitting them is how a
# green check over an unchecked record becomes possible.
PROJECT_MIXIN_NAMES: frozenset[str] = frozenset(
    kind.name
    for kind in (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)
    if kind.schema_closed
)

TYPE_MIXIN_NAMES = COMMONS_MIXIN_NAMES | PROJECT_MIXIN_NAMES


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
    components = [parse_component(token) for token in raw.split("+")]
    base = components[0]
    if base.name != BASE_NAME:
        raise ProfileParseError(
            f"schema_profile must start with {BASE_NAME!r}, got {base.name!r}"
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


def parse_component(token: str) -> ProfileComponent:
    """Parse one rendered `name/version` profile component."""
    if "/" not in token:
        raise ProfileParseError(f"profile component {token!r} missing version (expected 'name/version')")
    name, version = token.split("/", 1)
    if not name or not version:
        raise ProfileParseError(f"profile component {token!r} has empty name or version")
    return ProfileComponent(name=name, version=version)


# The GENERATION MATRIX: one generation number selects a whole row of mixin versions. Generation is
# the project's declared `entity_schema_version` -- gen 2 is the D5 baseline, gen 3 moves `dataset`
# and `hypothesis` onto their data-product shapes and leaves every other kind exactly where gen 2
# left it. A generation is a coherent SLICE across kinds, not a per-kind default: a project pins one
# number and every kind resolves against the same row, so two kinds can never disagree about which
# generation the project is on.
_MIXIN_VERSION_BY_GENERATION: dict[int, dict[str, str]] = {
    2: {
        "dataset": "2.0", "paper": "2.0", "topic": "2.0", "theme": "2.0",
        "hypothesis": "1.0", "concept": "1.1", "method": "1.0",
        "search": "1.0", "observation": "1.0",
    },
    3: {
        "dataset": "3.0", "paper": "2.0", "topic": "2.0", "theme": "2.0",
        "hypothesis": "2.0", "concept": "1.1", "method": "1.0",
        "search": "1.0", "observation": "1.0",
    },
}

# The base version is PER-KIND, not global. Commons kinds pin base 1.0 -- 369 live records depend
# on it and there is no reason to move them. Project kinds need base 2.0, whose kind/id constraints
# admit them (base 1.0's structurally cannot: it enum-locks `kind` to the four commons kinds, and
# an allOf can only narrow). Two base versions coexisting is what versioning is FOR.
_BASE_VERSION_FOR_MIXIN: dict[str, str] = {
    **{name: "1.0" for name in COMMONS_MIXIN_NAMES},
    **{name: "2.0" for name in PROJECT_MIXIN_NAMES},
}


def default_profile_for_kind(kind: str, *, generation: int = 2) -> ProfileString:
    """Return the default parsed ProfileString for a kind at a given schema `generation`.

    Project entities do NOT carry `schema_profile` in frontmatter -- it is derived here. (Commons
    records DO carry it: they travel between repos, so the profile must travel with the record. A
    project entity is versioned by the git history of the repo that contains it.)

    `generation` is the project's declared `entity_schema_version` (default 2, the D5 baseline).

    Raises ProfileParseError for an unknown generation or an unknown kind.
    """
    versions = _MIXIN_VERSION_BY_GENERATION.get(generation)
    if versions is None:
        raise ProfileParseError(
            f"unknown entity-schema generation {generation!r}; "
            f"expected one of {sorted(_MIXIN_VERSION_BY_GENERATION)}"
        )
    if kind not in versions:
        raise ProfileParseError(f"unknown kind {kind!r}; expected one of {sorted(versions)}")
    return parse_profile(
        f"{BASE_NAME}/{_BASE_VERSION_FOR_MIXIN[kind]}+{kind}/{versions[kind]}"
    )
