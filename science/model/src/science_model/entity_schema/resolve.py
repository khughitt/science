"""Resolve a kind + its project-declared extensions into one profile.

This is the third layer of the schema system, and it lives in its own module because it is the
first that needs BOTH of the other two: `profile` parses and renders, `loader` fetches, and
`resolve` composes a profile from a kind and a project's declared extensions -- checking, as it
goes, that every extension is purely ADDITIVE.

Putting it in `profile` would invert the existing dependency (`loader` imports `profile`) and make
the package cyclic.
"""

from __future__ import annotations

from typing import Any

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import (
    ProfileComponent,
    ProfileString,
    default_profile_for_kind,
    parse_component,
)


class ExtensionContractError(ValueError):
    """Raised when a project extension breaks the additive-only contract."""


class ExtensionRedefinesCoreField(ExtensionContractError):
    """Raised when an extension declares a field the base or the type mixin already owns.

    Composition is a pure `allOf`, and **an allOf can only NARROW.** An extension that redeclared
    `status` would therefore not REPLACE the core enum -- it would INTERSECT with it, yielding a
    schema that nothing can satisfy. The failure would then surface, far away and much later, as
    "this obviously valid file is invalid", with nothing pointing back at the extension.

    So it is caught here, at resolve time, by name. An extension may ADD fields to a kind. It may
    never redefine one the core already owns.
    """


# The project-extension ROOT CONTRACT: an ALLOW-list, not a deny-list.
#
# "Additive only" is not enforced by checking `properties` alone. A root-level applicator narrows
# the COMPOSED record from inside its own allOf branch, without ever naming a core property:
#
#   `required: ["verdict"]`   -- makes a core field mandatory for this project only
#   `not: {...}` / `if/then`  -- forbids composed records the core admits
#   `additionalProperties`    -- cannot see SIBLING branches' properties, so it rejects every field
#                                the base and the mixin declare (this is exactly why the validator
#                                composes with `unevaluatedProperties` instead)
#   `$ref`                    -- pulls in arbitrary constraints from anywhere
#
# These are not hypothetical: `extension-bio-geneset-member-1.0.json` already uses root `not` AND
# root `additionalProperties`. They are legal for a COMMONS extension, which is authored in this
# repo and reviewed with the mixin it extends. They are not legal for a PROJECT extension, which is
# authored in a project repo that the toolkit never sees.
#
# So the contract is stated positively: a project extension may declare properties, say which of
# ITS OWN properties are required, and nothing else. Enumerating what is forbidden would leave a
# hole for every keyword JSON Schema adds after today.
_ALLOWED_ROOT_KEYS = frozenset(
    {"$schema", "$id", "$comment", "$defs", "title", "description", "type", "properties", "required"}
)


def _certify_root_contract(component: ProfileComponent, schema: dict[str, Any]) -> set[str]:
    """Check one project extension against the root contract; return the fields it OWNS."""
    where = component.render()

    forbidden = sorted(set(schema) - _ALLOWED_ROOT_KEYS)
    if forbidden:
        raise ExtensionContractError(
            f"project extension {where!r} uses root-level key(s) {', '.join(forbidden)}. A project "
            "extension may declare `properties` and mark its OWN properties `required` — nothing "
            "else. A root applicator constrains the whole composed record from inside its allOf "
            "branch without naming a core field, which is exactly the narrowing this contract "
            "forbids."
        )

    declared_type = schema.get("type")
    if declared_type != "object":
        raise ExtensionContractError(
            f"project extension {where!r} must declare `\"type\": \"object\"`, got {declared_type!r}."
        )

    owned = set(schema.get("properties", {}) or {})
    required = set(schema.get("required", []) or [])
    foreign = sorted(required - owned)
    if foreign:
        raise ExtensionContractError(
            f"project extension {where!r} marks {', '.join(foreign)} as required without declaring "
            "them. `required` may only name properties the extension itself owns — requiring a core "
            "field would make it mandatory for this one project while the core leaves it optional."
        )
    return owned


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

    owner_of: dict[str, str] = {}
    for component in components:
        declared = _certify_root_contract(component, loader.load(component))

        collisions = sorted(declared & core_fields)
        if collisions:
            raise ExtensionRedefinesCoreField(
                f"extension {component.render()!r} redefines core field(s) "
                f"{', '.join(collisions)} — an extension may only ADD fields to a kind. "
                "Inside an allOf a redefinition intersects with the core constraint rather than "
                "replacing it, so the schema would become unsatisfiable rather than error."
            )

        # Two extensions owning one field is the same defect one level out: the field's constraints
        # INTERSECT, and neither owner can see the other's. Ownership must be unambiguous, so the
        # SECOND claimant is the error -- there is no rule for merging two owners.
        for field in sorted(declared):
            if field in owner_of:
                raise ExtensionContractError(
                    f"extensions {owner_of[field]!r} and {component.render()!r} both declare "
                    f"{field!r}. A field has exactly ONE owner; two extensions declaring it would "
                    "silently intersect their constraints, and neither project could see the other."
                )
            owner_of[field] = component.render()

    return ProfileString(
        base=default.base,
        mixin=default.mixin,
        extensions=default.extensions + components,
    )
