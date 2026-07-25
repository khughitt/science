"""Per-kind vocabulary declared by the shipped entity profiles.

The Kind Descriptor (`science_model.profiles.EntityKind`) is the sole SSOT for
what a kind is called, where it lives, and which statuses it may carry. This
module holds the lookup tables derived from the shipped profiles and nothing
else, so it imports `science_model` only.

That import floor is the point. `science_tool.entities` reaches the graph and
commons packages, so anything imported *from inside* those packages cannot read
the declared vocabulary through it — `commons.validator` doing so closed a cycle
(`entities` -> `graph` -> `commons` -> `entities`) that resolved only when some
unrelated module happened to be imported first. Layers below `entities` read the
vocabulary here instead of re-deriving it; three copies of a vocabulary is how
they drift.
"""

from __future__ import annotations

from science_model.profiles import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE

KIND_DESCRIPTORS = (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)

#: Kind -> the status vocabulary it declares. A kind declaring none is ABSENT
#: from this mapping rather than mapped to an empty set: the two mean different
#: things to `entities.valid_statuses`, which falls through to the project-local
#: manifest for an absent kind and would wrongly report a closed empty
#: vocabulary for a present-but-empty one.
DECLARED_STATUSES: dict[str, frozenset[str]] = {
    ek.name: frozenset(ek.statuses) for ek in KIND_DESCRIPTORS if ek.statuses
}
