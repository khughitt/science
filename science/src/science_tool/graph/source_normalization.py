"""The declared normalization between a structured source row and an entity mapping.

Named and declared rather than inline, because a drop that is not declared is indistinguishable
from a bug. This ran as anonymous dict-building inside the structured loader; the schema check
that now follows it is only meaningful if what it lost is written down.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Authored key -> entity-schema key. The row authors `canonical_id`/`source_path`; the entity
# schema expects normalized `id`/`file_path`.
STRUCTURED_KEY_MAPPING: dict[str, str] = {
    "canonical_id": "id",
    "source_path": "file_path",
}

# Keys deliberately dropped. `kind` is authoritative from the manifest declaration and ignored on
# the row. Nothing else may join this set without a written ruling in the design.
STRUCTURED_DROP_KEYS: frozenset[str] = frozenset({"kind"})


def normalize_structured_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Map a raw structured-source row onto entity-schema keys, preserving authored keys only.

    Ranges over what the author actually wrote -- never over a parsed record's defaults. The
    declared fields of `StructuredEntitySource` all default (`title=""`, five empty lists), so
    normalizing from the parsed object would promote those defaults into the mapping that gets
    schema-validated: an absent `title` would arrive as `""` and fail `minLength: 1`, and an
    absent `evidence_refs` would arrive as `[]` and read as an authored empty list. The loader's
    own backfills stay explicit and separately testable downstream of this.
    """
    normalized: dict[str, Any] = {}
    authored_keys_by_destination: dict[str, str] = {}
    for key, value in row.items():
        if key in STRUCTURED_DROP_KEYS:
            continue
        destination = STRUCTURED_KEY_MAPPING.get(key, key)
        if destination in authored_keys_by_destination:
            colliding_keys = sorted((authored_keys_by_destination[destination], key))
            raise ValueError(
                f"structured row authored keys {colliding_keys[0]!r} and "
                f"{colliding_keys[1]!r} both normalize to {destination!r}"
            )
        authored_keys_by_destination[destination] = key
        normalized[destination] = value
    return normalized
