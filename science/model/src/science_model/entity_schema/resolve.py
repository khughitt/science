"""Resolve a kind + its project-declared extensions into one profile.

This is the third layer of the schema system, and it lives in its own module because it is the
first that needs BOTH of the other two: `profile` parses and renders, `loader` fetches, and
`resolve` composes a profile from a kind and a project's declared extensions -- checking, as it
goes, that every extension is purely ADDITIVE.

Putting it in `profile` would invert the existing dependency (`loader` imports `profile`) and make
the package cyclic.
"""

from __future__ import annotations

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import (
    ProfileString,
    default_profile_for_kind,
    parse_component,
)


class ExtensionRedefinesCoreField(ValueError):
    """Raised when an extension declares a field the base or the type mixin already owns.

    Composition is a pure `allOf`, and **an allOf can only NARROW.** An extension that redeclared
    `status` would therefore not REPLACE the core enum -- it would INTERSECT with it, yielding a
    schema that nothing can satisfy. The failure would then surface, far away and much later, as
    "this obviously valid file is invalid", with nothing pointing back at the extension.

    So it is caught here, at resolve time, by name. An extension may ADD fields to a kind. It may
    never redefine one the core already owns.
    """


def resolve_profile(
    kind: str,
    *,
    extensions: list[str],
    loader: SchemaLoader | None = None,
) -> ProfileString:
    """Return the profile for `kind` with the project's declared `extensions` appended.

    `extensions` are rendered profile components (`"mm30.assessment/1.0"`), as declared under
    `entity_extensions:` in the project's `science.yaml`. With none declared, the result is exactly
    `default_profile_for_kind(kind)` -- which is the case for 20 of the 22 projects.
    """
    default = default_profile_for_kind(kind)
    if not extensions:
        return default

    loader = loader or SchemaLoader()
    components = tuple(parse_component(raw) for raw in extensions)

    core_fields: set[str] = set()
    for component in (default.base, default.mixin):
        if component is not None:
            core_fields |= set(loader.load(component).get("properties", {}))

    for component in components:
        declared = set(loader.load(component).get("properties", {}))
        collisions = sorted(declared & core_fields)
        if collisions:
            raise ExtensionRedefinesCoreField(
                f"extension {component.render()!r} redefines core field(s) "
                f"{', '.join(collisions)} — an extension may only ADD fields to a kind. "
                "Inside an allOf a redefinition intersects with the core constraint rather than "
                "replacing it, so the schema would become unsatisfiable rather than error."
            )

    return ProfileString(
        base=default.base,
        mixin=default.mixin,
        extensions=default.extensions + components,
    )
