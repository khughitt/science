"""D1 parser for bio.geneset collection member rows.

Rows are collection members, not promoted entities. The set identity is the
opaque `set_key`; member identifiers are interpreted in the collection-level
`identifier_space`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, get_args

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.packages.schema import DatasetUsage

GENESET_MEMBER_KEY_COLUMN = "set_key"
GENESET_REQUIRED_COLUMNS = frozenset({"set_key", "name", "member_ids"})
_DATASET_SCHEMA = SchemaLoader().load(ProfileComponent(name="dataset", version="1.0"))
GENESET_SOURCE_CLASSES = frozenset(_DATASET_SCHEMA["properties"]["source_class"]["enum"])
GENESET_DERIVED_KINDS = frozenset(_DATASET_SCHEMA["properties"]["derived_kind"]["enum"])
GENESET_USAGE_ROLES = frozenset(get_args(DatasetUsage.model_fields["role"].annotation))
GENESET_USAGE_OVERLAPS = frozenset(get_args(DatasetUsage.model_fields["overlap"].annotation))


class GenesetCollectionError(ValueError):
    """A bio.geneset collection row violates the D1 row contract."""


@dataclass(frozen=True, slots=True)
class GenesetRow:
    set_key: str
    name: str
    member_ids: tuple[str, ...]
    source_class: str | None
    derived_kind: str | None
    dataset_usage: tuple[dict[str, Any], ...]
    source_pmids: tuple[str, ...]

    @property
    def n_members(self) -> int:
        return len(self.member_ids)


def _split_semicolon(raw: str, *, field: str, row_number: int) -> tuple[str, ...]:
    text = raw.strip()
    if not text:
        return ()
    parts = tuple(part.strip() for part in raw.split(";"))
    if any(not part for part in parts):
        raise GenesetCollectionError(f"row {row_number}: {field} contains an empty token")
    return parts


def _dataset_usage_defect(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    ref = entry.get("ref")
    if not isinstance(ref, str) or not ref.startswith("dataset:"):
        return "ref must be a 'dataset:' reference"
    role = entry.get("role")
    if role not in GENESET_USAGE_ROLES:
        return f"role must be one of {sorted(GENESET_USAGE_ROLES)}"
    if "overlap" in entry and entry["overlap"] not in GENESET_USAGE_OVERLAPS:
        return f"overlap must be one of {sorted(GENESET_USAGE_OVERLAPS)}"
    return None


def _parse_dataset_usage(raw: str, *, row_number: int) -> tuple[dict[str, Any], ...]:
    text = raw.strip()
    if not text:
        return ()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GenesetCollectionError(f"row {row_number}: dataset_usage is not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, list):
        raise GenesetCollectionError(f"row {row_number}: dataset_usage must be a JSON list")
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(parsed):
        defect = _dataset_usage_defect(entry)
        if defect is not None:
            raise GenesetCollectionError(f"row {row_number}: dataset_usage[{index}] malformed -- {defect}")
        out.append(entry)
    return tuple(out)


def _source_class_defect(source_class: str | None, derived_kind: str | None) -> str | None:
    if source_class is not None and source_class not in GENESET_SOURCE_CLASSES:
        return f"source_class must be one of {sorted(GENESET_SOURCE_CLASSES)}"
    if source_class == "derived":
        if derived_kind not in GENESET_DERIVED_KINDS:
            return f"source_class=derived requires derived_kind one of {sorted(GENESET_DERIVED_KINDS)}"
    elif derived_kind is not None:
        return "derived_kind is only allowed when source_class=derived"
    return None


def parse_geneset_rows(rows: list[dict[str, Any]]) -> list[GenesetRow]:
    out: list[GenesetRow] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        missing = [col for col in sorted(GENESET_REQUIRED_COLUMNS) if col not in row]
        if missing:
            raise GenesetCollectionError(f"row {row_number}: missing required columns {missing}")
        set_key = str(row.get("set_key") or "").strip()
        if not set_key:
            raise GenesetCollectionError(f"row {row_number}: blank set_key")
        if set_key in seen:
            raise GenesetCollectionError(f"row {row_number}: duplicate set_key {set_key!r}")
        seen.add(set_key)
        name = str(row.get("name") or "").strip()
        if not name:
            raise GenesetCollectionError(f"row {row_number}: blank name")
        member_ids = _split_semicolon(str(row.get("member_ids") or ""), field="member_ids", row_number=row_number)
        if not member_ids:
            raise GenesetCollectionError(f"row {row_number}: member_ids must contain at least one identifier")
        source_class = str(row["source_class"]).strip() if row.get("source_class") not in (None, "") else None
        derived_kind = str(row["derived_kind"]).strip() if row.get("derived_kind") not in (None, "") else None
        defect = _source_class_defect(source_class, derived_kind)
        if defect is not None:
            raise GenesetCollectionError(f"row {row_number}: {defect}")
        out.append(
            GenesetRow(
                set_key=set_key,
                name=name,
                member_ids=member_ids,
                source_class=source_class,
                derived_kind=derived_kind,
                dataset_usage=_parse_dataset_usage(str(row.get("dataset_usage") or ""), row_number=row_number),
                source_pmids=_split_semicolon(
                    str(row.get("source_pmids") or ""), field="source_pmids", row_number=row_number
                ),
            )
        )
    return out
